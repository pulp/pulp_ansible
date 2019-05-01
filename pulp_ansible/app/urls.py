from django.conf.urls import url

from pulp_ansible.app.galaxy.views import (
    GalaxyVersionView,
    RoleList,
    RoleVersionList
)

urlpatterns = [
    url(r'pulp_ansible/galaxy/(?P<path>.+)/api/$', GalaxyVersionView.as_view()),
    url(r'pulp_ansible/galaxy/(?P<path>.+)/api/v1/roles/$', RoleList.as_view()),
    url(r'pulp_ansible/galaxy/(?P<path>.+)/api/v1/roles/(?P<role_pk>.+)/versions/$',
        RoleVersionList.as_view())
]
