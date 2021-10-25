import re

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics, pagination, response, views

from pulpcore.plugin.models import PulpTemporaryFile
from pulpcore.plugin.viewsets import OperationPostponedResponse
from pulpcore.plugin.models import ContentArtifact

from pulp_ansible.app.galaxy.mixins import UploadGalaxyCollectionMixin
from pulp_ansible.app.models import AnsibleDistribution, Collection, CollectionVersion, Role

from .serializers import (
    GalaxyCollectionSerializer,
    GalaxyCollectionUploadSerializer,
    GalaxyCollectionVersionSerializer,
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
        api_info = {
            "available_versions": {"v1": "v1/", "v2": "v2/", "v3": "v3/"},
            "current_version": "v3",
        }

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
            distro_content = distro.repository.latest_version().content
        roles = Role.objects.distinct("namespace", "name").filter(pk__in=distro_content)

        namespace = self.request.query_params.get("owner__username", None)
        if namespace:
            roles = roles.filter(namespace__iexact=namespace)
        name = self.request.query_params.get("name", None)
        if name:
            roles = roles.filter(name__iexact=name)

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
            distro_content = distro.repository.latest_version().content
        namespace, name = re.split(r"\.", self.kwargs["role_pk"])
        versions = Role.objects.filter(pk__in=distro_content, name=name, namespace=namespace)
        for version in versions:
            version.distro_path = distro.base_path
        return versions


class GalaxyCollectionDetailView(generics.RetrieveAPIView):
    """
    View for a Collection Detail.
    """

    model = Collection
    serializer_class = GalaxyCollectionSerializer
    authentication_classes = []
    permission_classes = []

    def get(self, request, path=None, namespace=None, name=None):
        """
        Get the detail view of a Collection.
        """
        collection = get_object_or_404(Collection, namespace=namespace, name=name)
        collection.path = path
        return response.Response(GalaxyCollectionSerializer(collection).data)


class GalaxyCollectionView(generics.ListAPIView, UploadGalaxyCollectionMixin):
    """
    View for Collection models.
    """

    model = Collection
    serializer_class = GalaxyCollectionSerializer
    authentication_classes = []
    permission_classes = []
    pagination_class = pagination.PageNumberPagination

    def get_queryset(self):
        """
        Get the list of Collections for this view.
        """
        distro = get_object_or_404(AnsibleDistribution, base_path=self.kwargs["path"])
        if distro.repository_version:
            distro_content = distro.repository_version.content
        else:
            distro_content = distro.repository.latest_version().content

        collections = Collection.objects.filter(versions__pk__in=distro_content).distinct()

        for c in collections:
            c.path = self.kwargs["path"]  # annotation needed by the serializer

        return collections

    def post(self, request, path):
        """
        Queues a task that creates a new Collection from an uploaded artifact.
        """
        distro = get_object_or_404(AnsibleDistribution, base_path=path)
        serializer = GalaxyCollectionUploadSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        temp_file = PulpTemporaryFile.init_and_validate(serializer.validated_data["file"])
        temp_file.save()

        async_result = self._dispatch_import_collection_task(temp_file.pk, distro.repository)
        return OperationPostponedResponse(async_result, request)


class GalaxyCollectionVersionList(generics.ListAPIView):
    """
    APIView for Collections by namespace/name.
    """

    model = CollectionVersion
    serializer_class = GalaxyCollectionVersionSerializer
    pagination_class = pagination.PageNumberPagination
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
            distro_content = distro.repository.latest_version().content

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
            distro_content = distro.repository.latest_version().content

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

        version.path = path
        data = GalaxyCollectionVersionSerializer(version).data
        data["download_url"] = download_url
        return response.Response(data)
