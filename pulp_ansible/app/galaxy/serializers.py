from gettext import gettext as _

from django.conf import settings
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

    def get_id(self, obj):
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

    def get_source(self, obj):
        """
        Get source.
        """
        if settings.CONTENT_ORIGIN:
            host = settings.CONTENT_ORIGIN
        else:
            host = self.context["request"].get_host()
        host = "{}://{}".format(self.context["request"].scheme, host)

        distro_base = self.context["request"].parser_context["kwargs"]["path"]
        distro_path = "".join([host, settings.CONTENT_PATH_PREFIX, distro_base])

        return "".join([distro_path, "/", obj.relative_path])

    class Meta:
        fields = ("name", "source")
        model = Role


class GalaxyCollectionSerializer(serializers.Serializer):
    """
    A serializer for a Collection.
    """

    name = serializers.CharField()
    namespace = serializers.CharField()
    href = serializers.SerializerMethodField(read_only=True)
    versions_url = serializers.SerializerMethodField(read_only=True)

    def get_versions_url(self, obj):
        """
        Get versions_url.
        """
        return (
            "{hostname}/pulp_ansible/galaxy/{path}/api/v2/collections/{namespace}/{name}/"
            "versions/".format(
                path=obj.path,
                hostname=settings.ANSIBLE_API_HOSTNAME,
                namespace=obj.namespace,
                name=obj.name,
            )
        )

    def get_href(self, obj):
        """
        Get href.
        """
        return (
            "{hostname}/pulp_ansible/galaxy/{path}/api/v2/collections/{namespace}/"
            "{name}/".format(
                path=obj.path,
                hostname=settings.ANSIBLE_API_HOSTNAME,
                namespace=obj.namespace,
                name=obj.name,
            )
        )

    class Meta:
        fields = ("name", "namespace", "href", "versions_url")
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

    def get_href(self, obj):
        """
        Get href.
        """
        return (
            "{hostname}/pulp_ansible/galaxy/{path}/api/v2/collections/{namespace}/{name}/"
            "versions/{version}/".format(
                path=obj.path,
                hostname=settings.ANSIBLE_API_HOSTNAME,
                namespace=obj.collection.namespace,
                name=obj.collection.name,
                version=obj.version,
            )
        )

    def get_namespace(self, obj):
        """Create a namespace dict."""
        return {"name": obj.collection.namespace}

    def get_collection(self, obj):
        """Create a collection dict."""
        return {"name": obj.collection.name}

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

    sha256 = serializers.CharField(
        help_text=_("The sha256 checksum of the Collection Artifact."),
        required=True,
        max_length=64,
        min_length=64,
    )
    file = serializers.FileField(
        help_text=_("The file containing the Artifact binary data."), required=True
    )
