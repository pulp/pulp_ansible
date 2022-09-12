from datetime import datetime
from gettext import gettext as _
import semantic_version

from django.contrib.postgres.aggregates import ArrayAgg
from django.db import DatabaseError
from django.db.models import F, Q
from django.db.models.expressions import Window
from django.db.models.functions.window import FirstValue
from django.http import StreamingHttpResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.utils.dateparse import parse_datetime
from django_filters import filters
from django.views.generic.base import RedirectView
from django.conf import settings

from drf_spectacular.utils import OpenApiParameter, extend_schema
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

from pulpcore.plugin.exceptions import DigestValidationError
from pulpcore.plugin.models import PulpTemporaryFile, Content
from pulpcore.plugin.serializers import AsyncOperationResponseSerializer
from pulpcore.plugin.viewsets import BaseFilterSet, OperationPostponedResponse
from pulpcore.plugin.tasking import add_and_remove, dispatch

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
    Collection,
    CollectionVersion,
    CollectionVersionSignature,
    CollectionImport,
    DownloadLog,
)
from pulp_ansible.app.serializers import (
    CollectionOneShotSerializer,
    CollectionImportDetailSerializer,
)

from pulp_ansible.app.galaxy.mixins import UploadGalaxyCollectionMixin
from pulp_ansible.app.galaxy.v3.pagination import LimitOffsetPagination
from pulp_ansible.app.viewsets import (
    CollectionVersionFilter,
)

from pulp_ansible.app.tasks.deletion import delete_collection_version, delete_collection

_PERMISSIVE_ACCESS_POLICY = {
    "statements": [
        {"action": "*", "principal": "*", "effect": "allow"},
    ],
    "creation_hooks": [],
}


class AnsibleDistributionMixin:
    """
    A mixin for ViewSets that use AnsibleDistribution.
    """

    @property
    def _repository_version(self):
        """Returns repository version."""
        path = self.kwargs["distro_base_path"]

        context = getattr(self, "pulp_context", None)
        if context and context.get(path, None):
            return self.pulp_context[path]

        distro = get_object_or_404(AnsibleDistribution, base_path=path)
        if distro.repository_version:
            self.pulp_context = {path: distro.repository_version}
            return distro.repository_version

        repo_version = distro.repository.latest_version() if distro.repository else None
        self.pulp_context = {path: repo_version}
        return repo_version

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

        distro_content = self._distro_content
        context["sigs"] = CollectionVersionSignature.objects.filter(pk__in=distro_content)
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
        distro_content = self._distro_content

        collections = CollectionVersion.objects.select_related(
            "content_ptr__contentartifact"
        ).filter(
            pk__in=distro_content, namespace=self.kwargs["namespace"], name=self.kwargs["name"]
        )
        return collections

    def retrieve(self, request, *args, **kwargs):
        """
        Returns a CollectionVersion object.
        """
        instance = self.get_object()

        context = self.get_serializer_context()

        serializer = self.get_serializer_class()(instance, context=context)

        return Response(serializer.data)


class CollectionFilter(BaseFilterSet):
    """
    FilterSet for Ansible Collections.
    """

    namespace = filters.CharFilter(field_name="namespace")
    name = filters.CharFilter(field_name="name")
    deprecated = filters.BooleanFilter(field_name="deprecated", method="get_deprecated")

    def get_deprecated(self, qs, name, value):
        """Deprecated filter."""
        deprecation = self.request.parser_context["view"]._deprecation
        if value and deprecation:
            return qs.filter(pk__in=deprecation)

        if value is False and deprecation:
            return qs.exclude(pk__in=deprecation)
        return qs

    class Meta:
        model = Collection
        fields = ["namespace", "name", "deprecated"]


