from collections import defaultdict
from gettext import gettext as _
from packaging.version import parse

from django.contrib.postgres.search import SearchQuery
from django.db.models import fields as db_fields
from django.db.models.expressions import F, Func
from django_filters import filters
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.parsers import FormParser, MultiPartParser

from pulpcore.plugin.actions import ModifyRepositoryActionMixin
from pulpcore.plugin.exceptions import DigestValidationError
from pulpcore.plugin.models import PulpTemporaryFile
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositorySyncURLSerializer,
)
from pulpcore.plugin.tasking import enqueue_with_reservation
from pulpcore.plugin.viewsets import (
    BaseDistributionViewSet,
    BaseFilterSet,
    ContentFilter,
    ContentViewSet,
    NamedModelViewSet,
    OperationPostponedResponse,
    RemoteViewSet,
    RepositoryViewSet,
    RepositoryVersionViewSet,
)
from pulp_ansible.app.galaxy.mixins import UploadGalaxyCollectionMixin
from .models import (
    AnsibleDistribution,
    RoleRemote,
    AnsibleRepository,
    Collection,
    CollectionVersion,
    CollectionRemote,
    Role,
    Tag,
)
from .serializers import (
    AnsibleDistributionSerializer,
    RoleRemoteSerializer,
    AnsibleRepositorySerializer,
    CollectionSerializer,
    CollectionVersionSerializer,
    CollectionRemoteSerializer,
    CollectionOneShotSerializer,
    RoleSerializer,
    TagSerializer,
)
from .tasks.collections import sync as collection_sync
from .tasks.roles import synchronize as role_sync


class RoleFilter(ContentFilter):
    """
    FilterSet for Roles.
    """

    class Meta:
        model = Role
        fields = ["name", "namespace", "version"]


class RoleViewSet(ContentViewSet):
    """
    ViewSet for Role.
    """

    endpoint_name = "roles"
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    filterset_class = RoleFilter


class CollectionFilter(BaseFilterSet):
    """
    FilterSet for Ansible Collections.
    """

    namespace = filters.CharFilter(field_name="namespace")
    name = filters.CharFilter(field_name="name")

    class Meta:
        model = Collection
        fields = ["namespace", "name"]


class CollectionViewset(NamedModelViewSet, mixins.RetrieveModelMixin, mixins.ListModelMixin):
    """
    Viewset for Ansible Collections.
    """

    endpoint_name = "ansible/collections"
    queryset = Collection.objects.all()
    serializer_class = CollectionSerializer
    filterset_class = CollectionFilter


class CollectionVersionFilter(ContentFilter):
    """
    FilterSet for Ansible CollectionVersions.
    """

    namespace = filters.CharFilter(field_name="namespace")
    name = filters.CharFilter(field_name="name")
    is_highest = filters.BooleanFilter(field_name="is_highest", method="get_highest")
    deprecated = filters.BooleanFilter(field_name="collection__deprecated")
    q = filters.CharFilter(field_name="q", method="filter_by_q")
    tags = filters.CharFilter(
        field_name="tags",
        method="filter_by_tags",
        help_text=_("Filter by comma separate list of tags that must all be matched"),
    )

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

    def filter_by_tags(self, qs, name, value):
        """
        Filter queryset qs by list of tags.

        Args:
            qs (django.db.models.query.QuerySet): CollectionVersion queryset
            value (string): A comma separated list of tags

        Returns:
            Queryset of CollectionVersion that matches all tags

        """
        for tag in value.split(","):
            qs = qs.filter(tags__name=tag)
        return qs

    def get_highest(self, qs, name, value):
        """
        Filter queryset qs by is_highest filter.

        """
        latest_pks = []
        namespace_name_dict = defaultdict(lambda: defaultdict(list))
        for collection in qs.all():
            version_entry = (parse(collection.version), collection.pk)
            namespace_name_dict[collection.namespace][collection.name].append(version_entry)

        for namespace, name_dict in namespace_name_dict.items():
            for name, version_list in name_dict.items():
                version_list.sort(reverse=True)
                latest_pk = version_list[0][1]
                latest_pks.append(latest_pk)

        return qs.filter(pk__in=latest_pks)

    class Meta:
        model = CollectionVersion
        fields = ["namespace", "name", "version", "q", "is_highest", "tags"]


