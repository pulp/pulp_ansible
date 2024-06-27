from rest_framework import viewsets

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view

from pulp_ansible.app.galaxy.v3.pagination import LimitOffsetPagination

from pulp_ansible.app.galaxy.v3.serializers import (
    CollectionVersionSearchListSerializer,
)
from pulp_ansible.app.galaxy.mixins import GalaxyAuthMixin

from pulpcore.plugin.util import get_url

from pulp_ansible.app.models import CrossRepositoryCollectionVersionIndex, AnsibleDistribution

from pulp_ansible.app.galaxy.v3.filters import CollectionVersionSearchFilter
from pulp_ansible.app.tasks.collectionversion_index import rebuild_index

from pulpcore.plugin.tasking import dispatch
from pulpcore.plugin.viewsets import OperationPostponedResponse


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                name="repository",
                type={"type": "array", "items": {"type": "string"}},
                location=OpenApiParameter.QUERY,
                required=False,
                style="form",
                explode=True,
                description="Filter collectionversions that are in these repository ids.",
            ),
            OpenApiParameter(
                name="repository_name",
                type={"type": "array", "items": {"type": "string"}},
                location=OpenApiParameter.QUERY,
                required=False,
                style="form",
                explode=True,
                description="Filter collectionversions that are in these repositories.",
            ),
            OpenApiParameter(
                name="distribution",
                type={"type": "array", "items": {"type": "string"}},
                location=OpenApiParameter.QUERY,
                required=False,
                style="form",
                explode=True,
                description="Filter collectionversions that are in these distrubtion ids.",
            ),
            OpenApiParameter(
                name="distribution_base_path",
                type={"type": "array", "items": {"type": "string"}},
                location=OpenApiParameter.QUERY,
                required=False,
                style="form",
                explode=True,
                description="Filter collectionversions that are in these base paths.",
            ),
        ],
    )
)
class CollectionVersionSearchViewSet(GalaxyAuthMixin, viewsets.ModelViewSet):
    """
    A viewset for cross-repo searches.
    """

    serializer_class = CollectionVersionSearchListSerializer
    pagination_class = LimitOffsetPagination
    filterset_class = CollectionVersionSearchFilter
    # This is a dummy, to make the model available to drf-spectacular
    queryset = CrossRepositoryCollectionVersionIndex.objects.none()

    def urlpattern(*args, **kwargs):
        """Helper for galaxy_ng access control."""
        return "pulp_ansible/v3/search/collection_versions"

    def get_queryset(self):
        qs = (
            CrossRepositoryCollectionVersionIndex.objects.select_related("repository")
            .select_related("collection_version")
            .select_related("repository_version")
            .select_related("namespace_metadata")
            .all()
        )

        for permission_class in self.get_permissions():
            if hasattr(permission_class, "scope_queryset"):
                qs = permission_class.scope_queryset(self, qs)

        return qs

    def rebuild(self, request, *args, **kwargs):
        async_result = dispatch(
            rebuild_index,
            exclusive_resources=[
                "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
            ],
            shared_resources=[get_url(AnsibleDistribution)],
        )
        return OperationPostponedResponse(async_result, request)
