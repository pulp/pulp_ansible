from logging import getLogger

from django.db import models
from django.contrib.postgres import fields as psql_fields

from pulpcore.plugin.models import Content, Model, Remote, RepositoryVersionDistribution


log = getLogger(__name__)


class Role(Content):
    """
    A content type representing a Role.
    """

    TYPE = "role"

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
        unique_together = ("version", "name", "namespace")


class Collection(Model):
    """A model representing a Collection."""

    TYPE = "collection"

    namespace = models.CharField(max_length=64, editable=False)
    name = models.CharField(max_length=64, editable=False)

    deprecated = models.BooleanField(default=False)

    class Meta:
        unique_together = ("namespace", "name")


class CollectionVersion(Content):
    """
    A content type representing a Collection.

    Fields:

        version (models.CharField): Version string.
        metadata: Artifact metadata in JSON format.
        contents: Contnet items (e.g. roles, modules) provided by
            collection in JSON format.
        quality_score: Total version quality score,
            floating-point number in range [0, 5].

    Relations:

        collection: Reference to a collection model.
    """

    TYPE = "collection_version"

    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, related_name="versions", editable=False
    )
    version = models.CharField(max_length=128, editable=False)

    quality_score = models.FloatField(null=True, editable=False)
    metadata = psql_fields.JSONField(default=dict, editable=False)
    contents = psql_fields.JSONField(default=list, editable=False)

    @property
    def namespace(self):
        """Returns collection namespace name."""
        return self.collection.namespace

    @property
    def name(self):
        """Returns collection name."""
        return self.collection.name

    @property
    def relative_path(self):
        """
        Return the relative path for the ContentArtifact.
        """
        return "{namespace}.{name}.{version}".format(
            namespace=self.namespace, name=self.name, version=self.version
        )

    class Meta:
        unique_together = ("collection", "version")


class AnsibleRemote(Remote):
    """
    A Remote for Ansible content.
    """

    TYPE = "ansible"


class CollectionRemote(Remote):
    """
    A Remote for Collection content.

    Fields:

        whitelist (models.TextField): The whitelist of Collections to sync.
    """

    TYPE = "collection"

    whitelist = models.TextField()


class AnsibleDistribution(RepositoryVersionDistribution):
    """
    A Distribution for Ansible content.
    """

    TYPE = "ansible"