class CollectionViewSet(
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

    DEFAULT_ACCESS_POLICY = _PERMISSIVE_ACCESS_POLICY

    def urlpattern(*args, **kwargs):
        """Return url pattern for RBAC."""
        return "pulp_ansible/v3/collections"

    @property
    def _deprecation(self):
        """Return deprecated collecion ids."""
        deprecations = Q()
        for namespace, name in AnsibleCollectionDeprecated.objects.filter(
            pk__in=self._distro_content
        ).values_list("namespace", "name"):
            deprecations |= Q(namespace=namespace, name=name)
        collection_pks = []
        if len(deprecations):
            collection_pks = Collection.objects.filter(deprecations).values_list("pk", flat=True)
        self.deprecated_collections_context = collection_pks  # needed by get__serializer_context
        return collection_pks

    def get_queryset(self):
        """
        Returns a Collections queryset for specified distribution.
        """
        if getattr(self, "swagger_fake_view", False):
            # drf_spectacular get filter from get_queryset().model
            # and it fails when "path" is not on self.kwargs
            return Collection.objects.none()
        repo_version = self._repository_version
        return Collection.objects.filter(
            versions__in=repo_version.content,
        )

    def append_context(self, queryset):
        """Appending collection data to context."""
        repo_version = self._repository_version
        collections_qs = queryset.annotate(available_versions=ArrayAgg("versions__version"))
        versions_context = {}
        for collection_id, available_versions in collections_qs.values_list(
            "pk", "available_versions"
        ):
            versions_context[collection_id] = available_versions

        self.available_versions_context = versions_context  # needed by get__serializer_context
        self._deprecation

        collections = Collection.objects.filter(
            pk__in=versions_context.keys(),
            versions__version_memberships__repository=repo_version.repository,
        ).annotate(
            repo_version_added_at=Window(
                expression=FirstValue(
                    "versions__version_memberships__version_added__pulp_last_updated"
                ),
                partition_by=[F("versions__collection_id")],
                order_by=F("versions__version_memberships__version_added__pulp_last_updated").desc(
                    nulls_last=True
                ),
            ),
            repo_version_removed_at=Window(
                expression=FirstValue(
                    "versions__version_memberships__version_removed__pulp_last_updated"
                ),
                partition_by=[F("versions__collection_id")],
                order_by=F(
                    "versions__version_memberships__version_removed__pulp_last_updated"
                ).desc(nulls_last=True),
            ),
        )

        return collections.distinct("versions__collection_id").only(
            "pulp_created", "name", "namespace"
        )

    def filter_queryset(self, queryset):
        """
        Filter Repository related fields.
        """
        queryset = super().filter_queryset(queryset)

        if self.paginator is None:
            queryset = self.append_context(queryset)

        return queryset

    def paginate_queryset(self, queryset):
        """Custom pagination."""
        if self.paginator is None:
            return None
        paginator = self.paginator
        # Making sure COUNT a lighter query (before append_context)
        paginator.count = paginator.get_count(
            queryset.model.objects.filter(pk__in=queryset).distinct("versions__collection_id")
        )
        paginator.limit = paginator.get_limit(self.request)
        if paginator.limit is None:
            return None

        paginator.offset = paginator.get_offset(self.request)
        paginator.request = self.request
        if paginator.count > paginator.limit and paginator.template is not None:
            paginator.display_page_controls = True

        if paginator.count == 0 or paginator.offset > paginator.count:
            return []
        new_queryset = queryset[paginator.offset : paginator.offset + paginator.limit]
        # Paginate query with appended context
        return list(self.append_context(new_queryset))

    def get_object(self):
        """
        Returns a Collection object.
        """
        queryset = self.filter_queryset(self.get_queryset())
        queryset = self.append_context(queryset)
        return get_object_or_404(
            queryset, namespace=self.kwargs["namespace"], name=self.kwargs["name"]
        )

    def get_serializer_context(self, *args, **kwargs):
        """
        Return the serializer context.

        This uses super() but also adds in the "highest_versions" data from get_queryset()
        """
        super_data = super().get_serializer_context()
        if getattr(self, "available_versions_context", None):
            super_data["available_versions"] = self.available_versions_context
        super_data["deprecated_collections"] = getattr(self, "deprecated_collections_context", [])
        return super_data

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
    ExceptionHandlerMixin, viewsets.GenericViewSet, UploadGalaxyCollectionMixin
):
    """
    ViewSet for Collection Uploads.
    """

    serializer_class = CollectionOneShotSerializer
    pulp_tag_name = "Pulp_Ansible: Artifacts Collections V3"

    DEFAULT_ACCESS_POLICY = _PERMISSIVE_ACCESS_POLICY

    def urlpattern(*args, **kwargs):
        """Return url pattern for RBAC."""
        return "pulp_ansible/v3/collections/upload"

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
        serializer = self.get_serializer(data=request.data, context={"request": request})
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

        kwargs = {}

        if serializer.validated_data["expected_namespace"]:
            kwargs["expected_namespace"] = serializer.validated_data["expected_namespace"]

        if serializer.validated_data["expected_name"]:
            kwargs["expected_name"] = serializer.validated_data["expected_name"]

        if serializer.validated_data["expected_version"]:
            kwargs["expected_version"] = serializer.validated_data["expected_version"]

        async_result = self._dispatch_import_collection_task(
            temp_file.pk, distro.repository, **kwargs
        )
        CollectionImport.objects.create(task_id=async_result.pk)

        data = {
            "task": reverse(
                settings.ANSIBLE_URL_NAMESPACE + "collection-imports-detail",
                kwargs={"pk": async_result.pk},
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


class CollectionArtifactDownloadView(views.APIView):
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

        DownloadLog.objects.create(
            content_unit=collection_version,
            user=request.user,
            ip=ip,
            extra_data={"org_id": _get_org_id(request)},
            user_agent=user_agent,
            repository=repository_version.repository,
            repository_version=repository_version,
        )

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

        if (
            distribution.content_guard
            and distribution.content_guard.pulp_type == "core.content_redirect"
        ):
            guard = distribution.content_guard.cast()
            url = guard.preauthenticate_url(url)

        return redirect(url)


class CollectionVersionViewSet(
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

    DEFAULT_ACCESS_POLICY = _PERMISSIVE_ACCESS_POLICY

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
        queryset = self.filter_queryset(self.get_queryset())
        queryset = sorted(
            queryset, key=lambda obj: semantic_version.Version(obj.version), reverse=True
        )

        context = self.get_serializer_context()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_list_serializer(page, many=True, context=context)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_list_serializer(queryset, many=True, context=context)
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
        distro_content = self._distro_content

        return CollectionVersion.objects.select_related().filter(pk__in=distro_content)

    @extend_schema(
        responses={202: list_serializer_class},
    )
    def list(self, request, *args, **kwargs):
        """
        Returns paginated CollectionVersions list.
        """
        queryset = self.get_queryset().iterator()

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


class CollectionImportViewSet(
    ExceptionHandlerMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
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


class ClientConfigurationView(views.APIView):
    """Return configurations for the ansible-galaxy client."""

    DEFAULT_ACCESS_POLICY = _PERMISSIVE_ACCESS_POLICY

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
