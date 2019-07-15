from gettext import gettext as _

from django.conf import settings
from rest_framework import serializers

from pulp_ansible.app.models import CollectionVersion, Role


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
        if settings.CONTENT_HOST:
            host = settings.CONTENT_HOST
        else:
            host = self.context["request"].get_host()
        host = "{}://{}".format(self.context["request"].scheme, host)

        distro_base = self.context["request"].parser_context["kwargs"]["path"]
        distro_path = "".join([host, settings.CONTENT_PATH_PREFIX, distro_base])

        return "".join([distro_path, "/", obj.relative_path])

    class Meta:
        fields = ("name", "source")
        model = Role


class GalaxyCollectionVersionSerializer(serializers.Serializer):
    """
    A serializer for a Collection.
    """

    name = serializers.CharField()
    namespace = serializers.CharField()
    version = serializers.CharField()
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
            "{hostname}/pulp_ansible/galaxy/{path}/api/v2/collections/{namespace}/{name}/"
            "versions/{version}/".format(
                path=obj.path,
                hostname=settings.ANSIBLE_API_HOSTNAME,
                namespace=obj.namespace,
                name=obj.name,
                version=obj.version,
            )
        )

    class Meta:
        fields = ("name", "namespace", "version", "href")
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
