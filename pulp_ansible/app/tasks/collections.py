import asyncio
import contextlib
from gettext import gettext as _
import json
import logging
import math
import tarfile

from django.db import transaction
from galaxy_importer.collection import import_collection as process_collection
from galaxy_importer.collection import CollectionFilename
from galaxy_importer.exceptions import ImporterError
from rq.job import get_current_job

from pulpcore.plugin.models import (
    Artifact,
    ContentArtifact,
    CreatedResource,
    ProgressReport,
    Remote,
    Repository,
)
from pulpcore.plugin.stages import (
    ArtifactDownloader,
    ArtifactSaver,
    ContentSaver,
    DeclarativeArtifact,
    DeclarativeContent,
    DeclarativeVersion,
    RemoteArtifactSaver,
    ResolveContentFutures,
    Stage,
    QueryExistingArtifacts,
    QueryExistingContents,
)
import semantic_version as semver

from pulp_ansible.app.models import (
    Collection,
    CollectionImport,
    CollectionRemote,
    CollectionVersion,
    Tag,
)
from pulp_ansible.app.tasks.utils import (
    get_page_url,
    parse_metadata,
    parse_collections_requirements_file,
)


log = logging.getLogger(__name__)


# default results per page. used to calculate number of pages
PAGE_SIZE = 10


def sync(remote_pk, repository_pk, mirror):
    """
    Sync Collections with ``remote_pk``, and save a new RepositoryVersion for ``repository_pk``.

    Args:
        remote_pk (str): The remote PK.
        repository_pk (str): The repository PK.
        mirror (bool): True for mirror mode, False for additive.

    Raises:
        ValueError: If the remote does not specify a URL to sync.

    """
    remote = CollectionRemote.objects.get(pk=remote_pk)
    repository = Repository.objects.get(pk=repository_pk)

    if not remote.url:
        raise ValueError(_("A CollectionRemote must have a 'url' specified to synchronize."))

    first_stage = CollectionSyncFirstStage(remote)
    d_version = AnsibleDeclarativeVersion(first_stage, repository, mirror=mirror)
    d_version.create()


def import_collection(
    artifact_pk,
    repository_pk=None,
    expected_namespace=None,
    expected_name=None,
    expected_version=None,
):
    """
    Create a Collection from an uploaded artifact and optionally validate its expected metadata.

    This task provides optional validation of the `namespace`, `name`, and `version` metadata
    attributes. If the Artifact fails validation or parsing, the Artifact is deleted and the
    Collection is not created.

    This task performs a CollectionImport object get_or_create() to allow import messages to be
    logged.

    Args:
        artifact_pk (str): The pk of the Artifact to create the Collection from.

    Keyword Args:
        repository_pk (str): Optional. If specified, a new RepositoryVersion will be created for the
            Repository and any new Collection content associated with it.
        expected_namespace (str): Optional. The namespace is validated against the namespace
            specified in the Collection's metadata. If it does not match a ImporterError is
            raised.
        expected_name (str): Optional. The name is validated against the name specified in the
            Collection's metadata. If it does not match a ImporterError is raised.
        expected_version (str): Optional. The version is validated against the version specified in
            the Collection's metadata. If it does not match a ImporterError is raised.

    Raises:
        ImporterError: If the `expected_namespace`, `expected_name`, or `expected_version` do not
            match the metadata in the tarball.

    """

    CollectionImport.objects.get_or_create(task_id=get_current_job().id)

    artifact = Artifact.objects.get(pk=artifact_pk)
    filename = CollectionFilename(expected_namespace, expected_name, expected_version)
    log.info(f"Processing collection from {artifact.file.name}")
    import_logger = logging.getLogger("pulp_ansible.app.tasks.collection.import_collection")

    with _artifact_guard(artifact):
        try:
            with artifact.file.open() as artifact_file:
                importer_result = process_collection(
                    artifact_file, filename=filename, logger=import_logger
                )

        except ImporterError as exc:
            log.info(f"Collection processing was not successfull: {exc}")
            raise

    collection_info = importer_result["metadata"]

    with transaction.atomic():
        collection, created = Collection.objects.get_or_create(
            namespace=collection_info["namespace"], name=collection_info["name"]
        )

        tags = collection_info.pop("tags")

        # Remove fields not used by this model
        collection_info.pop("license_file")
        collection_info.pop("readme")

        # the importer returns many None values. We need to let the defaults in the model prevail
        for key in ["description", "documentation", "homepage", "issues", "repository"]:
            if collection_info[key] is None:
                collection_info.pop(key)

        collection_version = CollectionVersion(
            collection=collection,
            **collection_info,
            contents=importer_result["contents"],
            docs_blob=importer_result["docs_blob"],
        )
        collection_version.save()

        for name in tags:
            tag, created = Tag.objects.get_or_create(name=name)
            collection_version.tags.add(tag)

        _update_highest_version(collection_version)

        collection_version.save()  # Save the FK updates

        ContentArtifact.objects.create(
            artifact=artifact,
            content=collection_version,
            relative_path=collection_version.relative_path,
        )
        CreatedResource.objects.create(content_object=collection_version)

        if repository_pk:
            repository = Repository.objects.get(pk=repository_pk)
            content_q = CollectionVersion.objects.filter(pk=collection_version.pk)
            with repository.new_version() as new_version:
                new_version.add_content(content_q)
            CreatedResource.objects.create(content_object=repository)


