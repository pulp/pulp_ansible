from gettext import gettext as _

from django.contrib.postgres.search import SearchQuery
from django.db.models import fields as db_fields
from django.db.models.expressions import F, Func
from django_filters import filters
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
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
    RemoteFilter,
    ContentViewSet,
    HyperlinkRelatedFilter,
    NamedModelViewSet,
    NAME_FILTER_OPTIONS,
    NoArtifactContentUploadViewSet,
    OperationPostponedResponse,
    ReadOnlyContentViewSet,
    RemoteViewSet,
    RepositoryViewSet,
    RepositoryVersionViewSet,
    SingleArtifactContentUploadViewSet,
)
from pulpcore.plugin.util import extract_pk, raise_for_unknown_content_units
from pulp_ansible.app.galaxy.mixins import UploadGalaxyCollectionMixin
from .models import (
    AnsibleCollectionDeprecated,
    AnsibleDistribution,
    AnsibleNamespaceMetadata,
    CollectionVersionMark,
    GitRemote,
    RoleRemote,
    AnsibleRepository,
    Collection,
    CollectionVersion,
    CollectionVersionSignature,
    CollectionRemote,
    Role,
    Tag,
)
from .serializers import (
    AnsibleDistributionSerializer,
    AnsibleNamespaceMetadataSerializer,
    CollectionVersionMarkSerializer,
    GitRemoteSerializer,
    RoleRemoteSerializer,
    AnsibleRepositorySerializer,
    AnsibleRepositoryMarkSerializer,
    AnsibleRepositorySyncURLSerializer,
    AnsibleRepositoryRebuildSerializer,
    AnsibleRepositorySignatureSerializer,
    CollectionSerializer,
    CollectionVersionSerializer,
    CollectionVersionSignatureSerializer,
    CollectionRemoteSerializer,
    CollectionOneShotSerializer,
    CopySerializer,
    RoleSerializer,
    TagSerializer,
    CollectionVersionCopyMoveSerializer,
)
from .tasks.collections import sync as collection_sync
from .tasks.collections import rebuild_repository_collection_versions_metadata
from .tasks.copy import copy_content, copy_or_move_and_sign
from .tasks.roles import synchronize as role_sync
from .tasks.git import synchronize as git_sync
from .tasks.mark import mark, unmark
from .tasks.signature import sign


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


class CollectionRemoteFilter(RemoteFilter):
    class Meta:
        model = CollectionRemote
        fields = {"url": ["exact", "in", "icontains", "contains"], **RemoteFilter.Meta.fields}


class CollectionVersionViewSet(UploadGalaxyCollectionMixin, SingleArtifactContentUploadViewSet):
    """
    ViewSet for Ansible Collection.
    """

    endpoint_name = "collection_versions"
    queryset = CollectionVersion.objects.prefetch_related("_artifacts")
    serializer_class = CollectionVersionSerializer
    filterset_class = CollectionVersionFilter
    ordering_fields = ("pulp_created", "name", "version", "namespace")


class SignatureFilter(ContentFilter):
    """
    A filter for signatures.
    """

    signed_collection = HyperlinkRelatedFilter(
        field_name="signed_collection",
        help_text=_("Filter signatures for collection version"),
    )
    signing_service = HyperlinkRelatedFilter(
        field_name="signing_service",
        help_text=_("Filter signatures produced by signature service"),
    )

    class Meta:
        model = CollectionVersionSignature
        fields = {
            "signed_collection": ["exact"],
            "pubkey_fingerprint": ["exact", "in"],
            "signing_service": ["exact"],
        }


class CollectionVersionSignatureViewSet(NoArtifactContentUploadViewSet):
    """
    ViewSet for looking at signature objects for CollectionVersion content.
    """

    endpoint_name = "collection_signatures"
    filterset_class = SignatureFilter
    queryset = CollectionVersionSignature.objects.all()
    serializer_class = CollectionVersionSignatureSerializer


