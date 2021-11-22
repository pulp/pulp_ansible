import logging

from asgiref.sync import sync_to_async
from django.urls import reverse
from django.db.utils import IntegrityError
from galaxy_importer.collection import sync_collection
from gettext import gettext as _
from git import GitCommandError, Repo
from rest_framework.exceptions import ValidationError

from pulpcore.plugin.models import Artifact, ContentArtifact, ProgressReport
from pulpcore.plugin.stages import (
    DeclarativeArtifact,
    DeclarativeContent,
    DeclarativeVersion,
    Stage,
)
from pulp_ansible.app.models import AnsibleRepository, CollectionVersion, GitRemote
from pulp_ansible.app.tasks.collections import create_collection_from_importer

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
            if self.remote.git_ref:
                try:
                    gitrepo = Repo.clone_from(
                        self.remote.url, self.remote.name, depth=1, branch=self.remote.git_ref
                    )
                except GitCommandError:
                    gitrepo = Repo.clone_from(self.remote.url, self.remote.name)
                    gitrepo.git.checkout(self.remote.git_ref)
            else:
                gitrepo = Repo.clone_from(self.remote.url, self.remote.name, depth=1)
            commit_sha = gitrepo.head.commit.hexsha
            metadata, artifact_path = sync_collection(gitrepo.working_dir, ".")
            if not self.remote.metadata_only:
                artifact = Artifact.init_and_validate(artifact_path)
                try:
                    await sync_to_async(artifact.save)()
                except IntegrityError:
                    artifact = Artifact.objects.get(sha256=artifact.sha256)
                metadata["artifact_url"] = reverse("artifacts-detail", args=[artifact.pk])
                metadata["artifact"] = artifact
            else:
                metadata["artifact"] = None
                metadata["artifact_url"] = None
            metadata["remote_artifact_url"] = "{}/commit/{}".format(
                self.remote.url.rstrip("/"), commit_sha
            )
            await self._add_collection_version(metadata)
            await pb.aincrement()

    async def _add_collection_version(self, metadata):
        """Add CollectionVersion to the sync pipeline."""
        artifact = metadata["artifact"]
        try:
            collection_version = await sync_to_async(create_collection_from_importer)(
                metadata, metadata_only=self.remote.metadata_only
            )
            await sync_to_async(ContentArtifact.objects.get_or_create)(
                artifact=artifact,
                content=collection_version,
                relative_path=collection_version.relative_path,
            )
        except ValidationError as e:
            if e.args[0]["non_field_errors"][0].code == "unique":
                namespace = metadata["metadata"]["namespace"]
                name = metadata["metadata"]["name"]
                version = metadata["metadata"]["version"]
            else:
                raise e
            collection_version = await sync_to_async(CollectionVersion.objects.get)(
                namespace=namespace, name=name, version=version
            )
        if artifact is None:
            artifact = Artifact()
        d_artifact = DeclarativeArtifact(
            artifact=artifact,
            url=metadata["remote_artifact_url"],
            relative_path=collection_version.relative_path,
            remote=self.remote,
            deferred_download=self.metadata_only,
        )

        # TODO: docs blob support??

        d_content = DeclarativeContent(
            content=collection_version,
            d_artifacts=[d_artifact],
        )
        await self.put(d_content)
