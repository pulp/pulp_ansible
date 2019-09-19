from django.contrib.postgres.search import SearchQuery
from django.db.models import fields as db_fields
from django.db.models.expressions import F, Func
from django_filters import filters
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins
from rest_framework.decorators import action

from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositorySyncURLSerializer,
)
from pulpcore.plugin.tasking import enqueue_with_reservation
from pulpcore.plugin.viewsets import (
    BaseDistributionViewSet,
    ContentFilter,
    SingleArtifactContentUploadViewSet,
    NamedModelViewSet,
    OperationPostponedResponse,
    RemoteViewSet,
)
from .models import (
    AnsibleDistribution,
    AnsibleRemote,
    CollectionVersion,
    CollectionRemote,
    Role,
    Tag,
)
from .serializers import (
    AnsibleDistributionSerializer,
    AnsibleRemoteSerializer,
    CollectionVersionSerializer,
    CollectionRemoteSerializer,
    RoleSerializer,
    TagSerializer,
)
from .tasks.collections import sync as collection_sync
from .tasks.synchronizing import synchronize as role_sync


class RoleFilter(ContentFilter):
    """
    FilterSet for Roles.
    """

    class Meta:
        model = Role
        fields = ["name", "namespace", "version"]


class RoleViewSet(SingleArtifactContentUploadViewSet):
    """
    ViewSet for Role.
    """

    endpoint_name = "roles"
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    filterset_class = RoleFilter


class CollectionVersionFilter(ContentFilter):
    """
    FilterSet for Ansible Collections.
    """

    namespace = filters.CharFilter(field_name="namespace")
    name = filters.CharFilter(field_name="name")
    is_highest = filters.BooleanFilter(field_name="is_highest")
    q = filters.CharFilter(field_name="q", method="filter_by_q")

    def filter_by_q(self, queryset, name, value):
        """
        Full text search provided by the 'q' option.

        Args:
            queryset: The query to add the additional full-text search filtering onto
            name: The name of the option specified, i.e. 'q'
            value: The string to search on

        Returns:
            The Django queryset that was passed in, additionally filtered by full-text search.

        """
        search_query = SearchQuery(value)
        qs = queryset.filter(search_vector=search_query)
        ts_rank_fn = Func(
            F("search_vector"),
            search_query,
            32,  # RANK_NORMALIZATION = 32
            function="ts_rank",
            output_field=db_fields.FloatField(),
        )
        return qs.annotate(rank=ts_rank_fn).order_by("-rank")

    class Meta:
        model = CollectionVersion
        fields = ["namespace", "name", "version", "q", "is_highest"]


class CollectionVersionViewSet(SingleArtifactContentUploadViewSet):
    """
    ViewSet for Ansible Collection.
    """

    endpoint_name = "collection_versions"
    queryset = CollectionVersion.objects.prefetch_related("_artifacts")
    serializer_class = CollectionVersionSerializer
    filterset_class = CollectionVersionFilter


class AnsibleRemoteViewSet(RemoteViewSet):
    """
    ViewSet for Ansible Remotes.
    """

    endpoint_name = "ansible"
    queryset = AnsibleRemote.objects.all()
    serializer_class = AnsibleRemoteSerializer

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to sync Ansible content.",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=RepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        Dispatches a sync task.
        """
        remote = self.get_object()
        serializer = RepositorySyncURLSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        repository = serializer.validated_data.get("repository")
        mirror = serializer.validated_data.get("mirror", False)
        result = enqueue_with_reservation(
            role_sync,
            [repository, remote],
            kwargs={"remote_pk": remote.pk, "repository_pk": repository.pk, "mirror": mirror},
        )
        return OperationPostponedResponse(result, request)


class CollectionRemoteViewSet(RemoteViewSet):
    """
    ViewSet for Collection Remotes.
    """

    endpoint_name = "collection"
    queryset = CollectionRemote.objects.all()
    serializer_class = CollectionRemoteSerializer

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to sync Collection content.",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=RepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        Dispatches a Collection sync task.
        """
        collection_remote = self.get_object()
        serializer = RepositorySyncURLSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        repository = serializer.validated_data.get("repository")
        mirror = serializer.validated_data.get("mirror", False)
        kwargs = {
            "remote_pk": collection_remote.pk,
            "repository_pk": repository.pk,
            "mirror": mirror,
        }

        result = enqueue_with_reservation(
            collection_sync, [repository, collection_remote], kwargs=kwargs
        )
        return OperationPostponedResponse(result, request)


class AnsibleDistributionViewSet(BaseDistributionViewSet):
    """
    ViewSet for Ansible Distributions.
    """

    endpoint_name = "ansible"
    queryset = AnsibleDistribution.objects.all()
    serializer_class = AnsibleDistributionSerializer


class TagViewSet(NamedModelViewSet, mixins.ListModelMixin):
    """
    ViewSet for Tag models.
    """

    endpoint_name = "pulp_ansible/tags"
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
