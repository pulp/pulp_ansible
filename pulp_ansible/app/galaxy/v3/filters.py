import datetime

from django_filters import filters
from django_filters import FilterSet
from django.db.models import Q

from pulpcore.plugin.viewsets import ContentFilter
from pulp_ansible.app.viewsets import (
    CollectionVersionFilter,
)


#class CollectionVersionSearchFilter(ContentFilter):
class CollectionVersionSearchFilter(FilterSet):

    name = filters.CharFilter(
        method="filter_by_name",
    )

    namespace = filters.CharFilter(
        method="filter_by_namespace",
    )

    distribution = filters.CharFilter(
        method="filter_by_repository_name",
    )

    repository = filters.CharFilter(
        method="filter_by_repository_name",
    )

    repository_name = filters.CharFilter(
        method="filter_by_repository_name",
    )

    dependency = filters.CharFilter(method="filter_by_dependency")

    deprecated = filters.CharFilter(method="filter_by_deprecated")

    def filter_by_repository_name(self, qs, name, value):
        """Allow for multiple repository names to filter on."""
        include_q = Q()
        if ',' in value:
            repository_names = value.split(",")
            for rn in repository_names:
                include_q = include_q | Q(repository__name=rn)
        else:
            include_q = include_q | Q(repository__name=value)
        qs = qs.filter(include_q)
        return qs

    def filter_by_name(self, qs, name, value):
        print('FILTER BY NAME')
        return qs.filter(Q(content__ansible_collectionversion__name=value))
        return qs

    def filter_by_namespace(self, qs, name, value):
        print('FILTER BY NAMESPACE')
        return qs.filter(Q(content__ansible_collectionversion__namespace=value))

    def filter_by_dependency(self, qs, name, value):
        """Return a list of collections that depend on a given collection name."""
        kwargs = {f"content__ansible_collectionversion__dependencies__{value}__isnull": False}
        qs = qs.filter(**kwargs)
        return qs

    def filter_by_deprecated(self, qs, name, value):
        bool_value = False
        if value in [True, "True", "true", "t", 1, "1"]:
            bool_value = True
        qs = qs.filter(is_deprecated=bool_value)
        return qs
