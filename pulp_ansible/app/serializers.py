from rest_framework import serializers

from pulpcore.plugin.serializers import ContentSerializer, ImporterSerializer, PublisherSerializer

from .models import AnsibleRoleVersion, AnsibleImporter, AnsiblePublisher


class AnsibleRoleVersionSerializer(ContentSerializer):
    name = serializers.CharField()
    namespace = serializers.CharField()
    version = serializers.CharField()

    class Meta:
        fields = ContentSerializer.Meta.fields + ('name', 'namespace', 'version')
        model = AnsibleRoleVersion


class AnsibleImporterSerializer(ImporterSerializer):
    class Meta:
        fields = ImporterSerializer.Meta.fields
        model = AnsibleImporter


class AnsiblePublisherSerializer(PublisherSerializer):
    class Meta:
        fields = PublisherSerializer.Meta.fields
        model = AnsiblePublisher
