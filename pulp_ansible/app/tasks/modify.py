from pulpcore.plugin.models import Content, RepositoryVersion

from pulp_ansible.app.models import AnsibleCollectionDeprecated, AnsibleRepository


def add_and_remove(repository_pk, add_content_units, remove_content_units, base_version_pk=None):
    """
    Create a new repository version by adding and then removing content units.

    Args:
        repository_pk (int): The primary key for a Repository for which a new Repository Version
            should be created.
        add_content_units (list): List of PKs for :class:`~pulpcore.app.Content` that
            should be added to the previous Repository Version for this Repository.
        remove_content_units (list): List of PKs for:class:`~pulpcore.app.Content` that
            should be removed from the previous Repository Version for this Repository.
        base_version_pk (int): the primary key for a RepositoryVersion whose content will be used
            as the initial set of content for our new RepositoryVersion
    """
    repository = AnsibleRepository.objects.get(pk=repository_pk)

    if base_version_pk:
        base_version = RepositoryVersion.objects.get(pk=base_version_pk)
    else:
        base_version = None

    if "*" in remove_content_units:
        latest = repository.latest_version()
        if latest:
            remove_content_units = latest.content.values_list("pk", flat=True)
        else:
            remove_content_units = []

    to_add = []
    with repository.new_version(base_version=base_version) as new_version:
        new_version.remove_content(Content.objects.filter(pk__in=remove_content_units))
        new_version.add_content(Content.objects.filter(pk__in=add_content_units))

        raise NotImplementedError("oh no!")
        for collection_id, deprecated in MutableCollectionMetadata.objects.filter(
            repository_version__repository=repository, collection__versions__in=add_content_units
        ).values_list("collection_id", "deprecated"):
            to_add.append(
                MutableCollectionMetadata(
                    repository_version=new_version,
                    collection_id=collection_id,
                    deprecated=deprecated,
                )
            )

        if to_add:
            MutableCollectionMetadata.objects.bulk_create(to_add, ignore_conflicts=True)
