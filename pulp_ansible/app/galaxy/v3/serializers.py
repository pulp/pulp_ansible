from django.conf import settings
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from rest_framework.reverse import reverse
from rest_framework import serializers, relations

from pulp_ansible.app import models


class CollectionSerializer(serializers.ModelSerializer):
    """A serializer for a Collection."""

    deprecated = serializers.BooleanField()
    created_at = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()
    href = serializers.SerializerMethodField()

    versions_url = serializers.SerializerMethodField()
    highest_version = serializers.SerializerMethodField()

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
        )
        model = models.Collection

    def get_href(self, obj) -> str:
        """Get href."""
        return reverse(
            "collections-detail",
            kwargs={"path": self.context["path"], "namespace": obj.namespace, "name": obj.name},
        )

    def get_versions_url(self, obj) -> str:
        """Get a link to a collection versions list."""
        return reverse(
            "collection-versions-list",
            kwargs={"path": self.context["path"], "namespace": obj.namespace, "name": obj.name},
        )

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_created_at(self, obj):
        """Get the timestamp of the lowest version CollectionVersion's created timestamp."""
        collection = self.context["lowest_versions"][obj.pk]
        return collection.pulp_created

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_updated_at(self, obj):
        """Get the timestamp of the highest version CollectionVersion's created timestamp."""
        collection = self.context["highest_versions"][obj.pk]
        return collection.pulp_created

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_highest_version(self, obj):
        """Get a highest version and its link."""
        collection = self.context["highest_versions"][obj.pk]
        href = reverse(
            "collection-versions-detail",
            kwargs={
                "path": self.context["path"],
                "namespace": collection.namespace,
                "name": collection.name,
                "version": collection.version,
            },
        )
        return {"href": href, "version": str(collection.version)}


class CollectionVersionListSerializer(serializers.ModelSerializer):
    """A serializer for a CollectionVersion list item."""

    href = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(source="collection.pulp_created")
    updated_at = serializers.DateTimeField(source="collection.pulp_last_updated")

    class Meta:
        fields = ("version", "href", "created_at", "updated_at")
        model = models.CollectionVersion

    def get_href(self, obj) -> str:
        """
        Get href.
        """
        return reverse(
            "collection-versions-detail",
            kwargs={
                "path": self.context["path"],
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
        return reverse(
            "collections-detail",
            kwargs={"path": self.context["path"], "namespace": obj.namespace, "name": obj.name},
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


class CollectionVersionSerializer(CollectionVersionListSerializer):
    """
    A serializer for a CollectionVersion.
    """

    collection = CollectionRefSerializer(read_only=True)
    artifact = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    metadata = CollectionMetadataSerializer(source="*", read_only=True)
    namespace = CollectionNamespaceSerializer(source="*", read_only=True)

    class Meta(CollectionVersionListSerializer.Meta):
        fields = CollectionVersionListSerializer.Meta.fields + (
            "artifact",
            "collection",
            "download_url",
            "name",
            "namespace",
            "metadata",
        )

    @extend_schema_field(ArtifactRefSerializer)
    def get_artifact(self, obj):
        """
        Get atrifact summary.
        """
        return ArtifactRefSerializer(self.context["content_artifact"]).data

    def get_download_url(self, obj) -> str:
        """
        Get artifact download URL.
        """
        host = settings.ANSIBLE_CONTENT_HOSTNAME.strip("/")
        distro_base_path = self.context["path"]
        filename_path = self.context["content_artifact"].relative_path.lstrip("/")
        download_url = f"{host}/{distro_base_path}/{filename_path}"
        return download_url


class CollectionVersionDocsSerializer(serializers.ModelSerializer):
    """A serializer to display the docs_blob of a CollectionVersion."""

    docs_blob = serializers.JSONField()

    class Meta:
        fields = ("docs_blob",)
        model = models.CollectionVersion
