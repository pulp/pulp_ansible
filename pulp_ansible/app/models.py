from logging import getLogger

from django.db import models

from pulpcore.plugin.models import Content, Remote, Publisher, SingleArtifactContent


log = getLogger(__name__)


class AnsibleRole(Content):
    """
    A model representing an Ansible Role
    """

    TYPE = 'ansible-role'

    namespace = models.CharField(max_length=64)
    name = models.CharField(max_length=64)

    class Meta:
        unique_together = (
            'namespace',
            'name'
        )


class AnsibleRoleVersion(SingleArtifactContent):
    """
    A content type representing an Ansible Role version
    """

    TYPE = 'ansible-role-version'

    version = models.CharField(max_length=128)
    role = models.ForeignKey(AnsibleRole, on_delete=models.PROTECT)

    def _calc_relative_path(self):
        return '{}/{}/{}.tar.gz'.format(self.role.namespace,
                                        self.role.name,
                                        self.version)

    class Meta:
        unique_together = (
            'version',
            'role'
        )


class AnsiblePublisher(Publisher):
    """
    A Publisher for Ansible content.
    """

    TYPE = 'ansible'


class AnsibleRemote(Remote):
    """
    A Remote for Ansible content
    """

    TYPE = 'ansible'
