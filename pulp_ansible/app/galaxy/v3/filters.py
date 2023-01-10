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
        field_name="name",
        method="filter_by_name",
    )

    namespace = filters.CharFilter(
        field_name="namepace",
        method="filter_by_namespace",
    )

    distribution = filters.CharFilter(
        field_name="repository",
        method="filter_by_repository_name",
    )

    repository = filters.CharFilter(
        field_name="repository",
        method="filter_by_repository_name",
    )

    repository_name = filters.CharFilter(
        field_name="repository",
        method="filter_by_repository_name",
    )

    dependency = filters.CharFilter(field_name="collection_version", method="filter_by_dependency")

    deprecated = filters.CharFilter(field_name="deprecated", method="filter_by_deprecated")

    def filter_by_repository_name(self, qs, name, value):
        """Allow for multiple repository names to filter on."""
        include_q = Q()
        repository_names = value.split(",")
        for rn in repository_names:
            include_q = include_q | Q(repository__name=rn)
        qs = qs.filter(include_q)
        return qs

    def filter_by_name(self, qs, name, value):
        print('FILTER BY NAME')
        return qs.filter(Q(content__collection_version__name=name))

    def filter_by_namespace(self, qs, name, value):
        print('FILTER BY NAMESPACE')
        return qs.filter(Q(content__collection_version__namespace=name))

    def filter_by_dependency(self, qs, name, value):
        """Return a list of collections that depend on a given collection name."""

        #kwargs = {f"dependencies__{value}__isnull": False}
        #qs = qs.filter(**kwargs)

        obj = qs.first()
        print(f'{datetime.datetime.now().isoformat()} OBJ: {type(obj)}')

        '''
        for x in dir(obj):
            print(f'OBJ: .{x}')

        print(f'OBJ.content: {obj.content}')
        for x in dir(obj.content):
            print(f'OBJ.content: .{x}')
        '''

        return qs

        kwargs = {f"collection_version__dependencies__{value}__isnull": False}
        qs = qs.filter(**kwargs)

        return qs

    def filter_by_deprecated(self, qs, name, value):
        bool_value = False
        if value in [True, "True", "true", "t", 1, "1"]:
            bool_value = True
        qs = qs.filter(is_deprecated=bool_value)
        return qs