class CollectionVersionMarkFilter(ContentFilter):
    """
    A filter for marks.
    """

    marked_collection = HyperlinkRelatedFilter(
        field_name="marked_collection",
        help_text=_("Filter marks for collection version"),
    )
    value = filters.CharFilter(field_name="value", help_text=_("Filter marks by value"))

    class Meta:
        model = CollectionVersionMark
        fields = {
            "marked_collection": ["exact"],
            "value": ["exact", "in"],
        }


class CollectionVersionMarkViewSet(ContentViewSet):
    """
    ViewSet for looking at mark objects for CollectionVersion content.
    """

    endpoint_name = "collection_marks"
    filterset_class = CollectionVersionMarkFilter
    queryset = CollectionVersionMark.objects.all()
    serializer_class = CollectionVersionMarkSerializer


class CollectionDeprecatedViewSet(ContentViewSet):
    """
    ViewSet for AnsibleCollectionDeprecated.
    """

    endpoint_name = "collection_deprecations"
    queryset = AnsibleCollectionDeprecated.objects.all()
    serializer_class = CollectionSerializer


class AnsibleNamespaceFilter(ContentFilter):
    """
    A filter for namespaces.
    """

    class Meta:
        model = AnsibleNamespaceMetadata
        fields = {
            "name": NAME_FILTER_OPTIONS,
            "company": NAME_FILTER_OPTIONS,
            "metadata_sha256": ["exact", "in"],
        }


class AnsibleNamespaceViewSet(ReadOnlyContentViewSet):
    """
    ViewSet for AnsibleNamespace.
    """

    endpoint_name = "namespaces"
    queryset = AnsibleNamespaceMetadata.objects.all()
    serializer_class = AnsibleNamespaceMetadataSerializer
    filterset_class = AnsibleNamespaceFilter


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

    @extend_schema(
        description="Trigger an asynchronous task to rebuild Ansible content meta.",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=AnsibleRepositoryRebuildSerializer)
    def rebuild_metadata(self, request, pk):
        """
        Dispatches a collection version rebuild task.
        """
        repository = self.get_object()
        serializer = AnsibleRepositoryRebuildSerializer(
            data=request.data, context={"request": request, "repository_pk": repository.pk}
        )
        serializer.is_valid(raise_exception=True)

        result = dispatch(
            rebuild_repository_collection_versions_metadata,
            exclusive_resources=[],
            shared_resources=[repository],
            args=[repository.latest_version().pk],
            kwargs=serializer.data,
        )
        return OperationPostponedResponse(result, request)

    @extend_schema(
        description="Trigger an asynchronous task to sign Ansible content.",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=AnsibleRepositorySignatureSerializer)
    def sign(self, request, pk):
        """
        Dispatches a sign task.

        This endpoint is in tech preview and can change at any time in the future.
        """
        content_units = {}

        repository = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        signing_service = serializer.validated_data["signing_service"]
        content = serializer.validated_data["content_units"]

        if "*" in content:
            content_units_pks = ["*"]
        else:
            for url in content:
                content_units[extract_pk(url)] = url
            content_units_pks = list(content_units.keys())
            existing_content_units = CollectionVersion.objects.filter(pk__in=content_units_pks)
            raise_for_unknown_content_units(existing_content_units, content_units)

        result = dispatch(
            sign,
            exclusive_resources=[repository],
            kwargs={
                "repository_href": repository.pk,
                "content_hrefs": content_units_pks,
                "signing_service_href": signing_service.pk,
            },
        )
        return OperationPostponedResponse(result, request)

    def _handle_copy_or_move(self, request, copy_or_move):
        repository = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        dest_repos_pks = [x.pk for x in data["destination_repositories"]]

        signing_service = data.get("signing_service", None)
        if signing_service:
            signing_service = signing_service.pk

        reserved = data["destination_repositories"] + [repository]

        result = dispatch(
            copy_or_move_and_sign,
            exclusive_resources=reserved,
            kwargs={
                "src_repo_pk": repository.pk,
                "cv_pk_list": [x.pk for x in data["collection_versions"]],
                "dest_repo_list": dest_repos_pks,
                "copy_or_move": copy_or_move,
                "signing_service_pk": signing_service,
            },
        )
        return OperationPostponedResponse(result, request)

    @extend_schema(
        description="Trigger an asynchronous task to copy collection versions.",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=CollectionVersionCopyMoveSerializer)
    def copy_collection_version(self, request, pk):
        """
        Copy a collection and all of its associated content from this repository.
        """

        return self._handle_copy_or_move(request, "copy")

    @extend_schema(
        description="Trigger an asynchronous task to move collection versions.",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=CollectionVersionCopyMoveSerializer)
    def move_collection_version(self, request, pk):
        """
        Move a collection and all of its associated content from this repository.
        """

        return self._handle_copy_or_move(request, "move")

    def _handle_mark_task(self, request, task_function):
        """
        Dispatches the `task_function` passed either by `mark` or `unmark` actions.
        """
        content_units = {}

        repository = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        value = serializer.validated_data["value"]
        content = serializer.validated_data["content_units"]

        if "*" in content:
            content_units_pks = ["*"]
        else:
            for url in content:
                content_units[extract_pk(url)] = url
            content_units_pks = list(content_units.keys())
            existing_content_units = CollectionVersion.objects.filter(pk__in=content_units_pks)
            raise_for_unknown_content_units(existing_content_units, content_units)

        result = dispatch(
            task_function,  # will be `mark` or `unmark`
            exclusive_resources=[repository],
            kwargs={
                "repository_href": repository.pk,
                "content_hrefs": content_units_pks,
                "value": value,
            },
        )
        return OperationPostponedResponse(result, request)

    @extend_schema(
        description="Trigger an asynchronous task to mark Ansible content.",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=AnsibleRepositoryMarkSerializer)
    def mark(self, request, pk):
        """
        Dispatches a mark task.
        """
        return self._handle_mark_task(request, mark)

    @extend_schema(
        description="Trigger an asynchronous task to unmark Ansible content.",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=AnsibleRepositoryMarkSerializer)
    def unmark(self, request, pk):
        """
        Dispatches the unmark task.

        Removes a mark from the repository, value and content_units are required
        then only marks having `marked_collection` in the content_units list
        will be removed from the repo.

        The CollectionVersionMark object will not be deleted, because
        it may be present in another repo, so we just remove from this repo
        and let orphan cleanup take care of deletion when it is eventually
        needed.
        """
        return self._handle_mark_task(request, unmark)


