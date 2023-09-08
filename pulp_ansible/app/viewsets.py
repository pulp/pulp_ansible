from gettext import gettext as _

from django.contrib.postgres.search import SearchQuery
from django.db.models import fields as db_fields
from django.db.models.expressions import F, Func
from django_filters import filters
from django.http import HttpResponseRedirect, HttpResponseNotFound
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
    RolesMixin,
    SingleArtifactContentUploadViewSet,
)
from pulpcore.plugin.util import extract_pk, raise_for_unknown_content_units, get_artifact_url
from pulp_ansible.app.galaxy.mixins import UploadGalaxyCollectionMixin
from pulp_ansible.app.utils import get_queryset_annotated_with_last_sync_task
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

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": ["create"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_required_repo_perms_on_upload:ansible.modify_ansible_repo_content",
                    "has_required_repo_perms_on_upload:ansible.view_ansiblerepository",
                    "has_upload_param_model_or_obj_perms:core.change_upload",
                ],
            },
        ],
    }


class CollectionFilter(BaseFilterSet):
    """
    FilterSet for Ansible Collections.
    """

    namespace = filters.CharFilter(field_name="namespace")
    name = filters.CharFilter(field_name="name")

    class Meta:
        model = Collection
        fields = ["namespace", "name"]


class CollectionViewset(
    NamedModelViewSet, mixins.RetrieveModelMixin, mixins.ListModelMixin, RolesMixin
):
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

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": "create",
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_required_repo_perms_on_upload:ansible.modify_ansible_repo_content",
                    "has_required_repo_perms_on_upload:ansible.view_ansiblerepository",
                    "has_upload_param_model_or_obj_perms:core.change_upload",
                ],
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }


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

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": "create",
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_required_repo_perms_on_upload:ansible.modify_ansible_repo_content",
                    "has_required_repo_perms_on_upload:ansible.view_ansiblerepository",
                ],
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }


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

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": "create",
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_required_repo_perms_on_upload:ansible.modify_ansible_repo_content",
                    "has_required_repo_perms_on_upload:ansible.view_ansiblerepository",
                ],
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }


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

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": "*",
                "principal": "admin",
                "effect": "allow",
            },
            {
                "action": "avatar",
                "principal": "*",
                "effect": "allow",
            },
        ],
        "creation_hooks": [],
    }

    @extend_schema(
        description="Get the logo for the this namespace.",
        responses={302: HttpResponseRedirect},
    )
    @action(detail=True, methods=["get"], serializer_class=None)
    def avatar(self, request, pk):
        """
        Tries to find a redirect link to the Namespace's avatar
        """
        ns = self.get_object()
        if artifact := ns.avatar_artifact:
            return HttpResponseRedirect(get_artifact_url(artifact))

        return HttpResponseNotFound()


