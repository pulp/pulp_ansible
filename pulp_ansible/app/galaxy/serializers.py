from django.conf import settings
from rest_framework import serializers

from pulp_ansible.app.models import Role


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
