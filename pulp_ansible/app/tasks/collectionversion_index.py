import logging
from collections import defaultdict

from django.db.models import Q
from semantic_version import Version

from pulpcore.plugin.models import RepositoryVersion

from pulp_ansible.app.models import (
    AnsibleCollectionDeprecated,
    AnsibleDistribution,
    AnsibleNamespaceMetadata,
    AnsibleRepository,
    CollectionVersion,
    CollectionVersionSignature,
)
from pulp_ansible.app.models import (
    CrossRepositoryCollectionVersionIndex as CVIndex,
)

log = logging.getLogger(__name__)

INDEX_FIELDS = ["is_highest", "is_signed", "is_deprecated", "namespace_metadata"]
INDEX_BATCH_SIZE = 1000


def has_distribution(repository, repository_version):
    """Is -any- distribution attached to this repo or repo version?"""
    return AnsibleDistribution.objects.filter(
        Q(repository=repository) | Q(repository_version=repository_version)
    ).exists()


def get_highest_version_string_from_cv_objects(cv_objects):
    """Return the highest version as a string (preferring stable releases)."""
    versions_strings = [x.version for x in cv_objects]
    versions = [Version(x) for x in versions_strings]
    versions = sorted(versions, reverse=True)
    stable_versions = [x for x in versions if not x.prerelease]
    if stable_versions:
        return str(stable_versions[0])
    return str(versions[0])


def compute_repository_changes(repository_version):
    """Use the previous version to make a list of namespace(s).name(s) changed."""
    # Figure out what the previous repo version is
    repository = repository_version.repository
    previous_number = repository_version.number - 1
    previous_version = RepositoryVersion.objects.filter(
        repository=repository, number=previous_number
    ).first()

    # If there isn't a previous verison, all things have "changed"
    if previous_version is None:
        return None

    added = repository_version.added(base_version=previous_version).values("pk")
    removed = repository_version.removed(base_version=previous_version).values("pk")
    changed = Q(pk__in=added) | Q(pk__in=removed)

    changed_collections = set(
        CollectionVersion.objects.filter(changed).values_list("namespace", "name").distinct()
    )
    changed_collections.update(
        AnsibleCollectionDeprecated.objects.filter(changed)
        .values_list("namespace", "name")
        .distinct()
    )
    changed_collections.update(
        CollectionVersionSignature.objects.filter(changed)
        .values_list("signed_collection__namespace", "signed_collection__name")
        .distinct()
    )
    changed_collections.update(
        (name, "*")
        for name in AnsibleNamespaceMetadata.objects.filter(changed)
        .values_list("name", flat=True)
        .distinct()
    )

    return changed_collections