def _update_highest_version(collection_version):
    """
    Checks if this version is greater than the most highest one.

    If this version is the first version in collection, is_highest is set to True.
    If this version is greater than the highest version in collection, set is_highest
    equals False on the last highest version and True on this version.
    Otherwise does nothing.
    """
    last_highest = collection_version.collection.versions.filter(is_highest=True).first()
    if not last_highest:
        collection_version.is_highest = True
        return None
    if semver.compare(collection_version.version, last_highest.version) > 0:
        last_highest.is_highest = False
        collection_version.is_highest = True
        last_highest.save()
        collection_version.save()


@contextlib.contextmanager
def _artifact_guard(artifact):
    """Will delete artifact in case of exception."""
    try:
        yield artifact
    except Exception:
        artifact.delete()
        raise


class AnsibleDeclarativeVersion(DeclarativeVersion):
    """
    Subclassed Declarative version creates a custom pipeline for RPM sync.
    """

    def pipeline_stages(self, new_version):
        """
        Build a list of stages feeding into the ContentUnitAssociation stage.

        This defines the "architecture" of the entire sync.

        Args:
            new_version (:class:`~pulpcore.plugin.models.RepositoryVersion`): The
                new repository version that is going to be built.

        Returns:
            list: List of :class:`~pulpcore.plugin.stages.Stage` instances

        """
        pipeline = [
            self.first_stage,
            QueryExistingArtifacts(),
            ArtifactDownloader(),
            ArtifactSaver(),
            QueryExistingContents(),
            CollectionContentSaver(),
            RemoteArtifactSaver(),
            ResolveContentFutures(),
        ]

        return pipeline


