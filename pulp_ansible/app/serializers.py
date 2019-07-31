from gettext import gettext as _

from django.conf import settings
from rest_framework import serializers

from pulpcore.plugin.serializers import (
    ContentChecksumSerializer,
    RemoteSerializer,
    SingleArtifactContentSerializer,
    RepositoryVersionDistributionSerializer,
)

from .models import AnsibleDistribution, AnsibleRemote, CollectionVersion, CollectionRemote, Role


class RoleSerializer(SingleArtifactContentSerializer):
    """
    A serializer for Role versions.
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
            namespace=data["namespace"], name=data["name"], version=data["version"]
        )
        data["_relative_path"] = relative_path
        return data

    class Meta:
        fields = tuple(set(SingleArtifactContentSerializer.Meta.fields) - {"_relative_path"}) + (
            "version",
            "name",
            "namespace",
        )
        model = Role


class AnsibleRemoteSerializer(RemoteSerializer):
    """
    A serializer for Ansible Remotes.
    """

    class Meta:
        fields = RemoteSerializer.Meta.fields
        model = AnsibleRemote


class CollectionRemoteSerializer(RemoteSerializer):
    """
    A serializer for Collection Remotes.
    """

    def validate(self, data):
        """
        Validate a a url to ensure it does not end with slashes.

        Args:
            data (dict): User data to validate

        Returns:
            dict: Validated data

        Raises:
            rest_framework.serializers.ValidationError: If the url is invalid

        """
        data = super().validate(data)

        if data["url"].endswith("/"):
            raise serializers.ValidationError(_("url should not end with '/'"))

        return data

    class Meta:
        fields = RemoteSerializer.Meta.fields + ("whitelist",)
        model = CollectionRemote


class CollectionOneShotSerializer(serializers.Serializer):
    """
    A serializer for the Collection One Shot Upload API.
    """

    file = serializers.FileField(help_text=_("The Collection tarball."), required=True)

    sha256 = serializers.CharField(
        help_text=_("An optional sha256 checksum of the uploaded file."),
        required=False,
        default=None,
    )


class AnsibleDistributionSerializer(RepositoryVersionDistributionSerializer):
    """
    Serializer for Ansible Distributions.
    """

    mazer_url = serializers.SerializerMethodField(
        read_only=True, help_text=_("The URL of a mazer content source.")
    )

    def get_mazer_url(self, obj):
        """
        Get mazer_url.
        """
        return "{hostname}/pulp_ansible/galaxy/{base_path}".format(
            hostname=settings.ANSIBLE_API_HOSTNAME, base_path=obj.base_path
        )

    class Meta:
        fields = (
            "_href",
            "_created",
            "base_path",
            "content_guard",
            "name",
            "repository",
            "repository_version",
            "mazer_url",
        )
        model = AnsibleDistribution


class CollectionVersionSerializer(SingleArtifactContentSerializer, ContentChecksumSerializer):
    """
    A serializer for Ansible Collection.
    """

    name = serializers.CharField()
    namespace = serializers.CharField()
    version = serializers.CharField()

    class Meta:
        fields = (
            tuple(set(SingleArtifactContentSerializer.Meta.fields) - {"_relative_path"})
            + ContentChecksumSerializer.Meta.fields
            + ("version", "name", "namespace")
        )
        model = CollectionVersion
