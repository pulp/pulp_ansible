from gettext import gettext as _

from django.conf import settings
from rest_framework import serializers

from pulpcore.plugin.serializers import (
    ContentChecksumSerializer,
    ModelSerializer,
    RemoteSerializer,
    SingleArtifactContentSerializer,
    RepositoryVersionDistributionSerializer,
)

from .models import (
    AnsibleDistribution,
    AnsibleRemote,
    CollectionVersion,
    CollectionRemote,
    Role,
    Tag,
)


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
        fields = RemoteSerializer.Meta.fields
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


class TagSerializer(serializers.ModelSerializer):
    """
    A serializer for the Tag model.
    """

    class Meta:
        model = Tag
        fields = ["name"]


class TagNestedSerializer(ModelSerializer):
    """
    A serializer for nesting in the CollectionVersion model.
    """

    name = serializers.CharField(help_text=_("The name of the Tag."), read_only=True)

    class Meta:
        model = Tag
        # this serializer is meant to be nested inside CollectionVersion serializer, so it will not
        # have its own endpoint. That's why we need to explicitly define fields to exclude other
        # inherited fields
        fields = ("name",)


class CollectionVersionSerializer(SingleArtifactContentSerializer, ContentChecksumSerializer):
    """
    A serializer for CollectionVersion Content.
    """

    authors = serializers.ListField(
        help_text=_("A list of the CollectionVersion content's authors."),
        child=serializers.CharField(max_length=64),
    )

    contents = serializers.JSONField(help_text=_("A JSON field with data about the contents."))

    dependencies = serializers.JSONField(
        help_text=_(
            "A dict declaring Collections that this collection requires to be installed for it to "
            "be usable."
        )
    )

    description = serializers.CharField(
        help_text=_("A short summary description of the collection."), allow_blank=True
    )

    docs_blob = serializers.JSONField(
        help_text=_("A JSON field holding the various documentation blobs in the collection.")
    )

    documentation = serializers.URLField(
        help_text=_("The URL to any online docs."), allow_blank=True, max_length=128
    )

    homepage = serializers.URLField(
        help_text=_("The URL to the homepage of the collection/project."),
        allow_blank=True,
        max_length=128,
    )

    issues = serializers.URLField(
        help_text=_("The URL to the collection issue tracker."), allow_blank=True, max_length=128
    )

    license = serializers.ListField(
        help_text=_("A list of licenses for content inside of a collection."),
        child=serializers.CharField(max_length=32),
    )

    name = serializers.CharField(help_text=_("The name of the collection."), max_length=32)

    namespace = serializers.CharField(
        help_text=_("The namespace of the collection."), max_length=32
    )

    repository = serializers.URLField(
        help_text=_("The URL of the originating SCM repository."), allow_blank=True, max_length=128
    )

    tags = TagNestedSerializer(many=True, read_only=True)

    version = serializers.CharField(help_text=_("The version of the collection."), max_length=32)

    class Meta:
        fields = (
            tuple(set(SingleArtifactContentSerializer.Meta.fields) - {"_relative_path"})
            + ContentChecksumSerializer.Meta.fields
            + (
                "authors",
                "contents",
                "dependencies",
                "description",
                "docs_blob",
                "documentation",
                "homepage",
                "issues",
                "license",
                "name",
                "namespace",
                "repository",
                "tags",
                "version",
            )
        )
        model = CollectionVersion
