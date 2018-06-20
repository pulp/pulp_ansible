from django.shortcuts import get_object_or_404
from rest_framework import generics, response, views

from pulpcore.app.models import Distribution

from pulp_ansible.app.models import AnsibleRole, AnsibleRoleVersion

from .serializers import GalaxyAnsibleRoleSerializer, GalaxyAnsibleRoleVersionSerializer


class AnsibleGalaxyVersionView(views.APIView):
    """
    APIView for Ansible Galaxy versions.
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


class AnsibleRoleList(generics.ListAPIView):
    """
    APIView for Ansible Roles.
    """

    model = AnsibleRole
    serializer_class = GalaxyAnsibleRoleSerializer
    authentication_classes = []
    permission_classes = []

    def get_queryset(self):
        """
        Get the list of items for this view.
        """
        distro = get_object_or_404(Distribution, base_path=self.kwargs['path'])
        distro_content = distro.publication.repository_version.content
        versions = AnsibleRoleVersion.objects.filter(pk__in=distro_content)
        roles = AnsibleRole.objects.filter(pk__in=versions.values_list('role_id', flat=True))

        namespace = self.request.query_params.get('owner__username', None)
        if namespace:
            roles = roles.filter(namespace=namespace)
        name = self.request.query_params.get('name', None)
        if name:
            roles = roles.filter(name=name)

        return roles


class AnsibleRoleVersionList(generics.ListAPIView):
    """
    APIView for Ansible Role Versions.
    """

    model = AnsibleRoleVersion
    serializer_class = GalaxyAnsibleRoleVersionSerializer
    authentication_classes = []
    permission_classes = []

    def get_queryset(self):
        """
        Get the list of items for this view.
        """
        distro = get_object_or_404(Distribution, base_path=self.kwargs['path'])
        distro_content = distro.publication.repository_version.content
        role = get_object_or_404(AnsibleRole, pk=self.kwargs['role_pk'])
        versions = AnsibleRoleVersion.objects.filter(pk__in=distro_content, role__pk=role.pk)
        for version in versions:
            version.distro_path = distro.base_path
        return versions
