from rest_framework import serializers
from rest_framework_nested.serializers import NestedHyperlinkedModelSerializer

from pulpcore.plugin.serializers import (
    IdentityField,
    NestedIdentityField,
    NoArtifactContentSerializer,
    RemoteSerializer,
    SingleArtifactContentSerializer,
)

from .models import AnsibleRemote, AnsibleRole, AnsibleRoleVersion


class AnsibleRoleSerializer(NoArtifactContentSerializer):
    """
    A serializer for Ansible Roles.
    """

    name = serializers.CharField()
    namespace = serializers.CharField()

    _versions_href = IdentityField(
        view_name='versions-list',
        lookup_url_kwarg='role_pk',
    )

    version_count = serializers.IntegerField(
        source='versions.count',
        read_only=True
    )

    class Meta:
        fields = NoArtifactContentSerializer.Meta.fields + (
            'name',
            'namespace',
            '_versions_href',
            'version_count',
        )
        model = AnsibleRole


class AnsibleRoleVersionSerializer(SingleArtifactContentSerializer,
                                   NestedHyperlinkedModelSerializer):
    """
    A serializer for Ansible Role versions.
    """

    parent_lookup_kwargs = {
        'role_pk': 'role__pk',
    }

    _href = NestedIdentityField(
        view_name='versions-detail',
        parent_lookup_kwargs={'role_pk': 'role__pk'},
    )

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
        view = self.context['view']
        role = AnsibleRole.objects.get(pk=view.kwargs['role_pk'])
        if role.versions.filter(version=data['version']).exists():
            raise serializers.ValidationError(
                'Version "{version}" exists already for role "{name}/{namespace}"'.format(
                    version=data['version'],
                    namespace=role.namespace,
                    name=role.name,
                )
            )
        relative_path = "{namespace}/{name}/{version}.tar.gz".format(
            namespace=role.namespace,
            name=role.name,
            version=data['version']
        )
        data['role'] = role
        data['_relative_path'] = relative_path
        return data

    class Meta:
        fields = tuple(set(SingleArtifactContentSerializer.Meta.fields) - {'_relative_path'}) + (
            'version',)
        model = AnsibleRoleVersion


class AnsibleRemoteSerializer(RemoteSerializer):
    """
    A serializer for Ansible Remotes.
    """

    class Meta:
        fields = RemoteSerializer.Meta.fields
        model = AnsibleRemote
