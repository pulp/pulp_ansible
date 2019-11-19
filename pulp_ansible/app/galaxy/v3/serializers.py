from gettext import gettext as _
from django.conf import settings
from rest_framework.reverse import reverse
from rest_framework import serializers, relations

from pulp_ansible.app import models


class CollectionSerializer(serializers.ModelSerializer):
    """A serializer for a Collection."""

    created_at = serializers.DateTimeField(source="collection.pulp_created")
    updated_at = serializers.DateTimeField(source="collection.pulp_last_updated")
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

    def update(self, obj, validated_data):
        """Update Collection."""
        collection_data = validated_data.pop("collection")
        if "deprecated" not in collection_data or len(collection_data.keys()) > 1:
            raise serializers.ValidationError(_("Only `deprecated` could be updated."))
        collection = models.Collection.objects.filter(pk=obj.collection.pk)
        collection.update(**collection_data)
        return super().update(obj, validated_data)

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
    created_at = serializers.DateTimeField(source="collection.pulp_created")
    updated_at = serializers.DateTimeField(source="collection.pulp_last_updated")

    class Meta:
        fields = ("version", "certification", "href", "created_at", "updated_at")
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

    def get_artifact(self, obj):
        """
        Get atrifact summary.
        """
        return ArtifactRefSerializer(self.context["content_artifact"]).data

    def get_download_url(self, obj):
        """
        Get artifact download URL.
        """
        host = settings.CONTENT_ORIGIN.strip("/")
        prefix = settings.CONTENT_PATH_PREFIX.strip("/")
        base_path = self.context["content_artifact"].relative_path.lstrip("/")
        return f"{host}/{prefix}/{base_path}"
