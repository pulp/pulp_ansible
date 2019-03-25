from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import detail_route
from rest_framework import mixins
from rest_framework_nested.viewsets import NestedViewSetMixin

from pulpcore.plugin.models import RepositoryVersion, Publication
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositoryPublishURLSerializer,
    RepositorySyncURLSerializer,
)
from pulpcore.plugin.tasking import enqueue_with_reservation
from pulpcore.plugin.viewsets import (
    ContentFilter,
    ContentViewSet,
    NamedModelViewSet,
    OperationPostponedResponse,
    RemoteViewSet
)

from . import tasks
from .models import AnsibleRemote, AnsibleRole, AnsibleRoleVersion
from .serializers import (AnsibleRemoteSerializer, AnsibleRoleSerializer,
                          AnsibleRoleVersionSerializer)


class AnsibleRoleFilter(ContentFilter):
    """
    FilterSet for Ansible Roles.
    """

    class Meta:
        model = AnsibleRole
        fields = [
            'name',
            'namespace'
        ]


class AnsibleRoleVersionFilter(ContentFilter):
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

    endpoint_name = 'roles'
    router_lookup = 'role'
    queryset = AnsibleRole.objects.all()
    serializer_class = AnsibleRoleSerializer
    filterset_class = AnsibleRoleFilter


class AnsibleRoleVersionViewSet(NestedViewSetMixin, ContentViewSet):
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
            tasks.synchronize,
            [repository, remote],
            kwargs={
                'remote_pk': remote.pk,
                'repository_pk': repository.pk,
                'mirror': mirror,
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
    serializer_class = RepositoryPublishURLSerializer

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to create a new Ansible "
                              "content publication.",
        responses={202: AsyncOperationResponseSerializer}
    )
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
