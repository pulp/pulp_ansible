from gettext import gettext as _

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
from rest_framework.serializers import ValidationError as DRFValidationError

from pulpcore.plugin.actions import ModifyRepositoryActionMixin
from pulpcore.plugin.exceptions import DigestValidationError
from pulpcore.plugin.models import PulpTemporaryFile, RepositoryVersion
from pulpcore.plugin.serializers import AsyncOperationResponseSerializer
from pulpcore.plugin.tasking import dispatch
from pulpcore.plugin.viewsets import (
    DistributionViewSet,
    BaseFilterSet,
    ContentFilter,
    ContentViewSet,
    NamedModelViewSet,
    OperationPostponedResponse,
    RemoteViewSet,
    RepositoryViewSet,
    RepositoryVersionViewSet,
    SingleArtifactContentUploadViewSet,
)
from pulp_ansible.app.galaxy.mixins import UploadGalaxyCollectionMixin
from .models import (
    AnsibleCollectionDeprecated,
    AnsibleDistribution,
    GitRemote,
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
    GitRemoteSerializer,
    RoleRemoteSerializer,
    AnsibleRepositorySerializer,
    AnsibleRepositorySyncURLSerializer,
    CollectionSerializer,
    CollectionVersionSerializer,
    CollectionVersionUploadSerializer,
    CollectionRemoteSerializer,
    CollectionOneShotSerializer,
    CopySerializer,
    RoleSerializer,
    TagSerializer,
)
from .tasks.collections import update_collection_remote, sync as collection_sync
from .tasks.copy import copy_content
from .tasks.roles import synchronize as role_sync
from .tasks.git import synchronize as git_sync


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
    is_highest = filters.BooleanFilter(field_name="is_highest")
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

    class Meta:
        model = CollectionVersion
        fields = ["namespace", "name", "version", "q", "is_highest", "tags"]


class CollectionVersionViewSet(SingleArtifactContentUploadViewSet, UploadGalaxyCollectionMixin):
    """
    ViewSet for Ansible Collection.
    """

    endpoint_name = "collection_versions"
    queryset = CollectionVersion.objects.prefetch_related("_artifacts")
    serializer_class = CollectionVersionSerializer
    filterset_class = CollectionVersionFilter
    filter_backends = (OrderingFilter, DjangoFilterBackend)
    ordering_fields = ("pulp_created", "name", "version", "namespace")

    @extend_schema(
        description="Trigger an asynchronous task to create content,"
        "optionally create new repository version.",
        request=CollectionVersionUploadSerializer,
        responses={202: AsyncOperationResponseSerializer},
    )
    def create(self, request):
        """Create a content unit."""
        serializer = CollectionVersionUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        kwargs = {}
        if serializer.validated_data["namespace"]:
            kwargs["expected_namespace"] = serializer.validated_data["namespace"]

        if serializer.validated_data["name"]:
            kwargs["expected_name"] = serializer.validated_data["name"]

        if serializer.validated_data["version"]:
            kwargs["expected_version"] = serializer.validated_data["version"]

        temp_file_pk = serializer.validated_data["temp_file_pk"]
        repository = serializer.validated_data.get("repository")
        async_result = self._dispatch_import_collection_task(temp_file_pk, repository, **kwargs)

        return OperationPostponedResponse(async_result, request)


class CollectionDeprecatedViewSet(ContentViewSet):
    """
    ViewSet for AnsibleCollectionDeprecated.
    """

    endpoint_name = "collection_deprecations"
    queryset = AnsibleCollectionDeprecated.objects.all()
    serializer_class = CollectionSerializer


class RoleRemoteViewSet(RemoteViewSet):
    """
    ViewSet for Role Remotes.
    """

    endpoint_name = "role"
    queryset = RoleRemote.objects.all()
    serializer_class = RoleRemoteSerializer