class CollectionSyncFirstStage(Stage):
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
        self.collection_info = parse_collections_requirements_file(remote.requirements_file)

        # Interpret download policy
        self.deferred_download = self.remote.policy != Remote.IMMEDIATE

    async def run(self):
        """
        Build and emit `DeclarativeContent` from the ansible metadata.
        """
        with ProgressReport(message="Parsing Collection Metadata", code="parsing.metadata") as pb:
            async for metadata in self._fetch_collections():

                url = metadata["download_url"]

                collection_version = CollectionVersion(
                    namespace=metadata["namespace"]["name"],
                    name=metadata["collection"]["name"],
                    version=metadata["version"],
                )

                relative_path = "%s.%s.%s" % (
                    metadata["namespace"]["name"],
                    metadata["collection"]["name"],
                    metadata["version"],
                )

                artifact = metadata["artifact"]

                d_artifact = DeclarativeArtifact(
                    artifact=Artifact(sha256=artifact["sha256"], size=artifact["size"]),
                    url=url,
                    relative_path=relative_path,
                    remote=self.remote,
                    deferred_download=self.deferred_download,
                )
                d_content = DeclarativeContent(content=collection_version, d_artifacts=[d_artifact])
                pb.increment()
                await self.put(d_content)

    async def _fetch_collections(self):
        """
        Fetch the collections in a remote repository.

        Returns:
            async generator: dicts that represent collections from galaxy api

        """
        page_count = 1
        remote = self.remote
        collection_info = self.collection_info

        def _get_url(page):
            if collection_info:
                name, version, source = collection_info[page - 1]
                namespace, name = name.split(".")
                root = source or remote.url
                url = f"{root}/api/v2/collections/{namespace}/{name}"
                return url

            return get_page_url(remote.url, page)

        progress_data = dict(message="Parsing Galaxy Collections API", code="parsing.collections")
        with ProgressReport(**progress_data) as progress_bar:
            url = _get_url(page_count)
            downloader = remote.get_downloader(url=url)
            initial_data = parse_metadata(await downloader.run())

            count = len(self.collection_info) or initial_data.get("count", 1)
            page_count = math.ceil(float(count) / float(PAGE_SIZE))
            progress_bar.total = count
            progress_bar.save()

            # Concurrent downloads are limited by aiohttp...
            not_done = set()
            for page in range(1, page_count + 1):
                downloader = remote.get_downloader(url=_get_url(page))
                not_done.add(downloader.run())

            while not_done:
                done, not_done = await asyncio.wait(not_done, return_when=asyncio.FIRST_COMPLETED)
                for item in done:
                    data = parse_metadata(item.result())
                    for result in data.get("results", [data]):
                        download_url = result.get("download_url")

                        if result.get("versions_url"):
                            not_done.update(
                                [remote.get_downloader(url=result["versions_url"]).run()]
                            )

                        if result.get("version") and not download_url:
                            not_done.update([remote.get_downloader(url=result["href"]).run()])

                        if download_url:
                            yield data
                            progress_bar.increment()


class CollectionContentSaver(ContentSaver):
    """
    A modification of ContentSaver stage that additionally saves Ansible plugin specific items.

    Saves Collection and Tag objects related to the CollectionVersion content unit.
    """

    async def _pre_save(self, batch):
        """
        Save a batch of Collection objects.

        Args:
            batch (list of :class:`~pulpcore.plugin.stages.DeclarativeContent`): The batch of
                :class:`~pulpcore.plugin.stages.DeclarativeContent` objects to be saved.

        """
        for d_content in batch:
            if d_content is None:
                continue
            if not isinstance(d_content.content, CollectionVersion):
                continue

            info = d_content.content.natural_key_dict()
            collection, created = Collection.objects.get_or_create(
                namespace=info["namespace"], name=info["name"]
            )
            d_content.content.collection = collection

    async def _post_save(self, batch):
        """
        Save a batch of CollectionVersion, Tag objects.

        Args:
            batch (list of :class:`~pulpcore.plugin.stages.DeclarativeContent`): The batch of
                :class:`~pulpcore.plugin.stages.DeclarativeContent` objects to be saved.

        """
        for d_content in batch:
            if d_content is None:
                continue
            if not isinstance(d_content.content, CollectionVersion):
                continue
            collection_version = d_content.content
            for d_artifact in d_content.d_artifacts:
                artifact = d_artifact.artifact
                with artifact.file.open() as artifact_file, tarfile.open(
                    fileobj=artifact_file, mode="r"
                ) as tar:
                    log.info(_("Reading MANIFEST.json from {path}").format(path=artifact.file.name))
                    file_obj = tar.extractfile("MANIFEST.json")
                    manifest_data = json.load(file_obj)
                    info = manifest_data["collection_info"]

                # Create the tags
                tags = info.pop("tags")
                for name in tags:
                    tag, created = Tag.objects.get_or_create(name=name)
                    collection_version.tags.add(tag)

                # Remove fields not used by this model
                info.pop("license_file")
                info.pop("readme")

                # Update with the additional data from the Collection
                for attr_name, attr_value in info.items():
                    if attr_value is None:
                        continue
                    setattr(collection_version, attr_name, attr_value)

                _update_highest_version(collection_version)

                collection_version.save()
