import re

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics, response, views

from pulpcore.app.models import Artifact, RepositoryVersion
from pulpcore.app.response import OperationPostponedResponse
from pulpcore.tasking.tasks import enqueue_with_reservation
from pulpcore.plugin.models import ContentArtifact

from pulp_ansible.app.tasks.collections import import_collection
from pulp_ansible.app.models import AnsibleDistribution, Collection, CollectionVersion, Role

from .serializers import (
    GalaxyCollectionVersionSerializer,
    GalaxyCollectionUploadSerializer,
    GalaxyRoleSerializer,
    GalaxyRoleVersionSerializer,
)


class GalaxyVersionView(views.APIView):
    """
    APIView for Galaxy versions.
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request, path):
        """
        Return a response to the "GET" action.
        """
        api_info = {"available_versions": {"v1": "/api/v1/"}, "current_version": "v1"}

        return response.Response(api_info)


class RoleList(generics.ListAPIView):
    """
    APIView for Roles.
    """

    model = Role
    serializer_class = GalaxyRoleSerializer
    authentication_classes = []
    permission_classes = []

    def get_queryset(self):
        """
        Get the list of items for this view.
        """
        distro = get_object_or_404(AnsibleDistribution, base_path=self.kwargs["path"])

        if distro.repository_version:
            distro_content = distro.repository_version.content
        else:
            distro_content = RepositoryVersion.latest(distro.repository).content
        roles = Role.objects.distinct("namespace", "name").filter(pk__in=distro_content)

        namespace = self.request.query_params.get("owner__username", None)
        if namespace:
            roles = roles.filter(namespace=namespace)
        name = self.request.query_params.get("name", None)
        if name:
            roles = roles.filter(name=name)

        return roles


class RoleVersionList(generics.ListAPIView):
    """
    APIView for Role Versions.
    """

    model = Role
    serializer_class = GalaxyRoleVersionSerializer
    authentication_classes = []
    permission_classes = []

    def get_queryset(self):
        """
        Get the list of items for this view.
        """
        distro = get_object_or_404(AnsibleDistribution, base_path=self.kwargs["path"])

        if distro.repository_version:
            distro_content = distro.repository_version.content
        else:
            distro_content = RepositoryVersion.latest(distro.repository).content
        namespace, name = re.split(r"\.", self.kwargs["role_pk"])
        versions = Role.objects.filter(pk__in=distro_content, name=name, namespace=namespace)
        for version in versions:
            version.distro_path = distro.base_path
        return versions


class GalaxyCollectionDetailView(generics.RetrieveAPIView):
    """
    View for a Collection Detail.
    """

    model = CollectionVersion
    serializer_class = GalaxyCollectionVersionSerializer
    authentication_classes = []
    permission_classes = []

    def get(self, request, path=None, namespace=None, name=None):
        """
        Get the detail view of a Collection.
        """
        version = get_object_or_404(
            CollectionVersion, collection__namespace=namespace, collection__name=name
        )
        version.path = path
        return response.Response(GalaxyCollectionVersionSerializer(version).data)


class GalaxyCollectionView(views.APIView):
    """
    View for Collection models.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        """
        Queues a task that creates a new Collection from an uploaded artifact.
        """
        serializer = GalaxyCollectionUploadSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        expected_digests = {"sha256": serializer.validated_data["sha256"]}
        artifact = Artifact.init_and_validate(
            serializer.validated_data["file"], expected_digests=expected_digests
        )
        artifact.save()

        async_result = enqueue_with_reservation(
            import_collection, [str(artifact.pk)], kwargs={"artifact_pk": artifact.pk}
        )
        return OperationPostponedResponse(async_result, request)


class GalaxyCollectionVersionList(generics.ListAPIView):
    """
    APIView for Collections by namespace/name.
    """

    model = CollectionVersion
    serializer_class = GalaxyCollectionVersionSerializer
    authentication_classes = []
    permission_classes = []

    def get_queryset(self):
        """
        Get the list of items for this view.
        """
        distro = get_object_or_404(AnsibleDistribution, base_path=self.kwargs["path"])
        if distro.repository_version:
            distro_content = distro.repository_version.content
        else:
            distro_content = RepositoryVersion.latest(distro.repository).content

        collection = get_object_or_404(
            Collection, namespace=self.kwargs["namespace"], name=self.kwargs["name"]
        )
        versions = collection.versions.filter(pk__in=distro_content)

        for c in versions:
            c.path = self.kwargs["path"]  # annotation needed by the serializer

        return versions


class GalaxyCollectionVersionDetail(views.APIView):
    """
    APIView for Galaxy Collections Detail view.
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request, path, namespace, name, version):
        """
        Return a response to the "GET" action.
        """
        distro = get_object_or_404(AnsibleDistribution, base_path=self.kwargs["path"])
        if distro.repository_version:
            distro_content = distro.repository_version.content
        else:
            distro_content = RepositoryVersion.latest(distro.repository).content

        version = CollectionVersion.objects.get(
            collection__namespace=namespace, collection__name=name, version=version
        )

        get_object_or_404(
            ContentArtifact, content__in=distro_content, relative_path=version.relative_path
        )

        download_url = "{content_hostname}/{base_path}/{relative_path}".format(
            content_hostname=settings.ANSIBLE_CONTENT_HOSTNAME,
            base_path=distro.base_path,
            relative_path=version.relative_path,
        )
        to_return = {"download_url": download_url}
        return response.Response(to_return)
