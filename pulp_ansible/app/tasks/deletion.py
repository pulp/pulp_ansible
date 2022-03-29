"""
This module includes tasks related to deleting Content.

You can remove Content from a Repository by making a new RepositoryVersion
without the Content. If an API endpoint uses a Distribution which points to
the latest_version of the Repository then the Content is unavailable,
however it is not deleted.

Content can only be deleted if it exists in no RepositoryVersion.

Content cannot be removed from a RepositoryVersion since it is immutable.

Pulp's orphan_cleanup task deletes any Content not part of a RepositoryVersion.
"""

import logging

from pulp_ansible.app.models import Collection, CollectionVersion
from pulpcore.plugin.tasking import add_and_remove, orphan_cleanup

log = logging.getLogger(__name__)


def _cleanup_old_versions(repo):
    """Delete all the old versions of the given repository."""
    for version in repo.versions.complete().order_by("-number")[1:]:
        version.delete()


def _remove_collection_version_from_repos(collection_version):
    """Remove CollectionVersion from latest RepositoryVersion of each repo."""
    for repo in collection_version.repositories.all():
        add_and_remove(repo.pk, add_content_units=[], remove_content_units=[collection_version.pk])
        _cleanup_old_versions(repo)


def delete_collection_version(collection_version_pk):
    """Task to delete CollectionVersion object.

    Sequentially do the following in a single task:
    1. Call _remove_collection_version_from_repos
    2. Run orphan_cleanup to delete the CollectionVersion
    3. Delete Collection if it has no more CollectionVersion
    """
    collection_version = CollectionVersion.objects.get(pk=collection_version_pk)
    collection = collection_version.collection

    _remove_collection_version_from_repos(collection_version)

    log.info("Running orphan_cleanup to delete CollectionVersion object and artifact")
    # Running orphan_protection_time=0 should be safe since we're specifying the content
    # to be deleted. This will prevent orphan_cleanup from deleting content that is in
    # the process of being uploaded.
    orphan_cleanup(content_pks=[collection_version.pk], orphan_protection_time=0)

    if not collection.versions.exists():
        log.info("Collection has no more versions, deleting collection {}".format(collection))
        collection.delete()


def delete_collection(collection_pk):
    """Task to delete Collection object.

    Sequentially do the following in a single task:
    1. For each CollectionVersion call _remove_collection_version_from_repos
    2. Run orphan_cleanup to delete the CollectionVersions
    3. Delete Collection
    """
    collection = Collection.objects.get(pk=collection_pk)
    version_pks = []
    for version in collection.versions.all():
        _remove_collection_version_from_repos(version)
        version_pks.append(version.pk)

    log.info("Running orphan_cleanup to delete CollectionVersion objects and artifacts")
    # Running orphan_protection_time=0 should be safe since we're specifying the content
    # to be deleted. This will prevent orphan_cleanup from deleting content that is in
    # the process of being uploaded.
    orphan_cleanup(content_pks=version_pks, orphan_protection_time=0)

    log.info("Deleting collection {}".format(collection))
    collection.delete()
