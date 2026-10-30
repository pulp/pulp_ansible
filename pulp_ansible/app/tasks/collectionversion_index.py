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

    changed_collections = set()

    cv_type = CollectionVersion.get_pulp_type()
    deprecation_type = AnsibleCollectionDeprecated.get_pulp_type()
    signature_type = CollectionVersionSignature.get_pulp_type()
    metadata_type = AnsibleNamespaceMetadata.get_pulp_type()

    for func in [repository_version.added, repository_version.removed]:
        for modified in func(base_version=previous_version):
            if modified.pulp_type == cv_type:
                cv = modified.ansible_collectionversion
                changed_collections.add((cv.namespace, cv.name))
            elif modified.pulp_type == deprecation_type:
                deprecation = modified.ansible_ansiblecollectiondeprecated
                changed_collections.add((deprecation.namespace, deprecation.name))
            elif modified.pulp_type == signature_type:
                signature = modified.ansible_collectionversionsignature
                changed_collections.add(
                    (signature.signed_collection.namespace, signature.signed_collection.name)
                )
            elif modified.pulp_type == metadata_type:
                metadata = modified.ansible_ansiblenamespacemetadata
                changed_collections.add((metadata.name, "*"))

    return changed_collections


def update_index(distribution=None, repository=None, repository_version=None, is_latest=False):
    """Rebuild index by distribtion|repository|repositoryversion."""

    # if the distro points at a specific repo version, we should use that in the index
    # otherwise the index value for repository version should be null
    # use_repository_version = False
    use_repository_version = not is_latest

    # a repov was passed in so we should use that
    # if repository_version:
    #    use_repository_version = True

    # make sure the distro points at a repo[version]
    if distribution and not repository and not repository_version:
        # sometimes distros point at a version
        if distribution.repository_version:
            repository = distribution.repository_version.repository
            repository_version = distribution.repository_version
            use_repository_version = True

        # sometimes distros point at a repository
        elif distribution.repository is not None:
            repository = distribution.repository
            repository_version = distribution.repository.latest_version()
            # is_latest = True
            use_repository_version = False

        # sometimes distros point at nothing?
        else:
            return

    # extract repository from repository version if needed
    if repository is None:
        repository = repository_version.repository

    # optimization: -must- have an AnsibleRepository for the index model
    if not isinstance(repository, AnsibleRepository):
        repository = AnsibleRepository.objects.filter(pk=repository.pk).first()
        if repository is None:
            return

    # optimization: we only want to index "distributed" CVs
    if distribution is None and not has_distribution(repository, repository_version):
        return

    repo_v = repository_version if use_repository_version else None

    # This block handles a case where the distribution that points at a repository
    # has been deleted. If no other distribution points at the repository, all related
    # indexes need to be removed and to exit early.
    if repo_v is None and not has_distribution(repository, repository_version):
        CVIndex.objects.filter(repository=repository, repository_version=None).delete()
        return

    # optimizaion: exit early if using a repo version and it's alreay indexed
    if repo_v is not None and CVIndex.objects.filter(repository_version=repo_v).exists():
        return

    # What has changed between this version and the last?
    changed_collections = compute_repository_changes(repository_version)
    if not changed_collections:
        return

    # get all CVs in this repository version
    cvs_pks = repository_version.content.filter(pulp_type="ansible.collection_version").values_list(
        "pk", flat=True
    )
    cvs = CollectionVersion.objects.filter(pk__in=cvs_pks)

    # Project only what is used: CollectionVersion rows carry large docs_blob/files columns.
    changed_namespaces = {namespace for namespace, _ in changed_collections}
    cvs_of_changed_namespaces = cvs.filter(namespace__in=changed_namespaces).only(
        "namespace", "name", "version"
    )
    cvs_by_collection = defaultdict(list)
    for cv in cvs_of_changed_namespaces.iterator():
        colkey = (cv.namespace, cv.name)
        if colkey in changed_collections or (cv.namespace, "*") in changed_collections:
            cvs_by_collection[colkey].append(cv)

    # clean out cvs no longer in the repo when a distro w/ a repo
    if repo_v is None:
        CVIndex.objects.filter(repository=repository, repository_version=None).exclude(
            collection_version__pk__in=cvs
        ).delete()

    if not cvs_by_collection:
        return

    # get the set of signatures in this repo version
    repo_signatures_pks = repository_version.content.filter(
        pulp_type="ansible.collection_signature"
    ).values_list("pk", flat=True)
    signed_pks = set(
        CollectionVersionSignature.objects.filter(pk__in=repo_signatures_pks).values_list(
            "signed_collection_id", flat=True
        )
    )

    # get the set of deprecations in this repo version
    deprecations = repository_version.content.filter(
        pulp_type="ansible.collection_deprecation"
    ).values_list("pk", flat=True)
    deprecations = AnsibleCollectionDeprecated.objects.filter(pk__in=deprecations)
    deprecations_set = {(x.namespace, x.name) for x in deprecations}

    # find all the most recent namespace metadata in the repo version
    namespaces = {}
    for ns in repository_version.get_content(content_qs=AnsibleNamespaceMetadata.objects).all():
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
                repository_version=repo_v,
                collection_version=rcv,
                is_highest=(rcv.version == highest_version),
                is_signed=(rcv.pk in signed_pks),
                is_deprecated=is_deprecated,
                namespace_metadata=namespace_metadata,
            )
            for rcv in related_cvs
        )

    if repo_v is not None:
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
