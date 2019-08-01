import asyncio
from gettext import gettext as _
import json
import logging
import math
import tarfile

from django.db import transaction
from urllib.parse import urlparse, urlunparse

from pulpcore.plugin.models import (
    Artifact,
    ContentArtifact,
    CreatedResource,
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

from pulp_ansible.app.models import Collection, CollectionRemote, CollectionVersion, Tag
from pulp_ansible.app.tasks.utils import get_json_from_url, get_page_url


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
        ValueError: If the remote does not specify a URL to sync or a ``whitelist`` of Collections
            to sync.

    """
    remote = CollectionRemote.objects.get(pk=remote_pk)
    repository = Repository.objects.get(pk=repository_pk)

    if not remote.url:
        raise ValueError(_("A CollectionRemote must have a 'url' specified to synchronize."))

    if not remote.whitelist:
        raise ValueError(_("A CollectionRemote must have a 'whitelist' specified to synchronize."))

    first_stage = AnsibleFirstStage(remote)
    d_version = DeclarativeVersion(first_stage, repository, mirror=mirror)
    d_version.create()


def import_collection(artifact_pk):
    """
    Create a Collection from an uploaded artifact.

    Args:
        artifact_pk (str): The pk or the Artifact to create the Collection from.
    """
    artifact = Artifact.objects.get(pk=artifact_pk)
    with tarfile.open(str(artifact.file.path), "r") as tar:
        log.info(_("Reading MANIFEST.json from {path}").format(path=artifact.file.path))
        file_obj = tar.extractfile("MANIFEST.json")
        manifest_data = json.load(file_obj)
        collection_info = manifest_data["collection_info"]

        with transaction.atomic():
            collection, created = Collection.objects.get_or_create(
                namespace=collection_info["namespace"], name=collection_info["name"]
            )
            if created:
                CreatedResource.objects.create(content_object=collection)

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

            collection_version.save()  # Save the FK updates

            ContentArtifact.objects.create(
                artifact=artifact,
                content=collection_version,
                relative_path=collection_version.relative_path,
            )
            CreatedResource.objects.create(content_object=collection_version)


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
        self.deferred_download = self.remote.policy != Remote.IMMEDIATE

    async def run(self):
        """
        Build and emit `DeclarativeContent` from the ansible metadata.
        """
        with ProgressBar(message="Parsing Collection Metadata") as pb:
            async for metadata in self._fetch_collections():

                for version in metadata["versions"]:

                    url_path = "download/%s-%s-%s.tar.gz" % (
                        metadata["namespace"],
                        metadata["name"],
                        version["version"],
                    )
                    url = urlunparse(urlparse(metadata["href"])._replace(path=url_path))

                    with transaction.atomic():
                        collection, created = Collection.objects.get_or_create(
                            namespace=metadata["namespace"], name=metadata["name"]
                        )
                        collection_version, created = CollectionVersion.objects.get_or_create(
                            namespace=metadata["namespace"],
                            name=metadata["name"],
                            version=version["version"],
                            collection=collection,
                        )

                    relative_path = "%s/%s/%s.tar.gz" % (
                        metadata["namespace"],
                        metadata["name"],
                        version["version"],
                    )
                    d_artifact = DeclarativeArtifact(
                        artifact=Artifact(),
                        url=url,
                        relative_path=relative_path,
                        remote=self.remote,
                        deferred_download=self.deferred_download,
                    )
                    d_content = DeclarativeContent(
                        content=collection_version, d_artifacts=[d_artifact]
                    )
                    pb.increment()
                    await self.put(d_content)

    async def _fetch_collections(self):
        async for metadata in self._fetch_galaxy_pages():
            for result in metadata["results"]:

                response = await get_json_from_url(url=result["versions_url"])

                collection = {
                    "href": result["href"],
                    "name": result["name"],
                    "namespace": result["namespace"]["name"],
                    "versions": response["results"],
                }
                yield collection

    async def _fetch_galaxy_pages(self):
        """
        Fetch the collections in a remote repository.

        Returns:
            async generator: dicts that represent pages from galaxy api

        """
        page_count = 0
        remote = self.remote

        with ProgressBar(message="Parsing Pages from Galaxy Collections API") as progress_bar:
            metadata = await get_json_from_url(url=get_page_url(remote.url))

            page_count = math.ceil(float(metadata["count"]) / float(PAGE_SIZE))
            progress_bar.total = page_count
            progress_bar.save()

            yield metadata
            progress_bar.increment()

            # Concurrent downloads are limited by aiohttp...
            not_done = set(
                asyncio.ensure_future(get_json_from_url(url=get_page_url(remote.url, page)))
                for page in range(2, page_count + 1)
            )

            while not_done:
                done, not_done = await asyncio.wait(not_done, return_when=asyncio.FIRST_COMPLETED)
                for item in done:
                    yield item.result()
                    progress_bar.increment()
