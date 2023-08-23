from datetime import datetime
from gettext import gettext as _
import semantic_version

from django.db import DatabaseError, IntegrityError
from django.db.models import F, OuterRef, Exists, Subquery, Prefetch
from django.db.models.functions import Greatest
from django.http import StreamingHttpResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.utils.dateparse import parse_datetime
from django_filters import filters
from django.views.generic.base import RedirectView
from django.conf import settings
from django.core.cache import cache
from django.db.utils import InternalError as DatabaseInternalError

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from jinja2 import Template
from rest_framework import mixins
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.reverse import reverse, reverse_lazy
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework import viewsets, views
from rest_framework.exceptions import NotFound
from rest_framework import status

from pulpcore.plugin.models import (
    Artifact,
    Content,
    ContentArtifact,
    RepositoryContent,
    Distribution,
)
from pulpcore.plugin.serializers import AsyncOperationResponseSerializer
from pulpcore.plugin.viewsets import (
    BaseFilterSet,
    OperationPostponedResponse,
    SingleArtifactContentUploadViewSet,
    NAME_FILTER_OPTIONS,
)
from pulpcore.plugin.tasking import add_and_remove, dispatch, general_create

from pulp_ansible.app.galaxy.v3.exceptions import ExceptionHandlerMixin
from pulp_ansible.app.galaxy.v3.serializers import (
    CollectionSerializer,
    CollectionVersionSerializer,
    CollectionVersionDocsSerializer,
    CollectionVersionListSerializer,
    RepoMetadataSerializer,
    UnpaginatedCollectionVersionSerializer,
    ClientConfigurationSerializer,
)
from pulp_ansible.app.models import (
    AnsibleCollectionDeprecated,
    AnsibleDistribution,
    AnsibleNamespaceMetadata,
    Collection,
    CollectionDownloadCount,
    CollectionVersion,
    CollectionVersionMark,
    CollectionVersionSignature,
    CollectionImport,
    DownloadLog,
)
from pulp_ansible.app.serializers import (
    AnsibleNamespaceMetadataSerializer,
    CollectionImportDetailSerializer,
    CollectionOneShotSerializer,
    CollectionVersionUploadSerializer,
)

from pulp_ansible.app.galaxy.mixins import UploadGalaxyCollectionMixin, GalaxyAuthMixin
from pulp_ansible.app.galaxy.v3.pagination import LimitOffsetPagination
from pulp_ansible.app.viewsets import (
    CollectionVersionFilter,
)

from pulp_ansible.app.tasks.deletion import delete_collection_version, delete_collection

from pulp_ansible.app.utils import filter_content_for_repo_version


_CAN_VIEW_REPO_CONTENT = {
    "action": ["list", "retrieve", "download"],
    "principal": "authenticated",
    "effect": "allow",
    "condition": "v3_can_view_repo_content",
}

_PERMISSIVE_ACCESS_POLICY = {
    "statements": [
        _CAN_VIEW_REPO_CONTENT,
    ],
    "creation_hooks": [],
}


class AnsibleDistributionMixin:
    """
    A mixin for ViewSets that use AnsibleDistribution.
    """

    _repo_version = None
    _repo = None

    @property
    def _repository_version(self):
        """Returns repository version."""
        if self._repo_version:
            return self._repo_version

        path = self.kwargs["distro_base_path"]

        context = getattr(self, "pulp_context", None)
        if context and context.get(path, None):
            return self.pulp_context[path]

        # using Distribution instead of Ansible distribution allows us to save a join
        distro = get_object_or_404(
            Distribution.objects.only(
                "base_path", "repository_version", "repository"
            ).select_related("repository__ansible_ansiblerepository"),
            base_path=path,
        )
        if distro.repository_version_id:
            self.pulp_context = {path: distro.repository_version}
            self._repo_version = distro.repository_version
            self._repo = self._repo_version.repository.cast()
            return distro.repository_version

        repo_version = distro.repository.latest_version() if distro.repository else None
        self.pulp_context = {path: repo_version}
        self._repo = distro.repository.ansible_ansiblerepository
        self._repo_version = repo_version
        return repo_version

    @property
    def _repository(self):
        if self._repo:
            return self._repo
        self._repo_version
        return self._repo

    @property
    def _distro_content(self):
        """Returns distribution content."""
        repo_version = self._repository_version
        if repo_version is None:
            return Content.objects.none()

        return repo_version.content

    def get_serializer_context(self):
        """Inserts distribution path to a serializer context."""
        context = super().get_serializer_context()
        if "path" in self.kwargs:
            context["path"] = self.kwargs["path"]

        context["distro_base_path"] = self.kwargs["distro_base_path"]
        return context