class RoleRemoteViewSet(RemoteViewSet, RolesMixin):
    """
    ViewSet for Role Remotes.
    """

    endpoint_name = "role"
    queryset = RoleRemote.objects.all()
    serializer_class = RoleRemoteSerializer
    queryset_filtering_required_permission = "ansible.view_roleremote"

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve", "my_permissions"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": "create",
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_perms:ansible.add_roleremote",
            },
            {
                "action": "destroy",
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:ansible.delete_roleremote",
            },
            {
                "action": ["update", "partial_update", "set_label", "unset_label"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:ansible.change_roleremote",
            },
            {
                "action": ["list_roles", "add_role", "remove_role"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:ansible.manage_roles_roleremote",
            },
        ],
        "creation_hooks": [
            {
                "function": "add_roles_for_object_creator",
                "parameters": {"roles": "ansible.roleremote_owner"},
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }

    LOCKED_ROLES = {
        "ansible.roleremote_creator": ["ansible.add_roleremote"],
        "ansible.roleremote_owner": [
            "ansible.view_roleremote",
            "ansible.change_roleremote",
            "ansible.delete_roleremote",
            "ansible.manage_roles_roleremote",
        ],
        "ansible.roleremote_viewer": ["ansible.view_roleremote"],
    }


class GitRemoteViewSet(RemoteViewSet, RolesMixin):
    """
    ViewSet for Ansible Remotes.

    This is a tech preview feature. The functionality may change in the future.
    """

    endpoint_name = "git"
    queryset = GitRemote.objects.all()
    serializer_class = GitRemoteSerializer
    queryset_filtering_required_permission = "ansible.view_gitremote"

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve", "my_permissions"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": "create",
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_perms:ansible.add_gitremote",
            },
            {
                "action": "destroy",
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:ansible.delete_gitremote",
            },
            {
                "action": ["update", "partial_update", "set_label", "unset_label"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:ansible.change_gitremote",
            },
            {
                "action": ["list_roles", "add_role", "remove_role"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:ansible.manage_roles_gitremote",
            },
        ],
        "creation_hooks": [
            {
                "function": "add_roles_for_object_creator",
                "parameters": {"roles": "ansible.gitremote_owner"},
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }

    LOCKED_ROLES = {
        "ansible.gitremote_creator": ["ansible.add_gitremote"],
        "ansible.gitremote_owner": [
            "ansible.view_gitremote",
            "ansible.change_gitremote",
            "ansible.delete_gitremote",
            "ansible.manage_roles_gitremote",
        ],
        "ansible.gitremote_viewer": ["ansible.view_gitremote"],
    }


class AnsibleRepositoryViewSet(RepositoryViewSet, ModifyRepositoryActionMixin, RolesMixin):
    """
    ViewSet for Ansible Repositories.
    """

    endpoint_name = "ansible"
    queryset = AnsibleRepository.objects.all()
    serializer_class = AnsibleRepositorySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        action = getattr(self, "action", "")
        if action == "list" or action == "retrieve":
            qs = get_queryset_annotated_with_last_sync_task(qs)

        return qs

    queryset_filtering_required_permission = "ansible.view_ansiblerepository"

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve", "my_permissions"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": "create",
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_perms:ansible.add_ansiblerepository",
            },
            {
                "action": "destroy",
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:ansible.delete_ansiblerepository",
            },
            {
                "action": ["update", "partial_update", "set_label", "unset_label"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:ansible.change_ansiblerepository",
                    "has_model_or_obj_perms:ansible.view_ansiblerepository",
                ],
            },
            {
                "action": ["modify", "mark", "unmark"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:ansible.modify_ansible_repo_content",
                    "has_model_or_obj_perms:ansible.view_ansiblerepository",
                ],
            },
            {
                "action": ["rebuild_metadata"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:ansible.rebuild_metadata_ansiblerepository",
                ],
            },
            {
                "action": ["repair"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:ansible.repair_ansiblerepository"
                    "has_model_or_obj_perms:ansible.view_ansiblerepository",
                ],
            },
            {
                "action": ["sign"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:ansible.sign_ansiblerepository",
                    "has_model_or_obj_perms:ansible.view_ansiblerepository",
                ],
            },
            {
                "action": ["sync"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:ansible.sync_ansiblerepository",
                    "has_model_or_obj_perms:ansible.view_ansiblerepository",
                    # TODO Update has_remote_param_model_or_obj to handle multiple remote types
                    # "has_remote_param_model_or_obj_perms:ansible.view_collectionremote",
                    # "has_remote_param_model_or_obj_perms:ansible.view_gitremote",
                    # "has_remote_param_model_or_obj_perms:ansible.view_roleremote",
                ],
            },
            {
                "action": ["copy_collection_version"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:modify_ansible_repo_content",
                    "has_model_or_obj_perms:ansible.view_ansiblerepository",
                ],
                # TODO: create a custom access condition to ensure user has perms on dest repos
            },
            {
                "action": ["move_collection_version"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:modify_ansible_repo_content",
                    "has_model_or_obj_perms:ansible.view_ansiblerepository",
                ],
                # TODO: create a custom access condition to ensure user has perms on dest repos
            },
            {
                "action": ["list_roles", "add_role", "remove_role"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:ansible.manage_roles_ansiblerepository",
            },
        ],
        "creation_hooks": [
            {
                "function": "add_roles_for_object_creator",
                "parameters": {"roles": "ansible.ansiblerepository_owner"},
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }

    LOCKED_ROLES = {
        "ansible.ansiblerepository_creator": ["ansible.add_ansiblerepository"],
        "ansible.ansiblerepository_owner": [
            "ansible.view_ansiblerepository",
            "ansible.change_ansiblerepository",
            "ansible.delete_ansiblerepository",
            "ansible.manage_roles_ansiblerepository",
            "ansible.modify_ansible_repo_content",
            "ansible.rebuild_metadata_ansiblerepository",
            "ansible.repair_ansiblerepository",
            "ansible.sign_ansiblerepository",
            "ansible.sync_ansiblerepository",
        ],
        "ansible.ansiblerepository_viewer": ["ansible.view_ansiblerepository"],
    }

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
        reserved = data["destination_repositories"]
        shared = [repository]
        signing_service = data.get("signing_service", None)
        if signing_service:
            signing_service = signing_service.pk

        result = dispatch(
            copy_or_move_and_sign,
            exclusive_resources=reserved,
            shared_resources=shared,
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
        Copy a list of collection versions and all of their associated content from this
        repository.
        """

        return self._handle_copy_or_move(request, "copy")

    @extend_schema(
        description="Trigger an asynchronous task to move collection versions.",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=CollectionVersionCopyMoveSerializer)
    def move_collection_version(self, request, pk):
        """
        Move a list of collection versions and all of their associated content from this
        repository.
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

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_repository_model_or_obj_perms:ansible.view_ansiblerepository",
            },
            {
                "action": "destroy",
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_repository_model_or_obj_perms:ansible.delete_ansiblerepository",
                    "has_repository_model_or_obj_perms:ansible.view_ansiblerepository",
                ],
            },
            {
                "action": ["repair"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_repository_model_or_obj_perms:ansible.repair_ansiblerepository",
                    "has_repository_model_or_obj_perms:ansible.view_ansiblerepository",
                ],
            },
            {
                "action": ["rebuild_metadata"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_repository_model_or_obj_perms:ansible.rebuild_metadata_ansiblerepository",
                ],
            },
        ],
    }

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


