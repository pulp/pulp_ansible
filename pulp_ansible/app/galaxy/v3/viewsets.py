from django.db.models import Value, F, CharField
from django.db.models import When, Case
from django.db.models import Q
from django.db.models import Prefetch
from django.db.models import OuterRef
from django.db.models import Subquery
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models.functions import Concat
from django_filters import filters
from rest_framework import viewsets

from pulp_ansible.app.galaxy.v3.serializers import (
    CollectionVersionSearchListSerializer,
    CollectionVersionListSerializer
)

from pulpcore.app.models import RepositoryContent

from pulp_ansible.app.models import (
    AnsibleCollectionDeprecated,
    AnsibleDistribution,
    CollectionVersion,
)

from pulp_ansible.app.viewsets import (
    CollectionVersionFilter,
)


class CollectionVersionSearchViewSetPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1000


class CollectionVersionSearchViewSet(viewsets.ModelViewSet):

    serializer_class = CollectionVersionSearchListSerializer
    pagination_class = CollectionVersionSearchViewSetPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = None

    def get_queryset(self):

        include_q = Q()
        exclude_q = Q()

        for distro in AnsibleDistribution.objects.all():
            print(f'DISTRO: {distro} {distro.name}')
            if not distro.repository_version and distro.repository is None:
                continue
            elif distro.repository_version:
                rv = distro.repository_version.number
            else:
                rv = distro.repository.latest_version().number

            include_q = include_q | Q(repository=distro.repository, version_added__number__lte=rv)
            exclude_q = exclude_q | Q(repository=distro.repository, version_removed__number__lte=rv)

        qs = RepositoryContent.objects.filter(
                content__pulp_type="ansible.collection_version"
            ).exclude(
                exclude_q
            ).filter(
                include_q
            )

        # gerrod's suggestion ...
        # sets the obj's collection_version property to the CV
        cvs = Prefetch("content", queryset=CollectionVersion.objects.all(), to_attr="collection_version")
        qs = qs.filter(content__pulp_type="ansible.collection_version").prefetch_related(cvs)

        print(f'COUNT: {qs.count()}')

        return qs

