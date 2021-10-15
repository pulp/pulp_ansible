from gettext import gettext as _

from django.conf import settings
from jsonschema import Draft7Validator
from rest_framework import serializers

from pulpcore.plugin.models import Artifact, PulpTemporaryFile
from pulpcore.plugin.serializers import (
    ContentChecksumSerializer,
    ModelSerializer,
    RemoteSerializer,
    RepositorySerializer,
    RepositorySyncURLSerializer,
    SingleArtifactContentSerializer,
    SingleArtifactContentUploadSerializer,
    SingleContentArtifactField,
    DistributionSerializer,
    RepositoryVersionRelatedField,
    validate_unknown_fields,
)
from rest_framework.exceptions import ValidationError

from .models import (
    AnsibleDistribution,
    GitRemote,
    RoleRemote,
    AnsibleRepository,
    Collection,
    CollectionImport,
    CollectionVersion,
    CollectionRemote,
    Role,
    Tag,
)
from pulp_ansible.app.schema import COPY_CONFIG_SCHEMA
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


class RoleRemoteSerializer(RemoteSerializer):
    """
    A serializer for Ansible Remotes.
    """

    class Meta:
        fields = RemoteSerializer.Meta.fields
        model = RoleRemote


class GitRemoteSerializer(RemoteSerializer):
    """
    A serializer for Git Collection Remotes.
    """

    metadata_only = serializers.BooleanField(
        help_text=_(
            "If True, only metadata about the content will be stored in Pulp. Clients will "
            "retrieve content from the remote URL."
        ),
        required=False,
    )
    git_ref = serializers.CharField(
        help_text=_("A git ref. e.g.: branch, tag, or commit sha."),
        required=False,
    )

    class Meta:
        model = GitRemote
        fields = tuple(set(RemoteSerializer.Meta.fields) - {"policy"}) + (
            "metadata_only",
            "git_ref",
        )


class AnsibleRepositorySerializer(RepositorySerializer):
    """
    Serializer for Ansible Repositories.
    """

    last_synced_metadata_time = serializers.DateTimeField(
        help_text=_("Last synced metadata time."), allow_null=True, required=False
    )

    class Meta:
        fields = RepositorySerializer.Meta.fields + ("last_synced_metadata_time",)
        model = AnsibleRepository


class AnsibleRepositorySyncURLSerializer(RepositorySyncURLSerializer):
    """
    Serializer for Ansible Repository Sync URL.
    """

    optimize = serializers.BooleanField(
        help_text=_("Whether to optimize sync or not."), default=True
    )

    class Meta:
        fields = RepositorySerializer.Meta.fields + ("optimize",)
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
    auth_url = serializers.CharField(
        help_text=_("The URL to receive a session token from, e.g. used with Automation Hub."),
        allow_null=True,
        required=False,
        max_length=255,
    )
    token = serializers.CharField(
        help_text=_(
            "The token key to use for authentication. See https://docs.ansible.com/ansible/"
            "latest/user_guide/collections_using.html#configuring-the-ansible-galaxy-client"
            "for more details"
        ),
        allow_null=True,
        required=False,
        max_length=2000,
    )

    sync_dependencies = serializers.BooleanField(
        help_text=_("Sync dependencies for collections specified via requirements file"),
        allow_null=True,
        default=True,
    )

    def validate(self, data):
        """
        Validate collection remote data.

            - url: to ensure it ends with slashes.
            - requirements_file: to ensure it is a valid yaml file.

        Args:
            data (dict): User data to validate

        Returns:
            dict: Validated data

        Raises:
            rest_framework.serializers.ValidationError: If the url or requirements_file is invalid

        """

        def _validate_url(url):
            """Based on https://git.io/JTMAA."""
            if not url.endswith("/") and url != "https://galaxy.ansible.com":
                raise serializers.ValidationError(
                    _("Invalid URL {url}. Ensure the URL ends '/'.").format(url=url)
                )

        data = super().validate(data)

        if data.get("url"):
            _validate_url(data["url"])

        if data.get("requirements_file"):
            collections = parse_collections_requirements_file(data["requirements_file"])
            for collection in collections:
                if collection[2]:
                    _validate_url(collection[2])

        has_token = "token" in data or getattr(self.instance, "token", False)
        if data.get("auth_url") and not has_token:
            raise serializers.ValidationError(
                _("When specifying 'auth_url' you must also specify 'token'.")
            )

        return data

    class Meta:
        fields = RemoteSerializer.Meta.fields + (
            "requirements_file",
            "auth_url",
            "token",
            "sync_dependencies",
        )
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


