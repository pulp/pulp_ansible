import json

from import_export import fields
from import_export.widgets import CharWidget, Widget

from pulpcore.plugin.importexport import BaseContentResource, QueryModelResource
from pulpcore.plugin.util import get_domain_pk

from pulp_ansible.app.models import (
    AnsibleCollectionDeprecated,
    AnsibleNamespace,
    AnsibleNamespaceMetadata,
    Collection,
    CollectionVersion,
    CollectionVersionMark,
    CollectionVersionSignature,
    Role,
)


class RoleContentResource(BaseContentResource):
    """
    Resource for import/export of ansible_role-content entities.
    """

    def set_up_queryset(self):
        """
        :return: Role content specific to a specified repo-version.
        """
        return Role.objects.filter(pk__in=self.repo_version.content)

    class Meta:
        model = Role
        import_id_fields = model.natural_key_fields()


class AnsibleNamespaceResource(QueryModelResource):
    """
    Resource for import/export of ansible_namespace entities
    """

    def set_up_queryset(self):
        """
        :return: Collections specific to a specified repo-version.
        """
        namespace_metadatas = AnsibleNamespaceMetadata.objects.filter(
            pk__in=self.repo_version.content
        )
        return AnsibleNamespace.objects.filter(
            pk__in=namespace_metadatas.values_list("namespace", flat=True)
        )

    class Meta:
        model = AnsibleNamespace
        import_id_fields = ("name", "pulp_domain")


class DictWidget(Widget):
    """Simple widget that uses JSON to store and load dictionary fields."""

    def clean(self, value, row=None, **kwargs):
        """Returns Python object from export representation."""
        return json.loads(value)

    def render(self, value, obj=None):
        """Converts Python object to export representation."""
        return json.dumps(value)


class AnsibleNamespaceMetadataResource(BaseContentResource):
    """
    Resource for import/export of ansible_namespace-metadata-content entities.
    """

    links = fields.Field(attribute="links", column_name="links", widget=DictWidget())
    # allow_blank=False keeps None as None; the default CharWidget would coerce it to ""
    # and break the metadata_sha256 digest check on import.
    avatar_sha256 = fields.Field(
        attribute="avatar_sha256",
        column_name="avatar_sha256",
        widget=CharWidget(allow_blank=False),
    )

    def before_import_row(self, row, **kwargs):
        """
        Finds and sets namespace using the name of the namespace metadata.
        """
        super().before_import_row(row, **kwargs)

        namespace = AnsibleNamespace.objects.get(name=row["name"], pulp_domain=get_domain_pk())
        row["namespace"] = str(namespace.pk)
        if row["avatar_sha256"] == "":
            row["avatar_sha256"] = None

    def set_up_queryset(self):
        """
        :return: AnsibleNamespaceMetadata content specific to a specified repo-version.
        """
        return AnsibleNamespaceMetadata.objects.filter(pk__in=self.repo_version.content)

    class Meta:
        model = AnsibleNamespaceMetadata
        import_id_fields = model.natural_key_fields()


class CollectionVersionContentResource(BaseContentResource):
    """
    Resource for import/export of ansible_collectionversion-content entities.
    """

    def before_import_row(self, row, **kwargs):
        """
        Finds and sets collection using name and namespace.

        Args:
            row (tablib.Dataset row): incoming import-row representing a single CollectionVersion.
            kwargs: args passed along from the import() call.
        """
        super().before_import_row(row, **kwargs)

        col = Collection.objects.get(
            name=row["name"], namespace=row["namespace"], pulp_domain=get_domain_pk()
        )
        row["collection"] = str(col.pk)
        row.pop("is_highest", None)

    def set_up_queryset(self):
        """
        :return: CollectionVersion content specific to a specified repo-version.
        """
        return CollectionVersion.objects.filter(pk__in=self.repo_version.content)

    class Meta:
        model = CollectionVersion
        import_id_fields = model.natural_key_fields()


class CollectionVersionSignatureResource(BaseContentResource):
    """
    Resource for import/export of ansible_collectionversionsignature entities.
    """

    def set_up_queryset(self):
        """
        :return: CollectionVersionSignature content specific to a specified repo-version.
        """
        return CollectionVersionSignature.objects.filter(pk__in=self.repo_version.content)

    def before_import_row(self, row, **kwargs):
        """
        Finds and sets collection version using upstream_id.

        Args:
            row (tablib.Dataset row): incoming import-row representing a single content.
            kwargs: args passed along from the import() call.
        """
        super().before_import_row(row, **kwargs)

        cv = CollectionVersion.objects.get(
            upstream_id=row["signed_collection"], _pulp_domain=get_domain_pk()
        )
        row["signed_collection"] = str(cv.pk)

    class Meta:
        model = CollectionVersionSignature
        import_id_fields = ("pubkey_fingerprint", "signed_collection")
        exclude = BaseContentResource.Meta.exclude + ("signing_service",)


class CollectionVersionMarkResource(BaseContentResource):
    """
    Resource for import/export of ansible_collectionversionmark entities.
    """

    def set_up_queryset(self):
        """
        :return: CollectionVersionMark content specific to a specified repo-version.
        """
        return CollectionVersionMark.objects.filter(pk__in=self.repo_version.content)

    def before_import_row(self, row, **kwargs):
        """
        Finds and sets collection version using upstream_id.

        Args:
            row (tablib.Dataset row): incoming import-row representing a single content.
            kwargs: args passed along from the import() call.
        """
        super().before_import_row(row, **kwargs)

        cv = CollectionVersion.objects.get(
            upstream_id=row["marked_collection"], _pulp_domain=get_domain_pk()
        )
        row["marked_collection"] = str(cv.pk)

    class Meta:
        model = CollectionVersionMark
        import_id_fields = ("value", "marked_collection")


class CollectionResource(QueryModelResource):
    """
    Resource for import/export of ansible_collection entities.
    """

    def set_up_queryset(self):
        """
        :return: Collections specific to a specified repo-version.
        """
        collection_versions = CollectionVersion.objects.filter(pk__in=self.repo_version.content)
        return Collection.objects.filter(
            pk__in=collection_versions.values_list("collection", flat=True)
        )

    class Meta:
        model = Collection
        import_id_fields = ("namespace", "name", "pulp_domain")


class CollectionDeprecationResource(BaseContentResource):
    """
    Resource for import/export of collection_deprecation-content entities.
    """

    def set_up_queryset(self):
        """
        :return: AnsibleCollectionDeprecated content specific to a specified repo-version.
        """
        return AnsibleCollectionDeprecated.objects.filter(pk__in=self.repo_version.content)

    class Meta:
        model = AnsibleCollectionDeprecated
        import_id_fields = model.natural_key_fields()


IMPORT_ORDER = [
    AnsibleNamespaceResource,
    AnsibleNamespaceMetadataResource,
    CollectionResource,
    CollectionDeprecationResource,
    CollectionVersionContentResource,
    CollectionVersionMarkResource,
    CollectionVersionSignatureResource,
    RoleContentResource,
]
