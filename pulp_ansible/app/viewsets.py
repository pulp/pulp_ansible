from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import detail_route

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
    RoleSerializer
)
from .tasks.collections import sync as collection_sync
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
    queryset = Collection.objects.all()
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


class AnsibleDistributionViewSet(BaseDistributionViewSet):
    """
    ViewSet for Ansible Distributions.
    """

    endpoint_name = 'ansible'
    queryset = AnsibleDistribution.objects.all()
    serializer_class = AnsibleDistributionSerializer
