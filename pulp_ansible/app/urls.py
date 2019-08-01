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

from pulp_ansible.app.viewsets import CollectionUploadViewSet


galaxy_api_prefix = "pulp_ansible/galaxy/<path:path>/api/"

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
]

urlpatterns = [
    path("ansible/collections/", CollectionUploadViewSet.as_view({"post": "create"})),
    path(galaxy_api_prefix, GalaxyVersionView.as_view()),
    path(galaxy_api_prefix + "v1/", include(v1_urls)),
    path(galaxy_api_prefix + "v2/", include(v2_urls)),
]
