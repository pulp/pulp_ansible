from django.conf.urls import url

from pulp_ansible.app.galaxy.views import (
    AnsibleGalaxyVersionView,
    AnsibleRoleList,
    AnsibleRoleVersionList
)

urlpatterns = [
    url(r'pulp_ansible/galaxy/(?P<path>.+)/api/$', AnsibleGalaxyVersionView.as_view()),
    url(r'pulp_ansible/galaxy/(?P<path>.+)/api/v1/roles/$', AnsibleRoleList.as_view()),
    url(r'pulp_ansible/galaxy/(?P<path>.+)/api/v1/roles/(?P<role_pk>[0-9a-f-]+)/versions/$',
        AnsibleRoleVersionList.as_view())
]