class CollectionVersionViewSet(ContentViewSet):
    """
    ViewSet for Ansible Collection.
    """

    endpoint_name = "collection_versions"
    queryset = CollectionVersion.objects.prefetch_related("_artifacts")
    serializer_class = CollectionVersionSerializer
    filterset_class = CollectionVersionFilter
    filter_backends = (OrderingFilter, DjangoFilterBackend)
    ordering_fields = ("pulp_created", "name", "version", "namespace")


class RoleRemoteViewSet(RemoteViewSet):
    """
    ViewSet for Role Remotes.
    """

    endpoint_name = "role"
    queryset = RoleRemote.objects.all()
    serializer_class = RoleRemoteSerializer


class AnsibleRepositoryViewSet(RepositoryViewSet, ModifyRepositoryActionMixin):
    """
    ViewSet for Ansible Repositories.
    """

    endpoint_name = "ansible"
    queryset = AnsibleRepository.objects.all()
    serializer_class = AnsibleRepositorySerializer

    @extend_schema(
        description="Trigger an asynchronous task to sync Ansible content.",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=RepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        Dispatches a sync task.
        """
        repository = self.get_object()
        serializer = RepositorySyncURLSerializer(
            data=request.data, context={"request": request, "repository_pk": repository.pk}
        )
        serializer.is_valid(raise_exception=True)

        remote = serializer.validated_data.get("remote")
        remote.cast()

        if isinstance(remote, RoleRemote):
            sync_func = role_sync
        elif isinstance(remote, CollectionRemote):
            sync_func = collection_sync

        mirror = serializer.validated_data.get("mirror", False)
        result = enqueue_with_reservation(
            sync_func,
            [repository, remote],
            kwargs={"remote_pk": remote.pk, "repository_pk": repository.pk, "mirror": mirror},
        )
        return OperationPostponedResponse(result, request)


class AnsibleRepositoryVersionViewSet(RepositoryVersionViewSet):
    """
    AnsibleRepositoryVersion represents a single file repository version.
    """

    parent_viewset = AnsibleRepositoryViewSet


class CollectionRemoteViewSet(RemoteViewSet):
    """
    ViewSet for Collection Remotes.
    """

    endpoint_name = "collection"
    queryset = CollectionRemote.objects.all()
    serializer_class = CollectionRemoteSerializer


class CollectionUploadViewSet(viewsets.ViewSet, UploadGalaxyCollectionMixin):
    """
    ViewSet for One Shot Collection Upload.

    Args:
        file@: package to upload

    """

    serializer_class = CollectionOneShotSerializer
    parser_classes = (MultiPartParser, FormParser)

    @extend_schema(
        description="Create an artifact and trigger an asynchronous task to create "
        "Collection content from it.",
        summary="Upload a collection",
        operation_id="upload_collection",
        request=CollectionOneShotSerializer,
        responses={202: AsyncOperationResponseSerializer},
    )
    def create(self, request):
        """
        Dispatch a Collection creation task.
        """
        serializer = CollectionOneShotSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        expected_digests = {}
        if serializer.validated_data["sha256"]:
            expected_digests["sha256"] = serializer.validated_data["sha256"]
        try:
            temp_file = PulpTemporaryFile.init_and_validate(
                serializer.validated_data["file"],
                expected_digests=expected_digests,
            )
        except DigestValidationError:
            raise serializers.ValidationError(
                _("The provided sha256 value does not match the sha256 of the uploaded file.")
            )

        temp_file.save()
        async_result = self._dispatch_import_collection_task(temp_file.pk)

        return OperationPostponedResponse(async_result, request)


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
