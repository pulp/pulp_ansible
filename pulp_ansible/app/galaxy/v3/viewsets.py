from rest_framework import viewsets

from pulp_ansible.app.galaxy.v3.pagination import LimitOffsetPagination

from pulp_ansible.app.galaxy.v3.serializers import (
    CollectionVersionSearchListSerializer,
)

from pulp_ansible.app.models import (
    CrossRepositoryCollectionVersionIndexView,
)

from pulp_ansible.app.galaxy.v3.filters import CollectionVersionSearchFilter


class CollectionVersionSearchViewSet(viewsets.ModelViewSet):
    """
    A viewset for cross-repo searches.
    """

    serializer_class = CollectionVersionSearchListSerializer
    pagination_class = LimitOffsetPagination
    filterset_class = CollectionVersionSearchFilter

    def get_queryset(self):
        return CrossRepositoryCollectionVersionIndexView.objects.all()