class CollectionVersionRetrieveMixin:
    """
    A mixin for ViewSets that get instance of CollectionVersion.
    """

    def get_queryset(self):
        """
        Returns a CollectionVersions queryset for specified distribution.
        """
        if getattr(self, "swagger_fake_view", False):
            # drf_spectacular get filter from get_queryset().model
            # and it fails when "path" is not on self.kwargs
            return CollectionVersion.objects.none()

        repo_version = self._repository_version

        qs = (
            filter_content_for_repo_version(CollectionVersion.objects, repo_version)
            .select_related("collection")
            .prefetch_related(
                Prefetch(
                    "marks",
                    queryset=filter_content_for_repo_version(
                        CollectionVersionMark.objects, repo_version
                    ),
                )
            )
            .filter(namespace=self.kwargs["namespace"], name=self.kwargs["name"])
        )

        return qs

    def get_object(self):
        """
        This modifies the qs for get requests to add some extra lookups for the detail view
        """
        repo_version = self._repository_version
        qs = self.get_queryset()
        qs = (
            qs.prefetch_related(
                Prefetch(
                    "signatures",
                    queryset=filter_content_for_repo_version(
                        CollectionVersionSignature.objects, repo_version
                    ),
                )
            )
            .prefetch_related(
                Prefetch(
                    "contentartifact_set",
                    queryset=ContentArtifact.objects.select_related("artifact"),
                    to_attr="artifacts",
                )
            )
            .annotate(
                namespace_sha256=Subquery(
                    filter_content_for_repo_version(AnsibleNamespaceMetadata.objects, repo_version)
                    .filter(name=OuterRef("namespace"))
                    .values("metadata_sha256"),
                )
            )
            .select_related("collection")
        )

        queryset = self.filter_queryset(qs)

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        assert lookup_url_kwarg in self.kwargs, (
            "Expected view %s to be called with a URL keyword argument "
            'named "%s". Fix your URL conf, or set the `.lookup_field` '
            "attribute on the view correctly." % (self.__class__.__name__, lookup_url_kwarg)
        )

        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj


class CollectionFilter(BaseFilterSet):
    """
    FilterSet for Ansible Collections.
    """

    namespace = filters.CharFilter(field_name="namespace")
    name = filters.CharFilter(field_name="name")
    deprecated = filters.BooleanFilter(field_name="deprecated")

    class Meta:
        model = Collection
        fields = ["namespace", "name", "deprecated"]


