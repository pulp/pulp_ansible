from django.db import transaction
from django.db.models import Q
from pulpcore.plugin.models import RepositoryVersion

from pulp_ansible.app.models import AnsibleCollectionDeprecated, AnsibleRepository, Collection


@transaction.atomic
def copy_content(config):
    """
    Copy content from one repo to another.

    Accepts a config containing:
      * source_repo_version_pk: repository version primary key to copy units from
      * dest_repo_pk: repository primary key to copy units into
      * content_pks: a list of content pks to copy from source to destination

    """

    def process_entry(entry):
        source_repo_version = RepositoryVersion.objects.get(pk=entry["source_repo_version"])
        dest_repo = AnsibleRepository.objects.get(pk=entry["dest_repo"])

        dest_version_provided = bool(entry.get("dest_base_version"))
        if dest_version_provided:
            dest_repo_version = RepositoryVersion.objects.get(pk=entry["dest_base_version"])
        else:
            dest_repo_version = dest_repo.latest_version()

        if entry.get("content") is not None:
            content_filter = Q(pk__in=entry.get("content"))
        else:
            content_filter = Q()

        return (
            source_repo_version,
            dest_repo_version,
            dest_repo,
            content_filter,
            dest_version_provided,
        )

    for entry in config:
        (
            source_repo_version,
            dest_repo_version,
            dest_repo,
            content_filter,
            dest_version_provided,
        ) = process_entry(entry)

        content_to_copy = source_repo_version.content.filter(content_filter)

        base_version = dest_repo_version if dest_version_provided else None
        with dest_repo.new_version(base_version=base_version) as new_version:
            new_version.add_content(content_to_copy)
            deprecated_in_source_repo_version_qs = Collection.objects.filter(
                ansiblecollectiondeprecated__repository_version=source_repo_version
            )
            to_deprecate = []
            for collection_deprecated in deprecated_in_source_repo_version_qs:
                to_deprecate.append(
                    AnsibleCollectionDeprecated(
                        repository_version=new_version, collection=collection_deprecated
                    )
                )

            if to_deprecate:
                AnsibleCollectionDeprecated.objects.bulk_create(to_deprecate, ignore_conflicts=True)
