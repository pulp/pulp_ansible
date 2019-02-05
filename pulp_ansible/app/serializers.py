from rest_framework import serializers

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
        fields = ('_href', 'name', 'namespace', '_versions_href', 'version_count')
        model = AnsibleRole


class AnsibleRoleVersionSerializer(SingleArtifactContentSerializer):
    """
    A serializer for Ansible Role versions.
    """

    _href = NestedIdentityField(
        view_name='versions-detail',
        parent_lookup_kwargs={'role_pk': 'role__pk'},
    )

    version = serializers.CharField()

    class Meta:
        fields = SingleArtifactContentSerializer.Meta.fields + ('version',)
        model = AnsibleRoleVersion


class AnsibleRemoteSerializer(RemoteSerializer):
    """
    A serializer for Ansible Remotes.
    """

    class Meta:
        fields = RemoteSerializer.Meta.fields
        model = AnsibleRemote
