import logging

from gettext import gettext as _


from pulpcore.plugin.models import ProgressReport
from pulpcore.plugin.stages import (
    DeclarativeVersion,
    Stage,
)
from pulp_ansible.app.models import AnsibleRepository, GitRemote
from pulp_ansible.app.tasks.collections import declarative_content_from_git_repo

log = logging.getLogger(__name__)


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
    remote = GitRemote.objects.get(pk=remote_pk)
    repository = AnsibleRepository.objects.get(pk=repository_pk)

    if not remote.url:
        raise ValueError(_("A remote must have a url specified to synchronize."))

    log.info(
        _("Synchronizing: repository=%(r)s remote=%(p)s"), {"r": repository.name, "p": remote.name}
    )
    first_stage = GitFirstStage(remote)
    d_version = DeclarativeVersion(first_stage, repository, mirror=mirror)
    return d_version.create()


class GitFirstStage(Stage):
    """
    The first stage of a pulp_ansible sync pipeline for git repositories.
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
        self.metadata_only = self.remote.metadata_only

    async def run(self):
        """
        Build and emit `DeclarativeContent` from the ansible metadata.
        """
        async with ProgressReport(
            message="Cloning Git repository for Collection", code="sync.git.clone"
        ) as pb:
            d_content = await declarative_content_from_git_repo(
                self.remote, self.remote.url, self.remote.git_ref, self.metadata_only
            )
            await self.put(d_content)
            await pb.aincrement()
