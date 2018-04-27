from rest_framework import serializers

from pulpcore.plugin.serializers import ContentSerializer, RemoteSerializer, PublisherSerializer
from pulpcore.plugin.models import Artifact

from .models import AnsibleRemote, AnsiblePublisher, AnsibleRole, AnsibleRoleVersion

from rest_framework_nested.relations import NestedHyperlinkedIdentityField


class AnsibleRoleSerializer(ContentSerializer):
    name = serializers.CharField()
    namespace = serializers.CharField()

    _versions_href = serializers.HyperlinkedIdentityField(
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
    _href = NestedHyperlinkedIdentityField(
        view_name='versions-detail',
        parent_lookup_kwargs={'role_pk': 'role__pk'},
    )

    artifact = serializers.HyperlinkedRelatedField(
        view_name='artifacts-detail',
        help_text="Artifact file representing the physical content",
        queryset=Artifact.objects.all()
    )

    version = serializers.CharField()

    class Meta:
        fields = ('_href', 'type', 'version', 'artifact')
        model = AnsibleRoleVersion


class AnsibleRemoteSerializer(RemoteSerializer):
    class Meta:
        fields = RemoteSerializer.Meta.fields
        model = AnsibleRemote


class AnsiblePublisherSerializer(PublisherSerializer):
    class Meta:
        fields = PublisherSerializer.Meta.fields
        model = AnsiblePublisher
