from logging import getLogger

from django.db import models

from pulpcore.plugin.models import Content, Importer, Publisher


log = getLogger(__name__)


class AnsibleRole(Content):
    """
    A content type respresenting an Ansible Role
    """

    TYPE = 'ansible'

    namespace = models.CharField(max_length=64)
    name = models.CharField(max_length=64)
    version = models.CharField(max_length=128)

    class Meta:
        unique_together = (
            'namespace',
            'name',
            'version'
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
