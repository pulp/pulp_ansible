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

from .models import AnsibleRole, AnsibleImporter, AnsiblePublisher
from .serializers import AnsibleRoleSerializer, AnsibleImporterSerializer, AnsiblePublisherSerializer


class AnsibleRoleFilter(filterset.FilterSet):
    class Meta:
        model = AnsibleRole
        fields = [
            'name',
            'namespace',
            'version'
        ]


class AnsibleRoleViewSet(ContentViewSet):
    endpoint_name = 'ansible'
    queryset = AnsibleRole.objects.all()
    serializer_class = AnsibleRoleSerializer
    filter_class = AnsibleRoleFilter
