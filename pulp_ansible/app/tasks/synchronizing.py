import json
import logging
import os

from collections import namedtuple
from gettext import gettext as _
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs

import asyncio
from aiohttp import ClientSession
from celery import shared_task
from django.db.models import Q

from pulpcore.plugin.models import Artifact, RepositoryVersion, Repository
from pulpcore.plugin.changeset import (
    BatchIterator,
    ChangeSet,
    PendingArtifact,
    PendingContent,
    SizedIterable)
from pulpcore.plugin.tasking import UserFacingTask, WorkingDirectory

from pulp_ansible.app.models import AnsibleRole, AnsibleRoleVersion, AnsibleImporter


log = logging.getLogger(__name__)


# The natural key.
Key = namedtuple('Key', ('namespace', 'name', 'version'))

# The set of Key to be added and removed.
Delta = namedtuple('Delta', ('additions', 'removals'))


# the roles per page when fetching the list of roles
PAGE_SIZE = 1000

GITHUB_URL = 'https://github.com/%s/%s/archive/%s.tar.gz'


@shared_task(base=UserFacingTask)
def synchronize(importer_pk, repository_pk):
    """
    Create a new version of the repository that is synchronized with the remote
    as specified by the importer.

    Args:
        importer_pk (str): The importer PK.
        repository_pk (str): The repository PK.

    Raises:
        ValueError: When feed_url is empty.
    """
    importer = AnsibleImporter.objects.get(pk=importer_pk)
    repository = Repository.objects.get(pk=repository_pk)
    base_version = RepositoryVersion.latest(repository)

    if not importer.feed_url:
        raise ValueError(_('An importer must have a feed_url specified to synchronize.'))

    with WorkingDirectory():
        with RepositoryVersion.create(repository) as new_version:
            log.info(
                _('Synchronizing: repository=%(r)s importer=%(p)s'),
                {
                    'r': repository.name,
                    'p': importer.name
                })
            roles = fetch_roles(importer)
            content = fetch_content(base_version)
            delta = find_delta(roles, content)
            additions = build_additions(importer, roles, delta)
            removals = build_removals(base_version, delta)
            changeset = ChangeSet(
                importer=importer,
                repository_version=new_version,
                additions=additions,
                removals=removals)
            for report in changeset.apply():
                if not log.isEnabledFor(logging.DEBUG):
                    continue
                log.debug(
                    _('Applied: repository=%(r)s importer=%(p)s change:%(c)s'),
                    {
                        'r': repository.name,
                        'p': importer.name,
                        'c': report,
                    })


def parse_roles(metadata):
    """
    Parse roles from  metadata json returned from galaxy

    Args:
        metadata (dict): Parsed metadata json

    Returns:
        roles (list): List of dicts containing role info
    """
    roles = list()

    for result in metadata['results']:
        role = {'name': result['name'],
                'namespace': result['namespace'],
                'summary_fields': result['summary_fields'],  # needed for versions
                'github_user': result['github_user'],
                'github_repo': result['github_repo']}
        roles.append(role)

    return roles


def fetch_roles(importer):
    """
    Fetch the roles in a remote repository

    Args:
        importer (AnsibleImporter): An importer.

    Returns:
        list: a list of dicts that represent roles
    """
    page_count = 0

    def role_url(importer, page=1, page_size=PAGE_SIZE):
        parsed = urlparse(importer.feed_url)
        new_query = {**parse_qs(parsed.query), **{'page': page, 'page_size': page_size}}
        parsed._replace(query=urlencode(new_query))
        return urlunparse(parsed)

    def parse_metadata(path):
        nonlocal page_count

        metadata = json.load(open(path))
        page_count = metadata['num_pages']
        return parse_roles(metadata)

    url = importer
    downloader = importer.get_downloader(role_url(importer))
    downloader.fetch()
    roles = parse_metadata(downloader.path)

    # TODO: make sure this loop runs asynchronously
    for page in range(2, page_count + 1):
        downloader = importer.get_downloader(role_url(importer, page))
        downloader.fetch()
        roles.extend(parse_metadata(downloader.path))

    return roles


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
        for role in AnsibleRoleVersion.objects.filter(pk__in=base_version.content):
            key = Key(name=role.name, namespace=role.namespace, version=role.version)
            content.add(key)
    return content


def find_delta(roles, content, mirror=True):
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
    for r in roles:
        for version in r['summary_fields']['versions']:
            role = Key(name=r['name'],
                       namespace=r['namespace'],
                       version=version['name'])
            remote_content.add(role)
    additions = (remote_content - content)
    if mirror:
        removals = (content - remote_content)
    else:
        removals = set()
    return Delta(additions, removals)


def build_additions(importer, roles, delta):
    """
    Build the content to be added.

    Args:
        importer (AnsibleImporter): An importer.
        roles (list): The list of role dict from Galaxy
        delta (Delta): The set of Key to be added and removed.

    Returns:
        SizedIterable: The PendingContent to be added to the repository.
    """
    def generate():
        for metadata in roles:
            role, _ = AnsibleRole.objects.get_or_create(name=metadata['name'],
                                                        namespace=metadata['namespace'])

            for version in metadata['summary_fields']['versions']:
                key = Key(name=metadata['name'],
                          namespace=metadata['namespace'],
                          version=version['name'])

                if key not in delta.additions:
                    continue

                url = GITHUB_URL % (metadata['github_user'], metadata['github_repo'], version['name'])
                role_version = AnsibleRoleVersion(version=version['name'], role=role)
                path = "%s/%s/%s.tar" % (metadata['namespace'], metadata['name'], version['name'])
                artifact = Artifact()
                content = PendingContent(
                    role_version,
                    artifacts={
                        PendingArtifact(artifact, url, path)
                    })
                yield content
    return SizedIterable(generate(), len(delta.additions))


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
            role = Role.objects.get(name=key.name, namespace=key.namespace)
            q = Q()
            for key in removals:
                q |= Q(ansibleroleversion__role_id=role.pk, ansibleroleversion__version=key.version)
            q_set = base_version.content.filter(q)
            q_set = q_set.only('id')
            for file in q_set:
                yield file
    return SizedIterable(generate(), len(delta.removals))
