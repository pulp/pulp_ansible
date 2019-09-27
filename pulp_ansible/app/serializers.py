from gettext import gettext as _

from django.conf import settings
from django.db import transaction
from galaxy_importer.collection import CollectionFilename, import_collection
from rest_framework import serializers

from pulpcore.plugin.serializers import (
    ContentChecksumSerializer,
    ModelSerializer,
    RemoteSerializer,
    SingleArtifactContentUploadSerializer,
    RepositoryVersionDistributionSerializer,
)

from .models import (
    AnsibleDistribution,
    AnsibleRemote,
    Collection,
    CollectionImport,
    CollectionVersion,
    CollectionRemote,
    Role,
    Tag,
)
from pulp_ansible.app.tasks.utils import parse_collections_requirements_file


class RoleSerializer(SingleArtifactContentUploadSerializer):
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
        fields = tuple(
            set(SingleArtifactContentUploadSerializer.Meta.fields) - {"relative_path"}
        ) + ("version", "name", "namespace")
        model = Role


class AnsibleRemoteSerializer(RemoteSerializer):
    """
    A serializer for Ansible Remotes.
    """

    class Meta:
        fields = RemoteSerializer.Meta.fields
        model = AnsibleRemote


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
            "_href",
            "_created",
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


class CollectionVersionSerializer(SingleArtifactContentUploadSerializer, ContentChecksumSerializer):
    """
    A serializer for CollectionVersion Content.
    """

    id = serializers.UUIDField(source="pk", help_text="A collection identifier.", read_only=True)

    authors = serializers.ListField(
        help_text=_("A list of the CollectionVersion content's authors."),
        child=serializers.CharField(max_length=64),
        read_only=True,
    )

    contents = serializers.ListField(
        child=serializers.DictField(),
        help_text=_("A JSON field with data about the contents."),
        read_only=True,
    )

    dependencies = serializers.DictField(
        help_text=_(
            "A dict declaring Collections that this collection requires to be installed for it to "
            "be usable."
        ),
        read_only=True,
    )

    description = serializers.CharField(
        help_text=_("A short summary description of the collection."),
        allow_blank=True,
        read_only=True,
    )

    docs_blob = serializers.DictField(
        help_text=_("A JSON field holding the various documentation blobs in the collection."),
        read_only=True,
    )

    documentation = serializers.URLField(
        help_text=_("The URL to any online docs."), allow_blank=True, max_length=128, read_only=True
    )

    homepage = serializers.URLField(
        help_text=_("The URL to the homepage of the collection/project."),
        allow_blank=True,
        max_length=128,
        read_only=True,
    )

    issues = serializers.URLField(
        help_text=_("The URL to the collection issue tracker."),
        allow_blank=True,
        max_length=128,
        read_only=True,
    )

    is_certified = serializers.BooleanField(
        help_text=_("Indicates that the version is certified"), read_only=True
    )

    license = serializers.ListField(
        help_text=_("A list of licenses for content inside of a collection."),
        child=serializers.CharField(max_length=32),
        read_only=True,
    )

    name = serializers.CharField(
        help_text=_("The name of the collection."), max_length=32, read_only=True
    )

    namespace = serializers.CharField(
        help_text=_("The namespace of the collection."), max_length=32, read_only=True
    )

    tags = TagNestedSerializer(many=True, read_only=True)

    version = serializers.CharField(
        help_text=_("The version of the collection."), max_length=32, read_only=True
    )

    expected_namespace = serializers.CharField(
        help_text=_(
            "The expected 'namespace' of the Collection to be verified against the "
            "metadata during import."
        ),
        required=False,
        write_only=True,
        default=None,
    )

    expected_name = serializers.CharField(
        help_text=_(
            "The expected 'name' of the Collection to be verified against the metadata during "
            "import."
        ),
        required=False,
        write_only=True,
        default=None,
    )

    expected_version = serializers.CharField(
        help_text=_(
            "The expected version of the Collection to be verified against the metadata during "
            "import."
        ),
        required=False,
        write_only=True,
        default=None,
    )

    def deferred_validate(self, data):
        """
        Validates data.

        Args:
            data (dict): User data to validate

        Returns:
            dict: Validated data

        Raises:
            rest_framework.serializers.ValidationError: If invalid data

        """
        data = super().deferred_validate(data)
        artifact = data["artifact"]

        expected_namespace = data.get("expected_namespace")
        expected_name = data.get("expected_name")
        expected_version = data.get("expected_version")
        filename = CollectionFilename(expected_namespace, expected_name, expected_version)

        with artifact.file.file.open() as artifact_file:
            importer_result = import_collection(file=artifact_file, filename=filename)

        collection_info = importer_result["metadata"]

        # Remove fields not used by this model
        collection_info.pop("license_file")
        collection_info.pop("readme")

        # the importer returns many None values. Letting the defaults in the model prevail
        for key in ["description", "documentation", "homepage", "issues", "repository"]:
            if collection_info[key] is None:
                collection_info.pop(key)

        collection_info.update(
            dict(contents=importer_result["contents"], docs_blob=importer_result["docs_blob"])
        )
        data.update(collection_info)

        collection_version = CollectionVersion.objects.filter(
            namespace=data["namespace"], name=data["name"], version=data["version"]
        )

        if collection_version.exists():
            raise serializers.ValidationError(
                _(
                    "There is already a collection_version with name '{name}', namespace "
                    "'{namespace}' and version '{version}'."
                ).format(name=data["name"], namespace=data["namespace"], version=data["version"])
            )

        return data

    def create(self, validated_data):
        """
        Create a CollectionVersion.

        Overriding default create() to write the tags nested field

        Args:
            validated_data (dict): Data used to create the CollectionVersion

        Returns:
            models.CollectionVersion: The created CollectionVersion

        """
        tags = validated_data.pop("tags")
        fields = [f.name for f in CollectionVersion._meta.get_fields()]
        data = {}
        for key, value in validated_data.items():
            if key in fields:
                data[key] = value

        with transaction.atomic():
            collection, created = Collection.objects.get_or_create(
                namespace=validated_data["namespace"], name=validated_data["name"]
            )

            collection_version = CollectionVersion.objects.create(collection=collection, **data)

            for name in tags:
                tag, created = Tag.objects.get_or_create(name=name)
                collection_version.tags.add(tag)

        return collection_version

    class Meta:
        fields = (
            SingleArtifactContentUploadSerializer.Meta.fields
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
                "is_certified",
                "license",
                "name",
                "namespace",
                "tags",
                "version",
                "expected_name",
                "expected_namespace",
                "expected_version",
            )
        )
        model = CollectionVersion


class CollectionImportListSerializer(serializers.ModelSerializer):
    """
    A serializer for a CollectionImport list view.
    """

    id = serializers.UUIDField(source="pk")
    state = serializers.CharField(source="task.state")
    created_at = serializers.DateTimeField(source="task._created")
    updated_at = serializers.DateTimeField(source="task._last_updated")
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
