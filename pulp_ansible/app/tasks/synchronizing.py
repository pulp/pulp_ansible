import json
import logging
import math

from collections import namedtuple
from concurrent.futures import FIRST_COMPLETED
from contextlib import suppress
from gettext import gettext as _
from urllib.parse import urlparse, urlencode, parse_qs

import asyncio
from django.db.models import Q

from pulpcore.plugin.models import Artifact, RepositoryVersion, Repository, ProgressBar
from pulpcore.plugin.changeset import (
    BatchIterator,
    ChangeSet,
    PendingArtifact,
    PendingContent,
    SizedIterable)
from pulpcore.plugin.tasking import WorkingDirectory

from pulp_ansible.app.models import AnsibleRole, AnsibleRoleVersion, AnsibleRemote


log = logging.getLogger(__name__)


# The natural key.
Key = namedtuple('Key', ('namespace', 'name', 'version'))

# The set of Key to be added and removed.
Delta = namedtuple('Delta', ('additions', 'removals'))

# The Github URL template to fetch a .tar.gz file from
GITHUB_URL = 'https://github.com/%s/%s/archive/%s.tar.gz'

# default results per page. used to calculate number of pages
PAGE_SIZE = 10


def synchronize(remote_pk, repository_pk):
    """
    Sync content from the remote repository.

    Create a new version of the repository that is synchronized with the remote.

    Args:
        remote_pk (str): The remote PK.
        repository_pk (str): The repository PK.

    Raises:
        ValueError: When remote has no url specified.

    """
    remote = AnsibleRemote.objects.get(pk=remote_pk)
    repository = Repository.objects.get(pk=repository_pk)
    base_version = RepositoryVersion.latest(repository)

    if not remote.url:
        raise ValueError(_('A remote must have a url specified to synchronize.'))

    with WorkingDirectory():
        with RepositoryVersion.create(repository) as new_version:
            log.info(
                _('Synchronizing: repository=%(r)s remote=%(p)s'),
                {
                    'r': repository.name,
                    'p': remote.name
                })
            roles = fetch_roles(remote)
            content = fetch_content(base_version)
            delta = find_delta(roles, content)
            additions = build_additions(remote, roles, delta)
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


def parse_roles(metadata):
    """
    Parse roles from  metadata json returned from galaxy.

    Args:
        metadata (dict): Parsed metadata json

    Returns:
        roles (list): List of dicts containing role info

    """
    roles = list()

    for result in metadata['results']:
        role = {'name': result['name'],
                'namespace': result['summary_fields']['namespace']['name'],
                'summary_fields': result['summary_fields'],  # needed for versions
                'github_user': result['github_user'],
                'github_repo': result['github_repo']}
        roles.append(role)

    return roles


def fetch_roles(remote):
    """
    Fetch the roles in a remote repository.

    Args:
        remote (AnsibleRemote): A remote.

    Returns:
        list: a list of dicts that represent roles

    """
    page_count = 0

    def role_page_url(remote, page=1):
        parsed = urlparse(remote.url)
        new_query = parse_qs(parsed.query)
        new_query['page'] = page
        return parsed.scheme + '://' + parsed.netloc + parsed.path + '?' + urlencode(new_query,
                                                                                     doseq=True)

    def parse_metadata(path):
        metadata = json.load(open(path))
        page_count = math.ceil(float(metadata['count']) / float(PAGE_SIZE))
        return page_count, parse_roles(metadata)

    downloader = remote.get_downloader(role_page_url(remote))
    downloader.fetch()

    page_count, roles = parse_metadata(downloader.path)

    progress_bar = ProgressBar(message='Parsing Pages from Galaxy Roles API', total=page_count,
                               done=1, state='running')
    progress_bar.save()

    def downloader_coroutines():
        for page in range(2, page_count + 1):
            downloader = remote.get_downloader(role_page_url(remote, page))
            yield downloader.run()

    loop = asyncio.get_event_loop()
    downloaders = downloader_coroutines()

    not_done = set()
    with suppress(StopIteration):
        for i in range(20):
            not_done.add(next(downloaders))

    while True:
        if not_done == set():
            break
        done, not_done = loop.run_until_complete(asyncio.wait(not_done,
                                                              return_when=FIRST_COMPLETED))
        for item in done:
            download_result = item.result()
            new_page_count, new_roles = parse_metadata(download_result.path)
            roles.extend(new_roles)
            progress_bar.increment()
            with suppress(StopIteration):
                not_done.add(next(downloaders))

    progress_bar.state = 'completed'
    progress_bar.save()

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
        for role_version in AnsibleRoleVersion.objects.filter(pk__in=base_version.content):
            key = Key(name=role_version.role.name, namespace=role_version.role.namespace,
                      version=role_version.version)
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


def build_additions(remote, roles, delta):
    """
    Build the content to be added.

    Args:
        remote (AnsibleRemote): A remote.
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

                url = GITHUB_URL % (metadata['github_user'], metadata['github_repo'],
                                    version['name'])
                role_version = AnsibleRoleVersion(version=version['name'], role=role)
                path = "%s/%s/%s.tar.gz" % (metadata['namespace'], metadata['name'],
                                            version['name'])
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
            q = Q()
            for key in removals:
                role = AnsibleRoleVersion.objects.get(name=key.name, namespace=key.namespace)
                q |= Q(ansibleroleversion__role_id=role.pk, ansibleroleversion__version=key.version)
            q_set = base_version.content.filter(q)
            q_set = q_set.only('id')
            for file in q_set:
                yield file
    return SizedIterable(generate(), len(delta.removals))
