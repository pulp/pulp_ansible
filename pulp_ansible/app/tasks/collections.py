import asyncio
from collections import defaultdict
from gettext import gettext as _
import json
import logging
import tarfile
import yaml
from operator import attrgetter
from urllib.parse import urljoin

from aiohttp.client_exceptions import ClientResponseError
from async_lru import alru_cache
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from galaxy_importer.collection import import_collection as process_collection
from galaxy_importer.collection import CollectionFilename
from galaxy_importer.exceptions import ImporterError
from pkg_resources import Requirement
from rq.job import get_current_job

from pulpcore.plugin.constants import TASK_STATES
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
from pulp_ansible.app.serializers import CollectionVersionSerializer, CollectionRemoteSerializer
from pulp_ansible.app.tasks.utils import (
    get_file_obj_from_tarball,
    parse_metadata,
    parse_collections_requirements_file,
    RequirementsFileEntry,
)


log = logging.getLogger(__name__)


def update_collection_remote(remote_pk, *args, **kwargs):
    """
    Update a CollectionRemote.

    Update `AnsibleRepository.last_synced_metadata_time` when URL or requirements file are updated.

    Args:
        remote_pk (str): the id of the CollectionRemote
        data (dict): dictionary whose keys represent the fields of the model and their corresponding
            values.
        partial (bool): When true, only the fields specified in the data dictionary are updated.
            When false, any fields missing from the data dictionary are assumed to be None and
            their values are updated as such.

    Raises:
        :class:`rest_framework.exceptions.ValidationError`: When serializer instance can't be saved
            due to validation error. This theoretically should never occur since validation is
            performed before the task is dispatched.
    """
    data = kwargs.pop("data", None)
    partial = kwargs.pop("partial", False)
    with transaction.atomic():
        if "url" in data or "requirements_file" in data:
            repos = list(
                AnsibleRepository.objects.filter(
                    remote_id=remote_pk, last_synced_metadata_time__isnull=False
                ).all()
            )
            for repo in repos:
                repo.last_synced_metadata_time = None
            AnsibleRepository.objects.bulk_update(repos, ["last_synced_metadata_time"])

        instance = CollectionRemote.objects.get(pk=remote_pk)
        serializer = CollectionRemoteSerializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()


