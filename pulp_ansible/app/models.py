from logging import getLogger

from django.db import models
from django.contrib.postgres import fields as psql_fields
from django.contrib.postgres import search as psql_search
from django.db.models import UniqueConstraint, Q

# NOTE(cutwater): Module pulpcore.plugin.models doesn't provide Task model
from pulpcore.app.models import Task
from pulpcore.plugin.models import (
    Content,
    Model,
    Remote,
    Repository,
    RepositoryVersionDistribution,
)

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
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("version", "name", "namespace")


class Collection(Model):
    """A model representing a Collection."""

    namespace = models.CharField(max_length=64, editable=False)
    name = models.CharField(max_length=64, editable=False)

    deprecated = models.BooleanField(default=False)

    class Meta:
        unique_together = ("namespace", "name")


class CollectionImport(models.Model):
    """A model representing a collection import task details."""

    task = models.OneToOneField(
        Task, on_delete=models.CASCADE, editable=False, related_name="+", primary_key=True
    )
    messages = psql_fields.JSONField(default=list, editable=False)

    class Meta:
        ordering = ["task__pulp_created"]

    def add_log_record(self, log_record):
        """
        Records a single log message but does not save the CollectionImport object.

        Args:
            log_record(logging.LogRecord): The logging record to record on messages.

        """
        self.messages.append(
            {"message": log_record.msg, "level": log_record.levelname, "time": log_record.created}
        )


class Tag(Model):
    """A model representing a Tag.

    Fields:

        name (models.CharField): The Tag's name.
    """

    name = models.CharField(max_length=32, unique=True, editable=False)

    def __str__(self):
        """Returns tag name."""
        return self.name


class CollectionVersion(Content):
    """
    A content type representing a CollectionVersion.

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
        is_highest (models.BooleanField): Indicates that the version is the highest one
            in the collection.
        certification (models.CharField): Enum with certification status.

    Relations:

        collection (models.ForeignKey): Reference to a collection model.
        tag (models.ManyToManyField): A symmetric reference to the Tag objects.
    """

    TYPE = "collection_version"

    CERTIFICATION_CHOICES = [
        ("certified", "certified"),
        ("not_certified", "not_certified"),
        ("needs_review", "needs_review"),
    ]

    # Data Fields
    authors = psql_fields.ArrayField(models.CharField(max_length=64), default=list, editable=False)
    contents = psql_fields.JSONField(default=list, editable=False)
    dependencies = psql_fields.JSONField(default=dict, editable=False)
    description = models.TextField(default="", blank=True, editable=False)
    docs_blob = psql_fields.JSONField(default=dict, editable=False)
    documentation = models.URLField(default="", blank=True, max_length=128, editable=False)
    homepage = models.URLField(default="", blank=True, max_length=128, editable=False)
    issues = models.URLField(default="", blank=True, max_length=128, editable=False)
    license = psql_fields.ArrayField(models.CharField(max_length=32), default=list, editable=False)
    name = models.CharField(max_length=64, editable=False)
    namespace = models.CharField(max_length=32, editable=False)
    repository = models.URLField(default="", blank=True, max_length=128, editable=False)
    version = models.CharField(max_length=32, editable=False)

    is_highest = models.BooleanField(editable=False, default=False)
    certification = models.CharField(
        max_length=13, choices=CERTIFICATION_CHOICES, default="needs_review"
    )

    # Foreign Key Fields
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, related_name="versions", editable=False
    )
    tags = models.ManyToManyField(Tag, editable=False)

    # Search Fields
    search_vector = psql_search.SearchVectorField(default="")

    @property
    def relative_path(self):
        """
        Return the relative path for the ContentArtifact.
        """
        return "{namespace}.{name}.{version}".format(
            namespace=self.namespace, name=self.name, version=self.version
        )

    def save(self, *args, **kwargs):
        """
        Validates certification before save.

        """
        certification_choices = [value for key, value in self.CERTIFICATION_CHOICES]
        if self.certification not in certification_choices:
            raise ValueError(
                "Invalid certification value: '{value}'".format(value=self.certification)
            )

        super().save(*args, **kwargs)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("namespace", "name", "version")
        constraints = [
            UniqueConstraint(
                fields=("collection", "is_highest"),
                name="unique_is_highest",
                condition=Q(is_highest=True),
            )
        ]


class AnsibleRemote(Remote):
    """
    A Remote for Ansible content.
    """

    TYPE = "ansible"

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class AnsibleRepository(Repository):
    """
    Repository for "ansible" content.
    """

    TYPE = "ansible"

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class CollectionRemote(Remote):
    """
    A Remote for Collection content.
    """

    TYPE = "collection"

    requirements_file = models.TextField(null=True, max_length=255)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class AnsibleDistribution(RepositoryVersionDistribution):
    """
    A Distribution for Ansible content.
    """

    TYPE = "ansible"

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
