from django.db.models import Value, F, CharField
from django.db.models import When, Case
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models.functions import Concat
from django_filters import filters
from rest_framework import viewsets

from pulp_ansible.app.galaxy.v3.serializers import (
    # CollectionSerializer,
    # CollectionVersionSerializer,
    # CollectionVersionDocsSerializer,
    CollectionVersionSearchListSerializer,
    # RepoMetadataSerializer,
    # CollectionVersionSearchResultsSerializer,
)
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


class CollectionVersionSearchFilter(CollectionVersionFilter):

    distributions = filters.CharFilter(
        field_name="distributions",
        method="filter_by_distribution",
    )

    repository = filters.CharFilter(
        field_name="distributions",
        method="filter_by_distribution",
    )

    repository_name = filters.CharFilter(
        field_name="distributions",
        method="filter_by_distribution",
    )

    dependency = filters.CharFilter(field_name="dependencies", method="filter_by_dependency")

    deprecated = filters.CharFilter(field_name="deprecated", method="filter_by_deprecated")

    def filter_by_distribution(self, qs, name, value):
        for distro_name in value.split(","):
            kwargs = {f"in_distro_{distro_name}": True}
            qs = qs.filter(**kwargs)
        return qs

    def filter_by_dependency(self, qs, name, value):
        """Return a list of collections that depend on a given collection name."""
        kwargs = {f"dependencies__{value}__isnull": False}
        qs = qs.filter(**kwargs)
        return qs

    def filter_by_deprecated(self, qs, name, value):
        bool_value = False
        if value in [True, "True", "true", "t", 1, "1"]:
            bool_value = True
        qs = qs.filter(is_deprecated=bool_value)
        return qs


class CollectionVersionSearchViewSet(viewsets.ModelViewSet):

    queryset = CollectionVersion.objects.all()
    serializer_class = CollectionVersionSearchListSerializer
    pagination_class = CollectionVersionSearchViewSetPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = CollectionVersionSearchFilter

    def get_queryset(self):
        qs = CollectionVersion.objects.all()

        # add a field for the namespace.name ...
        qs = qs.annotate(
            fqn=Concat(F("namespace"), Value("."), F("name"), output_field=CharField())
        )

        # make a queryable list of deprecated collections
        deprecation_qs = AnsibleCollectionDeprecated.objects.all()
        deprecation_qs = deprecation_qs.annotate(
            fqn=Concat(F("namespace"), Value("."), F("name"), output_field=CharField())
        )
        deprecations = [x.fqn for x in deprecation_qs]

        # add a field to indicate deprecation ...
        kwargs = {
            "is_deprecated": Case(
                When(fqn__in=deprecations, then=Value(True)), default=Value(False)
            )
        }
        qs = qs.annotate(**kwargs)

        # add a field to indicate if CV in each distro ...
        for distro in AnsibleDistribution.objects.all():
            kwargs = {
                f"in_distro_{distro.name}": Case(
                    When(pulp_id__in=distro.repository.latest_version().content, then=Value(True)),
                    default=Value(False),
                )
            }
            qs = qs.annotate(**kwargs)

        # add a field for signing state ...

        return qs
