from logging import getLogger

from django.db import models

from pulpcore.plugin.models import Content, Remote


log = getLogger(__name__)


class AnsibleRole(Content):
    """
    A model representing an Ansible Role.
    """

    TYPE = 'ansible-role'

    namespace = models.CharField(max_length=64)
    name = models.CharField(max_length=64)

    class Meta:
        unique_together = (
            'namespace',
            'name'
        )


class AnsibleRoleVersion(Content):
    """
    A content type representing an Ansible Role version.
    """

    TYPE = 'ansible-role-version'

    version = models.CharField(max_length=128)
    role = models.ForeignKey(AnsibleRole, on_delete=models.PROTECT, related_name='versions')

    @property
    def relative_path(self):
        """
        Return the relative path of the ContentArtifact.
        """
        return self.contentartifact_set.get().relative_path

    class Meta:
        unique_together = (
            'version',
            'role'
        )


class AnsibleRemote(Remote):
    """
    A Remote for Ansible content.
    """

    TYPE = 'ansible'
