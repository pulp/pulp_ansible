from rest_framework import serializers

from pulpcore.plugin.serializers import (
    RemoteSerializer,
    SingleArtifactContentSerializer,
)

from .models import AnsibleRemote, AnsibleRole


class AnsibleRoleSerializer(SingleArtifactContentSerializer):
    """
    A serializer for Ansible Role versions.
    """

    name = serializers.CharField()
    namespace = serializers.CharField()
    version = serializers.CharField()

    def validate(self, data):
        """
        Validates data.

        Args:
            data (dict): User data to validate

        Returns:
            dict: Validated data

        Raises:
            rest_framework.serializers.ValidationError: If invalid data

        """
        data = super().validate(data)
        relative_path = "{namespace}/{name}/{version}.tar.gz".format(
            namespace=data['namespace'],
            name=data['name'],
            version=data['version']
        )
        data['_relative_path'] = relative_path
        return data

    class Meta:
        fields = tuple(set(SingleArtifactContentSerializer.Meta.fields) - {'_relative_path'}) + (
            'version', 'name', 'namespace')
        model = AnsibleRole


class AnsibleRemoteSerializer(RemoteSerializer):
    """
    A serializer for Ansible Remotes.
    """

    class Meta:
        fields = RemoteSerializer.Meta.fields
        model = AnsibleRemote
