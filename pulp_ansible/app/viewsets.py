from gettext import gettext as _

from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import detail_route
from rest_framework.parsers import FormParser, MultiPartParser

from pulpcore.plugin.exceptions import DigestValidationError
from pulpcore.plugin.models import Artifact
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositorySyncURLSerializer,
)
from pulpcore.plugin.tasking import enqueue_with_reservation
from pulpcore.plugin.viewsets import (
    ContentFilter,
    ContentViewSet,
    OperationPostponedResponse,
    RemoteViewSet,
    BaseDistributionViewSet,
)

from .models import (
    AnsibleDistribution,
    AnsibleRemote,
    Collection,
    CollectionRemote,
    Role,
)
from .serializers import (
    AnsibleDistributionSerializer,
    AnsibleRemoteSerializer,
    CollectionSerializer,
    CollectionRemoteSerializer,
    CollectionOneShotSerializer,
    RoleSerializer
)
from .tasks.collections import sync as collection_sync
from .tasks.collections import import_collection
from .tasks.synchronizing import synchronize as role_sync


class RoleFilter(ContentFilter):
    """
    FilterSet for Roles.
    """

    class Meta:
        model = Role
        fields = [
            'name',
            'namespace',
            'version',
        ]


class RoleViewSet(ContentViewSet):
    """
    ViewSet for Role.
    """

    endpoint_name = 'roles'
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    filterset_class = RoleFilter


class CollectionFilter(ContentFilter):
    """
    FilterSet for Ansible Collections.
    """

    class Meta:
        model = Collection
        fields = [
            'name',
            'namespace',
            'version',
        ]


class CollectionViewSet(ContentViewSet):
    """
    ViewSet for Ansible Collection.
    """

    endpoint_name = 'collections'
    queryset = Collection.objects.prefetch_related("_artifacts")
    serializer_class = CollectionSerializer
    filterset_class = CollectionFilter


class AnsibleRemoteViewSet(RemoteViewSet):
    """
    ViewSet for Ansible Remotes.
    """

    endpoint_name = 'ansible'
    queryset = AnsibleRemote.objects.all()
    serializer_class = AnsibleRemoteSerializer

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to sync Ansible content.",
        responses={202: AsyncOperationResponseSerializer}
    )
    @detail_route(methods=('post',), serializer_class=RepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        Dispatches a sync task.
        """
        remote = self.get_object()
        serializer = RepositorySyncURLSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        repository = serializer.validated_data.get('repository')
        mirror = serializer.validated_data.get('mirror', False)
        result = enqueue_with_reservation(
            role_sync,
            [repository, remote],
            kwargs={
                'remote_pk': remote.pk,
                'repository_pk': repository.pk,
                'mirror': mirror,
            }
        )
        return OperationPostponedResponse(result, request)


class CollectionRemoteViewSet(RemoteViewSet):
    """
    ViewSet for Collection Remotes.
    """

    endpoint_name = 'collection'
    queryset = CollectionRemote.objects.all()
    serializer_class = CollectionRemoteSerializer

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to sync Collection content.",
        responses={202: AsyncOperationResponseSerializer}
    )
    @detail_route(methods=('post',), serializer_class=RepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        Dispatches a Collection sync task.
        """
        collection_remote = self.get_object()
        serializer = RepositorySyncURLSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        repository = serializer.validated_data.get('repository')
        result = enqueue_with_reservation(
            collection_sync,
            [repository, collection_remote],
            kwargs={
                'remote_pk': collection_remote.pk,
                'repository_pk': repository.pk,
            }
        )
        return OperationPostponedResponse(result, request)


class CollectionUploadViewSet(viewsets.ViewSet):
    """
    ViewSet for One Shot Collection Upload.

    Args:
        file@: package to upload
    """

    serializer_class = CollectionOneShotSerializer
    parser_classes = (MultiPartParser, FormParser)

    @swagger_auto_schema(
        operation_description="Create an artifact and trigger an asynchronous task to create "
                              "Collection content from it.",
        operation_summary="Upload a collection",
        operation_id="upload_collection",
        request_body=CollectionOneShotSerializer,
        responses={202: AsyncOperationResponseSerializer}
    )
    def create(self, request):
        """
        Dispatch a Collection creation task.
        """
        serializer = CollectionOneShotSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        expected_digests = {}
        if serializer.validated_data['sha256']:
            expected_digests['sha256'] = serializer.validated_data['sha256']
        try:
            artifact = Artifact.init_and_validate(serializer.validated_data['file'],
                                                  expected_digests=expected_digests)
        except DigestValidationError:
            raise serializers.ValidationError(
                _("The provided sha256 value does not match the sha256 of the uploaded file.")
            )

        artifact.save()

        async_result = enqueue_with_reservation(
            import_collection, [str(artifact.pk)],
            kwargs={
                'artifact_pk': artifact.pk,
            }
        )

        return OperationPostponedResponse(async_result, request)


class AnsibleDistributionViewSet(BaseDistributionViewSet):
    """
    ViewSet for Ansible Distributions.
    """

    endpoint_name = 'ansible'
    queryset = AnsibleDistribution.objects.all()
    serializer_class = AnsibleDistributionSerializer
