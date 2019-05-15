from logging import getLogger

from django.db import models

from pulpcore.plugin.models import Content, Remote, RepositoryVersionDistribution


log = getLogger(__name__)


class Role(Content):
    """
    A content type representing a Role.
    """

    TYPE = 'role'

    namespace = models.CharField(max_length=64)
    name = models.CharField(max_length=64)
    version = models.CharField(max_length=128)

    @property
    def relative_path(self):
        """
        Return the relative path of the ContentArtifact.
        """
        return self.contentartifact_set.get().relative_path

    class Meta:
        unique_together = (
            'version',
            'name',
            'namespace',
        )


class Collection(Content):
    """
    A content type representing a Collection.
    """

    TYPE = 'collection'

    namespace = models.CharField(max_length=64)
    name = models.CharField(max_length=64)
    version = models.CharField(max_length=128)

    @property
    def relative_path(self):
        """
        Return the relative path for the ContentArtifact.
        """
        return '{namespace}.{name}.{version}'.format(namespace=self.namespace, name=self.name,
                                                     version=self.version)

    class Meta:
        unique_together = (
            'namespace',
            'name',
            'version'
        )


class AnsibleRemote(Remote):
    """
    A Remote for Ansible content.
    """

    TYPE = 'ansible'


class AnsibleDistribution(RepositoryVersionDistribution):
    """
    A Distribution for Ansible content.
    """

    TYPE = 'ansible'