class AnsibleRepositoryVersionViewSet(RepositoryVersionViewSet):
    """
    AnsibleRepositoryVersion represents a single file repository version.
    """

    parent_viewset = AnsibleRepositoryViewSet

    @extend_schema(
        description="Trigger an asynchronous task to rebuild Ansible content meta.",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=AnsibleRepositoryRebuildSerializer)
    def rebuild_metadata(self, request, *args, **kwargs):
        """
        Dispatches a collection version rebuild task.
        """
        repository_version = self.get_object()
        serializer = AnsibleRepositoryRebuildSerializer(
            data=request.data,
            context={"request": request, "repository_version_pk": repository_version.pk},
        )
        serializer.is_valid(raise_exception=True)

        result = dispatch(
            rebuild_repository_collection_versions_metadata,
            exclusive_resources=[],
            shared_resources=[repository_version.repository],
            args=[repository_version.pk],
            kwargs=serializer.data,
        )
        return OperationPostponedResponse(result, request)


class CollectionRemoteViewSet(RemoteViewSet):
    """
    ViewSet for Collection Remotes.
    """

    endpoint_name = "collection"
    queryset = CollectionRemote.objects.all()
    serializer_class = CollectionRemoteSerializer
    filterset_class = CollectionRemoteFilter

    def async_reserved_resources(self, instance):
        if instance is None:
            return []
        lock = [instance]
        repos = AnsibleRepository.objects.filter(
            remote_id=instance.pk, last_synced_metadata_time__isnull=False
        )
        lock.extend(repos)
        return lock


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
        deprecated=True,
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
                    r["content"].append(extract_pk(c))
            result.append(r)

        return result, exclusive_resources, shared_resources
