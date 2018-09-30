from logging import getLogger

from django.db import models

from pulpcore.plugin.models import Content, ContentArtifact, Remote


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
    def artifact(self):
        """
        Return the artifact id (there is only one for this content type).
        """
        return self.artifacts.get().pk

    @artifact.setter
    def artifact(self, artifact):
        """
        Set the artifact for this Ansible Role version.
        """
        if self.pk:
            ca = ContentArtifact(
                artifact=artifact,
                content=self,
                relative_path="{namespace}/{name}/{version}.tar.gz".format(
                    namespace=self.role.namespace,
                    name=self.role.name,
                    version=self.version
                )
            )
            ca.save()

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
