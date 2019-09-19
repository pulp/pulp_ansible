import semantic_version

from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework import mixins
from rest_framework.response import Response
from rest_framework import viewsets

from pulpcore.plugin.models import Content, ContentArtifact, RepositoryVersion

from pulp_ansible.app.galaxy.v3.exceptions import ExceptionHandlerMixin
from pulp_ansible.app.galaxy.v3.serializers import (
    CollectionSerializer,
    CollectionVersionSerializer,
    CollectionVersionListSerializer,
)
from pulp_ansible.app.models import AnsibleDistribution, CollectionVersion, CollectionImport
from pulp_ansible.app.serializers import CollectionImportDetailSerializer


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
            repo_version = RepositoryVersion.latest(distro.repository)
            if repo_version is None:
                return Content.objects.none()
            else:
                return repo_version.content

    def get_serializer_context(self):
        """Inserts distribution path to a serializer context."""
        context = super().get_serializer_context()
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


class CollectionVersionViewSet(
    ExceptionHandlerMixin, AnsibleDistributionMixin, viewsets.GenericViewSet
):
    """
    ViewSet for CollectionVersions.
    """

    authentication_classes = []
    permission_classes = []

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
        queryset = self.get_queryset()
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

    @action(methods=["PUT", "DELETE"], detail=True, url_path="certified")
    def set_certified(self, request, *args, **kwargs):
        """
        Set collection version certified status.
        """
        obj = self.get_object()
        obj.is_certified = request.method == "PUT"
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
