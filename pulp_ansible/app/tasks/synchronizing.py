import asyncio
import json
import logging
import math

from asyncio import FIRST_COMPLETED
from gettext import gettext as _
from urllib.parse import (
    parse_qs,
    urlencode,
    urlparse,
    urlunparse,
)

from pulpcore.plugin.models import (
    Artifact,
    ProgressBar,
    Remote,
    Repository,
)
from pulpcore.plugin.stages import (
    DeclarativeArtifact,
    DeclarativeContent,
    DeclarativeVersion,
    Stage,
)
from pulp_ansible.app.models import AnsibleRole, AnsibleRoleVersion, AnsibleRemote


log = logging.getLogger(__name__)


# The Github URL template to fetch a .tar.gz file from
GITHUB_URL = 'https://github.com/%s/%s/archive/%s.tar.gz'

# default results per page. used to calculate number of pages
PAGE_SIZE = 10


def synchronize(remote_pk, repository_pk, mirror=False):
    """
    Sync content from the remote repository.

    Create a new version of the repository that is synchronized with the remote.

    Args:
        remote_pk (str): The remote PK.
        repository_pk (str): The repository PK.
        mirror (bool): True for mirror mode, False for additive.

    Raises:
        ValueError: If the remote does not specify a URL to sync.

    """
    remote = AnsibleRemote.objects.get(pk=remote_pk)
    repository = Repository.objects.get(pk=repository_pk)

    if not remote.url:
        raise ValueError(_('A remote must have a url specified to synchronize.'))

    log.info(
        _('Synchronizing: repository=%(r)s remote=%(p)s'),
        {
            'r': repository.name,
            'p': remote.name,
        },
    )
    first_stage = AnsibleFirstStage(remote)
    d_version = DeclarativeVersion(first_stage, repository, mirror=mirror)
    d_version.create()


class AnsibleFirstStage(Stage):
    """
    The first stage of a pulp_ansible sync pipeline.
    """

    def __init__(self, remote):
        """
        The first stage of a pulp_ansible sync pipeline.

        Args:
            remote (AnsibleRemote): The remote data to be used when syncing

        """
        super().__init__()
        self.remote = remote

        # Interpret download policy
        self.deferred_download = (self.remote.policy != Remote.IMMEDIATE)

    async def run(self):
        """
        Build and emit `DeclarativeContent` from the ansible metadata.
        """
        with ProgressBar(message='Parsing Role Metadata') as pb:
            pending = []
            async for metadata in self._fetch_roles():
                role = AnsibleRole(name=metadata['name'], namespace=metadata['namespace'])
                d_content = DeclarativeContent(content=role, d_artifacts=[], does_batch=False)
                pending.append(asyncio.ensure_future(self._add_role_versions(
                    d_content.get_or_create_future(),
                    metadata,
                )))
                await self.put(d_content)
                pb.increment()
            await asyncio.gather(*pending)

    async def _add_role_versions(self, role_future, metadata):
        role = await role_future
        for version in metadata['summary_fields']['versions']:
            url = GITHUB_URL % (
                metadata['github_user'],
                metadata['github_repo'],
                version['name'],
            )
            role_version = AnsibleRoleVersion(version=version['name'], role=role)
            relative_path = "%s/%s/%s.tar.gz" % (
                metadata['namespace'],
                metadata['name'],
                version['name'],
            )
            d_artifact = DeclarativeArtifact(
                artifact=Artifact(),
                url=url,
                relative_path=relative_path,
                remote=self.remote,
                deferred_download=self.deferred_download,
            )
            d_content = DeclarativeContent(
                content=role_version,
                d_artifacts=[d_artifact],
            )
            await self.put(d_content)

    async def _fetch_roles(self):
        async for metadata in self._fetch_galaxy_pages():
            for result in metadata['results']:
                role = {'name': result['name'],
                        'namespace': result['summary_fields']['namespace']['name'],
                        'summary_fields': result['summary_fields'],  # needed for versions
                        'github_user': result['github_user'],
                        'github_repo': result['github_repo']}
                yield role

    async def _fetch_galaxy_pages(self):
        """
        Fetch the roles in a remote repository.

        Returns:
            async generator: dicts that represent pages from galaxy api

        """
        page_count = 0
        remote = self.remote

        def role_page_url(url, page=1):
            parsed_url = urlparse(url)
            new_query = parse_qs(parsed_url.query)
            new_query['page'] = page
            return urlunparse(parsed_url._replace(query=urlencode(new_query, doseq=True)))

        def parse_metadata(download_result):
            with open(download_result.path) as fd:
                return json.load(fd)

        with ProgressBar(message='Parsing Pages from Galaxy Roles API') as progress_bar:
            downloader = remote.get_downloader(url=role_page_url(remote.url))
            metadata = parse_metadata(await downloader.run())

            page_count = math.ceil(float(metadata['count']) / float(PAGE_SIZE))
            progress_bar.total = page_count
            progress_bar.save()

            yield metadata
            progress_bar.increment()

            # Concurrent downloads are limited by aiohttp...
            not_done = set(
                remote.get_downloader(url=role_page_url(remote.url, page)).run()
                for page in range(2, page_count + 1)
            )

            while not_done:
                done, not_done = await asyncio.wait(not_done, return_when=FIRST_COMPLETED)
                for item in done:
                    yield parse_metadata(item.result())
                    progress_bar.increment()
