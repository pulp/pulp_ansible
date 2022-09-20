import asyncio
import hashlib
import json
import logging
import tarfile
from collections import defaultdict
from gettext import gettext as _
from operator import attrgetter
from urllib.parse import urljoin
from uuid import uuid4

import yaml
from aiohttp.client_exceptions import ClientResponseError
from asgiref.sync import sync_to_async
from async_lru import alru_cache
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.db.utils import IntegrityError
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from galaxy_importer.collection import CollectionFilename
from galaxy_importer.collection import import_collection as process_collection
from galaxy_importer.collection import sync_collection
from galaxy_importer.exceptions import ImporterError
from git import GitCommandError, Repo
from pkg_resources import Requirement
from pulpcore.plugin.models import (
    Artifact,
    ContentArtifact,
    CreatedResource,
    ProgressReport,
    PulpTemporaryFile,
    Remote,
    RepositoryContent,
    RepositoryVersion,
    Task,
)
from pulpcore.plugin.stages import (
    ArtifactDownloader,
    ArtifactSaver,
    ContentSaver,
    DeclarativeArtifact,
    DeclarativeContent,
    DeclarativeVersion,
    QueryExistingArtifacts,
    QueryExistingContents,
    RemoteArtifactSaver,
    ResolveContentFutures,
    Stage,
)
from rest_framework.serializers import ValidationError
from semantic_version import Version

from pulp_ansible.app.constants import PAGE_SIZE
from pulp_ansible.app.models import (
    AnsibleCollectionDeprecated,
    AnsibleRepository,
    Collection,
    CollectionImport,
    CollectionRemote,
    CollectionVersion,
    CollectionVersionSignature,
    Tag,
)
from pulp_ansible.app.serializers import CollectionVersionSerializer
from pulp_ansible.app.tasks.utils import (
    RequirementsFileEntry,
    get_file_obj_from_tarball,
    parse_collections_requirements_file,
    parse_metadata,
)

log = logging.getLogger(__name__)


async def declarative_content_from_git_repo(remote, url, git_ref=None, metadata_only=False):
    """Returns a DeclarativeContent for the Collection in a Git repository."""
    if git_ref:
        try:
            gitrepo = Repo.clone_from(
                url, uuid4(), depth=1, branch=git_ref, multi_options=["--recurse-submodules"]
            )
        except GitCommandError:
            gitrepo = Repo.clone_from(url, uuid4(), multi_options=["--recurse-submodules"])
            gitrepo.git.checkout(git_ref)
    else:
        gitrepo = Repo.clone_from(url, uuid4(), depth=1, multi_options=["--recurse-submodules"])
    commit_sha = gitrepo.head.commit.hexsha
    metadata, artifact_path = sync_collection(gitrepo.working_dir, ".")
    if not metadata_only:
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
    metadata["remote_artifact_url"] = "{}/commit/{}".format(url.rstrip("/"), commit_sha)

    artifact = metadata["artifact"]
    try:
        collection_version = await sync_to_async(create_collection_from_importer)(
            metadata, metadata_only=metadata_only
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
        remote=remote,
        deferred_download=metadata_only,
    )

    # TODO: docs blob support??

    d_content = DeclarativeContent(
        content=collection_version,
        d_artifacts=[d_artifact],
    )
    return d_content


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

    is_repo_remote = False
    if repository.remote:
        is_repo_remote = remote.pk == repository.remote.pk

    if not remote.url:
        raise ValueError(_("A CollectionRemote must have a 'url' specified to synchronize."))

    deprecation_before_sync = set()
    for namespace, name in AnsibleCollectionDeprecated.objects.filter(
        pk__in=repository.latest_version().content
    ).values_list("namespace", "name"):
        deprecation_before_sync.add(f"{namespace}.{name}")
    first_stage = CollectionSyncFirstStage(
        remote, repository, is_repo_remote, deprecation_before_sync, optimize
    )
    if first_stage.should_sync is False:
        log.debug(_("no-op: remote wasn't updated since last sync."))
        return

    d_version = AnsibleDeclarativeVersion(first_stage, repository, mirror=mirror)
    repo_version = d_version.create()

    if not repo_version:
        return

    repository.last_synced_metadata_time = first_stage.last_synced_metadata_time
    repository.save(update_fields=["last_synced_metadata_time"])

    to_undeprecate = Q()
    undeprecated = deprecation_before_sync.difference(first_stage.deprecation_after_sync)
    if undeprecated:
        for collection in undeprecated:
            namespace, name = collection.split(".")
            to_undeprecate |= Q(namespace=namespace, name=name)
        deprecated = AnsibleCollectionDeprecated.objects.filter(to_undeprecate)
        RepositoryContent.objects.filter(
            repository=repository, content__in=deprecated
        ).all().update(version_removed=repo_version)


