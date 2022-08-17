from gettext import gettext as _

from django.conf import settings
from jsonschema import Draft7Validator
from rest_framework import serializers

from pulpcore.plugin.models import Artifact, SigningService
from pulpcore.plugin.serializers import (
    DetailRelatedField,
    ContentChecksumSerializer,
    ModelSerializer,
    NoArtifactContentUploadSerializer,
    RelatedField,
    RemoteSerializer,
    RepositorySerializer,
    RepositorySyncURLSerializer,
    SingleArtifactContentSerializer,
    SingleArtifactContentUploadSerializer,
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
    CollectionVersionSignature,
    CollectionRemote,
    Role,
    Tag,
)
from pulp_ansible.app.schema import COPY_CONFIG_SCHEMA
from pulp_ansible.app.tasks.utils import (
    parse_collections_requirements_file,
    parse_collection_filename,
)
from pulp_ansible.app.tasks.signature import verify_signature_upload
from pulp_ansible.app.tasks.upload import process_collection_artifact, finish_collection_upload


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
    gpgkey = serializers.CharField(
        help_text="Gpg public key to verify collection signatures against",
        required=False,
        allow_null=True,
    )

    class Meta:
        fields = RepositorySerializer.Meta.fields + (
            "last_synced_metadata_time",
            "gpgkey",
        )
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


