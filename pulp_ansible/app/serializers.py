from gettext import gettext as _

from rest_framework import serializers

from pulpcore.plugin.serializers import ContentSerializer, IdentityField, NestedIdentityField, \
    RelatedField, RemoteSerializer
from pulpcore.plugin.models import Artifact, Repository

from .models import AnsibleRemote, AnsibleRole, AnsibleRoleVersion


class AnsibleRoleSerializer(ContentSerializer):
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


class AnsibleRoleVersionSerializer(ContentSerializer):
    """
    A serializer for Ansible Role versions.
    """

    _href = NestedIdentityField(
        view_name='versions-detail',
        parent_lookup_kwargs={'role_pk': 'role__pk'},
    )

    artifact = RelatedField(
        view_name='artifacts-detail',
        help_text="Artifact file representing the physical content",
        queryset=Artifact.objects.all()
    )

    version = serializers.CharField()

    class Meta:
        fields = ('_href', 'type', 'version', 'artifact')
        model = AnsibleRoleVersion


class AnsibleRemoteSerializer(RemoteSerializer):
    """
    A serializer for Ansible Remotes.
    """

    class Meta:
        fields = RemoteSerializer.Meta.fields
        model = AnsibleRemote


class OneShotUploadSerializer(serializers.Serializer):
    """
    A serializer for the One Shot Upload API.
    """

    repository = serializers.HyperlinkedRelatedField(
        help_text=_('A URI of the repository.'),
        required=True,
        queryset=Repository.objects.all(),
        view_name='repositories-detail',
    )

    file = serializers.FileField(
        help_text=_("The collection file."),
        required=True,
    )

    sha256 = serializers.CharField(
        required=False,
        default=None,
    )
