from rest_framework.reverse import reverse
from rest_framework import serializers, relations

from pulp_ansible.app import models


class CollectionSerializer(serializers.ModelSerializer):
    """A serializer for a Collection."""

    created_at = serializers.DateTimeField(source="collection._created")
    updated_at = serializers.DateTimeField(source="collection._last_updated")
    deprecated = serializers.BooleanField(source="collection.deprecated")
    href = serializers.SerializerMethodField()

    versions_url = serializers.SerializerMethodField()
    highest_version = serializers.SerializerMethodField()

    class Meta:
        fields = (
            "href",
            "created_at",
            "updated_at",
            "namespace",
            "name",
            "deprecated",
            "versions_url",
            "highest_version",
        )
        model = models.CollectionVersion

    def get_href(self, obj):
        """Get href."""
        return reverse(
            "collections-detail",
            kwargs={"path": self.context["path"], "namespace": obj.namespace, "name": obj.name},
        )

    def get_versions_url(self, obj):
        """Get a link to a collection versions list."""
        return reverse(
            "collection-versions-list",
            kwargs={"path": self.context["path"], "namespace": obj.namespace, "name": obj.name},
        )

    def get_highest_version(self, obj):
        """Get a highest version and its link."""
        href = reverse(
            "collection-versions-detail",
            kwargs={
                "path": self.context["path"],
                "namespace": obj.namespace,
                "name": obj.name,
                "version": obj.version,
            },
        )
        return {"href": href, "version": obj.version}


class CollectionVersionListSerializer(serializers.ModelSerializer):
    """A serializer for a CollectionVersion list item."""

    href = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(source="collection._created")
    updated_at = serializers.DateTimeField(source="collection._last_updated")

    class Meta:
        fields = ("version", "href", "created_at", "updated_at")
        model = models.CollectionVersion

    def get_href(self, obj):
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

    def get_href(self, obj):
        """Returns link to a collection."""
        return reverse(
            "collections-detail",
            kwargs={"path": self.context["path"], "namespace": obj.namespace, "name": obj.name},
        )


class CollectionVersionSerializer(CollectionVersionListSerializer):
    """
    A serializer for a CollectionVersion.
    """

    collection = CollectionRefSerializer()
    tags = relations.ManyRelatedField(relations.StringRelatedField())
    artifact = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta(CollectionVersionListSerializer.Meta):
        fields = CollectionVersionListSerializer.Meta.fields + (
            "artifact",
            "authors",
            "contents",
            "collection",
            "dependencies",
            "description",
            "documentation",
            "download_url",
            "homepage",
            "issues",
            "license",
            "name",
            "namespace",
            "repository",
            "tags",
        )

    def get_artifact(self, obj):
        """
        Get atrifact summary.
        """
        return ArtifactRefSerializer(self.context["content_artifact"]).data

    def get_download_url(self, obj):
        """
        Get artifact download URL.
        """
        filename = self.context["content_artifact"].relative_path
        return "/api/v3/artifacts/collections/" + filename
