import datetime

from django.contrib.postgres.search import SearchQuery
from django.db.models import fields as db_fields
from django.db.models.expressions import F, Func
from django_filters import filters
from django_filters import FilterSet
from django.db.models import Q

from pulpcore.app.models.repository import RepositoryContent
from pulpcore.plugin.viewsets import ContentFilter
from pulp_ansible.app.viewsets import (
    CollectionVersionFilter,
)


#class CollectionVersionSearchFilter(ContentFilter):
#class CollectionVersionSearchFilter(FilterSet):
#class CollectionVersionSearchFilter(CollectionVersionFilter):
class CollectionVersionSearchFilter(FilterSet):

    '''
    class Meta:
        model = RepositoryContent
        fields = ["namespace", "name", "version", "q", "is_highest", "tags"]
    '''

    name = filters.CharFilter(
        method="filter_by_name",
    )

    namespace = filters.CharFilter(
        method="filter_by_namespace",
    )

    version = filters.CharFilter(
        method="filter_by_version",
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

    signed = filters.CharFilter(method="filter_by_signed")

    is_highest = filters.BooleanFilter(field_name="is_highest")

    q = filters.CharFilter(field_name="q", method="filter_by_q")
    keywords = filters.CharFilter(field_name="q", method="filter_by_q")

    tags = filters.CharFilter(
        field_name="tags",
        method="filter_by_tags",
        #help_text=_("Filter by comma separate list of tags that must all be matched"),
        help_text="Filter by comma separate list of tags that must all be matched",
    )

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
        return qs.filter(Q(content__ansible_collectionversion__name=value))

    def filter_by_namespace(self, qs, name, value):
        return qs.filter(Q(content__ansible_collectionversion__namespace=value))

    def filter_by_version(self, qs, name, value):
        return qs.filter(Q(content__ansible_collectionversion__version=value))

    def filter_by_dependency(self, qs, name, value):
        """Return a list of collections that depend on a given collection name."""
        #kwargs = {f"content__ansible_collectionversion__dependencies__{value}__isnull": False}
        #qs = qs.filter(**kwargs)
        qs = qs.filter(content__ansible_collectionversion__dependencies__has_key=value)
        return qs

    def filter_by_deprecated(self, qs, name, value):
        bool_value = False
        if value in [True, "True", "true", "t", 1, "1"]:
            bool_value = True
        qs = qs.filter(is_deprecated=bool_value)
        return qs

    def filter_by_signed(self, qs, name, value):
        bool_value = False
        if value in [True, "True", "true", "t", 1, "1"]:
            bool_value = True

        '''
        #qs = qs.filter(is_deprecated=bool_value)
        obj = qs.first()
        for x in dir(obj):
            if not x.endswith('signed'):
                continue
            print(x)
            print(getattr(obj, x))
        '''

        if bool_value == True:
            qs = qs.filter(signatures_count__gte=1)
        else:
            qs = qs.filter(signatures_count__lte=0)

        return qs

    def filter_by_q(self, queryset, name, value):
        """
        Full text search provided by the 'q' option.
        Args:
            queryset: The query to add the additional full-text search filtering onto
            name: The name of the option specified, i.e. 'q'
            value: The string to search on
        Returns:
            The Django queryset that was passed in, additionally filtered by full-text search.
        """
        search_query = SearchQuery(value)
        qs = queryset.filter(content__ansible_collectionversion__search_vector=search_query)
        ts_rank_fn = Func(
            F("content__ansible_collectionversion__search_vector"),
            search_query,
            32,  # RANK_NORMALIZATION = 32
            function="ts_rank",
            output_field=db_fields.FloatField(),
        )
        return qs.annotate(rank=ts_rank_fn).order_by("-rank")

    def filter_by_tags(self, qs, name, value):
        """
        Filter queryset qs by list of tags.
        Args:
            qs (django.db.models.query.QuerySet): CollectionVersion queryset
            value (string): A comma separated list of tags
        Returns:
            Queryset of CollectionVersion that matches all tags
        """
        for tag in value.split(","):
            qs = qs.filter(content__ansible_collectionversion__tags__name=tag)
        return qs
