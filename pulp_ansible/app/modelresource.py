from import_export import fields
from import_export.widgets import ManyToManyWidget
from pulpcore.plugin.importexport import BaseContentResource, QueryModelResource
from pulp_ansible.app.models import (
    AnsibleCollectionDeprecated,
    Role,
    Collection,
    Tag,
    CollectionVersion,
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


class CollectionVersionContentResource(BaseContentResource):
    """
    Resource for import/export of ansible_collectionversion-content entities.
    """

    tags = fields.Field(
        column_name="tags", attribute="tags", widget=ManyToManyWidget(Tag, field="name")
    )

    def before_import_row(self, row, **kwargs):
        """
        Finds and sets collection using name and namespace.

        Args:
            row (tablib.Dataset row): incoming import-row representing a single CollectionVersion.
            kwargs: args passed along from the import() call.
        """
        col = Collection.objects.get(name=row["name"], namespace=row["namespace"])
        row["collection"] = str(col.pk)

    def set_up_queryset(self):
        """
        :return: CollectionVersion content specific to a specified repo-version.
        """
        return CollectionVersion.objects.filter(pk__in=self.repo_version.content)

    class Meta:
        model = CollectionVersion
        import_id_fields = model.natural_key_fields()


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
        import_id_fields = ("namespace", "name")


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
        import_id_fields = ("namespace", "name")


class TagResource(QueryModelResource):
    """
    Resource for import/export of ansible_tag entities.
    """

    def set_up_queryset(self):
        """
        :return: Tags specific to a specified repo-version.
        """
        collection_versions = CollectionVersion.objects.filter(pk__in=self.repo_version.content)
        return Tag.objects.filter(pk__in=collection_versions.values_list("tags", flat=True))

    class Meta:
        model = Tag
        import_id_fields = ("name",)


# TODO: Add resource for AnsibleCollectionDeprecated


IMPORT_ORDER = [
    CollectionResource,
    CollectionDeprecationResource,
    TagResource,
    CollectionVersionContentResource,
    RoleContentResource,
]
