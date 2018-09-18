from django.conf import settings
from rest_framework import serializers
from rest_framework.reverse import reverse

from pulp_ansible.app.models import AnsibleRole, AnsibleRoleVersion


class GalaxyAnsibleRoleSerializer(serializers.ModelSerializer):
    """
    A serializer for Ansible roles in Galaxy.
    """

    name = serializers.CharField()
    namespace = serializers.CharField()
    id = serializers.UUIDField()

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
        if settings.CONTENT['HOST']:
            host = settings.CONTENT['HOST']
        else:
            host = self.context['request'].get_host()
        host = "{}://{}".format(self.context['request'].scheme, host)

        distro_base = self.context['request'].parser_context['kwargs']['path']
        distro_path = ''.join([host, reverse('content-app'), distro_base])

        return ''.join([distro_path, '/', obj.relative_path])

    class Meta:
        fields = ('name', 'source')
        model = AnsibleRoleVersion