def sync(remote_pk, repository_pk, mirror, optimize):
    """
    Sync Collections with ``remote_pk``, and save a new RepositoryVersion for ``repository_pk``.

    Args:
        remote_pk (str): The remote PK.
        repository_pk (str): The repository PK.
        mirror (bool): True for mirror mode, False for additive.
        optimize (boolean): Whether to optimize sync or not.

    Raises:
        ValueError: If the remote does not specify a URL to sync.

    """
    remote = CollectionRemote.objects.get(pk=remote_pk)
    repository = AnsibleRepository.objects.get(pk=repository_pk)

    if not remote.url:
        raise ValueError(_("A CollectionRemote must have a 'url' specified to synchronize."))

    first_stage = CollectionSyncFirstStage(remote, repository, optimize)
    d_version = AnsibleDeclarativeVersion(first_stage, repository, mirror=mirror)
    repo_version = d_version.create()

    if not repo_version:
        return

    if first_stage.last_synced_metadata_time:
        repository.last_synced_metadata_time = first_stage.last_synced_metadata_time
        repository.save()

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
            url = _get_backend_storage_url(artifact_file)
            importer_result = process_collection(
                artifact_file, filename=filename, file_url=url, logger=user_facing_logger
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
            requires_ansible=importer_result.get("requires_ansible"),
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


def _get_backend_storage_url(artifact_file):
    """Get artifact url from pulp backend storage."""
    if settings.DEFAULT_FILE_STORAGE == "pulpcore.app.models.storage.FileSystem":
        url = None
    elif settings.DEFAULT_FILE_STORAGE == "storages.backends.s3boto3.S3Boto3Storage":
        parameters = {"ResponseContentDisposition": "attachment;filename=archive.tar.gz"}
        url = artifact_file.storage.url(artifact_file.name, parameters=parameters)
    elif settings.DEFAULT_FILE_STORAGE == "storages.backends.azure_storage.AzureStorage":
        url = artifact_file.storage.url(artifact_file.name)
    else:
        raise NotImplementedError(
            f"The value settings.DEFAULT_FILE_STORAGE={settings.DEFAULT_FILE_STORAGE} "
            "was not expected"
        )
    return url


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

    def __init__(self, remote, repository, optimize):
        """
        The first stage of a pulp_ansible sync pipeline.

        Args:
            remote (CollectionRemote): The remote data to be used when syncing
            repository (AnsibleRepository): The repository being syncedself.
            optimize (boolean): Whether to optimize sync or not.

        """
        super().__init__()
        msg = _("Parsing CollectionVersion Metadata")
        self.parsing_metadata_progress_bar = ProgressReport(
            message=msg, code="sync.parsing.metadata"
        )
        self.remote = remote
        self.repository = repository
        self.optimize = optimize
        self.collection_info = parse_collections_requirements_file(remote.requirements_file)
        self.deprecations = Q()
        self.add_dependents = self.collection_info and self.remote.sync_dependencies
        self.already_synced = set()
        self._unpaginated_collection_metadata = None
        self._unpaginated_collection_version_metadata = None
        self.last_synced_metadata_time = None

        # Interpret download policy
        self.deferred_download = self.remote.policy != Remote.IMMEDIATE

    @alru_cache(maxsize=128)
    async def _get_root_api(self, root):
        """
        Returns the root api path and api version.

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

        endpoint = f"{root}v{api_version}"

        return endpoint, api_version

    @alru_cache(maxsize=128)
    async def _get_paginated_collection_api(self, root):
        """
        Returns the collection api path and api version.

        Based on https://git.io/JTMxE.
        """
        endpoint, api_version = await self._get_root_api(root)
        return f"{endpoint}/collections/", api_version

    async def _fetch_collection_version_metadata(self, api_version, collection_version_url):
        downloader = self.remote.get_downloader(url=collection_version_url)
        metadata = parse_metadata(await downloader.run())
        await self._add_collection_version(api_version, collection_version_url, metadata)

    async def _add_collection_version(self, api_version, collection_version_url, metadata):
        """Add CollectionVersion to the sync pipeline."""
        url = metadata["download_url"]
        collection_version = CollectionVersion(
            namespace=metadata["namespace"]["name"],
            name=metadata["collection"]["name"],
            version=metadata["version"],
        )
        cv_unique = attrgetter("namespace", "name", "version")(collection_version)
        if cv_unique in self.already_synced:
            return
        self.already_synced.add(cv_unique)

        info = metadata["metadata"]

        if self.add_dependents:
            dependencies = info["dependencies"]
            tasks = []
            loop = asyncio.get_event_loop()
            for full_name, version in dependencies.items():
                namespace, name = full_name.split(".")
                req = (namespace, name, version)
                new_req = RequirementsFileEntry(full_name, version=version, source=None)
                if not any([req in self.already_synced, new_req in self.collection_info]):
                    self.collection_info.append(new_req)
                    tasks.append(loop.create_task(self._fetch_collection_metadata(new_req)))
            await asyncio.gather(*tasks)

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

    async def _fetch_paginated_collection_metadata(self, name, namespace, requirement, source=None):
        root = source or self.remote.url
        collection_endpoint, api_version = await self._get_paginated_collection_api(root)
        collection_url = f"{collection_endpoint}{namespace}/{name}"
        collection_metadata_downloader = self.remote.get_downloader(url=collection_url)
        collection_metadata = parse_metadata(await collection_metadata_downloader.run())
        loop = asyncio.get_event_loop()

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
                if collection_version["version"] in requirement:
                    version_num = collection_version["version"]
                    collection_version_detail_url = f"{collection_url}/versions/{version_num}/"
                    if collection_metadata["deprecated"]:
                        self.deprecations |= Q(namespace=namespace, name=name)
                    tasks.append(
                        loop.create_task(
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

    async def _read_from_downloaded_metadata(self, name, namespace, requirement):
        tasks = []
        loop = asyncio.get_event_loop()

        if self._unpaginated_collection_metadata[namespace][name]["deprecated"]:
            self.deprecations |= Q(namespace=namespace, name=name)

        all_versions_of_collection = self._unpaginated_collection_version_metadata[namespace][name]

        for col_version_metadata in all_versions_of_collection:
            if col_version_metadata["version"] in requirement:
                collection_version_url = urljoin(self.remote.url, f"{col_version_metadata['href']}")
                tasks.append(
                    loop.create_task(
                        self._add_collection_version(
                            self._api_version, collection_version_url, col_version_metadata
                        )
                    )
                )
        await asyncio.gather(*tasks)

    async def _fetch_collection_metadata(self, requirements_entry):
        if requirements_entry.version == "*":
            requirement_version = Requirement.parse("collection")
        else:
            # We need specifiers to enforce Requirement object criteria
            # https://setuptools.readthedocs.io/en/latest/pkg_resources.html#requirements-parsing
            # https://setuptools.readthedocs.io/en/latest/pkg_resources.html#requirement-methods-and-attributes
            # If requirements_entry.version is a valid version, adds == specifier to the requirement
            try:
                Version(requirements_entry.version)
                req_to_parse = f"collection=={requirements_entry.version}"
            except ValueError:
                req_to_parse = f"collection{requirements_entry.version}"

            requirement_version = Requirement.parse(req_to_parse)

        namespace, name = requirements_entry.name.split(".")

        if self._unpaginated_collection_version_metadata and requirements_entry.source is None:
            await self._read_from_downloaded_metadata(name, namespace, requirement_version)
        else:
            await self._fetch_paginated_collection_metadata(
                name, namespace, requirement_version, requirements_entry.source
            )

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

    async def _download_unpaginated_metadata(self):
        root_endpoint, api_version = await self._get_root_api(self.remote.url)
        self._api_version = api_version
        if api_version > 2:
            collection_endpoint = f"{root_endpoint}/collections/all/"
            downloader = self.remote.get_downloader(
                url=collection_endpoint, silence_errors_for_response_status_codes={404}
            )
            try:
                collection_metadata_list = parse_metadata(await downloader.run())
            except FileNotFoundError:
                pass
            else:
                self._unpaginated_collection_metadata = defaultdict(dict)
                for collection in collection_metadata_list:
                    namespace = collection["namespace"]
                    name = collection["name"]
                    self._unpaginated_collection_metadata[namespace][name] = collection

                collection_version_endpoint = f"{root_endpoint}/collection_versions/all/"
                downloader = self.remote.get_downloader(url=collection_version_endpoint)
                collection_version_metadata_list = parse_metadata(await downloader.run())

                self._unpaginated_collection_version_metadata = defaultdict(
                    lambda: defaultdict(list)
                )
                for collection_version_metadata in collection_version_metadata_list:
                    namespace = collection_version_metadata["namespace"]["name"]
                    name = collection_version_metadata["name"]
                    self._unpaginated_collection_version_metadata[namespace][name].append(
                        collection_version_metadata
                    )

    async def _find_all_collections_from_unpaginated_data(self):
        tasks = []
        loop = asyncio.get_event_loop()

        for collection_namespace_dict in self._unpaginated_collection_metadata.values():
            for collection in collection_namespace_dict.values():
                if collection["deprecated"]:
                    self.deprecations |= Q(
                        namespace=collection["namespace"], name=collection["name"]
                    )

        for collections_in_namespace in self._unpaginated_collection_version_metadata.values():
            for collection_versions in collections_in_namespace.values():
                for collection_version in collection_versions:
                    collection_version_url = urljoin(
                        self.remote.url, f"{collection_version['href']}"
                    )
                    tasks.append(
                        loop.create_task(
                            self._add_collection_version(
                                self._api_version, collection_version_url, collection_version
                            )
                        )
                    )

        await asyncio.gather(*tasks)

    async def _find_all_collections(self):
        if self._unpaginated_collection_version_metadata:
            await self._find_all_collections_from_unpaginated_data()
            return

        collection_endpoint, api_version = await self._get_paginated_collection_api(self.remote.url)
        loop = asyncio.get_event_loop()

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
                tasks.append(loop.create_task(self._fetch_collection_metadata(requirements_file)))

            next_value = self._get_response_next_value(api_version, collection_list)
            if not next_value:
                break
            page_num = page_num + 1

        await asyncio.gather(*tasks)

    async def _should_we_sync(self):
        """Check last synced metadata time."""
        msg = _("no_change: Checking if remote changed since last sync.")
        noop = ProgressReport(message=msg, code="sync.no_change")
        noop.state = TASK_STATES.COMPLETED
        noop.save()

        if not self.repository.remote:
            return True

        if self.remote != self.repository.remote.cast():
            return True

        root, api_version = await self._get_root_api(self.remote.url)
        if api_version == 3:
            downloader = self.remote.get_downloader(
                url=root, silence_errors_for_response_status_codes={404}
            )
            try:
                metadata = parse_metadata(await downloader.run())
            except FileNotFoundError:
                return True

            try:
                self.last_synced_metadata_time = parse_datetime(metadata["published"])
            except KeyError:
                return True

            sources = set()
            if self.collection_info:
                sources = {r.source for r in self.collection_info if r.source}
            sources.add(self.remote.url)
            if len(sources) > 1:
                return True

            if self.last_synced_metadata_time == self.repository.last_synced_metadata_time:
                noop.message = _(
                    "no-op: {remote} did not change since last sync - {published}".format(
                        remote=self.remote.url, published=self.last_synced_metadata_time
                    )
                )
                noop.save()
                return False

        return True

    async def run(self):
        """
        Build and emit `DeclarativeContent` from the ansible metadata.
        """
        if self.optimize:
            should_we_sync = await self._should_we_sync()
            if should_we_sync is False:
                log.debug(_("no-op: remote wasn't updated since last sync."))
                return

        tasks = []
        loop = asyncio.get_event_loop()

        await self._download_unpaginated_metadata()

        if self.collection_info:
            for requirement_entry in self.collection_info:
                tasks.append(loop.create_task(self._fetch_collection_metadata(requirement_entry)))
        else:
            tasks.append(loop.create_task(self._find_all_collections()))
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
            if docs_blob:
                collection_version.docs_blob = docs_blob

            for d_artifact in d_content.d_artifacts:
                artifact = d_artifact.artifact
                with artifact.file.open() as artifact_file, tarfile.open(
                    fileobj=artifact_file, mode="r"
                ) as tar:
                    runtime_metadata = get_file_obj_from_tarball(
                        tar, "meta/runtime.yml", artifact.file.name, raise_exc=False
                    )
                    if runtime_metadata:
                        runtime_yaml = yaml.safe_load(runtime_metadata)
                        collection_version.requires_ansible = runtime_yaml.get("requires_ansible")
                    manifest_data = json.load(
                        get_file_obj_from_tarball(tar, "MANIFEST.json", artifact.file.name)
                    )
                    files_data = json.load(
                        get_file_obj_from_tarball(tar, "FILES.json", artifact.file.name)
                    )
                    collection_version.manifest = manifest_data
                    collection_version.files = files_data
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
