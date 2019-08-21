from asyncio import wait, FIRST_COMPLETED
from gettext import gettext as _
import logging
import math
import resource

from django.db import transaction

from galaxy_importer.collection import import_collection as process_collection

from pulpcore.plugin.models import (
    Artifact,
    ContentArtifact,
    CreatedResource,
    ProgressBar,
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
    RemoveDuplicates,
    ResolveContentFutures,
    Stage,
    QueryExistingArtifacts,
    QueryExistingContents,
)
import semantic_version as semver

from pulp_ansible.app.models import Collection, CollectionRemote, CollectionVersion, Tag
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


def import_collection(artifact_pk):
    """
    Create a Collection from an uploaded artifact.

    Args:
        artifact_pk (str): The pk or the Artifact to create the Collection from.
    """
    artifact = Artifact.objects.get(pk=artifact_pk)
    log.info("Processing collection from {path}".format(path=artifact.file.path))
    importer_result = process_collection(str(artifact.file.path))
    collection_info = importer_result["metadata"]

    with transaction.atomic():
        collection, created = Collection.objects.get_or_create(
            namespace=collection_info["namespace"], name=collection_info["name"]
        )

        tags = collection_info.pop("tags")

        # Remove fields not used by this model
        collection_info.pop("license_file")
        collection_info.pop("readme")

        # Mazer returns many None values. We need to let the defaults in models.py prevail
        for key in ["description", "documentation", "homepage", "issues", "repository"]:
            if collection_info[key] is None:
                collection_info.pop(key)

        collection_version = CollectionVersion(collection=collection, **collection_info)
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
        for dupe_query_dict in self.remove_duplicates:
            pipeline.append(RemoveDuplicates(new_version, **dupe_query_dict))

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
        with ProgressBar(message="Parsing Collection Metadata") as pb:
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
        ulimit = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
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

        with ProgressBar(message="Parsing Galaxy Collections API") as progress_bar:
            url = _get_url(page_count)
            downloader = remote.get_downloader(url=url)
            initial_data = parse_metadata(await downloader.run())

            count = len(self.collection_info) or initial_data.get("count", 1)
            page_count = math.ceil(float(count) / float(PAGE_SIZE))
            batch = min(page_count, math.floor(float(ulimit) / float(PAGE_SIZE * 3)))
            progress_bar.total = count
            progress_bar.save()

            for n in range(1, page_count + 1, batch):
                # Concurrent downloads are limited by aiohttp...
                not_done = set()

                for page in range(n, n + batch):
                    downloader = remote.get_downloader(url=_get_url(page))
                    not_done.add(downloader.run())

                while not_done:
                    done, not_done = await wait(not_done, return_when=FIRST_COMPLETED)
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
                log.info("Processing collection from {path}".format(path=artifact.file.path))
                importer_result = process_collection(str(artifact.file.path))
                info = importer_result["metadata"]

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
