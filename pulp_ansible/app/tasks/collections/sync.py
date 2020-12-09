import asyncio
from aiohttp.client_exceptions import ClientResponseError
from gettext import gettext as _
import json
import logging
import tarfile
from urllib.parse import urljoin

from async_lru import alru_cache
from django.db.models import Q
from pkg_resources import Requirement

from pulpcore.plugin.constants import TASK_STATES
from pulpcore.plugin.models import (
    Artifact,
    ProgressReport,
    Remote,
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

from pulp_ansible.app.constants import PAGE_SIZE
from pulp_ansible.app.models import (
    AnsibleCollectionDeprecated,
    AnsibleRepository,
    Collection,
    CollectionRemote,
    CollectionVersion,
    Tag,
)
from pulp_ansible.app.tasks.utils import (
    parse_metadata,
    parse_collections_requirements_file,
    RequirementsFileEntry,
)
from pulp_ansible.app.tasks.collections.utils import update_highest_version


log = logging.getLogger(__name__)


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
    repository = AnsibleRepository.objects.get(pk=repository_pk)

    if not remote.url:
        raise ValueError(_("A CollectionRemote must have a 'url' specified to synchronize."))

    first_stage = CollectionSyncFirstStage(remote)
    d_version = AnsibleDeclarativeVersion(first_stage, repository, mirror=mirror)
    d_version.create()

    repo_version = repository.latest_version()
    to_deprecate = []
    if first_stage.deprecations:
        collections_deprecate_true_qs = Collection.objects.filter(first_stage.deprecations)
        for collection in collections_deprecate_true_qs:
            to_deprecate.append(
                AnsibleCollectionDeprecated(repository_version=repo_version, collection=collection)
            )

        AnsibleCollectionDeprecated.objects.bulk_create(to_deprecate, ignore_conflicts=True)

    non_deprecated_qs = Collection.objects.exclude(first_stage.deprecations)
    AnsibleCollectionDeprecated.objects.filter(
        repository_version=repo_version,
        collection__pk__in=non_deprecated_qs,
    ).delete()


class AnsibleDeclarativeVersion(DeclarativeVersion):
    """
    Subclassed Declarative version creates a custom pipeline for Ansible sync.
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
            DocsBlobDownloader(),
            CollectionContentSaver(new_version),
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
            remote (CollectionRemote): The remote data to be used when syncing

        """
        super().__init__()
        msg = _("Parsing CollectionVersion Metadata")
        self.parsing_metadata_progress_bar = ProgressReport(message=msg, code="parsing.metadata")
        self.remote = remote
        self.collection_info = parse_collections_requirements_file(remote.requirements_file)
        self.deprecations = Q()

        # Interpret download policy
        self.deferred_download = self.remote.policy != Remote.IMMEDIATE

    @alru_cache(maxsize=128)
    async def _get_collection_api(self, root):
        """
        Returns the collection api path and api version.

        Based on https://git.io/JTMxE.
        """
        if root == "https://galaxy.ansible.com" or root == "https://galaxy.ansible.com/":
            root = "https://galaxy.ansible.com/api/"

        downloader = self.remote.get_downloader(url=root)

        try:
            api_data = parse_metadata(await downloader.run())
        except (json.decoder.JSONDecodeError, ClientResponseError):
            if root.endswith("/api/"):
                raise

            root = urljoin(root, "api/")
            downloader = self.remote.get_downloader(url=root)
            api_data = parse_metadata(await downloader.run())

        if "available_versions" not in api_data:
            raise RuntimeError(_("Could not find 'available_versions' at {}").format(root))

        if "v3" in api_data.get("available_versions", {}):
            api_version = 3
        elif "v2" in api_data.get("available_versions", {}):
            api_version = 2
        else:
            raise RuntimeError(_("Unsupported API versions at {}").format(root))

        endpoint = f"{root}v{api_version}/collections/"

        return endpoint, api_version

    async def _fetch_collection_version_metadata(self, api_version, collection_version_url):
        downloader = self.remote.get_downloader(url=collection_version_url)
        metadata = parse_metadata(await downloader.run())

        url = metadata["download_url"]

        collection_version = CollectionVersion(
            namespace=metadata["namespace"]["name"],
            name=metadata["collection"]["name"],
            version=metadata["version"],
        )

        info = metadata["metadata"]

        info.pop("tags")
        for attr_name, attr_value in info.items():
            if attr_value is None or attr_name not in collection_version.__dict__:
                continue
            setattr(collection_version, attr_name, attr_value)

        artifact = metadata["artifact"]

        d_artifact = DeclarativeArtifact(
            artifact=Artifact(sha256=artifact["sha256"], size=artifact["size"]),
            url=url,
            relative_path=collection_version.relative_path,
            remote=self.remote,
            deferred_download=self.deferred_download,
        )

        extra_data = {}
        if api_version != 2:  # V2 never implemented the docs-blob requests
            extra_data["docs_blob_url"] = f"{collection_version_url}docs-blob/"

        d_content = DeclarativeContent(
            content=collection_version,
            d_artifacts=[d_artifact],
            extra_data=extra_data,
        )
        self.parsing_metadata_progress_bar.increment()
        await self.put(d_content)

    def _collection_versions_list_downloader(
        self, api_version, collection_endpoint, namespace, name, page_num, page_size
    ):
        url_without_get_params = f"{collection_endpoint}{namespace}/{name}/versions/"
        if api_version == 2:
            versions_list_url = f"{url_without_get_params}?page={page_num}&page_size={page_size}"
        else:
            offset = (page_num - 1) * page_size
            versions_list_url = f"{url_without_get_params}?limit={page_size}&offset={offset}"
        return self.remote.get_downloader(url=versions_list_url)

    async def _fetch_collection_metadata(self, requirements_entry):
        if requirements_entry.version == "*":
            requirement_version = Requirement.parse("collection")
        else:
            requirement_version = Requirement.parse(f"collection{requirements_entry.version}")
        if requirements_entry.source:
            root = requirements_entry.source
        else:
            root = self.remote.url
        collection_endpoint, api_version = await self._get_collection_api(root)
        namespace, name = requirements_entry.name.split(".")
        collection_url = f"{collection_endpoint}{namespace}/{name}"
        collection_metadata_downloader = self.remote.get_downloader(url=collection_url)
        collection_metadata = parse_metadata(await collection_metadata_downloader.run())

        tasks = []
        page_num = 1
        while True:
            versions_list_downloader = self._collection_versions_list_downloader(
                api_version, collection_endpoint, namespace, name, page_num, PAGE_SIZE
            )
            collection_versions_list = parse_metadata(await versions_list_downloader.run())
            if api_version == 2:
                collection_versions = collection_versions_list["results"]
            else:
                collection_versions = collection_versions_list["data"]
            for collection_version in collection_versions:
                if collection_version["version"] in requirement_version:
                    version_num = collection_version["version"]
                    collection_version_detail_url = f"{collection_url}/versions/{version_num}/"
                    if collection_metadata["deprecated"]:
                        self.deprecations |= Q(namespace=namespace, name=name)
                    tasks.append(
                        asyncio.create_task(
                            self._fetch_collection_version_metadata(
                                api_version,
                                collection_version_detail_url,
                            )
                        )
                    )
            next_value = self._get_response_next_value(api_version, collection_versions_list)
            if not next_value:
                break
            page_num = page_num + 1

        await asyncio.gather(*tasks)

    @staticmethod
    def _get_response_next_value(api_version, response):
        if api_version == 2:
            return response["next"]
        else:
            return response["links"]["next"]

    def _collection_list_downloader(self, api_version, collection_endpoint, page_num, page_size):
        if api_version == 2:
            collection_list_url = f"{collection_endpoint}?page={page_num}&page_size={page_size}"
        else:
            offset = (page_num - 1) * page_size
            collection_list_url = f"{collection_endpoint}?limit={page_size}&offset={offset}"
        return self.remote.get_downloader(url=collection_list_url)

    async def _find_all_collections(self):
        collection_endpoint, api_version = await self._get_collection_api(self.remote.url)

        tasks = []
        page_num = 1
        while True:
            collection_list_downloader = self._collection_list_downloader(
                api_version, collection_endpoint, page_num, PAGE_SIZE
            )
            collection_list = parse_metadata(await collection_list_downloader.run())

            if api_version == 2:
                collections = collection_list["results"]
            else:
                collections = collection_list["data"]

            for collection in collections:
                if api_version == 2:
                    namespace = collection["namespace"]["name"]
                else:
                    namespace = collection["namespace"]
                name = collection["name"]
                requirements_file = RequirementsFileEntry(
                    name=".".join([namespace, name]),
                    version="*",
                    source=None,
                )
                tasks.append(
                    asyncio.create_task(self._fetch_collection_metadata(requirements_file))
                )

            next_value = self._get_response_next_value(api_version, collection_list)
            if not next_value:
                break
            page_num = page_num + 1

        await asyncio.gather(*tasks)

    async def run(self):
        """
        Build and emit `DeclarativeContent` from the ansible metadata.
        """
        tasks = []
        if self.collection_info:
            for requirement_entry in self.collection_info:
                tasks.append(
                    asyncio.create_task(self._fetch_collection_metadata(requirement_entry))
                )
        else:
            tasks.append(asyncio.create_task(self._find_all_collections()))
        await asyncio.gather(*tasks)
        self.parsing_metadata_progress_bar.state = TASK_STATES.COMPLETED
        self.parsing_metadata_progress_bar.save()


class DocsBlobDownloader(ArtifactDownloader):
    """
    Stage for downloading docs_blob.

    Args:
        max_concurrent_content (int): The maximum number of
            :class:`~pulpcore.plugin.stages.DeclarativeContent` instances to handle simultaneously.
            Default is 200.
        args: unused positional arguments passed along to :class:`~pulpcore.plugin.stages.Stage`.
        kwargs: unused keyword arguments passed along to :class:`~pulpcore.plugin.stages.Stage`.
    """

    async def _handle_content_unit(self, d_content):
        """Handle one content unit.

        Returns:
            The number of downloads
        """
        downloaded = 0
        content_already_saved = not d_content.content._state.adding
        if not content_already_saved and d_content.d_artifacts:
            remote = d_content.d_artifacts[0].remote
            docs_blob = d_content.extra_data.get("docs_blob_url")
            if docs_blob:
                downloaded = 1
                downloader = remote.get_downloader(
                    url=docs_blob, silence_errors_for_response_status_codes={404}
                )
                try:
                    download_result = await downloader.run()
                    with open(download_result.path, "r") as docs_blob_file:
                        docs_blob_json = json.load(docs_blob_file)
                        d_content.extra_data["docs_blob"] = docs_blob_json.get("docs_blob", {})
                except FileNotFoundError:
                    pass

        await self.put(d_content)
        return downloaded


class CollectionContentSaver(ContentSaver):
    """
    A modification of ContentSaver stage that additionally saves Ansible plugin specific items.

    Saves Collection and Tag objects related to the CollectionVersion content unit.
    """

    def __init__(self, repository_version, *args, **kwargs):
        """Initialize CollectionContentSaver."""
        super().__init__(*args, **kwargs)
        self.repository_version = repository_version

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
            docs_blob = d_content.extra_data.get("docs_blob", {})
            collection_version.docs_blob = docs_blob

            for d_artifact in d_content.d_artifacts:
                artifact = d_artifact.artifact
                with artifact.file.open() as artifact_file, tarfile.open(
                    fileobj=artifact_file, mode="r"
                ) as tar:
                    log.info(_("Reading MANIFEST.json from {path}").format(path=artifact.file.name))
                    for manifest in ["MANIFEST.json", "./MANIFEST.json"]:
                        try:
                            file_obj = tar.extractfile(manifest)
                        except KeyError:
                            file_obj = None
                        else:
                            break
                    if not file_obj:
                        raise FileNotFoundError("MANIFEST.json not found")
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

                update_highest_version(collection_version)

                collection_version.save()
