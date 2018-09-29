from django.db import transaction
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import detail_route
from rest_framework import mixins, status
from rest_framework.response import Response

from pulpcore.plugin.models import Artifact, RepositoryVersion, Publication
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositoryPublishURLSerializer,
    RepositorySyncURLSerializer,
)
from pulpcore.plugin.tasking import enqueue_with_reservation
from pulpcore.plugin.viewsets import (
    BaseFilterSet,
    ContentViewSet,
    NamedModelViewSet,
    OperationPostponedResponse,
    RemoteViewSet
)

from . import tasks
from .models import AnsibleRemote, AnsibleRole, AnsibleRoleVersion
from .serializers import (AnsibleRemoteSerializer, AnsibleRoleSerializer,
                          AnsibleRoleVersionSerializer)


class AnsibleRoleFilter(BaseFilterSet):
    """
    FilterSet for Ansible Roles.
    """

    class Meta:
        model = AnsibleRole
        fields = [
            'name',
            'namespace'
        ]


class AnsibleRoleVersionFilter(BaseFilterSet):
    """
    FilterSet for Ansible Role Versions.
    """

    class Meta:
        model = AnsibleRoleVersion
        fields = [
            'version',
        ]


class AnsibleRoleViewSet(ContentViewSet):
    """
    ViewSet for Ansible Roles.
    """

    endpoint_name = 'ansible/roles'
    router_lookup = 'role'
    queryset = AnsibleRole.objects.all()
    serializer_class = AnsibleRoleSerializer
    filterset_class = AnsibleRoleFilter

    @transaction.atomic
    def create(self, request):
        """
        Create a new AnsibleRoleContent from a request.
        """
        # TODO: we should probably remove create() from ContentViewSet
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class AnsibleRoleVersionViewSet(ContentViewSet):
    """
    ViewSet for Ansible Role versions.
    """

    endpoint_name = 'versions'
    nest_prefix = 'ansible/roles'
    router_lookup = 'roleversion'
    parent_viewset = AnsibleRoleViewSet
    parent_lookup_kwargs = {'role_pk': 'role__pk'}
    queryset = AnsibleRoleVersion.objects.all()
    serializer_class = AnsibleRoleVersionSerializer
    filterset_class = AnsibleRoleVersionFilter

    @classmethod
    def endpoint_pieces(cls):
        """
        Return the pieces of the REST endpoint.
        """
        return (cls.endpoint_name,)

    @transaction.atomic
    def create(self, request, role_pk):
        """
        Create a new AnsibleRoleContent from a request.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        role_version = AnsibleRoleVersion(**validated_data)
        role_version.role = AnsibleRole.objects.get(pk=role_pk)
        role_version.save()
        role_version.artifact = self.get_resource(request.data['artifact'], Artifact)

        headers = self.get_success_headers(request.data)
        return Response(
            self.get_serializer(role_version).data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )


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
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        repository = serializer.validated_data.get('repository')
        result = enqueue_with_reservation(
            tasks.synchronize,
            [repository, remote],
            kwargs={
                'remote_pk': remote.pk,
                'repository_pk': repository.pk
            }
        )
        return OperationPostponedResponse(result, request)


class AnsiblePublicationsViewSet(NamedModelViewSet,
                                 mixins.CreateModelMixin):
    """
    ViewSet for Ansible Publications.
    """

    endpoint_name = 'ansible/publications'
    queryset = Publication.objects.all()

    @swagger_auto_schema(operation_description="Trigger an asynchronous task to create "
                                               "a new Ansible content publication.",
                         responses={202: AsyncOperationResponseSerializer})
    def create(self, request):
        """
        Queues a task that publishes a new Ansible Publication.
        """
        serializer = RepositoryPublishURLSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        repository_version = serializer.validated_data.get('repository_version')

        # Safe because version OR repository is enforced by serializer.
        if not repository_version:
            repository = serializer.validated_data.get('repository')
            repository_version = RepositoryVersion.latest(repository)

        result = enqueue_with_reservation(
            tasks.publish, [repository_version.repository],
            kwargs={
                'repository_version_pk': str(repository_version.pk)
            }
        )
        return OperationPostponedResponse(result, request)
