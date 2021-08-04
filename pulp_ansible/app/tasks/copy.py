from django.db import transaction
from django.db.models import Q
from pulpcore.plugin.models import RepositoryVersion

from pulp_ansible.app.models import AnsibleRepository


@transaction.atomic
def copy_content(config):
    """
    Copy content from one repo to another in a single transaction.

    This should be an iterable of dictionaries, with each dictionary containing the following keys:

        * source_repo_version: The RepositoryVersion pk
        * dest_repo: The pk of the `AnsibleRepository` pk to copy content into. This repository will
            receive the new RepositoryVersion with the copied content.
        * `content`: An optional key that if specified should contain a list of pks to copy. These
            specified keys must be members of the `source_repo_version`. If unspecified all content
            from the `source_repo_version` will be copied to the `dest_repo`.

    Args:
        config (iterable): The config that identifies the `source_repo_version`, `dest_repo`, and
            and `content`.

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
