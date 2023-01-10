import datetime

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

from pulp_ansible.app.galaxy.v3.filters import CollectionVersionSearchFilter


class CollectionVersionSearchViewSetPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1000


class CollectionVersionSearchViewSet(viewsets.ModelViewSet):

    serializer_class = CollectionVersionSearchListSerializer
    pagination_class = CollectionVersionSearchViewSetPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = CollectionVersionSearchFilter

    def get_queryset(self):

        include_q = Q()
        exclude_q = Q()

        # make a list of the latest repo versions ...
        for distro in AnsibleDistribution.objects.all():
            if not distro.repository_version and distro.repository is None:
                continue
            elif distro.repository_version:
                rv = distro.repository_version.number
            else:
                rv = distro.repository.latest_version().number

            include_q = include_q | Q(repository=distro.repository, version_added__number__lte=rv)
            exclude_q = exclude_q | Q(repository=distro.repository, version_removed__number__lte=rv)

        # reduce repository content down to collectionversions and those that are
        # in the latest repository versions found above ...
        qs = RepositoryContent.objects.filter(
                content__pulp_type="ansible.collection_version"
            ).exclude(
                exclude_q
            ).filter(
                include_q
            )

        # gerrod's suggestion ...
        # sets the obj's collection_version property to the CV (at the python level)
        cvs = Prefetch("content", queryset=CollectionVersion.objects.all(), to_attr="collection_version")
        qs = qs.filter(content__pulp_type="ansible.collection_version").prefetch_related(cvs)

		#################################
		# Annotations
		#################################

        # add a field for the fqn:<namespace>.<name> ...
        qs = qs.annotate(
            fqn=Concat(
                F("content__ansible_collectionversion__namespace"),
                Value("."),
                F("content__ansible_collectionversion__name"),
                output_field=CharField()
            )
        )

        # make a queryable list of deprecated collections
        deprecation_qs = AnsibleCollectionDeprecated.objects.all()
        deprecation_qs = deprecation_qs.annotate(
            fqn=Concat(F("namespace"), Value("."), F("name"), output_field=CharField())
        )
        deprecations = [x.fqn for x in deprecation_qs]

        # Annotate deprecation ...
        kwargs = {
            "is_deprecated": Case(
                When(fqn__in=deprecations, then=Value(True)), default=Value(False)
            )
        }
        qs = qs.annotate(**kwargs)

        #qs = qs.annotate(search_vector=F("content__ansible_collectionversion__search_vector"))

        return qs
