import asyncio
from aiohttp.client_exceptions import ClientResponseError
from gettext import gettext as _
import json
import logging
import math
import tarfile
from urllib.parse import urljoin, urlparse, urlunparse

from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from galaxy_importer.collection import import_collection as process_collection
from galaxy_importer.collection import CollectionFilename
from galaxy_importer.exceptions import ImporterError
from rq.job import get_current_job

from pulpcore.plugin.models import (
    Artifact,
    ContentArtifact,
    CreatedResource,
    ProgressReport,
    PulpTemporaryFile,
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
from semantic_version import Version

from pulp_ansible.app.constants import PAGE_SIZE
from pulp_ansible.app.models import (
    AnsibleCollectionDeprecated,
    AnsibleRepository,
    Collection,
    CollectionImport,
    CollectionRemote,
    CollectionVersion,
    Tag,
)
from pulp_ansible.app.serializers import CollectionVersionSerializer
from pulp_ansible.app.tasks.utils import (
    get_page_url,
    parse_metadata,
    parse_collections_requirements_file,
)


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


def import_collection(
    temp_file_pk,
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
        temp_file_pk (str): The pk of the PulpTemporaryFile to create the Collection from.

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

    temp_file = PulpTemporaryFile.objects.get(pk=temp_file_pk)
    filename = CollectionFilename(expected_namespace, expected_name, expected_version)
    log.info(f"Processing collection from {temp_file.file.name}")
    user_facing_logger = logging.getLogger("pulp_ansible.app.tasks.collection.import_collection")

    try:
        with temp_file.file.open() as artifact_file:
            importer_result = process_collection(
                artifact_file, filename=filename, logger=user_facing_logger
            )
            artifact = Artifact.from_pulp_temporary_file(temp_file)
            importer_result["artifact_url"] = reverse("artifacts-detail", args=[artifact.pk])
            collection_version = create_collection_from_importer(importer_result)

    except ImporterError as exc:
        log.info(f"Collection processing was not successful: {exc}")
        temp_file.delete()
        raise
    except Exception as exc:
        user_facing_logger.error(f"Collection processing was not successful: {exc}")
        temp_file.delete()
        raise

    ContentArtifact.objects.create(
        artifact=artifact,
        content=collection_version,
        relative_path=collection_version.relative_path,
    )
    CreatedResource.objects.create(content_object=collection_version)

    if repository_pk:
        repository = AnsibleRepository.objects.get(pk=repository_pk)
        content_q = CollectionVersion.objects.filter(pk=collection_version.pk)
        with repository.new_version() as new_version:
            new_version.add_content(content_q)
        CreatedResource.objects.create(content_object=repository)


def create_collection_from_importer(importer_result):
    """
    Process results from importer.
    """
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

        serializer_fields = CollectionVersionSerializer.Meta.fields
        data = {k: v for k, v in collection_version.__dict__.items() if k in serializer_fields}
        data["id"] = collection_version.pulp_id
        data["artifact"] = importer_result["artifact_url"]

        serializer = CollectionVersionSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        collection_version.save()

        for name in tags:
            tag, created = Tag.objects.get_or_create(name=name)
            collection_version.tags.add(tag)

        _update_highest_version(collection_version)

        collection_version.save()  # Save the FK updates
    return collection_version


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
    if Version(collection_version.version) > Version(last_highest.version):
        last_highest.is_highest = False
        collection_version.is_highest = True
        last_highest.save()
        collection_version.save()

    elif collection_version.is_highest and collection_version.version != last_highest.version:
        collection_version.is_highest = False
        collection_version.save()


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
        self.remote = remote
        self.collection_info = parse_collections_requirements_file(remote.requirements_file)
        self.deprecations = Q()

        # Interpret download policy
        self.deferred_download = self.remote.policy != Remote.IMMEDIATE

    async def run(self):
        """
        Build and emit `DeclarativeContent` from the ansible metadata.
        """
        msg = "Parsing CollectionVersion Metadata"
        with ProgressReport(message=msg, code="parsing.metadata") as pb:
            async for metadata in self._fetch_collections():

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

                extradata = dict(docs_blob_url=metadata["docs_blob_url"])

                d_content = DeclarativeContent(
                    content=collection_version,
                    d_artifacts=[d_artifact],
                    extra_data=extradata,
                )
                pb.increment()
                await self.put(d_content)

    async def _fetch_collections(self):
        """
        Fetch the collections in a remote repository.

        Returns:
            async generator: dicts that represent collections from galaxy api

        """
        remote = self.remote
        collection_info = self.collection_info

        async def _get_collection_api(root):
            """
            Returns the collection api path and api version.

            Based on https://git.io/JTMxE.
            """
            if root == "https://galaxy.ansible.com" or root == "https://galaxy.ansible.com/":
                root = "https://galaxy.ansible.com/api/"

            downloader = remote.get_downloader(url=root)

            try:
                api_data = parse_metadata(await downloader.run())
            except (json.decoder.JSONDecodeError, ClientResponseError):
                if root.endswith("/api/"):
                    raise

                root = urljoin(root, "api/")
                downloader = remote.get_downloader(url=root)
                api_data = parse_metadata(await downloader.run())

            if "available_versions" not in api_data:
                raise RuntimeError(_("Could not find 'available_versions' at {}").format(root))

            if "v3" in api_data.get("available_versions", {}):
                self.api_version = 3
            elif "v2" in api_data.get("available_versions", {}):
                self.api_version = 2
            else:
                raise RuntimeError(_("Unsupported API versions at {}").format(root))

            endpoint = f"{root}v{self.api_version}/collections/"

            return endpoint, self.api_version

        async def _get_url(page, versions_url=None):
            if collection_info and not versions_url:
                name, version, source = collection_info[page - 1]
                namespace, name = name.split(".")
                root = source or remote.url
                api_endpoint = (await _get_collection_api(root))[0]
                url = f"{api_endpoint}{namespace}/{name}/"
                return url

            if not versions_url:
                api_endpoint, api_version = await _get_collection_api(remote.url)
                return get_page_url(api_endpoint, api_version, page)

            if not self.api_version:
                await _get_collection_api(remote.url)

            return get_page_url(versions_url, self.api_version, page)

        async def _loop_through_pages(not_done, versions_url=None):
            """
            Loop through API pagination.
            """
            url = await _get_url(1, versions_url)
            downloader = remote.get_downloader(url=url)
            data = parse_metadata(await downloader.run())

            count = data.get("count") or data.get("meta", {}).get("count", 1)
            if collection_info and not versions_url:
                count = len(collection_info)
                page_count = count
            else:
                page_count = math.ceil(float(count) / float(PAGE_SIZE))

            for page in range(1, page_count + 1):
                url = await _get_url(page, versions_url)
                downloader = remote.get_downloader(url=url)
                not_done.add(downloader.run())

            return count

        def _build_url(path_or_url):
            """Check value and turn it into a url using remote.url if it's a relative path."""
            url_parts = urlparse(path_or_url)
            if not url_parts.netloc:
                new_url_parts = urlparse(self.remote.url)._replace(path=url_parts.path)
                return urlunparse(new_url_parts)
            else:
                return path_or_url

        def _add_collection_version_level_metadata(data, additional_metadata):
            """Additional metadata at collection version level to be sent through stages."""
            metadata = additional_metadata.get(_build_url(data["href"]), {})
            data["docs_blob_url"] = metadata.get("docs_blob_url")

        progress_data = dict(message="Parsing Galaxy Collections API", code="parsing.collections")
        with ProgressReport(**progress_data) as progress_bar:
            not_done = set()
            count = await _loop_through_pages(not_done)
            progress_bar.total = count
            progress_bar.save()

            additional_metadata = {}

            while not_done:
                done, not_done = await asyncio.wait(not_done, return_when=asyncio.FIRST_COMPLETED)

                for item in done:
                    data = parse_metadata(item.result())

                    if "data" in data:  # api v3
                        results = data["data"]
                    elif "results" in data:  # api v2
                        results = data["results"]
                    else:
                        results = [data]

                    for result in results:
                        download_url = result.get("download_url")

                        if result.get("deprecated"):
                            name = result["name"]
                            try:
                                namespace = result["namespace"]["name"]  # api v3
                            except TypeError:
                                namespace = result["namespace"]  # api v2
                            self.deprecations |= Q(namespace=namespace, name=name)

                        if result.get("versions_url"):
                            versions_url = _build_url(result.get("versions_url"))
                            await _loop_through_pages(not_done, versions_url)
                            progress_bar.increment()

                        if result.get("version") and not download_url:
                            version_url = _build_url(result["href"])
                            not_done.update([remote.get_downloader(url=version_url).run()])
                            if self.api_version > 2:
                                additional_metadata[version_url] = {
                                    "docs_blob_url": f"{version_url}docs-blob/"
                                }

                        if download_url:
                            _add_collection_version_level_metadata(data, additional_metadata)
                            yield data


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
            if docs_blob:
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

                _update_highest_version(collection_version)

                collection_version.save()
