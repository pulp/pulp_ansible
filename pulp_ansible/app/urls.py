from django.conf import settings
from django.conf.urls import url
from django.urls import include, path

from pulp_ansible.app.galaxy.views import (
    GalaxyCollectionVersionDetail,
    GalaxyCollectionVersionList,
    GalaxyCollectionDetailView,
    GalaxyCollectionView,
    GalaxyVersionView,
    RoleList,
    RoleVersionList,
)
from pulp_ansible.app.galaxy.v3 import views as views_v3

from pulp_ansible.app.viewsets import CopyViewSet, CollectionUploadViewSet


GALAXY_API_ROOT = getattr(settings, "GALAXY_API_ROOT", "pulp_ansible/galaxy/<path:path>/api/")


v1_urls = [
    path("roles/", RoleList.as_view()),
    path("roles/<str:role_pk>/versions/", RoleVersionList.as_view()),
]

v2_urls = [
    path("collections/", GalaxyCollectionView.as_view()),
    path("collections/<str:namespace>/<str:name>/", GalaxyCollectionDetailView.as_view()),
    path("collections/<str:namespace>/<str:name>/versions/", GalaxyCollectionVersionList.as_view()),
    path(
        "collections/<str:namespace>/<str:name>/versions/<str:version>/",
        GalaxyCollectionVersionDetail.as_view(),
    ),
    path(
        "collection-imports/<uuid:pk>/",
        views_v3.CollectionImportViewSet.as_view({"get": "retrieve"}),
    ),
]

v3_urls = [
    path("", views_v3.RepoMetadataViewSet.as_view({"get": "retrieve"}), name="repo-metadata"),
    path(
        "collections/", views_v3.CollectionViewSet.as_view({"get": "list"}), name="collections-list"
    ),
    path(
        "artifacts/collections/",
        views_v3.CollectionUploadViewSet.as_view({"post": "create"}),
        name="collection-artifact-upload",
    ),
    path(
        "collections/<str:namespace>/<str:name>/",
        views_v3.CollectionViewSet.as_view({"get": "retrieve", "patch": "update"}),
        name="collections-detail",
    ),
    path(
        "collections/<str:namespace>/<str:name>/versions/",
        views_v3.CollectionVersionViewSet.as_view({"get": "list"}),
        name="collection-versions-list",
    ),
    path(
        "collections/<str:namespace>/<str:name>/versions/<str:version>/",
        views_v3.CollectionVersionViewSet.as_view({"get": "retrieve"}),
        name="collection-versions-detail",
    ),
    path(
        "collections/<str:namespace>/<str:name>/versions/<str:version>/docs-blob/",
        views_v3.CollectionVersionDocsViewSet.as_view({"get": "retrieve"}),
        name="collection-versions-detail-docs",
    ),
    path(
        "imports/collections/<uuid:pk>/",
        views_v3.CollectionImportViewSet.as_view({"get": "retrieve"}),
        name="collection-imports-detail",
    ),
    path(
        "collections/all/",
        views_v3.UnpaginatedCollectionViewSet.as_view({"get": "list"}),
        name="metadata-collection-list",
    ),
    path(
        "collection_versions/all/",
        views_v3.UnpaginatedCollectionVersionViewSet.as_view({"get": "list"}),
        name="metadata-collection-versions-list",
    ),
]

urlpatterns = [
    path("ansible/collections/", CollectionUploadViewSet.as_view({"post": "create"})),
    path(GALAXY_API_ROOT + "v1/", include(v1_urls)),
    path(GALAXY_API_ROOT + "v2/", include(v2_urls)),
    path(GALAXY_API_ROOT + "v3/", include(v3_urls)),
    path(GALAXY_API_ROOT, GalaxyVersionView.as_view()),
    url(r"^pulp/api/v3/ansible/copy/$", CopyViewSet.as_view({"post": "create"})),
]
