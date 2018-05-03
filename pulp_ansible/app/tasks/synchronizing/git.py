import logging
import os
import tarfile

from collections import namedtuple
from concurrent.futures import FIRST_COMPLETED
from contextlib import suppress
from gettext import gettext as _
from urllib.parse import urlparse, urlencode, parse_qs

import asyncio
from celery import shared_task
from django.db.models import Q
from git import Repo

from pulpcore.plugin.models import Artifact, RepositoryVersion, Repository, ProgressBar
from pulpcore.plugin.changeset import (
    BatchIterator,
    ChangeSet,
    PendingArtifact,
    PendingContent,
    SizedIterable)
from pulpcore.plugin.tasking import UserFacingTask, WorkingDirectory

from pulp_ansible.app.models import AnsibleRole, AnsibleRoleVersion, AnsibleGitRemote


log = logging.getLogger(__name__)


# The natural key.
Key = namedtuple('Key', ('namespace', 'name', 'version'))

# The set of Key to be added and removed.
Delta = namedtuple('Delta', ('additions', 'removals'))


@shared_task(base=UserFacingTask)
def synchronize(remote_pk, repository_pk, role_pk):
    """
    Create a new version of the repository that is synchronized with the remote
    as specified by the remote.

    Args:
        remote_pk (str): The remote PK.
        repository_pk (str): The repository PK.

    Raises:
        ValueError: When remote has no url specified.
    """
    remote = AnsibleGitRemote.objects.get(pk=remote_pk)
    repository = Repository.objects.get(pk=repository_pk)
    role = AnsibleRole.objects.get(pk=role_pk)
    base_version = RepositoryVersion.latest(repository)

    if not remote.url:
        raise ValueError(_('A remote must have a url specified to synchronize.'))

    with WorkingDirectory() as working_dir:
        with RepositoryVersion.create(repository) as new_version:
            log.info(
                _('Synchronizing: repository=%(r)s remote=%(p)s'),
                {
                    'r': repository.name,
                    'p': remote.name
                })
            versions = fetch_role_versions(remote, os.join(working_dir, remote.id), role)
            content = fetch_content(base_version)
            delta = find_delta(versions, content)
            additions = build_additions(remote, versions, delta)
            removals = build_removals(base_version, delta)
            changeset = ChangeSet(
                remote=remote,
                repository_version=new_version,
                additions=additions,
                removals=removals)
            for report in changeset.apply():
                if not log.isEnabledFor(logging.DEBUG):
                    continue
                log.debug(
                    _('Applied: repository=%(r)s remote=%(p)s change:%(c)s'),
                    {
                        'r': repository.name,
                        'p': remote.name,
                        'c': report,
                    })


def fetch_role_versions(remote, working_dir, role):
    """
    Fetch the role versions in a remote git repository

    Args:
        remote (AnsibleGitRemote): A remote.

    Returns:
        list: a list of dicts that represent roles
    """
    repo = Repo.clone_from(remote.url, working_dir)
    tags = repo.tags
    versions = set()

    progress_bar = ProgressBar(message='Fetching and parsing git repo', total=len(tags),
                               done=0, state='running')
    progress_bar.save()

    for tag in tags:
        repo.heads.tag.checkout()
        versions.append(Key(name=role.name, namespace=role.namespace, version=tag.name))
        with tarfile.open(tag.name, "w:gz") as tar:
            tar.add(working_dir, arcname=os.path.basename(working_dir))
        progress_bar.increment()

    progress_bar.state = 'completed'
    progress_bar.save()

    return versions


def fetch_content(base_version):
    """
    Fetch the AnsibleRoleVersions contained in the (base) repository version.

    Args:
        base_version (RepositoryVersion): A repository version.

    Returns:
        set: A set of Key contained in the (base) repository version.
    """
    content = set()
    if base_version:
        for role_version in AnsibleRoleVersion.objects.filter(pk__in=base_version.content):
            key = Key(name=role_version.role.name, namespace=role_version.role.namespace,
                      version=role_version.version)
            content.add(key)
    return content


def find_delta(role_versions, content, mirror=True):
    """
    Find the content that needs to be added and removed.

    Args:
        roles (list): A list of roles from a remote repository
        content: (set): The set of natural keys for content contained in the (base)
            repository version.
        mirror (bool): The delta should include changes needed to ensure the content
            contained within the pulp repository is exactly the same as the
            content contained within the remote repository.

    Returns:
        Delta: The set of Key to be added and removed.
    """
    remote_content = set()
    additions = (role_versions - content)
    if mirror:
        removals = (content - remote_content)
    else:
        removals = set()
    return Delta(additions, removals)


def build_additions(remote, roles, delta):
    """
    Build the content to be added.

    Args:
        remote (AnsibleGitRemote): A remote.
        roles (list): The list of role dict from Git
        delta (Delta): The set of Key to be added and removed.

    Returns:
        SizedIterable: The PendingContent to be added to the repository.
    """
    pass
    # def generate():
        # for metadata in roles:
            # role, _ = AnsibleRole.objects.get_or_create(name=metadata['name'],
                                                        # namespace=metadata['namespace'])

            # for version in metadata['summary_fields']['versions']:
                # key = Key(name=metadata['name'],
                          # namespace=metadata['namespace'],
                          # version=version['name'])

                # if key not in delta.additions:
                    # continue

                # url = GITHUB_URL % (metadata['github_user'], metadata['github_repo'],
                                    # version['name'])
                # role_version = AnsibleRoleVersion(version=version['name'], role=role)
                # path = "%s/%s/%s.tar.gz" % (metadata['namespace'], metadata['name'],
                                            # version['name'])
                # artifact = Artifact()
                # content = PendingContent(
                    # role_version,
                    # artifacts={
                        # PendingArtifact(artifact, url, path)
                    # })
                # yield content
    # return SizedIterable(generate(), len(delta.additions))


def build_removals(base_version, delta):
    """
    Build the content to be removed.

    Args:
        base_version (RepositoryVersion):  The base repository version.
        delta (Delta): The set of Key to be added and removed.

    Returns:
        SizedIterable: The AnsibleRoleVersion to be removed from the repository.
    """
    def generate():
        for removals in BatchIterator(delta.removals):
            q = Q()
            for key in removals:
                role = AnsibleRoleVersion.objects.get(name=key.name, namespace=key.namespace)
                q |= Q(ansibleroleversion__role_id=role.pk, ansibleroleversion__version=key.version)
            q_set = base_version.content.filter(q)
            q_set = q_set.only('id')
            for file in q_set:
                yield file
    return SizedIterable(generate(), len(delta.removals))
