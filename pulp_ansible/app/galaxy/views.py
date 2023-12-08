import re

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, response, views

from pulp_ansible.app.models import AnsibleDistribution, Role

from .serializers import GalaxyRoleSerializer, GalaxyRoleVersionSerializer


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
        available_versions = {"v1": "v1/", "v3": "v3/"}
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


@extend_schema_view(get=extend_schema(operation_id="api_v1_roles_versions_list"))
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
