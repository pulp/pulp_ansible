import re

from django.conf import settings
from django.shortcuts import get_object_or_404, HttpResponse
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


class DistributionMixin:
    """
    Mixin for getting the content for the view.
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

        repo_version = distro.repository.latest_version() if distro.repository else None
        self.pulp_context = {path: repo_version}
        return repo_version

    @property
    def _distro_content(self):
        """Returns distribution content."""
        repo_version = self._repository_version
        if repo_version is None:
            return self.model.objects.none()

        return repo_version.content

    def get_serializer_context(self):
        """Inserts distribution path to a serializer context."""
        context = super().get_serializer_context()
        if "path" in self.kwargs:
            context["path"] = self.kwargs["path"]
        return context


class GalaxyVersionView(views.APIView):
    """
    APIView for Galaxy versions.
    """

    authentication_classes = []
    permission_classes = []

    v3_only = False

    def get(self, request, **kwargs):
        """
        Return a response to the "GET" action.
        """
        available_versions = {"v1": "v1/", "v2": "v2/", "v3": "v3/"}
        if self.v3_only:
            available_versions = {"v3": "v3/"}

        api_info = {
            "available_versions": available_versions,
            "current_version": "v3",
        }

        return response.Response(api_info)


class RoleList(DistributionMixin, generics.ListAPIView):
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
        roles = Role.objects.distinct("namespace", "name").filter(pk__in=self._distro_content)

        namespace = self.request.query_params.get("owner__username", None)
        if namespace:
            roles = roles.filter(namespace__iexact=namespace)
        name = self.request.query_params.get("name", None)
        if name:
            roles = roles.filter(name__iexact=name)

        return roles


class RoleVersionList(DistributionMixin, generics.ListAPIView):
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
        namespace, name = re.split(r"\.", self.kwargs["role_pk"])
        versions = Role.objects.filter(pk__in=self._distro_content, name=name, namespace=namespace)
        return versions


class GalaxyCollectionDetailView(DistributionMixin, generics.RetrieveAPIView):
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
        # This seems wrong, no repository scoping occurring
        collection = get_object_or_404(Collection, namespace=namespace, name=name)
        return response.Response(GalaxyCollectionSerializer(collection).data)


class GalaxyCollectionView(DistributionMixin, UploadGalaxyCollectionMixin, generics.ListAPIView):
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
        return Collection.objects.filter(versions__pk__in=self._distro_content).distinct()

    def post(self, request, path):
        """
        Queues a task that creates a new Collection from an uploaded artifact.
        """
        distro = get_object_or_404(AnsibleDistribution, base_path=path)
        if not distro.repository and not distro.repository_version:
            return HttpResponse(status=400, reason="Distribution has no repository.")

        serializer = GalaxyCollectionUploadSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        temp_file = PulpTemporaryFile.init_and_validate(serializer.validated_data["file"])
        temp_file.save()

        async_result = self._dispatch_import_collection_task(temp_file.pk, distro.repository)
        return OperationPostponedResponse(async_result, request)


class GalaxyCollectionVersionList(DistributionMixin, generics.ListAPIView):
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
        collection = get_object_or_404(
            Collection, namespace=self.kwargs["namespace"], name=self.kwargs["name"]
        )
        versions = collection.versions.filter(pk__in=self._distro_content)

        return versions


class GalaxyCollectionVersionDetail(DistributionMixin, views.APIView):
    """
    APIView for Galaxy Collections Detail view.
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request, path, namespace, name, version):
        """
        Return a response to the "GET" action.
        """
        version = CollectionVersion.objects.get(
            collection__namespace=namespace, collection__name=name, version=version
        )

        get_object_or_404(
            ContentArtifact, content__in=self._distro_content, relative_path=version.relative_path
        )

        download_url = "{content_hostname}/{base_path}/{relative_path}".format(
            content_hostname=settings.ANSIBLE_CONTENT_HOSTNAME,
            base_path=self.kwargs["path"],
            relative_path=version.relative_path,
        )

        data = GalaxyCollectionVersionSerializer(version).data
        data["download_url"] = download_url
        return response.Response(data)