def parse_requirements_entry(requirements_entry):
    """Parses a `RequirementsFileEntry` and returns a `Requirement` object."""
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
    return requirement_version


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
    CollectionImport.objects.get_or_create(task_id=Task.current().pulp_id)

    temp_file = PulpTemporaryFile.objects.get(pk=temp_file_pk)
    filename = CollectionFilename(expected_namespace, expected_name, expected_version)
    log.info(f"Processing collection from {temp_file.file.name}")
    user_facing_logger = logging.getLogger("pulp_ansible.app.tasks.collection.import_collection")

    try:
        with temp_file.file.open() as artifact_file:
            with tarfile.open(fileobj=artifact_file, mode="r") as tar:
                manifest_data = json.load(
                    get_file_obj_from_tarball(tar, "MANIFEST.json", temp_file.file.name)
                )
                files_data = json.load(
                    get_file_obj_from_tarball(tar, "FILES.json", temp_file.file.name)
                )
            url = _get_backend_storage_url(artifact_file)
            artifact_file.seek(0)
            importer_result = process_collection(
                artifact_file, filename=filename, file_url=url, logger=user_facing_logger
            )
            artifact = Artifact.from_pulp_temporary_file(temp_file)
            temp_file = None
            importer_result["artifact_url"] = reverse("artifacts-detail", args=[artifact.pk])
            collection_version = create_collection_from_importer(importer_result)
            collection_version.manifest = manifest_data
            collection_version.files = files_data
            collection_version.save()

    except ImporterError as exc:
        log.info(f"Collection processing was not successful: {exc}")
        if temp_file:
            temp_file.delete()
        raise
    except Exception as exc:
        user_facing_logger.error(f"Collection processing was not successful: {exc}")
        if temp_file:
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


def create_collection_from_importer(importer_result, metadata_only=False):
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
        if not metadata_only:
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


def rebuild_repository_collection_versions_metadata(
    repository_version_pk, namespace=None, name=None, version=None
):
    """Rebuild metadata for all collection versions in a repo."""
    repov = RepositoryVersion.objects.get(pk=repository_version_pk)

    qs = None
    if namespace or name or version:
        qkwargs = {}
        if namespace:
            qkwargs["namespace"] = namespace
        if name:
            qkwargs["name"] = name
        if version:
            qkwargs["version"] = version
        qs = CollectionVersion.objects.filter(**qkwargs)

    qs = repov.get_content(content_qs=qs)
    with ProgressReport(
        message=_("Rebuild collection version metadata (total)"),
        code="rebuild_metadata.total",
        total=qs.count(),
    ) as ptotal, ProgressReport(
        message=_("Rebuild collection version metadata (failed)"), code="rebuild_metadata.failed"
    ) as pfailed:
        for cv in qs:
            try:
                _rebuild_collection_version_meta(cv)
            except Exception as e:
                pfailed.increment()
                log.exception(e)
            ptotal.increment()


def _rebuild_collection_version_meta(collection_version):
    """Rebuild metadata for a single collection version."""
    # where is the artifact?
    artifact = collection_version._artifacts.first()

    # call the importer to re-generate meta
    importer_result = process_collection(
        artifact.file, filename=artifact.file.name, file_url=artifact.file.url, logger=None
    )

    # set the new info and save
    collection_version.requires_ansible = importer_result["requires_ansible"]
    collection_version.docs_blob = importer_result["docs_blob"]
    collection_version.contents = importer_result["contents"]
    collection_version.save()


