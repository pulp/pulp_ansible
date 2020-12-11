from collections import defaultdict, namedtuple
from datetime import datetime
from gettext import gettext as _
import semantic_version

from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404
from django.utils.datastructures import MultiValueDictKeyError
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework import viewsets

from pulpcore.plugin.exceptions import DigestValidationError
from pulpcore.plugin.models import PulpTemporaryFile, Content, ContentArtifact
from pulpcore.plugin.serializers import AsyncOperationResponseSerializer

from pulp_ansible.app.galaxy.v3.exceptions import ExceptionHandlerMixin
from pulp_ansible.app.galaxy.v3.serializers import (
    CollectionSerializer,
    CollectionVersionSerializer,
    CollectionVersionDocsSerializer,
    CollectionVersionListSerializer,
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


CollectionTuple = namedtuple("CollectionTuple", ["namespace", "name", "version", "pulp_created"])


class AnsibleDistributionMixin:
    """
    A mixin for ViewSets that use AnsibleDistribution.
    """

    @staticmethod
    def get_repository_version(path):
        """Returns repository version."""
        distro = get_object_or_404(AnsibleDistribution, base_path=path)
        if distro.repository_version:
            return distro.repository_version

        return distro.repository.latest_version()

    @staticmethod
    def get_distro_content(path):
        """Returns distribution content."""
        repo_version = AnsibleDistributionMixin.get_repository_version(path)
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
        distro_content = self.get_distro_content(self.kwargs["path"])

        collections = CollectionVersion.objects.select_related("collection").filter(
            pk__in=distro_content, namespace=self.kwargs["namespace"], name=self.kwargs["name"]
        )
        return collections

    def retrieve(self, request, *args, **kwargs):
        """
        Returns a CollectionVersion object.
        """
        instance = self.get_object()
        artifact = ContentArtifact.objects.get(content=instance)

        context = self.get_serializer_context()
        context["content_artifact"] = artifact

        serializer = self.get_serializer_class()(instance, context=context)

        return Response(serializer.data)


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
    pagination_class = LimitOffsetPagination

    def filter_queryset(self, queryset):
        """
        Filter Repository related fields.
        """
        queryset = super().filter_queryset(queryset)

        try:
            user_deprecated_value = self.request.query_params["deprecated"]
        except MultiValueDictKeyError:
            pass
        else:
            if user_deprecated_value.lower() in ["true", "yes", "1"]:
                queryset = queryset.filter(deprecated=True)
            elif user_deprecated_value.lower() in ["false", "no", "0"]:
                queryset = queryset.filter(deprecated=False)
            else:
                raise ValidationError("Cannot parse value of `deprecated` GET parameter")

        return queryset

    def get_queryset(self):
        """
        Returns a Collections queryset for specified distribution.
        """
        repo_version = self.get_repository_version(self.kwargs["path"])
        deprecated_query = AnsibleCollectionDeprecated.objects.filter(
            collection=OuterRef("pk"), repository_version=repo_version
        )
        collections = Collection.objects.filter(versions__in=repo_version.content).distinct()
        collections = collections.annotate(deprecated=Exists(deprecated_query))

        versions_qs = CollectionVersion.objects.filter(pk__in=repo_version.content).values_list(
            "collection_id",
            "namespace",
            "name",
            "version",
            "pulp_created",
        )

        highest_versions = defaultdict(
            lambda: CollectionTuple(None, None, semantic_version.Version("0.0.0"), None)
        )
        lowest_versions = defaultdict(
            lambda: CollectionTuple(None, None, semantic_version.Version("100000000000.0.0"), None)
        )
        for collection_id, namespace, name, version, pulp_created in versions_qs:
            version_to_consider = semantic_version.Version(version)
            collection_tuple = CollectionTuple(namespace, name, version_to_consider, pulp_created)
            if version_to_consider > highest_versions[collection_id].version:
                highest_versions[collection_id] = collection_tuple
            if version_to_consider < lowest_versions[collection_id].version:
                lowest_versions[collection_id] = collection_tuple

        self.highest_versions_context = highest_versions  # needed by get__serializer_context
        self.lowest_versions_context = lowest_versions  # needed by get__serializer_context
        return collections

    def get_object(self):
        """
        Returns a Collection object.
        """
        queryset = self.filter_queryset(self.get_queryset())
        return get_object_or_404(
            queryset, namespace=self.kwargs["namespace"], name=self.kwargs["name"]
        )

    def get_serializer_context(self, *args, **kwargs):
        """
        Return the serializer context.

        This uses super() but also adds in the "highest_versions" data from get_queryset()
        """
        super_data = super().get_serializer_context()
        super_data["highest_versions"] = self.highest_versions_context
        super_data["lowest_versions"] = self.lowest_versions_context
        return super_data

    def update(self, request, *args, **kwargs):
        """
        Update a Collection object.
        """
        repo_version = self.get_repository_version(self.kwargs["path"])
        collection = self.get_object()
        serializer = self.get_serializer(collection, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        deprecated_value = serializer.validated_data["deprecated"]
        if deprecated_value:
            AnsibleCollectionDeprecated.objects.get_or_create(
                repository_version=repo_version, collection=collection
            )
        else:
            AnsibleCollectionDeprecated.objects.filter(
                repository_version=repo_version, collection=collection
            ).delete()
        return Response(serializer.data)


class CollectionUploadViewSet(
    ExceptionHandlerMixin, viewsets.GenericViewSet, UploadGalaxyCollectionMixin
):
    """
    ViewSet for Collection Uploads.
    """

    authentication_classes = []
    permission_classes = []
    serializer_class = CollectionOneShotSerializer

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
        CollectionImport.objects.create(task_id=async_result.id)

        data = {
            "task": reverse(
                "collection-imports-detail",
                kwargs={"path": path, "pk": async_result.id},
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
    filterset_class = CollectionVersionFilter
    pagination_class = LimitOffsetPagination

    lookup_field = "version"

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
            serializer = CollectionVersionListSerializer(page, many=True, context=context)
            return self.get_paginated_response(serializer.data)

        serializer = CollectionVersionListSerializer(queryset, many=True, context=context)
        return Response(serializer.data)


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