class CollectionRemoteViewSet(RemoteViewSet, RolesMixin):
    """
    ViewSet for Collection Remotes.
    """

    endpoint_name = "collection"
    queryset = CollectionRemote.objects.all()
    serializer_class = CollectionRemoteSerializer
    filterset_class = CollectionRemoteFilter

    def get_queryset(self):
        qs = super().get_queryset()
        action = getattr(self, "action", "")
        if action == "list" or action == "retrieve":
            qs = get_queryset_annotated_with_last_sync_task(qs)

        return qs

    queryset_filtering_required_permission = "ansible.view_collectionremote"

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve", "my_permissions"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": "create",
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_perms:ansible.add_collectionremote",
            },
            {
                "action": "destroy",
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:ansible.delete_collectionremote",
            },
            {
                "action": ["update", "partial_update", "set_label", "unset_label"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:ansible.change_collectionremote",
            },
            {
                "action": ["list_roles", "add_role", "remove_role"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:ansible.manage_roles_collectionremote",
            },
        ],
        "creation_hooks": [
            {
                "function": "add_roles_for_object_creator",
                "parameters": {"roles": "ansible.collectionremote_owner"},
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }

    LOCKED_ROLES = {
        "ansible.collectionremote_creator": ["ansible.add_collectionremote"],
        "ansible.collectionremote_owner": [
            "ansible.view_collectionremote",
            "ansible.change_collectionremote",
            "ansible.delete_collectionremote",
            "ansible.manage_roles_collectionremote",
        ],
        "ansible.collectionremote_viewer": ["ansible.view_collectionremote"],
    }

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


class AnsibleDistributionViewSet(DistributionViewSet, RolesMixin):
    """
    ViewSet for Ansible Distributions.
    """

    endpoint_name = "ansible"
    queryset = AnsibleDistribution.objects.all()
    serializer_class = AnsibleDistributionSerializer

    queryset_filtering_required_permission = "ansible.view_ansibledistribution"

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve", "my_permissions"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": "create",
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_perms:ansible.add_ansibledistribution",
                    "has_repo_or_repo_ver_param_model_or_obj_perms:ansible.view_ansiblerepository",
                ],
            },
            {
                "action": "destroy",
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:ansible.delete_ansibledistribution",
                ],
            },
            {
                "action": ["update", "partial_update", "set_label", "unset_label"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:ansible.change_ansibledistribution",
                ],
            },
            {
                "action": ["list_roles", "add_role", "remove_role"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:ansible.manage_roles_ansibledistribution",
            },
        ],
        "creation_hooks": [
            {
                "function": "add_roles_for_object_creator",
                "parameters": {"roles": "ansible.ansibledistribution_owner"},
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }

    LOCKED_ROLES = {
        "ansible.ansibledistribution_creator": ["ansible.add_ansibledistribution"],
        "ansible.ansibledistribution_owner": [
            "ansible.view_ansibledistribution",
            "ansible.change_ansibledistribution",
            "ansible.delete_ansibledistribution",
            "ansible.manage_roles_ansibledistribution",
        ],
        "ansible.ansibledistribution_viewer": ["ansible.view_ansibledistribution"],
    }


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
