from rest_framework import serializers

from pulpcore.plugin.serializers import ContentSerializer, ImporterSerializer, PublisherSerializer

from .models import AnsibleRole, AnsibleImporter, AnsiblePublisher


class AnsibleRoleSerializer(ContentSerializer):
    name = serializers.CharField()
    namespace = serializers.CharField()
    version = serializers.CharField()

    class Meta:
        fields = ContentSerializer.Meta.fields + ('name', 'namespace', 'version')
        model = AnsibleRole


class AnsibleImporterSerializer(ImporterSerializer):
    class Meta:
        fields = ImporterSerializer.Meta.fields
        model = AnsibleImporter


class AnsiblePublisherSerializer(PublisherSerializer):
    class Meta:
        fields = PublisherSerializer.Meta.fields
        model = AnsiblePublisher
