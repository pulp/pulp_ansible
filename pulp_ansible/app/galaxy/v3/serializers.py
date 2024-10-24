from typing import List
from django.conf import settings
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from drf_spectacular.types import OpenApiTypes
from rest_framework.reverse import reverse
from rest_framework import serializers, relations

from pulp_ansible.app import models, fields, serializers as ansible_serializers
from pulpcore.plugin.models import RepositoryVersion
from pulpcore.plugin import serializers as core_serializers


def _get_distro_context(context):
    distro_context = {}
    if "path" in context:
        distro_context["path"] = context["path"]
    if "distro_base_path" in context:
        distro_context["distro_base_path"] = context["distro_base_path"]
    return distro_context


class CollectionSerializer(serializers.ModelSerializer):
    """A serializer for a Collection."""

    deprecated = serializers.BooleanField()
    created_at = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()
    href = serializers.SerializerMethodField()

    versions_url = serializers.SerializerMethodField()
    highest_version = serializers.SerializerMethodField()
    download_count = serializers.SerializerMethodField()

    class Meta:
        fields = (
            "href",
            "namespace",
            "name",
            "deprecated",
            "versions_url",
            "highest_version",
            "created_at",
            "updated_at",
            "download_count",
        )
        model = models.Collection

    def get_href(self, obj) -> str:
        """Get href."""
        ctx = _get_distro_context(self.context)
        return reverse(
            settings.ANSIBLE_URL_NAMESPACE + "collections-detail",
            kwargs={**ctx, "namespace": obj.namespace, "name": obj.name},
        )

    def get_versions_url(self, obj) -> str:
        """Get a link to a collection versions list."""
        ctx = _get_distro_context(self.context)
        return reverse(
            settings.ANSIBLE_URL_NAMESPACE + "collection-versions-list",
            kwargs={**ctx, "namespace": obj.namespace, "name": obj.name},
        )

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_created_at(self, obj):
        """Get the timestamp of the lowest version CollectionVersion's created timestamp."""
        return obj.pulp_created

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_updated_at(self, obj):
        """Get the timestamp of the latest version CollectionVersion's created timestamp."""
        # NOTE: this should reflect the last time the collection was updated, not the last
        # time that the latest version was updated. See https://pulp.plan.io/issues/7775
        return obj.latest_version_modified

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_highest_version(self, obj):
        """Get a highest version and its link."""
        ctx = _get_distro_context(self.context)
        href = reverse(
            settings.ANSIBLE_URL_NAMESPACE + "collection-versions-detail",
            kwargs={
                **ctx,
                "namespace": obj.namespace,
                "name": obj.name,
                "version": obj.highest_version,
            },
        )
        return {"href": href, "version": obj.highest_version}

    def get_download_count(self, obj):
        """Get the download count of the collection"""

        return obj.download_count or 0


class CollectionVersionListSerializer(serializers.ModelSerializer):
    """A serializer for a CollectionVersion list item."""

    href = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(source="pulp_created")
    updated_at = serializers.DateTimeField(source="pulp_last_updated")
    marks = serializers.SerializerMethodField()

    class Meta:
        fields = (
            "version",
            "href",
            "created_at",
            "updated_at",
            "requires_ansible",
            "marks",
        )
        model = models.CollectionVersion

    def get_marks(self, obj) -> List[str]:
        """Get a list of mark values filtering only those in the current repo."""
        return [x.value for x in obj.marks.all()]

    def get_href(self, obj) -> str:
        """
        Get href.
        """
        ctx = _get_distro_context(self.context)

        return reverse(
            settings.ANSIBLE_URL_NAMESPACE + "collection-versions-detail",
            kwargs={
                **ctx,
                "namespace": obj.namespace,
                "name": obj.name,
                "version": obj.version,
            },
        )


class ArtifactRefSerializer(serializers.Serializer):
    """A serializer for an Artifact reference."""

    filename = serializers.CharField(source="relative_path")
    sha256 = serializers.CharField(source="artifact.sha256")
    size = serializers.IntegerField(source="artifact.size")


class CollectionRefSerializer(serializers.Serializer):
    """
    A serializer for a Collection reference.
    """

    id = serializers.CharField(source="pk")
    name = serializers.CharField()
    href = serializers.SerializerMethodField()

    def get_href(self, obj) -> str:
        """Returns link to a collection."""
        ctx = _get_distro_context(self.context)
        return reverse(
            settings.ANSIBLE_URL_NAMESPACE + "collections-detail",
            kwargs={**ctx, "namespace": obj.namespace, "name": obj.name},
        )


class CollectionMetadataSerializer(serializers.ModelSerializer):
    """
    A serializer for a CollectionVersion metadata.
    """

    tags = relations.ManyRelatedField(relations.StringRelatedField())

    class Meta:
        model = models.CollectionVersion
        fields = (
            "authors",
            "contents",
            "dependencies",
            "description",
            "documentation",
            "homepage",
            "issues",
            "license",
            "repository",
            "tags",
        )


class CollectionNamespaceSerializer(serializers.Serializer):
    """
    A serializer for a Collection Version namespace field.
    """

    name = serializers.CharField(source="namespace")
    metadata_sha256 = serializers.CharField(source="namespace_sha256", allow_null=True)


