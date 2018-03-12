from gettext import gettext as _

from django_filters.rest_framework import filterset
from rest_framework.decorators import detail_route
from rest_framework import serializers

from pulpcore.plugin.models import Repository, RepositoryVersion
from pulpcore.plugin.viewsets import (
    ContentViewSet,
    ImporterViewSet,
    OperationPostponedResponse,
    PublisherViewSet)

from . import tasks
from .models import AnsibleRoleVersion, AnsibleImporter, AnsiblePublisher
from .serializers import AnsibleRoleVersionSerializer, AnsibleImporterSerializer, AnsiblePublisherSerializer


class AnsibleRoleVersionFilter(filterset.FilterSet):
    class Meta:
        model = AnsibleRoleVersion
        fields = [
            'version',
            'role__name',
            'role__namespace'
        ]


class AnsibleRoleVersionViewSet(ContentViewSet):
    endpoint_name = 'ansible'
    queryset = AnsibleRoleVersion.objects.all()
    serializer_class = AnsibleRoleVersionSerializer
    filter_class = AnsibleRoleVersionFilter


class AnsibleImporterViewSet(ImporterViewSet):
    endpoint_name = 'ansible'
    queryset = AnsibleImporter.objects.all()
    serializer_class = AnsibleImporterSerializer

    @detail_route(methods=('post',))
    def sync(self, request, pk):
        importer = self.get_object()
        repository = self.get_resource(request.data['repository'], Repository)
        if not importer.feed_url:
            raise serializers.ValidationError(detail=_('A feed_url must be specified.'))
        result = tasks.synchronize.apply_async_with_reservation(
            [repository, importer],
            kwargs={
                'importer_pk': importer.pk,
                'repository_pk': repository.pk
            }
        )
        return OperationPostponedResponse([result], request)


class AnsiblePublisherViewSet(PublisherViewSet):
    endpoint_name = 'ansible'
    queryset = AnsiblePublisher.objects.all()
    serializer_class = AnsiblePublisherSerializer

    @detail_route(methods=('post',))
    def publish(self, request, pk):
        publisher = self.get_object()
        repository = None
        repository_version = None
        if 'repository' not in request.data and 'repository_version' not in request.data:
            raise serializers.ValidationError("Either the 'repository' or 'repository_version' "
                                              "need to be specified.")

        if 'repository' in request.data and request.data['repository']:
            repository = self.get_resource(request.data['repository'], Repository)

        if 'repository_version' in request.data and request.data['repository_version']:
            repository_version = self.get_resource(request.data['repository_version'],
                                                   RepositoryVersion)

        if repository and repository_version:
            raise serializers.ValidationError("Either the 'repository' or 'repository_version' "
                                              "can be specified - not both.")

        if not repository_version:
            repository_version = RepositoryVersion.latest(repository)

        result = tasks.publish.apply_async_with_reservation(
            [repository_version.repository, publisher],
            kwargs={
                'publisher_pk': str(publisher.pk),
                'repository_version_pk': str(repository_version.pk)
            }
        )
        return OperationPostponedResponse([result], request)
