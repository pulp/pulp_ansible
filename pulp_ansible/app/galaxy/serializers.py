from django.conf import settings
from rest_framework import serializers

from pulp_ansible.app.models import AnsibleRole, AnsibleRoleVersion


class GalaxyAnsibleRoleSerializer(serializers.ModelSerializer):
    """
    A serializer for Ansible roles in Galaxy.
    """

    name = serializers.CharField()
    namespace = serializers.CharField()
    id = serializers.UUIDField(source="_id")

    class Meta:
        fields = ('id', 'name', 'namespace')
        model = AnsibleRole


class GalaxyAnsibleRoleVersionSerializer(serializers.Serializer):
    """
    A serializer for Ansible role versions in Galaxy.
    """

    name = serializers.CharField(source='version')

    source = serializers.SerializerMethodField(read_only=True)

    def get_source(self, obj):
        """
        Get source.
        """
        if settings.CONTENT_HOST:
            host = settings.CONTENT_HOST
        else:
            host = self.context['request'].get_host()
        host = "{}://{}".format(self.context['request'].scheme, host)

        distro_base = self.context['request'].parser_context['kwargs']['path']
        distro_path = ''.join([host, settings.CONTENT_PATH_PREFIX, distro_base])

        return ''.join([distro_path, '/', obj.relative_path])

    class Meta:
        fields = ('name', 'source')
        model = AnsibleRoleVersion