class AnsibleDistributionSerializer(DistributionSerializer):
    """
    Serializer for Ansible Distributions.
    """

    client_url = serializers.SerializerMethodField(
        read_only=True, help_text=_("The URL of a Collection content source.")
    )
    repository_version = RepositoryVersionRelatedField(
        required=False, help_text=_("RepositoryVersion to be served"), allow_null=True
    )

    def get_client_url(self, obj) -> str:
        """
        Get client_url.
        """
        return "{hostname}/pulp_ansible/galaxy/{base_path}/".format(
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
            "pulp_labels",
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


class CollectionVersionUploadSerializer(SingleArtifactContentUploadSerializer):
    """
    A serializer for CollectionVersion Content.
    """

    name = serializers.CharField(help_text=_("The name of the collection."), max_length=64)

    namespace = serializers.CharField(
        help_text=_("The namespace of the collection."), max_length=64
    )

    version = serializers.CharField(help_text=_("The version of the collection."), max_length=128)

    def validate(self, data):
        """Validate that we have a file or can create one."""
        if "artifact" in data:
            raise serializers.ValidationError(_("Only 'file' may be specified."))

        if "request" not in self.context:
            data = self.deferred_validate(data)

        sha256 = data["file"].hashers["sha256"].hexdigest()
        artifact = Artifact.objects.filter(sha256=sha256).first()
        if artifact:
            ValidationError(_("Artifact already exists"))
        temp_file = PulpTemporaryFile.init_and_validate(data.pop("file"))
        temp_file.save()
        data["temp_file_pk"] = str(temp_file.pk)

        return data

    class Meta:
        fields = tuple(
            set(SingleArtifactContentUploadSerializer.Meta.fields) - {"artifact", "relative_path"}
        ) + (
            "name",
            "namespace",
            "version",
        )
        model = CollectionVersion


class CollectionVersionSerializer(SingleArtifactContentSerializer, ContentChecksumSerializer):
    """
    A serializer for CollectionVersion Content.
    """

    artifact = SingleContentArtifactField(
        help_text=_("Artifact file representing the physical content"),
        required=False,
    )

    id = serializers.UUIDField(source="pk", help_text="A collection identifier.")

    authors = serializers.ListField(
        help_text=_("A list of the CollectionVersion content's authors."),
        child=serializers.CharField(max_length=64),
    )

    contents = serializers.JSONField(help_text=_("A JSON field with data about the contents."))

    dependencies = serializers.JSONField(
        help_text=_(
            "A dict declaring Collections that this collection requires to be installed for it to "
            "be usable."
        )
    )

    description = serializers.CharField(
        help_text=_("A short summary description of the collection."), allow_blank=True
    )

    docs_blob = serializers.JSONField(
        help_text=_("A JSON field holding the various documentation blobs in the collection.")
    )

    manifest = serializers.JSONField(help_text=_("A JSON field holding MANIFEST.json data."))

    files = serializers.JSONField(help_text=_("A JSON field holding FILES.json data."))

    documentation = serializers.CharField(
        help_text=_("The URL to any online docs."), allow_blank=True, max_length=2000
    )

    homepage = serializers.CharField(
        help_text=_("The URL to the homepage of the collection/project."),
        allow_blank=True,
        max_length=2000,
    )

    issues = serializers.CharField(
        help_text=_("The URL to the collection issue tracker."), allow_blank=True, max_length=2000
    )

    license = serializers.ListField(
        help_text=_("A list of licenses for content inside of a collection."),
        child=serializers.CharField(max_length=32),
    )

    name = serializers.CharField(help_text=_("The name of the collection."), max_length=64)

    namespace = serializers.CharField(
        help_text=_("The namespace of the collection."), max_length=64
    )

    repository = serializers.CharField(
        help_text=_("The URL of the originating SCM repository."), allow_blank=True, max_length=2000
    )

    tags = TagNestedSerializer(many=True, read_only=True)

    version = serializers.CharField(help_text=_("The version of the collection."), max_length=128)

    requires_ansible = serializers.CharField(
        help_text=_(
            "The version of Ansible required to use the collection. "
            "Multiple versions can be separated with a comma."
        ),
        allow_null=True,
        required=False,
        max_length=255,
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
                "manifest",
                "files",
                "documentation",
                "homepage",
                "issues",
                "license",
                "name",
                "namespace",
                "repository",
                "tags",
                "version",
                "requires_ansible",
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
    finished_at = serializers.DateTimeField(source="task.finished_at", required=False)

    class Meta:
        model = CollectionImport
        fields = ("id", "state", "created_at", "updated_at", "started_at", "finished_at")


class CollectionImportDetailSerializer(CollectionImportListSerializer):
    """
    A serializer for a CollectionImport detail view.
    """

    error = serializers.JSONField(source="task.error", required=False)
    messages = serializers.JSONField()

    class Meta(CollectionImportListSerializer.Meta):
        fields = CollectionImportListSerializer.Meta.fields + ("error", "messages")


class CopySerializer(serializers.Serializer):
    """
    A serializer for Content Copy API.
    """

    config = serializers.JSONField(
        help_text=_("A JSON document describing sources, destinations, and content to be copied"),
    )

    def validate(self, data):
        """
        Validate that the Serializer contains valid data.

        Set the AnsibleRepository based on the RepositoryVersion if only the latter is provided.
        Set the RepositoryVersion based on the AnsibleRepository if only the latter is provided.
        Convert the human-friendly names of the content types into what Pulp needs to query on.
        """
        super().validate(data)

        if hasattr(self, "initial_data"):
            validate_unknown_fields(self.initial_data, self.fields)

        if "config" in data:
            validator = Draft7Validator(COPY_CONFIG_SCHEMA)

            err = []
            for error in sorted(validator.iter_errors(data["config"]), key=str):
                err.append(error.message)
            if err:
                raise serializers.ValidationError(
                    _("Provided copy criteria is invalid:'{}'".format(err))
                )

        return data
