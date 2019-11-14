from gettext import gettext as _

from django.conf import settings
from rest_framework import serializers

from pulpcore.plugin.serializers import (
    ContentChecksumSerializer,
    ModelSerializer,
    RemoteSerializer,
    RepositorySerializer,
    SingleArtifactContentSerializer,
    RepositoryVersionDistributionSerializer,
)

from .models import (
    AnsibleDistribution,
    AnsibleRemote,
    AnsibleRepository,
    Collection,
    CollectionImport,
    CollectionVersion,
    CollectionRemote,
    Role,
    Tag,
)
from pulp_ansible.app.tasks.utils import parse_collections_requirements_file


class RoleSerializer(SingleArtifactContentSerializer):
    """
    A serializer for Role versions.
    """

    name = serializers.CharField()
    namespace = serializers.CharField()
    version = serializers.CharField()

    def validate(self, data):
        """
        Validates data.

        Args:
            data (dict): User data to validate

        Returns:
            dict: Validated data

        Raises:
            rest_framework.serializers.ValidationError: If invalid data

        """
        data = super().validate(data)
        relative_path = "{namespace}/{name}/{version}.tar.gz".format(
            namespace=data["namespace"], name=data["name"], version=data["version"]
        )
        data["relative_path"] = relative_path
        return data

    class Meta:
        fields = tuple(set(SingleArtifactContentSerializer.Meta.fields) - {"relative_path"}) + (
            "version",
            "name",
            "namespace",
        )
        model = Role


class AnsibleRemoteSerializer(RemoteSerializer):
    """
    A serializer for Ansible Remotes.
    """

    class Meta:
        fields = RemoteSerializer.Meta.fields
        model = AnsibleRemote


class AnsibleRepositorySerializer(RepositorySerializer):
    """
    Serializer for Ansible Repositories.
    """

    class Meta:
        fields = RepositorySerializer.Meta.fields
        model = AnsibleRepository


class CollectionRemoteSerializer(RemoteSerializer):
    """
    A serializer for Collection Remotes.
    """

    requirements_file = serializers.CharField(
        help_text=_("The string version of Collection requirements yaml."),
        required=False,
        allow_null=True,
    )

    def validate(self, data):
        """
        Validate collection remote data.

            - url: to ensure it does not end with slashes.
            - requirements_file: to ensure it is a valid yaml file.

        Args:
            data (dict): User data to validate

        Returns:
            dict: Validated data

        Raises:
            rest_framework.serializers.ValidationError: If the url or requirements_file is invalid

        """
        data = super().validate(data)

        if data.get("requirements_file"):
            parse_collections_requirements_file(data["requirements_file"])

        if data["url"].endswith("/"):
            raise serializers.ValidationError(_("url should not end with '/'"))

        return data

    class Meta:
        fields = RemoteSerializer.Meta.fields + ("requirements_file",)
        model = CollectionRemote


class CollectionOneShotSerializer(serializers.Serializer):
    """
    A serializer for the Collection One Shot Upload API.
    """

    file = serializers.FileField(help_text=_("The Collection tarball."), required=True)

    sha256 = serializers.CharField(
        help_text=_("An optional sha256 checksum of the uploaded file."),
        required=False,
        default=None,
    )

    expected_namespace = serializers.CharField(
        help_text=_(
            "The expected 'namespace' of the Collection to be verified against the "
            "metadata during import."
        ),
        required=False,
        default=None,
    )

    expected_name = serializers.CharField(
        help_text=_(
            "The expected 'name' of the Collection to be verified against the metadata during "
            "import."
        ),
        required=False,
        default=None,
    )

    expected_version = serializers.CharField(
        help_text=_(
            "The expected version of the Collection to be verified against the metadata during "
            "import."
        ),
        required=False,
        default=None,
    )


class AnsibleDistributionSerializer(RepositoryVersionDistributionSerializer):
    """
    Serializer for Ansible Distributions.
    """

    client_url = serializers.SerializerMethodField(
        read_only=True, help_text=_("The URL of a Collection content source.")
    )

    def get_client_url(self, obj):
        """
        Get client_url.
        """
        return "{hostname}/pulp_ansible/galaxy/{base_path}".format(
            hostname=settings.ANSIBLE_API_HOSTNAME, base_path=obj.base_path
        )

    class Meta:
        fields = (
            "pulp_href",
            "pulp_created",
            "base_path",
            "content_guard",
            "name",
            "repository",
            "repository_version",
            "client_url",
        )
        model = AnsibleDistribution


