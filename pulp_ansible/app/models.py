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

    namespace = models.CharField(max_length=64, editable=False)
    name = models.CharField(max_length=64, editable=False)

    deprecated = models.BooleanField(default=False)

    class Meta:
        unique_together = ("namespace", "name")


class Tag(Model):
    """A model representing a Tag.

    Fields:

        name (models.CharField): The Tag's name.
    """

    name = models.CharField(max_length=32, unique=True, editable=False)


class CollectionVersion(Content):
    """
    A content type representing a Collection.

    This model is primarily designed to adhere to the data format for Collection content. That spec
    is here: https://docs.ansible.com/ansible/devel/dev_guide/collections_galaxy_meta.html

    Fields:

        authors (psql_fields.ArrayField): A list of the CollectionVersion content's authors.
        contents (psql_fields.JSONField): A JSON field with data about the contents.
        dependencies (psql_fields.JSONField): A dict declaring Collections that this collection
            requires to be installed for it to be usable.
        description (models.TextField): A short summary description of the collection.
        docs_blob (psql_fields.JSONField): A JSON field holding the various documentation blobs in
            the collection.
        documentation (models.URLField): The URL to any online docs.
        homepage (models.URLField): The URL to the homepage of the collection/project.
        issues (models.URLField): The URL to the collection issue tracker.
        license (psql_fields.ArrayField): A list of licenses for content inside of a collection.
        name (models.CharField): The name of the collection.
        namespace (models.CharField): The namespace of the collection.
        repository (models.URLField): The URL of the originating SCM repository.
        version (models.CharField): The version of the collection.

    Relations:

        collection (models.ForeignKey): Reference to a collection model.
        tag (models.ManyToManyField): A symmetric reference to the Tag objects.
    """

    TYPE = "collection_version"

    authors = psql_fields.ArrayField(models.CharField(max_length=64), default=list, editable=False)
    contents = psql_fields.JSONField(default=list, editable=False)
    dependencies = psql_fields.JSONField(default=dict, editable=False)
    description = models.TextField(default="", blank=True, editable=False)
    docs_blob = psql_fields.JSONField(default=dict, editable=False)
    documentation = models.URLField(default="", blank=True, max_length=128, editable=False)
    homepage = models.URLField(default="", blank=True, max_length=128, editable=False)
    issues = models.URLField(default="", blank=True, max_length=128, editable=False)
    license = psql_fields.ArrayField(models.CharField(max_length=32), default=list, editable=False)
    name = models.CharField(max_length=32, editable=False)
    namespace = models.CharField(max_length=32, editable=False)
    repository = models.URLField(default="", blank=True, max_length=128, editable=False)
    version = models.CharField(max_length=32, editable=False)

    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, related_name="versions", editable=False
    )
    tags = models.ManyToManyField(Tag, editable=False)

    @property
    def relative_path(self):
        """
        Return the relative path for the ContentArtifact.
        """
        return "{namespace}.{name}.{version}".format(
            namespace=self.namespace, name=self.name, version=self.version
        )

    class Meta:
        unique_together = ("namespace", "name", "version")


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
