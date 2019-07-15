from django.conf.urls import url

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


urlpatterns = [
    url(r"pulp_ansible/galaxy/(?P<path>.+)/api/$", GalaxyVersionView.as_view()),
    url(r"ansible/collections/$", CollectionUploadViewSet.as_view({"post": "create"})),
    url(r"pulp_ansible/galaxy/(?P<path>.+)/api/v1/roles/$", RoleList.as_view()),
    url(
        r"pulp_ansible/galaxy/(?P<path>.+)/api/v1/roles/(?P<role_pk>[^/]+)/versions/$",
        RoleVersionList.as_view(),
    ),
    url(r"pulp_ansible/galaxy/(?P<path>.+)/api/v2/collections/$", GalaxyCollectionView.as_view()),
    url(
        r"pulp_ansible/galaxy/(?P<path>.+)/api/v2/collections/(?P<namespace>[^/]+)/(?P<name>[^/]+)/"
        r"$",
        GalaxyCollectionDetailView.as_view(),
    ),
    url(
        r"pulp_ansible/galaxy/(?P<path>.+)/api/v2/collections/(?P<namespace>[^/]+)/(?P<name>[^/]+)/"
        r"versions/$",
        GalaxyCollectionVersionList.as_view(),
    ),
    url(
        r"pulp_ansible/galaxy/(?P<path>.+)/api/v2/collections/(?P<namespace>[^/]+)/(?P<name>[^/]+)/"
        r"versions/(?P<version>[^/]+)/$",
        GalaxyCollectionVersionDetail.as_view(),
    ),
]