class GitRemoteViewSet(RemoteViewSet):
    """
    ViewSet for Ansible Remotes.

    This is a tech preview feature. The functionality may change in the future.
    """

    endpoint_name = "git"
    queryset = GitRemote.objects.all()
    serializer_class = GitRemoteSerializer


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
    @action(detail=True, methods=["post"], serializer_class=AnsibleRepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        Dispatches a sync task.
        """
        repository = self.get_object()
        serializer = AnsibleRepositorySyncURLSerializer(
            data=request.data, context={"request": request, "repository_pk": repository.pk}
        )
        serializer.is_valid(raise_exception=True)

        remote = serializer.validated_data.get("remote", repository.remote)
        remote = remote.cast()

        mirror = serializer.validated_data["mirror"]
        sync_kwargs = {
            "remote_pk": remote.pk,
            "repository_pk": repository.pk,
            "mirror": mirror,
        }

        if isinstance(remote, RoleRemote):
            sync_func = role_sync
        elif isinstance(remote, CollectionRemote):
            sync_func = collection_sync
            sync_kwargs["optimize"] = serializer.validated_data["optimize"]
        elif isinstance(remote, GitRemote):
            sync_func = git_sync

        result = dispatch(
            sync_func,
            exclusive_resources=[repository],
            shared_resources=[remote],
            kwargs=sync_kwargs,
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

    @extend_schema(
        description="Trigger an asynchronous update task",
        responses={202: AsyncOperationResponseSerializer},
    )
    def update(self, request, pk, **kwargs):
        """Update remote."""
        partial = kwargs.pop("partial", False)
        lock = [self.get_object()]
        repos = AnsibleRepository.objects.filter(
            remote_id=pk, last_synced_metadata_time__isnull=False
        ).all()
        lock.extend(repos)
        async_result = dispatch(
            update_collection_remote,
            exclusive_resources=lock,
            args=(pk,),
            kwargs={"data": request.data, "partial": partial},
        )
        return OperationPostponedResponse(async_result, request)


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


class AnsibleDistributionViewSet(DistributionViewSet):
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


class CopyViewSet(viewsets.ViewSet):
    """
    ViewSet for Content Copy.
    """

    serializer_class = CopySerializer

    @extend_schema(
        description="Trigger an asynchronous task to copy ansible content from one repository "
        "into another, creating a new repository version.",
        summary="Copy content",
        operation_id="copy_content",
        request=CopySerializer,
        responses={202: AsyncOperationResponseSerializer},
    )
    def create(self, request):
        """Copy content."""
        serializer = CopySerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        config = serializer.validated_data["config"]

        config, exclusive_resources, shared_resources = self._process_config(config)

        async_result = dispatch(
            copy_content,
            exclusive_resources=exclusive_resources,
            shared_resources=shared_resources,
            args=[config],
        )
        return OperationPostponedResponse(async_result, request)

    def _process_config(self, config):
        """
        Change the hrefs into pks within config.

        This method also implicitly validates that the hrefs map to objects and it returns a list of
        repos so that the task can lock on them.
        """
        result = []
        exclusive_resources = []
        shared_resources = []

        for entry in config:
            r = dict()
            source_version = NamedModelViewSet().get_resource(
                entry["source_repo_version"], RepositoryVersion
            )
            dest_repo = NamedModelViewSet().get_resource(entry["dest_repo"], AnsibleRepository)
            r["source_repo_version"] = source_version.pk
            r["dest_repo"] = dest_repo.pk
            exclusive_resources.append(dest_repo)
            shared_resources.append(source_version.repository)

            if "dest_base_version" in entry:
                try:
                    r["dest_base_version"] = dest_repo.versions.get(
                        number=entry["dest_base_version"]
                    ).pk
                except RepositoryVersion.DoesNotExist:
                    message = _(
                        "Version {version} does not exist for repository " "'{repo}'."
                    ).format(version=entry["dest_base_version"], repo=dest_repo.name)
                    raise DRFValidationError(detail=message)

            if entry.get("content") is not None:
                r["content"] = []
                for c in entry["content"]:
                    r["content"].append(NamedModelViewSet().extract_pk(c))
            result.append(r)

        return result, exclusive_resources, shared_resources