def update_index(distribution=None, repository=None, repository_version=None, index_latest=False):
    """Update the index for a distribution, a repository, or a repository version.

    ``index_latest`` builds the repository-level index, whose rows are not keyed to a
    version; otherwise the index rows are keyed to the version being indexed.
    """
    content_version = repository_version
    index_version = None if index_latest else content_version

    if distribution is not None and repository is None and content_version is None:
        if distribution.repository_version:
            content_version = distribution.repository_version
            repository = content_version.repository
            index_version = content_version
        elif distribution.repository is not None:
            repository = distribution.repository
            content_version = repository.latest_version()
            index_version = None
        else:
            return

    # extract repository from repository version if needed
    if repository is None:
        repository = content_version.repository

    # optimization: -must- have an AnsibleRepository for the index model
    if not isinstance(repository, AnsibleRepository):
        repository = AnsibleRepository.objects.filter(pk=repository.pk).first()
        if repository is None:
            return

    # optimization: we only want to index "distributed" CVs
    if distribution is None and not has_distribution(repository, content_version):
        return

    # This block handles a case where the distribution that points at a repository
    # has been deleted. If no other distribution points at the repository, all related
    # indexes need to be removed and to exit early.
    if index_version is None and not has_distribution(repository, content_version):
        CVIndex.objects.filter(repository=repository, repository_version=None).delete()
        return

    # optimizaion: exit early if using a repo version and it's alreay indexed
    if (
        index_version is not None
        and CVIndex.objects.filter(repository_version=index_version).exists()
    ):
        return

    # What has changed between this version and the last?
    changed_collections = compute_repository_changes(content_version)
    if not changed_collections:
        return

    # get all CVs in this repository version
    cvs = content_version.get_content(content_qs=CollectionVersion.objects)

    # Project only what is used: CollectionVersion rows carry large docs_blob/files columns.
    # pulp_type is included because pulpcore's BaseModel.__init__ reads it; without it, each
    # instance triggers a parent-row fetch.
    changed_namespaces = {namespace for namespace, _ in changed_collections}
    cvs_of_changed_namespaces = cvs.filter(namespace__in=changed_namespaces).only(
        "namespace", "name", "version", "pulp_type"
    )
    cvs_by_collection = defaultdict(list)
    for cv in cvs_of_changed_namespaces.iterator():
        colkey = (cv.namespace, cv.name)
        if colkey in changed_collections or (cv.namespace, "*") in changed_collections:
            cvs_by_collection[colkey].append(cv)

    # clean out cvs no longer in the repo when a distro w/ a repo
    if index_version is None:
        CVIndex.objects.filter(repository=repository, repository_version=None).exclude(
            collection_version__pk__in=cvs
        ).delete()

    if not cvs_by_collection:
        return

    # get the set of signatures in this repo version
    signed_pks = set(
        content_version.get_content(content_qs=CollectionVersionSignature.objects).values_list(
            "signed_collection_id", flat=True
        )
    )

    # get the set of deprecations in this repo version
    deprecations_set = set(
        content_version.get_content(content_qs=AnsibleCollectionDeprecated.objects).values_list(
            "namespace", "name"
        )
    )

    # find all the most recent namespace metadata in the repo version
    namespaces = {}
    for ns in content_version.get_content(content_qs=AnsibleNamespaceMetadata.objects).all():
        if ns.name not in namespaces:
            namespaces[ns.name] = ns
            continue
        if namespaces[ns.name].timestamp_of_interest < ns.timestamp_of_interest:
            namespaces[ns.name] = ns

    objs = []
    for (namespace, name), related_cvs in cvs_by_collection.items():
        # what is the "highest" version in this list?
        highest_version = get_highest_version_string_from_cv_objects(related_cvs)

        # should all of these CVs be deprecated?
        is_deprecated = (namespace, name) in deprecations_set
        namespace_metadata = namespaces.get(namespace, None)

        objs.extend(
            CVIndex(
                repository=repository,
                repository_version=index_version,
                collection_version=rcv,
                is_highest=(rcv.version == highest_version),
                is_signed=(rcv.pk in signed_pks),
                is_deprecated=is_deprecated,
                namespace_metadata=namespace_metadata,
            )
            for rcv in related_cvs
        )

    if index_version is not None:
        CVIndex.objects.bulk_create(
            objs,
            batch_size=INDEX_BATCH_SIZE,
            update_conflicts=True,
            unique_fields=["repository", "repository_version", "collection_version"],
            update_fields=INDEX_FIELDS,
        )
        return

    # NULLs do not conflict on the unique index, so ON CONFLICT cannot dedupe here;
    # update existing rows in place to retain their ids.
    for start in range(0, len(objs), INDEX_BATCH_SIZE):
        batch = objs[start : start + INDEX_BATCH_SIZE]
        existing = defaultdict(list)
        for idx in CVIndex.objects.filter(
            repository=repository,
            repository_version=None,
            collection_version__pk__in=[obj.collection_version_id for obj in batch],
        ):
            existing[idx.collection_version_id].append(idx)

        to_create = []
        to_update = []
        for obj in batch:
            current = existing.get(obj.collection_version_id)
            if current is None:
                to_create.append(obj)
                continue
            for row in current:
                for field in INDEX_FIELDS:
                    setattr(row, field, getattr(obj, field))
            to_update.extend(current)
        if to_create:
            CVIndex.objects.bulk_create(to_create)
        if to_update:
            CVIndex.objects.bulk_update(to_update, INDEX_FIELDS)


def update_distribution_index(distribution):
    return update_index(distribution=distribution)


def rebuild_index():
    """Rebuild -everything-."""
    indexed_repos = set()
    dqs = AnsibleDistribution.objects.select_related(
        "repository", "repository_version", "repository_version__repository"
    ).all()
    for distro in dqs:
        if distro.repository_version:
            rv = distro.repository_version
        else:
            rv = distro.repository.latest_version()

        if rv.pk in indexed_repos:
            continue

        update_index(distribution=distro)
        indexed_repos.add(rv.pk)