class CollectionViewSet(
    GalaxyAuthMixin,
    ExceptionHandlerMixin,
    AnsibleDistributionMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for Collections.
    """

    serializer_class = CollectionSerializer
    filterset_class = CollectionFilter
    pagination_class = LimitOffsetPagination

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            _CAN_VIEW_REPO_CONTENT,
            {
                "action": "destroy",
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_perms:ansible.delete_collection",
            },
            {
                "action": ["update", "partial_update"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "v3_can_modify_repo_content",
            },
        ],
    }

    def urlpattern(*args, **kwargs):
        """Return url pattern for RBAC."""
        return "pulp_ansible/v3/collections"

    def get_queryset(self):
        """
        Returns a Collections queryset for specified distribution.
        """
        if getattr(self, "swagger_fake_view", False):
            # drf_spectacular get filter from get_queryset().model
            # and it fails when "path" is not on self.kwargs
            return Collection.objects.none()
        repo_version = self._repository_version

        deprecated_qs = filter_content_for_repo_version(
            AnsibleCollectionDeprecated.objects, repo_version
        ).filter(namespace=OuterRef("namespace"), name=OuterRef("name"))

        latest_cv_version_qs = (
            filter_content_for_repo_version(CollectionVersion.objects, repo_version)
            .filter(collection=OuterRef("pk"))
            .order_by(
                "-version_major",
                "-version_minor",
                "-version_patch",
                "-version_prerelease",
                "-pulp_created",
            )
            .only("version")
        )

        latest_version_modified_qs = (
            RepositoryContent.objects.filter(
                repository_id=repo_version.repository_id,
                version_added__number__lte=repo_version.number,
            )
            .select_related("content__ansible_collectionversion")
            .select_related("version_added")
            .select_related("version_removed")
            .filter(content__ansible_collectionversion__collection_id=OuterRef("pk"))
            .annotate(
                last_updated=Greatest(
                    "version_added__pulp_created", "version_removed__pulp_created"
                )
            )
            .order_by("-last_updated")
            .only("last_updated")
        )

        download_count_qs = CollectionDownloadCount.objects.filter(
            name=OuterRef("name"), namespace=OuterRef("namespace")
        )

        qs = (
            Collection.objects.annotate(
                highest_version=Subquery(latest_cv_version_qs.values("version")[:1]),
                latest_version_modified=Subquery(
                    latest_version_modified_qs.values("last_updated")[:1]
                ),
            )
            .annotate(
                deprecated=Exists(deprecated_qs),
                download_count=Subquery(download_count_qs.values("download_count")[:1]),
            )
            .filter(highest_version__isnull=False)
        )

        return qs

    def get_object(self):
        """
        Returns a Collection object.
        """
        queryset = self.filter_queryset(self.get_queryset())
        return get_object_or_404(
            queryset, namespace=self.kwargs["namespace"], name=self.kwargs["name"]
        )

    @extend_schema(
        description="Trigger an asynchronous update task",
        responses={202: AsyncOperationResponseSerializer},
    )
    def update(self, request, *args, **kwargs):
        """
        Update a Collection object.
        """
        repo_version = self._repository_version
        collection = self.get_object()
        serializer = self.get_serializer(collection, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        deprecated_value = request.data.get("deprecated")
        add_content_units = []
        remove_content_units = []

        deprecation, created = AnsibleCollectionDeprecated.objects.get_or_create(
            namespace=collection.namespace, name=collection.name
        )
        if not created:
            try:
                deprecation.touch()
            except DatabaseError:
                # deprecation has since been removed. try to create it
                deprecation = AnsibleCollectionDeprecated.objects.create(
                    namespace=collection.namespace, name=collection.name
                )

        if deprecated_value:
            add_content_units.append(deprecation.pk)
        else:
            remove_content_units.append(deprecation.pk)

        task = dispatch(
            add_and_remove,
            exclusive_resources=[repo_version.repository],
            kwargs={
                "repository_pk": repo_version.repository.pk,
                "base_version_pk": repo_version.pk,
                "add_content_units": add_content_units,
                "remove_content_units": remove_content_units,
            },
        )
        return OperationPostponedResponse(task, request)

    @extend_schema(
        description="Trigger an asynchronous delete task",
        responses={202: AsyncOperationResponseSerializer},
    )
    def destroy(self, request: Request, *args, **kwargs) -> Response:
        """
        Allow a Collection to be deleted.

        1. Perform Dependency Check to verify that each CollectionVersion
           inside Collection can be deleted
        2. If the Collection can’t be deleted, return the reason why
        3. If it can, dispatch task to delete each CollectionVersion
           and the Collection
        """
        collection = self.get_object()

        # dependency check
        dependents = get_collection_dependents(collection)
        if dependents:
            return Response(
                {
                    "detail": _(
                        "Collection {namespace}.{name} could not be deleted "
                        "because there are other collections that require it."
                    ).format(
                        namespace=collection.namespace,
                        name=collection.name,
                    ),
                    "dependent_collection_versions": [
                        f"{dep.namespace}.{dep.name} {dep.version}" for dep in dependents
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        repositories = set()
        for version in collection.versions.all():
            for repo in version.repositories.all():
                repositories.add(repo)

        async_result = dispatch(
            delete_collection,
            exclusive_resources=list(repositories),
            kwargs={"collection_pk": collection.pk},
        )

        return OperationPostponedResponse(async_result, request)


def get_collection_dependents(parent):
    """Given a parent collection, return a list of collection versions that depend on it."""
    key = f"{parent.namespace}.{parent.name}"
    return list(
        CollectionVersion.objects.exclude(collection=parent).filter(dependencies__has_key=key)
    )


def get_unique_dependents(parent):
    """Given a parent collection version, return a list of collection versions that depend on it."""
    key = f"{parent.namespace}.{parent.name}"

    this_version = semantic_version.Version(parent.version)

    # Other versions contain a set of all versions of this collection aside from the version
    # that is being deleted.
    other_versions = []
    for v in parent.collection.versions.exclude(version=parent.version):
        other_versions.append(semantic_version.Version(v.version))

    dependents = []
    for child in CollectionVersion.objects.filter(dependencies__has_key=key):
        spec = semantic_version.SimpleSpec(child.dependencies[key])

        # If this collection matches the parent collections version and there are no other
        # collection versions that can satisfy the requirement, add it to the list of dependants.
        if spec.match(this_version) and not spec.select(other_versions):
            dependents.append(child)

    return dependents


class UnpaginatedCollectionViewSet(CollectionViewSet):
    """Unpaginated ViewSet for Collections."""

    pagination_class = None

    def urlpattern(*args, **kwargs):
        """Return url pattern for RBAC."""
        return "pulp_ansible/v3/collections/all"


class CollectionUploadViewSet(
    GalaxyAuthMixin,
    ExceptionHandlerMixin,
    UploadGalaxyCollectionMixin,
    SingleArtifactContentUploadViewSet,
    AnsibleDistributionMixin,
):
    """
    ViewSet for Collection Uploads.
    """

    queryset = None
    endpoint_pieces = None
    serializer_class = CollectionVersionUploadSerializer
    pulp_tag_name = "Pulp_Ansible: Artifacts Collections V3"

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            _CAN_VIEW_REPO_CONTENT,
            {
                "action": ["create"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_perms:ansible.add_collection",
                    "v3_can_view_repo_content",
                ],
            },
        ],
    }

    def urlpattern(*args, **kwargs):
        """Return url pattern for RBAC."""
        return "pulp_ansible/v3/collections/upload"

    def _dispatch_upload_collection_task(self, args=None, kwargs=None, repository=None):
        """
        Dispatch an Upload Collection creation task.
        """
        locks = []
        if repository:
            locks.append(repository)

        return dispatch(general_create, exclusive_resources=locks, args=args, kwargs=kwargs)

    @extend_schema(
        description="Create an artifact and trigger an asynchronous task to create "
        "Collection content from it.",
        summary="Upload a collection",
        request=CollectionOneShotSerializer,
        responses={202: AsyncOperationResponseSerializer},
    )
    def create(self, request, distro_base_path):
        """
        Dispatch a Collection creation task.
        """
        distro = get_object_or_404(AnsibleDistribution, base_path=distro_base_path)
        repo = distro.repository
        if repo is None:
            if distro.repository_version is None:
                raise serializers.ValidationError(
                    _("Distribution must have either repository or repository_version set")
                )
            repo = distro.repository_version.repository
        # Check that invalid fields were not specified
        serializer = CollectionOneShotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Check that namespace, name and version can be extracted
        request.data["repository"] = reverse("repositories-ansible/ansible-detail", args=[repo.pk])
        serializer = CollectionVersionUploadSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        # Convert file to an artifact
        task_payload = self.init_content_data(serializer, request)
        # Dispatch create task
        task = self._dispatch_upload_collection_task(
            repository=serializer.validated_data["repository"],
            args=(CollectionVersion._meta.app_label, serializer.__class__.__name__),
            kwargs={
                "data": task_payload,
                "context": self.get_deferred_context(request),
            },
        )
        # Create CollectionImport and response
        CollectionImport.objects.create(task_id=task.pk)
        data = {
            "task": reverse(
                settings.ANSIBLE_URL_NAMESPACE + "collection-imports-detail",
                kwargs={"pk": task.pk},
                request=None,
            )
        }
        return Response(data, status=http_status.HTTP_202_ACCEPTED)


class LegacyCollectionUploadViewSet(CollectionUploadViewSet):
    """
    Collection upload viewset with deprecated markers for the openAPI spec.
    """

    @extend_schema(
        description="Create an artifact and trigger an asynchronous task to create "
        "Collection content from it.",
        summary="Upload a collection",
        request=CollectionOneShotSerializer,
        responses={202: AsyncOperationResponseSerializer},
        deprecated=True,
    )
    def create(self, request, path):
        """Create collection."""
        return super().create(request, distro_base_path=path)


class CollectionArtifactDownloadView(GalaxyAuthMixin, views.APIView, AnsibleDistributionMixin):
    """Collection download endpoint."""

    action = "download"

    DEFAULT_ACCESS_POLICY = _PERMISSIVE_ACCESS_POLICY

    @staticmethod
    def log_download(request, filename, distro_base_path):
        """Log the download of the collection version."""

        def _get_org_id(request):
            if not isinstance(request.auth, dict):
                return None

            x_rh_identity = request.auth.get("rh_identity")
            if not x_rh_identity:
                return None

            identity = x_rh_identity["identity"]

            if (not identity) or (not identity.get("internal")):
                return None

            return identity["internal"]["org_id"]

        # Gettung user IP
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        ip = x_forwarded_for.split(",")[0] if x_forwarded_for else request.META.get("REMOTE_ADDR")

        user_agent = request.headers.get("user-agent", "unknown")

        distribution = get_object_or_404(AnsibleDistribution, base_path=distro_base_path)
        repository_version = (
            distribution.repository_version or distribution.repository.latest_version()
        )

        # Getting collection version
        ns, name, version = filename.split("-", maxsplit=2)
        # Get off the ending .tar.gz
        version = ".".join(version.split(".")[:3])
        collection_version = get_object_or_404(
            CollectionVersion.objects.filter(pk__in=repository_version.content),
            namespace=ns,
            name=name,
            version=version,
        )

        log_params = dict(
            content_unit=collection_version,
            ip=ip,
            extra_data={"org_id": _get_org_id(request)},
            user_agent=user_agent,
            repository=repository_version.repository,
            repository_version=repository_version,
        )
        if request.user.is_authenticated:
            log_params["user"] = request.user

        try:
            DownloadLog.objects.create(**log_params)
        except DatabaseInternalError as e:
            # handle a read-only replica scenario
            msg = str(e)
            if "read-only" in msg:
                return
            raise

    def count_download(filename):
        ns, name, _ = filename.split("-", maxsplit=2)
        try:
            collection, created = CollectionDownloadCount.objects.get_or_create(
                namespace=ns, name=name, defaults={"download_count": 1}
            )
            if not created:
                collection.download_count = F("download_count") + 1
                collection.save()
        except DatabaseInternalError as e:
            # handle a read-only replica scenario
            msg = str(e)
            if "read-only" in msg:
                return
            raise

    def urlpattern(*args, **kwargs):
        """Return url pattern for RBAC."""
        return "pulp_ansible/v3/collections/download"

    def get(self, request, *args, **kwargs):
        """Download collection."""
        distro_base_path = self.kwargs["distro_base_path"]
        distribution = AnsibleDistribution.objects.get(base_path=distro_base_path)

        url = "{host}/{prefix}/{distro_base_path}/{filename}".format(
            host=settings.CONTENT_ORIGIN.strip("/"),
            prefix=settings.CONTENT_PATH_PREFIX.strip("/"),
            distro_base_path=distro_base_path,
            filename=self.kwargs["filename"],
        )

        if settings.ANSIBLE_COLLECT_DOWNLOAD_LOG:
            CollectionArtifactDownloadView.log_download(
                request, self.kwargs["filename"], distro_base_path
            )

        if settings.ANSIBLE_COLLECT_DOWNLOAD_COUNT:
            CollectionArtifactDownloadView.count_download(self.kwargs["filename"])

        if (
            distribution.content_guard
            and distribution.content_guard.pulp_type == "core.content_redirect"
        ):
            guard = distribution.content_guard.cast()
            url = guard.preauthenticate_url(url)

        return redirect(url)


@extend_schema_view(
    create=extend_schema(responses={202: AsyncOperationResponseSerializer}),
    partial_update=extend_schema(responses={202: AsyncOperationResponseSerializer}),
    delete=extend_schema(responses={202: AsyncOperationResponseSerializer}),
)
class AnsibleNamespaceViewSet(
    GalaxyAuthMixin, ExceptionHandlerMixin, AnsibleDistributionMixin, viewsets.ModelViewSet
):
    serializer_class = AnsibleNamespaceMetadataSerializer
    lookup_field = "name"
    filterset_fields = {
        "name": NAME_FILTER_OPTIONS,
        "company": NAME_FILTER_OPTIONS,
        "metadata_sha256": ["exact", "in"],
    }

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            _CAN_VIEW_REPO_CONTENT,
            {
                "action": "create",
                "principal": "authenticated",
                "effect": "allow",
                "conditions": "v3_can_modify_repo_content",
            },
            {
                "action": "delete",
                "principal": "authenticated",
                "effect": "allow",
                "conditions": "v3_can_modify_repo_content",
            },
            {
                "action": "partial_update",
                "principal": "authenticated",
                "effect": "allow",
                "conditions": "v3_can_modify_repo_content",
            },
        ],
    }

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            # drf_spectacular get filter from get_queryset().model
            # and it fails when "path" is not on self.kwargs
            return AnsibleNamespaceMetadata.objects.none()
        return filter_content_for_repo_version(
            AnsibleNamespaceMetadata.objects, self._repository_version
        )

    def create(self, request, *args, **kwargs):
        return self._create(request, data=request.data)

    def _create(self, request, data, context=None):
        """Dispatch task to create and add Namespace to repository."""
        repo = self._repository_version.repository
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        context = context or {}
        context["repository"] = repo.pk
        # If avatar was uploaded, init into artifact
        if avatar := serializer.validated_data.pop("avatar", None):
            artifact = Artifact.init_and_validate(avatar)
            try:
                artifact.save()
            except IntegrityError:
                # if artifact already exists, let's use it
                try:
                    artifact = Artifact.objects.get(sha256=artifact.sha256)
                    artifact.touch()
                except (Artifact.DoesNotExist, DatabaseError):
                    # the artifact has since been removed from when we first attempted to save it
                    artifact.save()
            context["artifact"] = artifact.pk

        # Dispatch general_create task
        app_label = AnsibleNamespaceMetadata._meta.app_label
        task = dispatch(
            general_create,
            args=(app_label, serializer.__class__.__name__),
            exclusive_resources=[repo],
            kwargs={
                "data": serializer.validated_data,
                "context": context,
            },
        )
        return OperationPostponedResponse(task, request)

    def update(self, request, *args, **kwargs):
        """Dispatch task to update Namespace in repository."""
        partial = kwargs.pop("partial", False)
        namespace = self.get_object()
        serializer = self.get_serializer(namespace, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        for name, field in serializer.fields.items():
            if not field.read_only and not field.write_only:
                serializer.validated_data.setdefault(name, serializer.data[name])
        context = {}
        if "avatar" not in request.data and namespace.avatar_sha256:
            context["artifact"] = Artifact.objects.get(sha256=namespace.avatar_sha256).pk
        return self._create(request, data=serializer.validated_data, context=context)

    def delete(self, request, *args, **kwargs):
        """Try to remove the Namespace if no Collections under Namespace are present."""
        namespace = self.get_object()

        if self._distro_content.filter(
            ansible_collectionversion__namespace=namespace.name
        ).exists():
            raise serializers.ValidationError(
                detail=_(
                    "Namespace {name} cannot be deleted because "
                    "there are still collections associated with it."
                ).format(name=namespace.name)
            )

        repository = self._repository_version.repository
        async_result = dispatch(
            add_and_remove,
            args=(repository.pk, [], [namespace.pk]),
            exclusive_resources=[repository],
        )
        return OperationPostponedResponse(async_result, request)


class CollectionVersionViewSet(
    GalaxyAuthMixin,
    CollectionVersionRetrieveMixin,
    ExceptionHandlerMixin,
    AnsibleDistributionMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for CollectionVersions.
    """

    serializer_class = CollectionVersionSerializer
    list_serializer_class = CollectionVersionListSerializer
    filterset_class = CollectionVersionFilter
    pagination_class = LimitOffsetPagination

    lookup_field = "version"

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            _CAN_VIEW_REPO_CONTENT,
            {
                "action": ["destroy"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_perms:ansible.delete_collection",
            },
        ],
    }

    def urlpattern(*args, **kwargs):
        """Return url pattern for RBAC."""
        return "pulp_ansible/v3/collection-versions"

    def get_list_serializer(self, *args, **kwargs):
        """
        Return the list serializer instance.
        """
        kwargs.setdefault("context", self.get_serializer_context)
        return self.list_serializer_class(*args, **kwargs)

    @extend_schema(
        responses={202: list_serializer_class},
    )
    def list(self, request, *args, **kwargs):
        """
        Returns paginated CollectionVersions list.
        """

        # there are too many potential permutations of query params to be able
        # to cache all of them, so this will only cache queries that stick to
        # limit/offset params, which the ansible-galaxy client uses
        cache_request = True
        for k in request.query_params.keys():
            if k not in ("offset", "limit"):
                cache_request = False
                break

        cache_key = "".join(
            [
                str(self._repository_version.pk),
                kwargs["namespace"],
                kwargs["name"],
                str(request.query_params.get("offset", "0")),
                str(request.query_params.get("limit", "0")),
            ]
        )

        if cache_key in cache and cache_request:
            return Response(cache.get(cache_key))

        queryset = self.get_queryset()

        # prevent OOMKILL ...
        queryset = queryset.only(
            "pk",
            "content_ptr_id",
            "marks",
            "namespace",
            "name",
            "version",
            "pulp_created",
            "pulp_last_updated",
            "requires_ansible",
            "collection",
        )

        queryset = self.filter_queryset(queryset)

        context = self.get_serializer_context()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_list_serializer(page, many=True, context=context)
            data = self.paginator.get_paginated_data(serializer.data)
            if cache_request:
                cache.set(cache_key, data)

            return Response(data)

        serializer = self.get_list_serializer(queryset, many=True, context=context)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """
        Returns a CollectionVersion object.
        """
        repo_version = self._repository_version
        # the contents of a repo version can be cached without worry because repo
        # versions are immutable
        cache_key = (
            f"version-details-{repo_version.pk}"
            f"{kwargs['namespace']}{kwargs['name']}{kwargs['version']}"
        )

        if data := cache.get(cache_key):
            return Response(data)

        instance = self.get_object()
        context = self.get_serializer_context()
        serializer = self.get_serializer_class()(instance, context=context)
        cache.set(cache_key, serializer.data)

        return Response(serializer.data)

    @extend_schema(
        description="Trigger an asynchronous delete task",
        responses={202: AsyncOperationResponseSerializer},
    )
    def destroy(self, request: Request, *args, **kwargs) -> Response:
        """
        Allow a CollectionVersion to be deleted.

        1. Perform Dependency Check to verify that the collection version can be deleted
        2. If the collection version can’t be deleted, return the reason why
        3. If it can, dispatch task to delete CollectionVersion and clean up repository.
           If the version being deleted is the last collection version in the collection,
           remove the collection object as well.
        """
        collection_version = self.get_object()

        # dependency check
        dependents = get_unique_dependents(collection_version)
        if dependents:
            return Response(
                {
                    "detail": _(
                        "Collection version {namespace}.{name} {version} could not be "
                        "deleted because there are other collections that require it."
                    ).format(
                        namespace=collection_version.namespace,
                        name=collection_version.collection.name,
                        version=collection_version.version,
                    ),
                    "dependent_collection_versions": [
                        f"{dep.namespace}.{dep.name} {dep.version}" for dep in dependents
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        async_result = dispatch(
            delete_collection_version,
            exclusive_resources=collection_version.repositories.all(),
            kwargs={"collection_version_pk": collection_version.pk},
        )

        return OperationPostponedResponse(async_result, request)


class UnpaginatedCollectionVersionViewSet(CollectionVersionViewSet):
    """Unpaginated ViewSet for CollectionVersions."""

    list_serializer_class = UnpaginatedCollectionVersionSerializer
    pagination_class = None

    def urlpattern(*args, **kwargs):
        """Return url pattern for RBAC."""
        return "pulp_ansible/v3/collection-versions/all"

    def get_queryset(self):
        """
        Returns a CollectionVersions queryset for specified distribution.
        """
        return (
            filter_content_for_repo_version(
                CollectionVersion.objects.select_related(), self._repository_version
            )
            .annotate(
                namespace_sha256=Subquery(
                    filter_content_for_repo_version(
                        AnsibleNamespaceMetadata.objects, self._repository_version
                    )
                    .filter(name=OuterRef("namespace"))
                    .values("metadata_sha256"),
                )
            )
            .prefetch_related(
                Prefetch(
                    "contentartifact_set",
                    queryset=ContentArtifact.objects.select_related("artifact"),
                    to_attr="artifacts",
                )
            )
            .select_related("collection")
        )

    @extend_schema(
        responses={202: list_serializer_class},
    )
    def list(self, request, *args, **kwargs):
        """
        Returns paginated CollectionVersions list.
        """
        queryset = self.get_queryset().iterator(chunk_size=100)

        context = self.get_serializer_context()
        cvs_template_string = (
            "[{% for cv in versions %}"
            "{{ cv|tojson }}{% if not loop.last %},{% endif %}"
            "{% endfor %}]"
        )
        cvs_template = Template(cvs_template_string)
        serialized_map = (self.get_list_serializer(x, context=context).data for x in queryset)
        streamed = (x.encode("utf-8") for x in cvs_template.stream(versions=serialized_map))
        return StreamingHttpResponse(streamed)


class CollectionVersionDocsViewSet(
    GalaxyAuthMixin,
    CollectionVersionRetrieveMixin,
    ExceptionHandlerMixin,
    AnsibleDistributionMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for docs_blob of CollectionVersion.
    """

    serializer_class = CollectionVersionDocsSerializer

    lookup_field = "version"

    DEFAULT_ACCESS_POLICY = _PERMISSIVE_ACCESS_POLICY

    def urlpattern(*args, **kwargs):
        """Return url pattern for RBAC."""
        return "pulp_ansible/v3/collection-versions/docs"

    def retrieve(self, request, *args, **kwargs):
        """
        Returns a CollectionVersion object.
        """
        repo_version = self._repository_version
        # the contents of a repo version can be cached without worry because repo
        # versions are immutable
        cache_key = (
            f"version-docs-{repo_version.pk}"
            f"{kwargs['namespace']}{kwargs['name']}{kwargs['version']}"
        )

        if data := cache.get(cache_key):
            return Response(data)

        instance = self.get_object()
        context = self.get_serializer_context()
        serializer = self.get_serializer_class()(instance, context=context)
        cache.set(cache_key, serializer.data)

        return Response(serializer.data)


class CollectionImportViewSet(
    GalaxyAuthMixin,
    ExceptionHandlerMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
    AnsibleDistributionMixin,
):
    """
    ViewSet for CollectionImports.
    """

    queryset = CollectionImport.objects.prefetch_related("task").all()
    serializer_class = CollectionImportDetailSerializer

    DEFAULT_ACCESS_POLICY = _PERMISSIVE_ACCESS_POLICY

    since_filter = OpenApiParameter(
        name="since",
        location=OpenApiParameter.QUERY,
        type=str,
        # format=openapi.FORMAT_DATETIME,
        description="Filter messages since a given timestamp",
    )

    def urlpattern(*args, **kwargs):
        """Return url pattern for RBAC."""
        return "pulp_ansible/v3/collections/imports"

    @extend_schema(parameters=[since_filter])
    def retrieve(self, request, *args, **kwargs):
        """
        Returns a CollectionImport object.
        """
        instance = self.get_object()

        if "since" in self.request.query_params:
            since = parse_datetime(self.request.query_params["since"])
            messages = []
            for message in instance.messages:
                message_time = datetime.fromtimestamp(message["time"])
                if message_time.replace(tzinfo=since.tzinfo) > since:
                    messages.append(message)
            instance.messages = messages

        context = self.get_serializer_context()
        serializer = CollectionImportDetailSerializer(instance, context=context)

        return Response(serializer.data)


class RepoMetadataViewSet(
    GalaxyAuthMixin,
    ExceptionHandlerMixin,
    AnsibleDistributionMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for Repository Metadata.
    """

    DEFAULT_ACCESS_POLICY = _PERMISSIVE_ACCESS_POLICY

    serializer_class = RepoMetadataSerializer

    def urlpattern(*args, **kwargs):
        """Return url pattern for RBAC."""
        return "pulp_ansible/v3/repo-metadata"

    def get_object(self):
        """
        Returns a RepositoryVersion object.
        """
        return self._repository_version


def redirect_view_generator(actions, url, viewset, distro_view=True, responses={}):
    """
    Generates a redirect view.

    Generates a viewset that
        - Redirects the selected actions to the given URL
        - Mocks the OpenAPI generation for the selected viewset

    Args:
        actions: dictionary of actions to be passed into .as_view()
        url: path name of the viewset that this view should redirect to
        viewset: viewset class of the viewset that this path redirects to
        distro_view: indicates if the viewset that is being redirected to is scoped to
            a distribution base path (such as collections).
        responses: allows the 202 response type to be overridden for specific actions.
            ex: responses={"list": MyListSerializer} will override the list action on
            the viewset to return MyListSerializer in the open api spec

    Returns:
        ViewSet.as_view()
    """
    # Serializers from the parent class are required so that the auto generated
    # clients return the correct data structure when they call the API.
    serializer = getattr(viewset, "serializer_class", None)
    list_serializer = getattr(viewset, "list_serializer_class", serializer)

    # TODO: it would be nice to be able to get a url pattern for the view that
    # this redirects to to add to the description.
    # url_pattern = resolve(settings.ANSIBLE_URL_NAMESPACE + url).route

    description = "Legacy v3 endpoint."

    # TODO: Might be able to load serializer info directly from spectacular
    # schema that gets set on the viewset
    def get_responses(action):
        default = serializer
        if action == "list":
            default = list_serializer
        elif action == "destroy":
            default = AsyncOperationResponseSerializer
        return {302: None, 202: responses.get(action, default)}

    # subclasses viewset to make .as_view work correctly on non viewset views
    # subclasses the redirected viewset to get pagination class and query params
    class GeneratedRedirectView(RedirectView, viewsets.ViewSet, viewset):
        permanent = False

        def urlpattern(*args, **kwargs):
            """Return url pattern for RBAC."""
            return "pulp_ansible/v3/legacy-redirected-viewset"

        def _get(self, *args, **kwargs):
            try:
                return super().get(*args, **kwargs)
            except NotFound:
                return HttpResponseNotFound()

        def get_redirect_url(self, *args, **kwargs):
            if distro_view:
                if "path" not in kwargs:
                    if settings.ANSIBLE_DEFAULT_DISTRIBUTION_PATH is None:
                        raise NotFound()
                    else:
                        path = settings.ANSIBLE_DEFAULT_DISTRIBUTION_PATH
                else:
                    path = self.kwargs["path"]
                    # remove the old path kwarg since we're redirecting to the new api endpoints
                    del kwargs["path"]

                kwargs = {**self.kwargs, "distro_base_path": path}

            # don't pass request. redirects work with just the path and this solves the client
            # redirect issues for aiohttp
            url = reverse_lazy(
                settings.ANSIBLE_URL_NAMESPACE + self.url,
                kwargs=kwargs,
                # request=self.request,
            )

            args = self.request.META.get("QUERY_STRING", "")
            if args:
                url = "%s?%s" % (url, args)

            return url

        @extend_schema(
            description=description,
            responses=get_responses("retrieve"),
            deprecated=True,
        )
        def retrieve(self, request, *args, **kwargs):
            return self._get(request, *args, **kwargs)

        @extend_schema(
            description=description,
            responses=get_responses("destroy"),
            deprecated=True,
        )
        def destroy(self, request, *args, **kwargs):
            return self._get(request, *args, **kwargs)

        @extend_schema(
            description=description,
            responses=get_responses("list"),
            deprecated=True,
        )
        def list(self, request, *args, **kwargs):
            return self._get(request, *args, **kwargs)

        @extend_schema(
            description=description,
            responses=get_responses("update"),
            deprecated=True,
        )
        def update(self, request, *args, **kwargs):
            return self._get(request, *args, **kwargs)

    return GeneratedRedirectView.as_view(actions, url=url)


class ClientConfigurationView(GalaxyAuthMixin, views.APIView, AnsibleDistributionMixin):
    """Return configurations for the ansible-galaxy client."""

    DEFAULT_ACCESS_POLICY = _PERMISSIVE_ACCESS_POLICY

    action = "retrieve"

    @extend_schema(responses=ClientConfigurationSerializer)
    def get(self, request, *args, **kwargs):
        """Get the client configs."""

        data = ClientConfigurationSerializer(
            {
                "default_distribution_path": self.kwargs.get(
                    "path", settings.ANSIBLE_DEFAULT_DISTRIBUTION_PATH
                )
            }
        )

        return Response(data.data)
