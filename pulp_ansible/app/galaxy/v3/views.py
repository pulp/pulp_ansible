from datetime import datetime
from gettext import gettext as _
import semantic_version

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import action
from rest_framework import mixins
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework import viewsets

from pulpcore.plugin.exceptions import DigestValidationError
from pulpcore.plugin.models import PulpTemporaryFile, Content, ContentArtifact
from pulpcore.plugin.serializers import AsyncOperationResponseSerializer
from rest_framework.reverse import reverse

from pulp_ansible.app.galaxy.v3.exceptions import ExceptionHandlerMixin
from pulp_ansible.app.galaxy.v3.serializers import (
    CollectionSerializer,
    CollectionVersionSerializer,
    CollectionVersionDocsSerializer,
    CollectionVersionListSerializer,
)
from pulp_ansible.app.models import AnsibleDistribution, CollectionVersion, CollectionImport
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

    @staticmethod
    def get_distro_content(path):
        """Returns distribution content."""
        distro = get_object_or_404(AnsibleDistribution, base_path=path)
        if distro.repository_version:
            return distro.repository_version.content
        else:
            repo_version = distro.repository.latest_version()
            if repo_version is None:
                return Content.objects.none()
            else:
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

    def get_queryset(self):
        """
        Returns a CollectionVersions queryset for specified distribution.
        """
        distro_content = self.get_distro_content(self.kwargs["path"])

        versions = CollectionVersion.objects.filter(pk__in=distro_content).values_list(
            "collection_id",
            "version",
        )

        collection_versions = {}
        for collection_id, version in versions:
            value = collection_versions.get(str(collection_id))
            if not value or semantic_version.Version(version) > semantic_version.Version(value):
                collection_versions[str(collection_id)] = version

        query_params = Q()
        for collection_id, version in collection_versions.items():
            query_params |= Q(collection_id=collection_id, version=version)

        collections = CollectionVersion.objects.select_related("collection").filter(query_params)
        return collections

    def get_object(self):
        """
        Returns a Collection object.
        """
        queryset = self.filter_queryset(self.get_queryset())

        return get_object_or_404(
            queryset, namespace=self.kwargs["namespace"], name=self.kwargs["name"]
        )

    def update(self, request, *args, **kwargs):
        """
        Update a Collection object.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CollectionUploadViewSet(
    ExceptionHandlerMixin, viewsets.GenericViewSet, UploadGalaxyCollectionMixin
):
    """
    ViewSet for Collection Uploads.
    """

    authentication_classes = []
    permission_classes = []
    serializer_class = CollectionSerializer

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

    @action(methods=["PUT"], detail=True, url_path="certified")
    def set_certified(self, request, *args, **kwargs):
        """
        Set collection version certified status.
        """
        obj = self.get_object()
        obj.certification = request.data["certification"]
        obj.save()
        return Response({})


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
