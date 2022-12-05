from pprint import pprint
from django.db.models import Exists, OuterRef, Q, Value, F, Func, CharField
from django.db.models import When, Case
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models.functions import Concat

from datetime import datetime
from gettext import gettext as _
import semantic_version

from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.search import SearchQuery
from django.db import DatabaseError
from django.db.models import F, Q
from django.db.models.expressions import Window
from django.db.models.functions.window import FirstValue
from django.http import StreamingHttpResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.utils.dateparse import parse_datetime
from django_filters import filters
from django.views.generic.base import RedirectView
from django.conf import settings

from drf_spectacular.utils import OpenApiParameter, extend_schema
from jinja2 import Template
from rest_framework import mixins
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.reverse import reverse, reverse_lazy
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework import viewsets, views
from rest_framework.exceptions import NotFound
from rest_framework import status

from pulpcore.plugin.exceptions import DigestValidationError
from pulpcore.plugin.models import PulpTemporaryFile, Content
from pulpcore.plugin.serializers import AsyncOperationResponseSerializer
from pulpcore.plugin.viewsets import BaseFilterSet, OperationPostponedResponse
from pulpcore.plugin.tasking import add_and_remove, dispatch

from pulp_ansible.app.galaxy.v3.exceptions import ExceptionHandlerMixin
from pulp_ansible.app.galaxy.v3.serializers import (
    CollectionSerializer,
    CollectionVersionSerializer,
    CollectionVersionDocsSerializer,
    CollectionVersionListSerializer,
    CollectionVersionSearchListSerializer,
    RepoMetadataSerializer,
    UnpaginatedCollectionVersionSerializer,
    ClientConfigurationSerializer,
    CollectionVersionSearchResultsSerializer,
)
from pulp_ansible.app.models import (
    AnsibleCollectionDeprecated,
    AnsibleDistribution,
    AnsibleRepository,
    Collection,
    CollectionVersion,
    CollectionVersionSignature,
    CollectionImport,
    DownloadLog,
)
from pulp_ansible.app.serializers import (
    CollectionOneShotSerializer,
    CollectionImportDetailSerializer,
)

from pulp_ansible.app.galaxy.mixins import UploadGalaxyCollectionMixin
from pulp_ansible.app.galaxy.v3.pagination import LimitOffsetPagination
from pulp_ansible.app.viewsets import (
    CollectionVersionFilter,
)

from pulp_ansible.app.tasks.deletion import delete_collection_version, delete_collection


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
