from datetime import datetime
from gettext import gettext as _
import semantic_version

from django.contrib.postgres.aggregates import ArrayAgg
from django.db import DatabaseError
from django.db.models import F, Q
from django.db.models.expressions import Window
from django.db.models.functions.window import FirstValue
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from django_filters import filters
from drf_spectacular.utils import OpenApiParameter, extend_schema
from jinja2 import Template
from rest_framework import mixins
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework import viewsets

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
)
from pulp_ansible.app.models import (
    AnsibleCollectionDeprecated,
    AnsibleDistribution,
    Collection,
    CollectionVersion,
    CollectionImport,
)
from pulp_ansible.app.serializers import (
    CollectionOneShotSerializer,
    CollectionImportDetailSerializer,
)

from pulp_ansible.app.galaxy.mixins import UploadGalaxyCollectionMixin
from pulp_ansible.app.galaxy.v3.pagination import LimitOffsetPagination
from pulp_ansible.app.viewsets import CollectionVersionFilter


class AnsibleDistributionMixin:
    """
    A mixin for ViewSets that use AnsibleDistribution.
    """

    @property
    def _repository_version(self):
        """Returns repository version."""
        path = self.kwargs["path"]
        context = getattr(self, "pulp_context", None)
        if context and context.get(path, None):
            return self.pulp_context[path]

        distro = get_object_or_404(AnsibleDistribution, base_path=path)
        if distro.repository_version:
            self.pulp_context = {path: distro.repository_version}
            return distro.repository_version

        repo_version = distro.repository.latest_version()
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

    authentication_classes = []
    permission_classes = []
    serializer_class = CollectionSerializer
    filterset_class = CollectionFilter
    pagination_class = LimitOffsetPagination

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
            queryset.distinct("versions__collection_id").only("pk")
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


class UnpaginatedCollectionViewSet(CollectionViewSet):
    """Unpaginated ViewSet for Collections."""

    pagination_class = None


class CollectionUploadViewSet(
    ExceptionHandlerMixin, viewsets.GenericViewSet, UploadGalaxyCollectionMixin
):
    """
    ViewSet for Collection Uploads.
    """

    authentication_classes = []
    permission_classes = []
    serializer_class = CollectionOneShotSerializer
    pulp_tag_name = "Pulp_Ansible: Artifacts Collections V3"

    @extend_schema(
        description="Create an artifact and trigger an asynchronous task to create "
        "Collection content from it.",
        summary="Upload a collection",
        request=CollectionOneShotSerializer,
        responses={202: AsyncOperationResponseSerializer},
    )
    def create(self, request, path):
        """
        Dispatch a Collection creation task.
        """
        distro = get_object_or_404(AnsibleDistribution, base_path=path)
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
                "collection-imports-detail",
                kwargs={"path": path, "pk": async_result.pk},
                request=None,
            )
        }
        return Response(data, status=http_status.HTTP_202_ACCEPTED)


class CollectionVersionViewSet(
    CollectionVersionRetrieveMixin,
    ExceptionHandlerMixin,
    AnsibleDistributionMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for CollectionVersions.
    """

    authentication_classes = []
    permission_classes = []
    serializer_class = CollectionVersionSerializer
    list_serializer_class = CollectionVersionListSerializer
    filterset_class = CollectionVersionFilter
    pagination_class = LimitOffsetPagination

    lookup_field = "version"

    def get_list_serializer(self, *args, **kwargs):
        """
        Return the list serializer instance.
        """
        kwargs.setdefault("context", self.get_serializer_context)
        return self.list_serializer_class(*args, **kwargs)

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


class UnpaginatedCollectionVersionViewSet(CollectionVersionViewSet):
    """Unpaginated ViewSet for CollectionVersions."""

    serializer_class = UnpaginatedCollectionVersionSerializer
    pagination_class = None

    def get_queryset(self):
        """
        Returns a CollectionVersions queryset for specified distribution.
        """
        distro_content = self._distro_content

        return CollectionVersion.objects.select_related().filter(pk__in=distro_content)

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
        serialized_map = (self.get_serializer(x, context=context).data for x in queryset)
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

    authentication_classes = []
    permission_classes = []
    serializer_class = CollectionVersionDocsSerializer

    lookup_field = "version"


class CollectionImportViewSet(
    ExceptionHandlerMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """
    ViewSet for CollectionImports.
    """

    queryset = CollectionImport.objects.prefetch_related("task").all()
    serializer_class = CollectionImportDetailSerializer

    since_filter = OpenApiParameter(
        name="since",
        location=OpenApiParameter.QUERY,
        type=str,
        # format=openapi.FORMAT_DATETIME,
        description="Filter messages since a given timestamp",
    )

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

    authentication_classes = []
    permission_classes = []
    serializer_class = RepoMetadataSerializer

    def get_object(self):
        """
        Returns a RepositoryVersion object.
        """
        return self._repository_version
