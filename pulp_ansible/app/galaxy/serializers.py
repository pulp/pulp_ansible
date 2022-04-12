from gettext import gettext as _

from django.conf import settings
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from rest_framework.reverse import reverse
from rest_framework import serializers

from pulp_ansible.app.models import Collection, CollectionVersion, Role
from pulp_ansible.app.galaxy.v3.serializers import CollectionMetadataSerializer


class GalaxyRoleSerializer(serializers.ModelSerializer):
    """
    A serializer for Galaxy's representation of Roles.
    """

    id = serializers.SerializerMethodField(read_only=True)
    name = serializers.CharField()
    namespace = serializers.CharField()

    def get_id(self, obj) -> str:
        """
        Get id.
        """
        return "{}.{}".format(obj.namespace, obj.name)

    class Meta:
        fields = ("id", "name", "namespace")
        model = Role


class GalaxyRoleVersionSerializer(serializers.Serializer):
    """
    A serializer for Galaxy's representation of Role versions.
    """

    name = serializers.CharField(source="version")

    source = serializers.SerializerMethodField(read_only=True)

    def get_source(self, obj) -> str:
        """
        Get source.
        """
        distro_base = self.context["path"]
        distro_path = "".join([settings.CONTENT_ORIGIN, settings.CONTENT_PATH_PREFIX, distro_base])

        return "".join([distro_path, "/", obj.relative_path])

    class Meta:
        fields = ("name", "source")
        model = Role


class GalaxyCollectionSerializer(serializers.Serializer):
    """
    A serializer for a Collection.
    """

    id = serializers.CharField(source="pulp_id")
    name = serializers.CharField()
    namespace = serializers.SerializerMethodField()
    href = serializers.SerializerMethodField(read_only=True)
    versions_url = serializers.SerializerMethodField(read_only=True)
    created = serializers.DateTimeField(source="pulp_created")
    modified = serializers.DateTimeField(source="pulp_last_updated")
    latest_version = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_namespace(self, obj):
        """Create a namespace dict."""
        return {"name": obj.namespace}

    def get_versions_url(self, obj) -> str:
        """
        Get versions_url.
        """
        return (
            "{hostname}/pulp_ansible/galaxy/{path}/api/v2/collections/{namespace}/{name}/"
            "versions/".format(
                path=self.context["path"],
                hostname=settings.ANSIBLE_API_HOSTNAME,
                namespace=obj.namespace,
                name=obj.name,
            )
        )

    def get_href(self, obj) -> str:
        """
        Get href.
        """
        return (
            "{hostname}/pulp_ansible/galaxy/{path}/api/v2/collections/{namespace}/"
            "{name}/".format(
                path=self.context["path"],
                hostname=settings.ANSIBLE_API_HOSTNAME,
                namespace=obj.namespace,
                name=obj.name,
            )
        )

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_latest_version(self, obj):
        """
        Get latest version.
        """
        rv = obj.versions.filter(is_highest=True).first()
        href = reverse(
            "collection-versions-detail",
            kwargs={
                "path": self.context["path"],
                "namespace": obj.namespace,
                "name": obj.name,
                "version": rv.version,
            },
        )
        return {"href": href, "version": rv.version}

    class Meta:
        fields = (
            "id",
            "href",
            "name",
            "namespace",
            "versions_url",
            "latest_version",
            "created",
            "modified",
        )
        model = Collection


class GalaxyCollectionVersionSerializer(serializers.Serializer):
    """
    A serializer for a CollectionVersion.
    """

    version = serializers.CharField()
    href = serializers.SerializerMethodField(read_only=True)
    namespace = serializers.SerializerMethodField(read_only=True)
    collection = serializers.SerializerMethodField(read_only=True)
    artifact = serializers.SerializerMethodField(read_only=True)
    metadata = CollectionMetadataSerializer(source="*")

    def get_href(self, obj) -> str:
        """
        Get href.
        """
        return (
            "{hostname}/pulp_ansible/galaxy/{path}/api/v2/collections/{namespace}/{name}/"
            "versions/{version}/".format(
                path=self.context["path"],
                hostname=settings.ANSIBLE_API_HOSTNAME,
                namespace=obj.collection.namespace,
                name=obj.collection.name,
                version=obj.version,
            )
        )

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_namespace(self, obj):
        """Create a namespace dict."""
        return {"name": obj.collection.namespace}

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_collection(self, obj):
        """Create a collection dict."""
        return {"name": obj.collection.name}

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_artifact(self, obj):
        """Create an artifact dict."""
        artifact = obj.contentartifact_set.get().artifact
        return {"sha256": artifact.sha256, "size": artifact.size}

    class Meta:
        fields = ("version", "href", "metadata")
        model = CollectionVersion


class GalaxyCollectionUploadSerializer(serializers.Serializer):
    """
    A serializer for Collection Uploads.
    """

    file = serializers.FileField(
        help_text=_("The file containing the Artifact binary data."), required=True
    )