class AnsibleRepositoryRebuildSerializer(serializers.Serializer):
    """
    Serializer for Ansible Repository Rebuild.
    """

    namespace = serializers.CharField(
        required=False,
        allow_null=True,
    )
    name = serializers.CharField(
        required=False,
        allow_null=True,
    )
    version = serializers.CharField(
        required=False,
        allow_null=True,
    )


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
        write_only=True,
    )

    sync_dependencies = serializers.BooleanField(
        help_text=_("Sync dependencies for collections specified via requirements file"),
        default=True,
    )

    signed_only = serializers.BooleanField(
        help_text=_("Sync only collections that have a signature"),
        default=False,
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
            "signed_only",
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

    def validate(self, data):
        """Ensure duplicate artifact isn't uploaded."""
        data = super().validate(data)
        sha256 = data["file"].hashers["sha256"].hexdigest()
        artifact = Artifact.objects.filter(sha256=sha256).first()
        if artifact:
            raise ValidationError(_("Artifact already exists"))
        return data


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
    A serializer with the logic necessary to upload a CollectionVersion.

    Used in ``.viewsets.CollectionVersionViewSet`` and ``.galaxy.v3.views.CollectionUploadViewSet``
    to perform the creation and validation of a CollectionVersion and add to repository if
    necessary. This serializer is meant to be compliant with
    ``pulpcore.plugin.viewsets.SingleArtifactContentUploadViewSet`` and thus follows these steps on
    creation:

    1. ``SingleArtifactContentUploadViewSet.create()`` calls ``validate()`` with request in context
    2. Task payload is created, converting uploaded-file (if present) to an artifact
    3. ``pulpcore.plugin.tasks.general_create`` is dispatched with this serializer, the task payload
        and a deferred context determine by the viewset (default an empty context).
    4. ``general_create`` calls ``validate()`` again with deferred context now.
        ``deferred_validate()`` is now called and the upload object (if present) is converted to an
        artifact.
    5. ``general_create`` calls ``save()`` which will call ``create()``. ``create`` uses the
        validated data to create and save the CollectionVersion. If repository is specified the
        CollectionVersion is then added to the repository.
    """

    sha256 = serializers.CharField(
        help_text=_("An optional sha256 checksum of the uploaded file."),
        required=False,
        write_only=True,
    )

    expected_name = serializers.CharField(
        help_text=_("The name of the collection."),
        max_length=64,
        required=False,
        write_only=True,
    )

    expected_namespace = serializers.CharField(
        help_text=_("The namespace of the collection."),
        max_length=64,
        required=False,
        write_only=True,
    )

    expected_version = serializers.CharField(
        help_text=_("The version of the collection."),
        max_length=128,
        required=False,
        write_only=True,
    )

    def validate(self, data):
        """Check and set the namespace, name & version."""
        fields = ("namespace", "name", "version")
        if not all((f"expected_{x}" in data for x in fields)):
            if not ("file" in data or "filename" in self.context):
                raise ValidationError(
                    _(
                        "expected_namespace, expected_name, and expected_version must be "
                        "specified when using artifact or upload objects"
                    )
                )
            filename = self.context.get("filename") or data["file"].name
            try:
                collection = parse_collection_filename(filename)
            except ValueError:
                raise ValidationError(
                    _("Failed to parse Collection file upload '{}'").format(filename)
                )
            data["expected_namespace"] = collection.namespace
            data["expected_name"] = collection.name
            data["expected_version"] = collection.version

        if CollectionVersion.objects.filter(**{f: data[f"expected_{f}"] for f in fields}).exists():
            raise ValidationError(
                _("Collection {}.{}-{} already exists").format(
                    data["expected_namespace"], data["expected_name"], data["expected_version"]
                )
            )

        # Super will call deferred_validate on second call in task context
        return super().validate(data)

    def deferred_validate(self, data):
        """Import the CollectionVersion extracting the metadata from its artifact."""
        # Call super to ensure that data contains artifact
        data = super().deferred_validate(data)
        artifact = data.get("artifact")
        if (sha256 := data.pop("sha256", None)) and sha256 != artifact.sha256:
            raise ValidationError(_("Expected sha256 did not match uploaded artifact's sha256"))

        collection_info = process_collection_artifact(
            artifact=artifact,
            namespace=data.pop("expected_namespace"),
            name=data.pop("expected_name"),
            version=data.pop("expected_version"),
        )
        # repository field clashes
        collection_info["origin_repository"] = collection_info.pop("repository", None)
        data.update(collection_info)

        return data

    def create(self, validated_data):
        """Final step in creating the CollectionVersion."""
        tags = validated_data.pop("tags")
        origin_repository = validated_data.pop("origin_repository")
        # Create CollectionVersion from its metadata and adds to repository if specified
        content = super().create(validated_data)

        # Now add tags and update latest CollectionVersion
        finish_collection_upload(content, tags=tags, origin_repository=origin_repository)

        return content

    class Meta:
        fields = tuple(
            set(SingleArtifactContentUploadSerializer.Meta.fields) - {"relative_path"}
        ) + (
            "sha256",
            "expected_name",
            "expected_namespace",
            "expected_version",
        )
        model = CollectionVersion


class CollectionVersionSerializer(ContentChecksumSerializer, CollectionVersionUploadSerializer):
    """
    A serializer for CollectionVersion Content.
    """

    id = serializers.UUIDField(source="pk", help_text="A collection identifier.", read_only=True)

    authors = serializers.ListField(
        help_text=_("A list of the CollectionVersion content's authors."),
        child=serializers.CharField(max_length=64),
        read_only=True,
    )

    contents = serializers.JSONField(
        help_text=_("A JSON field with data about the contents."), read_only=True
    )

    dependencies = serializers.JSONField(
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

    docs_blob = serializers.JSONField(
        help_text=_("A JSON field holding the various documentation blobs in the collection."),
        read_only=True,
    )

    manifest = serializers.JSONField(
        help_text=_("A JSON field holding MANIFEST.json data."), read_only=True
    )

    files = serializers.JSONField(
        help_text=_("A JSON field holding FILES.json data."), read_only=True
    )

    documentation = serializers.CharField(
        help_text=_("The URL to any online docs."),
        allow_blank=True,
        max_length=2000,
        read_only=True,
    )

    homepage = serializers.CharField(
        help_text=_("The URL to the homepage of the collection/project."),
        allow_blank=True,
        max_length=2000,
        read_only=True,
    )

    issues = serializers.CharField(
        help_text=_("The URL to the collection issue tracker."),
        allow_blank=True,
        max_length=2000,
        read_only=True,
    )

    license = serializers.ListField(
        help_text=_("A list of licenses for content inside of a collection."),
        child=serializers.CharField(max_length=32),
        read_only=True,
    )

    name = serializers.CharField(
        help_text=_("The name of the collection."), max_length=64, read_only=True
    )

    namespace = serializers.CharField(
        help_text=_("The namespace of the collection."), max_length=64, read_only=True
    )

    origin_repository = serializers.CharField(
        help_text=_("The URL of the originating SCM repository."),
        source="repository",
        allow_blank=True,
        max_length=2000,
        read_only=True,
    )

    tags = TagNestedSerializer(many=True, read_only=True)

    version = serializers.CharField(
        help_text=_("The version of the collection."), max_length=128, read_only=True
    )

    requires_ansible = serializers.CharField(
        help_text=_(
            "The version of Ansible required to use the collection. "
            "Multiple versions can be separated with a comma."
        ),
        allow_null=True,
        read_only=True,
        max_length=255,
    )

    creating = True

    def validate(self, data):
        """Run super() validate if creating, else return data."""
        # This validation is for creating CollectionVersions
        if not self.creating or self.instance:
            return data
        return super().validate(data)

    def is_valid(self, raise_exception=False):
        """
        Allow this serializer to be used for validating before saving a model.

        See Validating Models:
            https://docs.pulpproject.org/pulpcore/plugins/plugin-writer/concepts/index.html
        """
        write_fields = set(CollectionVersionUploadSerializer.Meta.fields) - {"pulp_created"}
        if hasattr(self, "initial_data"):
            if any((x in self.initial_data for x in self.Meta.read_fields)):
                # Pop shared fields: artifact & repository
                artifact = self.initial_data.pop("artifact", None)
                repository = self.initial_data.pop("repository", None)
                if any((x in self.initial_data for x in write_fields)):
                    if raise_exception:
                        raise ValidationError(
                            _("Read and write fields can not be used at the same time")
                        )
                    return False
                # Only read fields set, change each one from read_only so they are validated
                for name, field in self.fields.items():
                    if name in self.Meta.read_fields:
                        field.read_only = False
                # Put back in shared fields
                if artifact is not None:
                    self.initial_data["artifact"] = artifact
                if repository is not None:
                    self.initial_data["origin_repository"] = repository
                self.creating = False

        return super().is_valid(raise_exception=raise_exception)

    class Meta:
        read_fields = (
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
            "origin_repository",
            "tags",
            "version",
            "requires_ansible",
        )
        fields = (
            CollectionVersionUploadSerializer.Meta.fields
            + ContentChecksumSerializer.Meta.fields
            + read_fields
        )
        model = CollectionVersion


class CollectionVersionSignatureSerializer(NoArtifactContentUploadSerializer):
    """
    A serializer for signature models.
    """

    signed_collection = DetailRelatedField(
        help_text=_("The content this signature is pointing to."),
        view_name_pattern=r"content(-.*/.*)-detail",
        queryset=CollectionVersion.objects.all(),
    )
    pubkey_fingerprint = serializers.CharField(
        help_text=_("The fingerprint of the public key."),
        read_only=True,
    )
    signing_service = RelatedField(
        help_text=_("The signing service used to create the signature."),
        view_name="signing-services-detail",
        read_only=True,
        allow_null=True,
    )

    def __init__(self, *args, **kwargs):
        """Ensure `file` field is required."""
        super().__init__(*args, **kwargs)
        self.fields["file"].required = True

    def validate(self, data):
        """
        Verify the signature is valid before creating it.
        """
        data = super().validate(data)

        if "request" not in self.context:
            # Validate is called twice, first on the viewset, and second on the create task
            # data should be set up properly on the second time, when request isn't in context
            data = verify_signature_upload(data)

        return data

    class Meta:
        model = CollectionVersionSignature
        fields = NoArtifactContentUploadSerializer.Meta.fields + (
            "signed_collection",
            "pubkey_fingerprint",
            "signing_service",
        )


class AnsibleRepositorySignatureSerializer(serializers.Serializer):
    """
    A serializer for the signing action.
    """

    content_units = serializers.ListField(
        required=True,
        help_text=_(
            "List of collection version hrefs to sign, use * to sign all content in repository"
        ),
    )
    signing_service = RelatedField(
        required=True,
        view_name="signing-services-detail",
        queryset=SigningService.objects.all(),
        help_text=_("A signing service to use to sign the collections"),
    )

    def validate_content_units(self, value):
        """Make sure the list is correctly formatted."""
        if len(value) > 1 and "*" in value:
            raise serializers.ValidationError("Cannot supply content units and '*'.")
        return value


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