class CollectionVersionSignatureSerializer(serializers.ModelSerializer):
    """
    A serializer for the signatures on a Collection Version.
    """

    signature = serializers.SerializerMethodField()
    signing_service = serializers.SlugRelatedField(
        slug_field="name",
        allow_null=True,
        read_only=True,
    )

    def get_signature(self, obj):
        """
        Get the signature data.
        """
        return obj.data

    class Meta:
        model = models.CollectionVersionSignature
        fields = ("signature", "pubkey_fingerprint", "signing_service", "pulp_created")


class UnpaginatedCollectionVersionSerializer(CollectionVersionListSerializer):
    """
    A serializer for unpaginated CollectionVersion.
    """

    collection = CollectionRefSerializer(read_only=True)
    artifact = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    git_url = serializers.SerializerMethodField()
    git_commit_sha = serializers.SerializerMethodField()

    metadata = CollectionMetadataSerializer(source="*", read_only=True)
    namespace = CollectionNamespaceSerializer(source="*", read_only=True)
    signatures = CollectionVersionSignatureSerializer(many=True)

    class Meta:
        model = models.CollectionVersion
        fields = CollectionVersionListSerializer.Meta.fields + (
            "artifact",
            "collection",
            "download_url",
            "name",
            "namespace",
            "signatures",
            "metadata",
            "git_url",
            "git_commit_sha",
        )

    @extend_schema_field(ArtifactRefSerializer)
    def get_artifact(self, obj):
        """
        Get artifact summary.
        """
        ca = obj.artifacts[0]
        if ca.artifact:
            return ArtifactRefSerializer(ca).data

    def get_download_url(self, obj) -> str:
        """
        Get artifact download URL.
        """
        if obj.artifacts[0].artifact:
            distro_base_path = self.context.get("path", self.context["distro_base_path"])
            filename_path = obj.relative_path.lstrip("/")

            # Note: We're using ANSIBLE_API_HOSTNAME here instead of calling reverse with request=
            # because using the request context to generate the full URL causes the download URL
            # to be inaccessible when pulp is running behind a reverse proxy.
            host = settings.ANSIBLE_API_HOSTNAME.strip("/")
            path = reverse(
                settings.ANSIBLE_URL_NAMESPACE + "collection-artifact-download",
                kwargs={"distro_base_path": distro_base_path, "filename": filename_path},
            ).strip("/")

            return f"{host}/{path}"

    def get_git_url(self, obj) -> str:
        """
        Get the git URL.
        """
        ca = obj.artifacts[0]
        if not ca.artifact:
            return ca.remoteartifact_set.all()[0].url[:-47]

    def get_git_commit_sha(self, obj) -> str:
        """
        Get the git commit sha.
        """
        ca = obj.artifacts[0]
        if not ca.artifact:
            return ca.remoteartifact_set.all()[0].url[-40:]


class CollectionVersionSerializer(UnpaginatedCollectionVersionSerializer):
    """
    A serializer for a CollectionVersion.
    """

    manifest = fields.JSONDictField(
        help_text="A JSON field holding MANIFEST.json data.", read_only=True
    )
    files = fields.JSONDictField(help_text="A JSON field holding FILES.json data.", read_only=True)

    class Meta:
        model = models.CollectionVersion
        fields = UnpaginatedCollectionVersionSerializer.Meta.fields + (
            "manifest",
            "files",
        )


class CollectionVersionDocsSerializer(serializers.ModelSerializer):
    """A serializer to display the docs_blob of a CollectionVersion."""

    docs_blob = fields.JSONDictField()

    class Meta:
        fields = ("docs_blob",)
        model = models.CollectionVersion


class RepoMetadataSerializer(serializers.ModelSerializer):
    """A serializer to display RepositoryVersion metadata."""

    published = serializers.DateTimeField(source="pulp_created")

    class Meta:
        fields = ("published",)
        model = RepositoryVersion


class ClientConfigurationSerializer(serializers.Serializer):
    """Configuration settings for the ansible-galaxy client."""

    default_distribution_path = serializers.CharField(allow_null=True)


@extend_schema_serializer(component_name="CollectionSummary")
class CollectionSummarySerializer(ansible_serializers.CollectionVersionSerializer):
    """Collection Version serializer without docs blob."""

    class Meta:
        model = models.CollectionVersion
        fields = (
            "pulp_href",
            "namespace",
            "name",
            "version",
            "requires_ansible",
            "pulp_created",
            "contents",
            "dependencies",
            "description",
            "tags",
        )


class NamespaceSummarySerializer(ansible_serializers.AnsibleNamespaceMetadataSerializer):
    """Namespace serializer without resources."""

    class Meta:
        model = models.AnsibleNamespaceMetadata
        fields = (
            "pulp_href",
            "name",
            "company",
            "description",
            "avatar",
            "avatar_url",
        )


class CollectionVersionSearchListSerializer(CollectionVersionListSerializer):
    """Cross-repo search results."""

    # All of these fields have to operate differently from the parent class
    repository = core_serializers.RepositorySerializer()
    collection_version = CollectionSummarySerializer()
    repository_version = serializers.SerializerMethodField()
    namespace_metadata = NamespaceSummarySerializer(allow_null=True)

    is_highest = serializers.BooleanField()
    is_signed = serializers.BooleanField()
    is_deprecated = serializers.BooleanField()

    class Meta:
        model = models.CrossRepositoryCollectionVersionIndex

        fields = (
            "repository",
            "collection_version",
            "repository_version",
            "namespace_metadata",
            "is_highest",
            "is_deprecated",
            "is_signed",
        )

    def get_repository_version(self, obj):
        if obj.repository_version:
            return obj.repository_version.number
        else:
            return "latest"
