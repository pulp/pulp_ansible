import re

from django.shortcuts import get_object_or_404
from rest_framework import generics, response, views

from pulpcore.app.models import Artifact, Distribution
from pulpcore.app.response import OperationPostponedResponse
from pulpcore.tasking.tasks import enqueue_with_reservation

from pulp_ansible.app.galaxy.tasks import import_collection
from pulp_ansible.app.models import Collection, Role

from .serializers import (
    GalaxyCollectionUploadSerializer, GalaxyRoleSerializer,
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


class GalaxyCollectionView(views.APIView):
    """
    ViewSet for Collection models.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        """
        Queues a task that publishes a new Ansible Publication.
        """
        serializer = GalaxyCollectionUploadSerializer(data=request.data,
                                                      context={'request': request})
        serializer.is_valid(raise_exception=True)

        expected_digests = {'sha256': serializer.validated_data['sha256']}
        artifact = Artifact.init_and_validate(serializer.validated_data['file'],
                                              expected_digests=expected_digests)
        artifact.save()

        async_result = enqueue_with_reservation(
            import_collection, [str(artifact.pk)],
            kwargs={
                'artifact_pk': artifact.pk,
            })
        return OperationPostponedResponse(async_result, request)