def _get_backend_storage_url(artifact_file):
    """Get artifact url from pulp backend storage."""
    if (
        settings.DEFAULT_FILE_STORAGE == "pulpcore.app.models.storage.FileSystem"
        or not settings.REDIRECT_TO_OBJECT_STORAGE
    ):
        url = None
    elif settings.DEFAULT_FILE_STORAGE == "storages.backends.s3boto3.S3Boto3Storage":
        parameters = {"ResponseContentDisposition": "attachment%3Bfilename=archive.tar.gz"}
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

    def __init__(self, remote, repository, is_repo_remote, deprecation_before_sync, optimize):
        """
        The first stage of a pulp_ansible sync pipeline.

        Args:
            remote (CollectionRemote): The remote data to be used when syncing
            repository (AnsibleRepository): The repository being syncedself.
            is_repo_remote (bool): True if the remote is the repository's remote.
            deprecation_before_sync (set): Set of deprecations before the sync.
            optimize (boolean): Whether to optimize sync or not.

        """
        super().__init__()
        self.remote = remote
        self.repository = repository
        self.deprecation_before_sync = deprecation_before_sync
        self.deprecation_after_sync = set()
        self.collection_info = parse_collections_requirements_file(remote.requirements_file)
        self.exclude_info = {}
        self.add_dependents = self.collection_info and self.remote.sync_dependencies
        self.signed_only = self.remote.signed_only
        self.already_synced = set()
        self._unpaginated_collection_metadata = None
        self._unpaginated_collection_version_metadata = None
        self.optimize = optimize
        self.last_synced_metadata_time = None

        # Interpret download policy
        self.deferred_download = self.remote.policy != Remote.IMMEDIATE

        # Check if we should sync
        self.should_sync = not is_repo_remote or asyncio.get_event_loop().run_until_complete(
            self._should_we_sync()
        )

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
        fullname, version = f"{cv_unique[0]}.{cv_unique[1]}", cv_unique[2]
        if fullname in self.exclude_info and version in self.exclude_info[fullname]:
            return
        if cv_unique in self.already_synced:
            return
        self.already_synced.add(cv_unique)

        info = metadata["metadata"]
        signatures = metadata.get("signatures")

        if self.signed_only and not signatures:
            return

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
        await self.parsing_metadata_progress_bar.aincrement()
        await self.put(d_content)

        if signatures:
            collection_version = await d_content.resolution()
            for signature in signatures:
                sig = signature["signature"]
                cv_signature = CollectionVersionSignature(
                    signed_collection=collection_version,
                    data=sig,
                    digest=hashlib.sha256(sig.encode("utf-8")).hexdigest(),
                    pubkey_fingerprint=signature["pubkey_fingerprint"],
                )
                await self.put(DeclarativeContent(content=cv_signature))

    async def _add_collection_version_from_git(self, url, gitref, metadata_only):
        d_content = await declarative_content_from_git_repo(
            self.remote, url, gitref, metadata_only=False
        )
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
                        d_content = DeclarativeContent(
                            content=AnsibleCollectionDeprecated(namespace=namespace, name=name),
                        )
                        self.deprecation_after_sync.add(f"{namespace}.{name}")
                        await self.put(d_content)
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

        if (
            namespace not in self._unpaginated_collection_metadata
            or name not in self._unpaginated_collection_metadata[namespace]
        ):
            raise FileNotFoundError(
                f"Collection {namespace}.{name} does not exist on {self.remote.url}"
            )

        if self._unpaginated_collection_metadata[namespace][name]["deprecated"]:
            d_content = DeclarativeContent(
                content=AnsibleCollectionDeprecated(namespace=namespace, name=name),
            )
            self.deprecation_after_sync.add(f"{namespace}.{name}")
            await self.put(d_content)

        all_versions_of_collection = self._unpaginated_collection_version_metadata[namespace][name]
        for col_version_metadata in all_versions_of_collection:
            if col_version_metadata["version"] in requirement:
                if "git_url" in col_version_metadata and col_version_metadata["git_url"]:
                    tasks.append(
                        loop.create_task(
                            self._add_collection_version_from_git(
                                col_version_metadata["git_url"],
                                col_version_metadata["git_commit_sha"],
                                False,
                            )
                        )
                    )
                else:
                    collection_version_url = urljoin(
                        self.remote.url, f"{col_version_metadata['href']}"
                    )
                    tasks.append(
                        loop.create_task(
                            self._add_collection_version(
                                self._api_version, collection_version_url, col_version_metadata
                            )
                        )
                    )
        await asyncio.gather(*tasks)

    async def _fetch_collection_metadata(self, requirements_entry):
        requirement_version = parse_requirements_entry(requirements_entry)

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
            loop = asyncio.get_event_loop()

            collection_endpoint = f"{root_endpoint}/collections/all/"
            excludes_endpoint = f"{root_endpoint}/excludes/"
            col_downloader = self.remote.get_downloader(
                url=collection_endpoint, silence_errors_for_response_status_codes={404}
            )
            exc_downloader = self.remote.get_downloader(
                url=excludes_endpoint, silence_errors_for_response_status_codes={404}
            )
            tasks = [loop.create_task(col_downloader.run()), loop.create_task(exc_downloader.run())]
            col_results, exc_results = await asyncio.gather(*tasks, return_exceptions=True)

            if not isinstance(exc_results, FileNotFoundError):
                excludes_response = parse_metadata(exc_results)
                if excludes_response:
                    try:
                        excludes_list = parse_collections_requirements_file(excludes_response)
                    except ValidationError:
                        pass
                    else:
                        excludes = {r.name: parse_requirements_entry(r) for r in excludes_list}
                        self.exclude_info.update(excludes)

            if not isinstance(col_results, FileNotFoundError):
                collection_metadata_list = parse_metadata(col_results)

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
                    d_content = DeclarativeContent(
                        content=AnsibleCollectionDeprecated(
                            namespace=collection["namespace"], name=collection["name"]
                        ),
                    )
                    self.deprecation_after_sync.add(
                        f"{collection['namespace']}.{collection['name']}"
                    )
                    await self.put(d_content)

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
        async with ProgressReport(message=msg, code="sync.no_change") as noop:
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

                if not self.optimize:
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
                    return False

        return True

    async def run(self):
        """
        Build and emit `DeclarativeContent` from the ansible metadata.
        """
        tasks = []
        loop = asyncio.get_event_loop()

        msg = _("Parsing CollectionVersion Metadata")
        async with ProgressReport(message=msg, code="sync.parsing.metadata") as pb:
            self.parsing_metadata_progress_bar = pb
            await self._download_unpaginated_metadata()

            if self.collection_info:
                for requirement_entry in self.collection_info:
                    tasks.append(
                        loop.create_task(self._fetch_collection_metadata(requirement_entry))
                    )
            else:
                tasks.append(loop.create_task(self._find_all_collections()))
            await asyncio.gather(*tasks)


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

    def _pre_save(self, batch):
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

    def _post_save(self, batch):
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
                        if runtime_yaml:
                            collection_version.requires_ansible = runtime_yaml.get(
                                "requires_ansible"
                            )
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
