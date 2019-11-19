from datetime import datetime
from gettext import gettext as _
import semantic_version

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import action
from rest_framework import mixins
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework import viewsets

from pulpcore.plugin.exceptions import DigestValidationError
from pulpcore.plugin.models import Artifact, Content, ContentArtifact
from pulpcore.plugin.serializers import AsyncOperationResponseSerializer
from pulpcore.plugin.tasking import enqueue_with_reservation
from rest_framework.reverse import reverse

from pulp_ansible.app.galaxy.v3.exceptions import ExceptionHandlerMixin
from pulp_ansible.app.galaxy.v3.serializers import (
    CollectionSerializer,
    CollectionVersionSerializer,
    CollectionVersionListSerializer,
)
from pulp_ansible.app.models import AnsibleDistribution, CollectionVersion, CollectionImport
from pulp_ansible.app.serializers import (
    CollectionOneShotSerializer,
    CollectionImportDetailSerializer,
)
from pulp_ansible.app.tasks.collections import import_collection

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

    def get_queryset(self):
        """
        Returns a CollectionVersions queryset for specified distribution.
        """
        distro_content = self.get_distro_content(self.kwargs["path"])

        collections = CollectionVersion.objects.select_related("collection").filter(
            pk__in=distro_content, is_highest=True
        )
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


class CollectionUploadViewSet(ExceptionHandlerMixin, viewsets.GenericViewSet):
    """
    ViewSet for Collection Uploads.
    """

    authentication_classes = []
    permission_classes = []
    serializer_class = CollectionSerializer

    @swagger_auto_schema(
        operation_description="Create an artifact and trigger an asynchronous task to create "
        "Collection content from it.",
        operation_summary="Upload a collection",
        request_body=CollectionOneShotSerializer,
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
            artifact = Artifact.init_and_validate(
                serializer.validated_data["file"], expected_digests=expected_digests
            )
        except DigestValidationError:
            raise serializers.ValidationError(
                _("The provided sha256 value does not match the sha256 of the uploaded file.")
            )

        try:
            artifact.save()
        except IntegrityError:
            raise serializers.ValidationError(_("Artifact already exists."))

        locks = [str(artifact.pk)]
        kwargs = {"artifact_pk": artifact.pk}

        if serializer.validated_data["expected_namespace"]:
            kwargs["expected_namespace"] = serializer.validated_data["expected_namespace"]

        if serializer.validated_data["expected_name"]:
            kwargs["expected_name"] = serializer.validated_data["expected_name"]

        if serializer.validated_data["expected_version"]:
            kwargs["expected_version"] = serializer.validated_data["expected_version"]

        if distro.repository:
            locks.append(distro.repository)
            kwargs["repository_pk"] = distro.repository.pk

        async_result = enqueue_with_reservation(import_collection, locks, kwargs=kwargs)
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
    ExceptionHandlerMixin, AnsibleDistributionMixin, viewsets.GenericViewSet
):
    """
    ViewSet for CollectionVersions.
    """

    authentication_classes = []
    permission_classes = []
    serializer_class = CollectionVersionSerializer
    filterset_class = CollectionVersionFilter

    lookup_field = "version"

    def get_queryset(self):
        """
        Returns a CollectionVersions queryset for specified distribution.
        """
        distro_content = self.get_distro_content(self.kwargs["path"])

        collections = CollectionVersion.objects.select_related("collection").filter(
            pk__in=distro_content, namespace=self.kwargs["namespace"], name=self.kwargs["name"]
        )
        return collections

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

    def retrieve(self, request, *args, **kwargs):
        """
        Returns a CollectionVersion object.
        """
        instance = self.get_object()
        artifact = ContentArtifact.objects.get(content=instance)

        context = self.get_serializer_context()
        context["content_artifact"] = artifact

        serializer = CollectionVersionSerializer(instance, context=context)

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


class CollectionImportViewSet(
    ExceptionHandlerMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """
    ViewSet for CollectionImports.
    """

    queryset = CollectionImport.objects.prefetch_related("task").all()
    serializer_class = CollectionImportDetailSerializer

    since_filter = openapi.Parameter(
        "since",
        openapi.IN_QUERY,
        type=openapi.TYPE_STRING,
        format=openapi.FORMAT_DATETIME,
        description="Filter messages since a given timestamp",
    )

    @swagger_auto_schema(manual_parameters=[since_filter])
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
