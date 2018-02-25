from logging import getLogger

from django.db import models

from pulpcore.plugin.models import Content, Model, Importer, Publisher


log = getLogger(__name__)


class AnsibleRole(Model):
    """
    A model representing an Ansible Role
    """

    namespace = models.CharField(max_length=64)
    name = models.CharField(max_length=64)

    class Meta:
        unique_together = (
            'namespace',
            'name'
        )


class AnsibleRoleVersion(Content):
    """
    A content type representing an Ansible Role version
    """

    TYPE = 'ansible'

    version = models.CharField(max_length=128)
    role = models.ForeignKey(AnsibleRole, on_delete=models.PROTECT)

    @property
    def name(self):
        return self.role.name

    @property
    def namespace(self):
        return self.role.namespace

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


class AnsibleImporter(Importer):
    """
    An Importer for Ansible content
    """

    TYPE = 'ansible'
