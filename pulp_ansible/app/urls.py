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

from pulpcore.plugin.serializers import AsyncOperationResponseSerializer

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

# Legacy urls that need to be redirected to plugin/ansible/collections/<base_path>/
legacy_v3_collection_urls = [
    path(
        "",
        views_v3.redirect_view_generator(
            {"get": "retrieve"}, url="repo-metadata", viewset=views_v3.RepoMetadataViewSet
        ),
        name="legacy-v3-repo-metadata",
    ),
    path(
        "collections/",
        views_v3.redirect_view_generator(
            {"get": "list"}, url="collections-list", viewset=views_v3.CollectionViewSet
        ),
        name="legacy-v3-collections-list",
    ),
    path(
        "artifacts/collections/<str:path>/<str:filename>",
        views_v3.redirect_view_generator(
            {"get": "get"},
            url="collection-artifact-download",
            viewset=views_v3.CollectionArtifactDownloadView,
        ),
        name="legacy-v3-collection-artifact-download",
    ),
    path(
        "collections/<str:namespace>/<str:name>/",
        views_v3.redirect_view_generator(
            {"get": "retrieve", "patch": "update", "delete": "destroy"},
            url="collections-detail",
            viewset=views_v3.CollectionViewSet,
            responses={"update": AsyncOperationResponseSerializer},
        ),
        name="legacy-v3-collections-detail",
    ),
    path(
        "collections/<str:namespace>/<str:name>/versions/",
        views_v3.redirect_view_generator(
            {"get": "list"},
            url="collection-versions-list",
            viewset=views_v3.CollectionVersionViewSet,
        ),
        name="legacy-v3-collection-versions-list",
    ),
    path(
        "collections/<str:namespace>/<str:name>/versions/<str:version>/",
        views_v3.redirect_view_generator(
            {"get": "retrieve", "delete": "destroy"},
            url="collection-versions-detail",
            viewset=views_v3.CollectionVersionViewSet,
        ),
        name="legacy-v3-collection-versions-detail",
    ),
    path(
        "collections/<str:namespace>/<str:name>/versions/<str:version>/docs-blob/",
        views_v3.redirect_view_generator(
            {"get": "retrieve"},
            url="collection-versions-detail-docs",
            viewset=views_v3.CollectionVersionDocsViewSet,
        ),
        name="legacy-v3-collection-versions-detail-docs",
    ),
    path(
        "collections/all/",
        views_v3.redirect_view_generator(
            {"get": "list"},
            url="metadata-collection-list",
            viewset=views_v3.UnpaginatedCollectionViewSet,
        ),
        name="legacy-v3-metadata-collection-list",
    ),
    path(
        "collection_versions/all/",
        views_v3.redirect_view_generator(
            {"get": "list"},
            url="metadata-collection-versions-list",
            viewset=views_v3.UnpaginatedCollectionVersionViewSet,
        ),
        name="legacy-v3-metadata-collection-versions-list",
    ),
    # the ansible-galaxy client doesn't play well with redirects for POST operations, so these
    # views don't redirect
    path(
        "artifacts/collections/",
        views_v3.LegacyCollectionUploadViewSet.as_view({"post": "create"}),
        name="collection-artifact-upload",
    ),
]


legacy_v3_urls = [
    path(
        "imports/collections/<uuid:pk>/",
        views_v3.redirect_view_generator(
            {"get": "retrieve"},
            url="collection-imports-detail",
            viewset=views_v3.CollectionImportViewSet,
            distro_view=False,
        ),
        name="legacy-v3-collection-imports-detail",
    ),
]

v3_collection_urls = [
    path("", views_v3.RepoMetadataViewSet.as_view({"get": "retrieve"}), name="repo-metadata"),
    path("index/", views_v3.CollectionViewSet.as_view({"get": "list"}), name="collections-list"),
    path(
        "artifacts/",
        views_v3.CollectionUploadViewSet.as_view({"post": "create"}),
        name="collection-artifact-upload",
    ),
    path(
        "artifacts/<str:filename>",
        views_v3.CollectionArtifactDownloadView.as_view(),
        name="collection-artifact-download",
    ),
    path(
        "index/<str:namespace>/<str:name>/",
        views_v3.CollectionViewSet.as_view(
            {"get": "retrieve", "patch": "update", "delete": "destroy"}
        ),
        name="collections-detail",
    ),
    path(
        "index/<str:namespace>/<str:name>/versions/",
        views_v3.CollectionVersionViewSet.as_view({"get": "list"}),
        name="collection-versions-list",
    ),
    path(
        "index/<str:namespace>/<str:name>/versions/<str:version>/",
        views_v3.CollectionVersionViewSet.as_view({"get": "retrieve", "delete": "destroy"}),
        name="collection-versions-detail",
    ),
    path(
        "index/<str:namespace>/<str:name>/versions/<str:version>/docs-blob/",
        views_v3.CollectionVersionDocsViewSet.as_view({"get": "retrieve"}),
        name="collection-versions-detail-docs",
    ),
    path(
        "all-collections/",
        views_v3.UnpaginatedCollectionViewSet.as_view({"get": "list"}),
        name="metadata-collection-list",
    ),
    path(
        "all-versions/",
        views_v3.UnpaginatedCollectionVersionViewSet.as_view({"get": "list"}),
        name="metadata-collection-versions-list",
    ),
]

v3_plugin_urls = [
    # path:var captures /, so it has to have something at the end to make it work
    # correctly.
    path("content/<path:distro_base_path>/collections/", include(v3_collection_urls)),
    path(
        "imports/collections/<uuid:pk>/",
        views_v3.CollectionImportViewSet.as_view({"get": "retrieve"}),
        name="collection-imports-detail",
    ),
    path(
        "client-configuration/",
        views_v3.ClientConfigurationView.as_view(),
        name="client-configuration-viewset",
    ),
]

v3_urls = [
    path("", include(legacy_v3_collection_urls)),
    path("", include(legacy_v3_urls)),
    path("plugin/ansible/", include(v3_plugin_urls)),
]

urlpatterns = [
    path("ansible/collections/", CollectionUploadViewSet.as_view({"post": "create"})),
    path(GALAXY_API_ROOT.split("<path:path>")[0] + "default/api/v3/", include(v3_urls)),
    path(
        GALAXY_API_ROOT.split("<path:path>")[0] + "default/api/",
        GalaxyVersionView.as_view(v3_only=True),
    ),
    path(GALAXY_API_ROOT + "v1/", include(v1_urls)),
    path(GALAXY_API_ROOT + "v2/", include(v2_urls)),
    path(GALAXY_API_ROOT + "v3/", include(v3_urls)),
    path(GALAXY_API_ROOT, GalaxyVersionView.as_view()),
    url(r"^pulp/api/v3/ansible/copy/$", CopyViewSet.as_view({"post": "create"})),
]
