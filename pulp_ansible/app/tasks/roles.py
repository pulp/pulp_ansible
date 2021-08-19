import asyncio
import logging
import math

from asyncio import FIRST_COMPLETED
from gettext import gettext as _

from pulpcore.plugin.models import Artifact, ProgressReport, Remote
from pulpcore.plugin.stages import (
    DeclarativeArtifact,
    DeclarativeContent,
    DeclarativeVersion,
    Stage,
)
from pulp_ansible.app.constants import PAGE_SIZE
from pulp_ansible.app.models import AnsibleRepository, RoleRemote, Role
from pulp_ansible.app.tasks.utils import get_api_version, get_page_url, parse_metadata


log = logging.getLogger(__name__)


# The Github URL template to fetch a .tar.gz file from
GITHUB_URL = "https://github.com/%s/%s/archive/%s.tar.gz"


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
    remote = RoleRemote.objects.get(pk=remote_pk)
    repository = AnsibleRepository.objects.get(pk=repository_pk)

    if not remote.url:
        raise ValueError(_("A remote must have a url specified to synchronize."))

    log.info(
        _("Synchronizing: repository=%(r)s remote=%(p)s"), {"r": repository.name, "p": remote.name}
    )
    first_stage = RoleFirstStage(remote)
    d_version = DeclarativeVersion(first_stage, repository, mirror=mirror)
    return d_version.create()


class RoleFirstStage(Stage):
    """
    The first stage of a pulp_ansible sync pipeline for roles.
    """

    def __init__(self, remote):
        """
        The first stage of a pulp_ansible sync pipeline.

        Args:
            remote (RoleRemote): The remote data to be used when syncing

        """
        super().__init__()
        self.remote = remote

        # Interpret download policy
        self.deferred_download = self.remote.policy != Remote.IMMEDIATE

    async def run(self):
        """
        Build and emit `DeclarativeContent` from the ansible metadata.
        """
        async with ProgressReport(
            message="Parsing Role Metadata", code="sync.parsing.metadata"
        ) as pb:
            async for metadata in self._fetch_roles():
                for version in metadata["summary_fields"]["versions"]:
                    url = GITHUB_URL % (
                        metadata["github_user"],
                        metadata["github_repo"],
                        version["name"],
                    )
                    role = Role(
                        version=version["name"],
                        name=metadata["name"],
                        namespace=metadata["namespace"],
                    )
                    relative_path = "%s/%s/%s.tar.gz" % (
                        metadata["namespace"],
                        metadata["name"],
                        version["name"],
                    )
                    d_artifact = DeclarativeArtifact(
                        artifact=Artifact(),
                        url=url,
                        relative_path=relative_path,
                        remote=self.remote,
                        deferred_download=self.deferred_download,
                    )
                    d_content = DeclarativeContent(content=role, d_artifacts=[d_artifact])
                    await pb.aincrement()
                    await self.put(d_content)

    async def _fetch_roles(self):
        async for metadata in self._fetch_galaxy_pages():
            for result in metadata["results"]:
                role = {
                    "name": result["name"],
                    "namespace": result["summary_fields"]["namespace"]["name"],
                    "summary_fields": result["summary_fields"],  # needed for versions
                    "github_user": result["github_user"],
                    "github_repo": result["github_repo"],
                }
                yield role

    async def _fetch_galaxy_pages(self):
        """
        Fetch the roles in a remote repository.

        Returns:
            async generator: dicts that represent pages from galaxy api

        """
        page_count = 0
        remote = self.remote

        progress_data = dict(
            message="Parsing Pages from Galaxy Roles API", code="sync.parsing.roles"
        )
        async with ProgressReport(**progress_data) as progress_bar:
            api_version = get_api_version(remote.url)
            downloader = remote.get_downloader(url=get_page_url(remote.url, api_version))
            metadata = parse_metadata(await downloader.run())

            page_count = math.ceil(float(metadata["count"]) / float(PAGE_SIZE))
            progress_bar.total = page_count
            await progress_bar.asave()

            yield metadata
            await progress_bar.aincrement()

            # Concurrent downloads are limited by aiohttp...
            not_done = set(
                remote.get_downloader(url=get_page_url(remote.url, api_version, page)).run()
                for page in range(2, page_count + 1)
            )

            while not_done:
                done, not_done = await asyncio.wait(not_done, return_when=FIRST_COMPLETED)
                for item in done:
                    yield parse_metadata(item.result())
                    await progress_bar.aincrement()
