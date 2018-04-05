from rest_framework import serializers

from pulpcore.plugin.serializers import ContentSerializer, ImporterSerializer, PublisherSerializer
from pulpcore.plugin.models import Artifact

from .models import AnsibleImporter, AnsiblePublisher, AnsibleRole, AnsibleRoleVersion

from rest_framework_nested.relations import NestedHyperlinkedIdentityField


class AnsibleRoleSerializer(ContentSerializer):
    name = serializers.CharField()
    namespace = serializers.CharField()

    _versions_href = serializers.HyperlinkedIdentityField(
        view_name='versions-list',
        lookup_url_kwarg='role_pk',
    )

    class Meta:
        fields = ('_href', 'name', 'namespace', '_versions_href')
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


class AnsibleImporterSerializer(ImporterSerializer):
    class Meta:
        fields = ImporterSerializer.Meta.fields
        model = AnsibleImporter


class AnsiblePublisherSerializer(PublisherSerializer):
    class Meta:
        fields = PublisherSerializer.Meta.fields
        model = AnsiblePublisher
