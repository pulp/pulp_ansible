from gettext import gettext as _

from django_filters.rest_framework import filterset
from rest_framework.decorators import detail_route
from rest_framework.exceptions import ValidationError

from pulpcore.plugin.models import Repository
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
            raise ValidationError(detail=_('A feed_url must be specified.'))
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
        repository = self.get_resource(request.data['repository'], Repository)
        result = tasks.publish.apply_async_with_reservation(
            [repository, publisher],
            kwargs={
                'publisher_pk': str(publisher.pk),
                'repository_pk': repository.pk
            }
        )
        return OperationPostponedResponse([result], request)
