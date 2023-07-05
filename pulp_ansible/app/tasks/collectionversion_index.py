import logging
from semantic_version import Version

from django.db.models import Q

from pulp_ansible.app.models import (
    AnsibleDistribution,
    AnsibleCollectionDeprecated,
    AnsibleNamespaceMetadata,
    AnsibleRepository,
    CollectionVersion,
    CollectionVersionSignature,
    CrossRepositoryCollectionVersionIndex as CVIndex,
)

from pulpcore.plugin.models import RepositoryVersion


log = logging.getLogger(__name__)


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

    # This block handles a case where the distribution that points at a repository
    # has been deleted. If no other distribution points at the repository, all related
    # indexes need to be removed and to exit early.
    if not use_repository_version:
        if not has_distribution(repository, repository_version):
            CVIndex.objects.filter(repository=repository, repository_version=None).delete()
            return

    # optimizaion: exit early if using a repo version and it's alreay indexed
    if use_repository_version:
        if CVIndex.objects.filter(repository_version=repository_version).exists():
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

    # get the set of signatures in this repo version
    repo_signatures_pks = repository_version.content.filter(
        pulp_type="ansible.collection_signature"
    ).values_list("pk", flat=True)
    repo_signatures = CollectionVersionSignature.objects.filter(pk__in=repo_signatures_pks)

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

    # map out the namespace(s).name(s) for everything in the repo version
    colset = set(cvs.values_list("namespace", "name").distinct())

    repo_v = None
    if use_repository_version:
        repo_v = repository_version

    # clean out cvs no longer in the repo when a distro w/ a repo
    if not use_repository_version:
        CVIndex.objects.filter(repository=repository, repository_version=None).exclude(
            collection_version__pk__in=cvs
        ).delete()

    # iterate through each collection in the repository
    for colkey in colset:
        namespace, name = colkey

        if (namespace, name) not in changed_collections and (
            namespace,
            "*",
        ) not in changed_collections:
            continue

        # get all the versions for this collection
        related_cvs = cvs.filter(namespace=namespace, name=name).only("version")

        # what is the "highest" version in this list?
        highest_version = get_highest_version_string_from_cv_objects(related_cvs)

        # should all of these CVs be deprecated?
        is_deprecated = colkey in deprecations_set

        # process each related CV
        for rcv in related_cvs:
            # get the related signatures for this CV
            rcv_signatures = repo_signatures.filter(signed_collection=rcv).count()

            # create|update the index for this CV
            CVIndex.objects.update_or_create(
                repository=repository,
                repository_version=repo_v,
                collection_version=rcv,
                defaults={
                    "is_highest": rcv.version == highest_version,
                    "is_signed": rcv_signatures > 0,
                    "is_deprecated": is_deprecated,
                    "namespace_metadata": namespaces.get(namespace, None),
                },
            )


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
