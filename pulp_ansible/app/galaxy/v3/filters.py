from django.contrib.postgres.search import SearchQuery
from django.db.models import fields as db_fields
from django.db.models import Q
from django.db.models.expressions import F, Func
from django_filters import (
    filters,
    FilterSet,
    OrderingFilter,
)
import semantic_version
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from pulpcore.plugin.viewsets import LabelFilter

from pulpcore.plugin.models import RepositoryVersion
from pulp_ansible.app import models


class CollectionVersionSearchFilter(FilterSet):
    """A custom filterset for cross-repo search."""

    strict = False

    name = filters.CharFilter(field_name="collection_version__name", lookup_expr="exact")
    namespace = filters.CharFilter(field_name="collection_version__namespace", lookup_expr="exact")
    version = filters.CharFilter(field_name="collection_version__version", lookup_expr="exact")
    repository_name = filters.CharFilter(method="filter_by_repository_name")
    repository = filters.CharFilter(method="filter_by_repository_id")
    is_highest = filters.BooleanFilter(field_name="is_highest")
    highest = filters.BooleanFilter(field_name="is_highest")
    is_deprecated = filters.BooleanFilter(field_name="is_deprecated")
    deprecated = filters.BooleanFilter(field_name="is_deprecated")
    is_signed = filters.BooleanFilter(field_name="is_signed")
    signed = filters.BooleanFilter(field_name="is_signed")
    q = filters.CharFilter(field_name="q", method="filter_by_q")
    tags = filters.CharFilter(
        field_name="tags",
        method="filter_by_tags",
        help_text="Filter by comma separate list of tags that must all be matched",
    )
    distribution = filters.CharFilter(method="filter_by_distribution_id")
    distribution_base_path = filters.CharFilter(method="filter_by_base_path")
    dependency = filters.CharFilter(method="filter_by_dependency")
    version_range = filters.CharFilter(field_name="version_range", method="version_range_filter")
    repository_version = filters.CharFilter(
        field_name="repository_version__number", method="repository_version_filter"
    )
    keywords = filters.CharFilter(field_name="q", method="filter_by_q")
    repository_label = LabelFilter(label_field_name="repository__pulp_labels")

    order_by = OrderingFilter(
        choices=(
            ("pulp_created", "by CV created"),
            ("-pulp_created", "by CV created (descending)"),
            ("namespace", "by CV namespace"),
            ("-namespace", "by CV namespace (descending)"),
            ("name", "by CV name"),
            ("-name", "by CV name (descending)"),
            ("version", "by CV version"),
            ("-version", "by CV version (descending)"),
        ),
        fields={
            "collection_version__pulp_created": "pulp_created",
            "collection_version__namespace": "namespace",
            "collection_version__name": "name",
            "collection_version__version": "version",
        },
    )

    def version_range_filter(self, queryset, name, value):
        try:
            s = semantic_version.SimpleSpec(value)
            full_version_list = [
                semantic_version.Version(v)
                for v in queryset.values_list("collection_version__version", flat=True)
            ]
            version_list = [str(v) for v in s.filter(full_version_list)]

            return queryset.filter(collection_version__version__in=version_list)
        except ValueError:
            raise ValidationError(_("%s must be a valid semantic version range." % name))

    def filter_by_repository_name(self, queryset, name, value):
        repository_names = self.request.query_params.getlist(name)
        return queryset.filter(repository__name__in=repository_names)

    def filter_by_repository_id(self, queryset, name, value):
        repository_ids = self.request.query_params.getlist(name)
        return queryset.filter(repository__pk__in=repository_ids)

    def filter_by_distribution_id(self, qs, name, value):
        dist_ids = self.request.query_params.getlist(name)

        query = Q()

        for dist_id in dist_ids:
            for distribution in models.AnsibleDistribution.objects.filter(pk=dist_id):
                if distribution.repository_version_id:
                    query = query | Q(repository_version__pk=distribution.repository_version_id)
                else:
                    query = query | Q(repository__pk=distribution.repository_id)

        return qs.filter(query)

    def filter_by_base_path(self, qs, name, value):
        base_paths = self.request.query_params.getlist(name)

        query = Q()

        for base_path in base_paths:
            for distribution in models.AnsibleDistribution.objects.filter(base_path=base_path):
                if distribution.repository_version_id:
                    query = query | Q(repository_version__pk=distribution.repository_version_id)
                else:
                    query = query | Q(repository__pk=distribution.repository_id)

        return qs.filter(query)

    def repository_version_filter(self, qs, name, value):
        if value != "latest":
            return qs.filter(repository_version__number=value)

        # Reduce queryset down to the "latest" repository version number(s)
        rqs = (
            RepositoryVersion.objects.filter(repository__pulp_type="ansible.ansible")
            .order_by("repository", "-pulp_created")
            .distinct("repository")
            .values_list("repository__pk", "number")
        )
        query = Q(repository_version=None)
        for rpk, number in rqs:
            query = query | Q(repository__pk=rpk, repository_version__number=number)

        return qs.filter(query)

    def filter_by_dependency(self, qs, name, value):
        """Return a list of collections that depend on a given collection name."""
        qs = qs.filter(collection_version__dependencies__has_key=value)
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
        qs = queryset.filter(collection_version__search_vector=search_query)
        ts_rank_fn = Func(
            F("collection_version__search_vector"),
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
            qs = qs.filter(collection_version__tags__name=tag)
        return qs
