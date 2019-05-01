import re

from django.shortcuts import get_object_or_404
from rest_framework import generics, response, views

from pulpcore.app.models import Distribution

from pulp_ansible.app.models import Role

from .serializers import GalaxyRoleSerializer, GalaxyRoleVersionSerializer


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
            'available_versions': {'v1': '/api/v1/'},
            'current_version': 'v1'
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
        distro = get_object_or_404(Distribution, base_path=self.kwargs['path'])
        distro_content = distro.publication.repository_version.content
        roles = Role.objects.distinct('namespace', 'name').filter(pk__in=distro_content)

        namespace = self.request.query_params.get('owner__username', None)
        if namespace:
            roles = roles.filter(namespace=namespace)
        name = self.request.query_params.get('name', None)
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
        distro = get_object_or_404(Distribution, base_path=self.kwargs['path'])
        distro_content = distro.publication.repository_version.content
        namespace, name = re.split(r'\.', self.kwargs['role_pk'])
        versions = Role.objects.filter(pk__in=distro_content, name=name, namespace=namespace)
        for version in versions:
            version.distro_path = distro.base_path
        return versions