class TagSerializer(serializers.ModelSerializer):
    """
    A serializer for the Tag model.
    """

    class Meta:
        model = Tag
        fields = ["name"]


class TagNestedSerializer(ModelSerializer):
    """
    A serializer for nesting in the CollectionVersion model.
    """

    name = serializers.CharField(help_text=_("The name of the Tag."), read_only=True)

    class Meta:
        model = Tag
        # this serializer is meant to be nested inside CollectionVersion serializer, so it will not
        # have its own endpoint. That's why we need to explicitly define fields to exclude other
        # inherited fields
        fields = ("name",)


class CollectionSerializer(ModelSerializer):
    """
    A serializer for Ansible Collections.
    """

    name = serializers.CharField(help_text=_("The name of the Collection."))
    namespace = serializers.CharField(help_text=_("The namespace of the Collection."))

    class Meta:
        model = Collection
        fields = ("name", "namespace")


class CollectionVersionSerializer(SingleArtifactContentSerializer, ContentChecksumSerializer):
    """
    A serializer for CollectionVersion Content.
    """

    id = serializers.UUIDField(source="pk", help_text="A collection identifier.")

    authors = serializers.ListField(
        help_text=_("A list of the CollectionVersion content's authors."),
        child=serializers.CharField(max_length=64),
    )

    contents = serializers.ListField(
        child=serializers.DictField(), help_text=_("A JSON field with data about the contents.")
    )

    dependencies = serializers.DictField(
        help_text=_(
            "A dict declaring Collections that this collection requires to be installed for it to "
            "be usable."
        )
    )

    description = serializers.CharField(
        help_text=_("A short summary description of the collection."), allow_blank=True
    )

    docs_blob = serializers.DictField(
        help_text=_("A JSON field holding the various documentation blobs in the collection.")
    )

    documentation = serializers.URLField(
        help_text=_("The URL to any online docs."), allow_blank=True, max_length=128
    )

    homepage = serializers.URLField(
        help_text=_("The URL to the homepage of the collection/project."),
        allow_blank=True,
        max_length=128,
    )

    issues = serializers.URLField(
        help_text=_("The URL to the collection issue tracker."), allow_blank=True, max_length=128
    )

    certification = serializers.CharField(help_text=_("Indicates that the version is certified"))

    license = serializers.ListField(
        help_text=_("A list of licenses for content inside of a collection."),
        child=serializers.CharField(max_length=32),
    )

    name = serializers.CharField(help_text=_("The name of the collection."), max_length=32)

    namespace = serializers.CharField(
        help_text=_("The namespace of the collection."), max_length=32
    )

    repository = serializers.URLField(
        help_text=_("The URL of the originating SCM repository."), allow_blank=True, max_length=128
    )

    tags = TagNestedSerializer(many=True, read_only=True)

    version = serializers.CharField(help_text=_("The version of the collection."), max_length=32)

    deprecated = serializers.BooleanField(
        source="collection.deprecated",
        help_text=_("Whether or not the collection has been deprecated."),
        read_only=True,
    )

    class Meta:
        fields = (
            tuple(set(SingleArtifactContentSerializer.Meta.fields) - {"relative_path"})
            + ContentChecksumSerializer.Meta.fields
            + (
                "id",
                "authors",
                "contents",
                "dependencies",
                "description",
                "docs_blob",
                "documentation",
                "homepage",
                "issues",
                "certification",
                "license",
                "name",
                "namespace",
                "repository",
                "tags",
                "version",
                "deprecated",
            )
        )
        model = CollectionVersion


class CollectionImportListSerializer(serializers.ModelSerializer):
    """
    A serializer for a CollectionImport list view.
    """

    id = serializers.UUIDField(source="pk")
    state = serializers.CharField(source="task.state")
    created_at = serializers.DateTimeField(source="task.pulp_created")
    updated_at = serializers.DateTimeField(source="task.pulp_last_updated")
    started_at = serializers.DateTimeField(source="task.started_at")
    finished_at = serializers.DateTimeField(source="task.finished_at")

    class Meta:
        model = CollectionImport
        fields = ("id", "state", "created_at", "updated_at", "started_at", "finished_at")


class CollectionImportDetailSerializer(CollectionImportListSerializer):
    """
    A serializer for a CollectionImport detail view.
    """

    error = serializers.JSONField(source="task.error")
    messages = serializers.JSONField()

    class Meta(CollectionImportListSerializer.Meta):
        fields = CollectionImportListSerializer.Meta.fields + ("error", "messages")
