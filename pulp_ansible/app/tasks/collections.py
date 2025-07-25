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
import tempfile

import yaml
from aiohttp.client_exceptions import ClientError, ClientResponseError
from asgiref.sync import sync_to_async
from async_lru import alru_cache
from django.db import transaction
from django.db.models import Q
from django.db.utils import IntegrityError
from django.utils.dateparse import parse_datetime
from galaxy_importer.collection import CollectionFilename
from galaxy_importer.collection import import_collection as process_collection
from galaxy_importer.collection import sync_collection
from galaxy_importer.exceptions import ImporterError
from git import GitCommandError, Repo
from pulpcore.plugin.exceptions import DigestValidationError
from pulpcore.plugin.models import (
    Artifact,
    ContentArtifact,
    CreatedResource,
    ProgressReport,
    PulpTemporaryFile,
    Remote,
    RepositoryVersion,
    Task,
)
from pulpcore.plugin.stages import (
    ArtifactDownloader,
    ArtifactSaver,
    ContentSaver,
    ContentAssociation,
    EndStage,
    DeclarativeArtifact,
    DeclarativeContent,
    DeclarativeVersion,
    GenericDownloader,
    QueryExistingArtifacts,
    QueryExistingContents,
    RemoteArtifactSaver,
    ResolveContentFutures,
    Stage,
    create_pipeline,
)
from pulpcore.plugin.util import get_url, get_domain
from rest_framework.serializers import ValidationError
from semantic_version import SimpleSpec, Version
from semantic_version.base import Always

from pulp_ansible.app.constants import PAGE_SIZE
from pulp_ansible.app.models import (
    AnsibleCollectionDeprecated,
    AnsibleNamespace,
    AnsibleNamespaceMetadata,
    AnsibleRepository,
    Collection,
    CollectionImport,
    CollectionRemote,
    CollectionVersion,
    CollectionVersionMark,
    CollectionVersionSignature,
)
from pulp_ansible.app.serializers import CollectionVersionSerializer
from pulp_ansible.app.tasks.utils import (
    RequirementsFileEntry,
    get_file_obj_from_tarball,
    parse_collections_requirements_file,
    parse_metadata,
)

log = logging.getLogger(__name__)

aget_url = sync_to_async(get_url)


# semantic_version.SimpleSpec interpretes "*" as ">=0.0.0"
class AnsibleSpec(SimpleSpec):
    def __init__(self, expression):
        super().__init__(expression)
        if self.expression == "*":
            self.clause = Always()


@sync_to_async
def _save_collection_version(collection_version, artifact):
    with transaction.atomic():
        collection_version.save()
        ContentArtifact.objects.create(
            artifact=artifact,
            content=collection_version,
            relative_path=collection_version.relative_path,
        )


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
    artifact = Artifact.init_and_validate(artifact_path)
    if metadata_only:
        metadata["artifact"] = None
        metadata["artifact_url"] = None
    else:
        if existing_artifact := await Artifact.objects.filter(
            sha256=artifact.sha256, pulp_domain=get_domain()
        ).afirst():
            await existing_artifact.atouch()
            artifact = existing_artifact
        else:
            try:
                assert artifact._state.adding is True
                await sync_to_async(artifact.save)()
                assert artifact._state.adding is False
            except IntegrityError:
                artifact = await Artifact.objects.aget(
                    sha256=artifact.sha256, pulp_domain=get_domain()
                )
        metadata["artifact_url"] = await aget_url(artifact)
        metadata["artifact"] = artifact
    metadata["remote_artifact_url"] = "{}/commit/{}".format(url.rstrip("/"), commit_sha)
    metadata["sha256"] = artifact.sha256

    artifact = metadata["artifact"]
    try:
        collection_version = await sync_to_async(create_collection_from_importer)(metadata)
        await _save_collection_version(collection_version, artifact)
    except ValidationError as e:
        if "unique" in str(e):
            namespace = metadata["metadata"]["namespace"]
            name = metadata["metadata"]["name"]
            version = metadata["metadata"]["version"]
        else:
            raise e
        collection_version = await CollectionVersion.objects.aget(
            namespace=namespace, name=name, version=version, pulp_domain=get_domain()
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
    extra_data = {}
    if metadata_only:
        extra_data["d_artifact_files"] = {d_artifact: artifact_path}

    d_content = DeclarativeContent(
        content=collection_version,
        d_artifacts=[d_artifact],
        extra_data=extra_data,
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

    first_stage = CollectionSyncFirstStage(remote, repository, is_repo_remote, optimize)
    if first_stage.should_sync is False:
        log.debug(_("no-op: remote wasn't updated since last sync."))
        return

    d_version = AnsibleDeclarativeVersion(first_stage, repository, mirror=mirror)
    repo_version = d_version.create()

    if not repo_version:
        return

    repository.last_synced_metadata_time = first_stage.last_synced_metadata_time
    repository.save(update_fields=["last_synced_metadata_time"])


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
    user_facing_logger = logging.getLogger("pulp_ansible.app.tasks.collections.import_collection")

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
        importer_result["artifact_url"] = get_url(artifact)
        importer_result["sha256"] = artifact.sha256
        collection_version = create_collection_from_importer(importer_result)
        collection_version.manifest = manifest_data
        collection_version.files = files_data
        with transaction.atomic():
            collection_version.save()
            ContentArtifact.objects.create(
                artifact=artifact,
                content=collection_version,
                relative_path=collection_version.relative_path,
            )

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

    Do not perform any database operations, just return an unsaved CollectionVersion.
    """
    collection_info = importer_result["metadata"]

    # Remove fields not used by this model
    collection_info.pop("license_file")
    collection_info.pop("readme")

    # the importer returns many None values. We need to let the defaults in the model prevail
    for key in ["description", "documentation", "homepage", "issues", "repository"]:
        if collection_info[key] is None:
            collection_info.pop(key)

    collection, created = Collection.objects.get_or_create(
        namespace=collection_info["namespace"], name=collection_info["name"]
    )
    collection_version = CollectionVersion(
        **collection_info,
        collection=collection,
        requires_ansible=importer_result.get("requires_ansible"),
        contents=importer_result["contents"],
        docs_blob=importer_result["docs_blob"],
        sha256=importer_result["sha256"],
    )

    serializer_fields = CollectionVersionSerializer.Meta.fields
    data = {k: v for k, v in collection_version.__dict__.items() if k in serializer_fields}

    serializer = CollectionVersionSerializer(data=data)
    serializer.is_valid(raise_exception=True)

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


def _rebuild_collection_version_meta(content_object):
    """Rebuild metadata for a single collection version."""

    # Cast to get the CV
    collection_version = content_object.cast()

    # where is the artifact?
    artifact = content_object._artifacts.first()

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
    domain = get_domain()
    if (
        domain.storage_class == "pulpcore.app.models.storage.FileSystem"
        or not domain.redirect_to_object_storage
    ):
        url = None
    elif domain.storage_class == "storages.backends.s3boto3.S3Boto3Storage":
        parameters = {"ResponseContentDisposition": "attachment%3Bfilename=archive.tar.gz"}
        url = artifact_file.storage.url(artifact_file.name, parameters=parameters)
    elif domain.storage_class == "storages.backends.azure_storage.AzureStorage":
        url = artifact_file.storage.url(artifact_file.name)
    else:
        raise NotImplementedError(f"The value {domain.storage_class=} was not expected")
    return url


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
            AnsibleContentSaver(new_version),
            RemoteArtifactSaver(),
            ResolveContentFutures(),
        ]

        return pipeline

    def create(self):
        """
        Perform the work. This is the long-blocking call where all syncing occurs.

        Returns: The created RepositoryVersion or None if it represents no change from the latest.
        """
        with tempfile.TemporaryDirectory(dir="."):
            with self.repository.new_version() as new_version:
                deprecation_before_sync = {
                    (namespace, name)
                    for namespace, name in AnsibleCollectionDeprecated.objects.filter(
                        pk__in=self.repository.latest_version().content
                    ).values_list("namespace", "name")
                }
                loop = asyncio.get_event_loop()
                stages = self.pipeline_stages(new_version)
                stages.append(UndeprecateStage(deprecation_before_sync))
                stages.append(ContentAssociation(new_version, self.mirror))
                stages.append(EndStage())
                pipeline = create_pipeline(stages)
                loop.run_until_complete(pipeline)

                if deprecation_before_sync:
                    to_undeprecate = Q()
                    for namespace, name in deprecation_before_sync:
                        to_undeprecate |= Q(namespace=namespace, name=name)
                    new_version.remove_content(
                        AnsibleCollectionDeprecated.objects.filter(
                            to_undeprecate, pulp_domain=get_domain()
                        )
                    )

        return new_version if new_version.complete else None


class UndeprecateStage(Stage):
    def __init__(self, deprecation_before_sync):
        self.deprecation_before_sync = deprecation_before_sync

    async def run(self):
        async for batch in self.batches():
            for d_content in batch:
                if isinstance(d_content.content, AnsibleCollectionDeprecated):
                    key = (d_content.content.namespace, d_content.content.name)
                    self.deprecation_before_sync.discard(key)
                await self.put(d_content)


class CollectionSyncFirstStage(Stage):
    """
    The first stage of a pulp_ansible sync pipeline.
    """

    def __init__(self, remote, repository, is_repo_remote, optimize):
        """
        The first stage of a pulp_ansible sync pipeline.

        Args:
            remote (CollectionRemote): The remote data to be used when syncing
            repository (AnsibleRepository): The repository being syncedself.
            is_repo_remote (bool): True if the remote is the repository's remote.
            optimize (boolean): Whether to optimize sync or not.

        """
        super().__init__()
        self.remote = remote
        self.repository = repository
        self.collection_info = parse_collections_requirements_file(remote.requirements_file)
        self.exclude_info = {}
        self.add_dependents = self.collection_info and self.remote.sync_dependencies
        self.signed_only = self.remote.signed_only
        self.already_synced = set()
        self._unpaginated_collection_metadata = None
        self._unpaginated_collection_version_metadata = None
        self.optimize = optimize
        self.last_synced_metadata_time = None
        self.namespace_shas = {}
        self._unpaginated_namespace_metadata = None

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
        if cv_unique in self.already_synced:
            return

        # Mark the collection version as being processed
        self.already_synced.add(cv_unique)
        await self.parsing_metadata_progress_bar.aincrement()

        if fullname in self.exclude_info and Version(version) in self.exclude_info[fullname]:
            log.debug(_("{}-{} is in excludes list, skipping").format(fullname, version))
            return

        info = metadata["metadata"]
        signatures = metadata.get("signatures", [])
        marks = metadata.get("marks", [])

        if self.signed_only and not signatures:
            log.debug(_("{}-{} does not have any signatures, skipping").format(fullname, version))
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
        collection_version.sha256 = artifact["sha256"]
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
        await self.put(d_content)

        if signatures or marks:
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

            for mark_value in marks:
                cv_mark = CollectionVersionMark(
                    marked_collection=collection_version,
                    value=mark_value,
                )
                await self.put(DeclarativeContent(content=cv_mark))

        # Process syncing CV Namespace Metadata if present
        namespace_sha = metadata["namespace"].get("metadata_sha256")
        if namespace_sha:
            self.namespace_shas[collection_version.namespace] = namespace_sha

    async def _add_namespace(self, name, namespace_sha):
        """Adds A Namespace metadata content to the pipeline."""

        try:
            ns = await AnsibleNamespaceMetadata.objects.aget(
                metadata_sha256=namespace_sha, pulp_domain=get_domain()
            )
            await self.put(DeclarativeContent(ns))
            await self.parsing_namespace_progress_bar.aincrement()
            return
        except AnsibleNamespaceMetadata.DoesNotExist:
            pass

        endpoint, api_version = await self._get_root_api(self.remote.url)
        namespace_url = f"{endpoint}/namespaces/{name}"
        downloader = self.remote.get_downloader(
            url=namespace_url, silence_errors_for_response_codes={404}
        )
        try:
            result = await downloader.run()
        except FileNotFoundError:
            pass
        else:
            namespace = parse_metadata(result)
            links = namespace.get("links", None)

            # clean up the galaxy API for pulp
            if links:
                namespace["links"] = {x["name"]: x["url"] for x in links}
            else:
                namespace["links"] = dict()

            for key in ("pulp_href", "groups", "id", "related_fields", "users"):
                namespace.pop(key, None)

            url = namespace.pop("avatar_url", None)

            da = (
                [
                    DeclarativeFailsafeArtifact(
                        Artifact(sha256=namespace.get("avatar_sha256")),
                        url=url,
                        remote=self.remote,
                        relative_path=f"{name}-avatar",
                        deferred_download=False,
                        extra_data={"namespace": name},
                    )
                ]
                if url
                else None
            )

            namespace = AnsibleNamespaceMetadata(**namespace)
            dc = DeclarativeContent(namespace, d_artifacts=da)
            await self.put(dc)
            await self.parsing_namespace_progress_bar.aincrement()
            return

        log.info(f"Failed to find namespace {name}")

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
                if Version(collection_version["version"]) in requirement:
                    version_num = collection_version["version"]
                    collection_version_detail_url = f"{collection_url}/versions/{version_num}/"
                    if collection_metadata["deprecated"]:
                        d_content = DeclarativeContent(
                            content=AnsibleCollectionDeprecated(namespace=namespace, name=name),
                        )
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

        self.parsing_metadata_progress_bar.total += len(tasks)
        await self.parsing_metadata_progress_bar.asave(update_fields=["total"])
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
            await self.put(d_content)

        all_versions_of_collection = self._unpaginated_collection_version_metadata[namespace][name]
        for col_version_metadata in all_versions_of_collection:
            if Version(col_version_metadata["version"]) in requirement:
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
        self.parsing_metadata_progress_bar.total += len(tasks)
        await self.parsing_metadata_progress_bar.asave(update_fields=["total"])
        await asyncio.gather(*tasks)

    async def _fetch_collection_metadata(self, requirements_entry):
        requirement_version = AnsibleSpec(requirements_entry.version)

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
            return response.get("next")
        elif links := response.get("links"):
            return links.get("next")
        else:
            return None

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
                        excludes = {r.name: AnsibleSpec(r.version) for r in excludes_list}
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

        self.parsing_metadata_progress_bar.total = len(tasks)
        await self.parsing_metadata_progress_bar.asave(update_fields=["total"])
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

        self.parsing_metadata_progress_bar.total = len(tasks)
        await self.parsing_metadata_progress_bar.asave(update_fields=["total"])
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
        async with ProgressReport(message=msg, code="sync.parsing.metadata", total=0) as pb:
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
            # Ensure PR 'total' is correct before stage finishes
            pb.total = pb.done

        tasks = []
        msg = _("Parsing Namespace Metadata")
        async with ProgressReport(
            message=msg, code="sync.parsing.namespace", total=len(self.namespace_shas)
        ) as pr:
            self.parsing_namespace_progress_bar = pr
            for namespace, namespace_sha in self.namespace_shas.items():
                tasks.append(loop.create_task(self._add_namespace(namespace, namespace_sha)))
            await asyncio.gather(*tasks)
            # Ensuring the total is correct, as some avatar download might fail
            pr.total = pr.done


class DeclarativeFailsafeArtifact(DeclarativeArtifact):
    """
    Special handling for downloading Namespace Avatar Artifacts.
    """

    async def download(self):
        """Allow download to fail, but not stop the sync."""
        artifact_copy = self.artifact
        try:
            return await super().download()
        except (ClientError, DigestValidationError) as e:
            # Reset DA so that future stages can properly handle it
            self.artifact = artifact_copy
            self.deferred_download = True
            name = self.extra_data.get("namespace")
            log.info(f"Failed to download namespace avatar: {name} - {e}, Skipping")
            return None


class DocsBlobDownloader(GenericDownloader):
    """
    Stage for downloading docs_blob.

    Args:
        max_concurrent_content (int): The maximum number of
            :class:`~pulpcore.plugin.stages.DeclarativeContent` instances to handle simultaneously.
            Default is 200.
        args: unused positional arguments passed along to :class:`~pulpcore.plugin.stages.Stage`.
        kwargs: unused keyword arguments passed along to :class:`~pulpcore.plugin.stages.Stage`.
    """

    PROGRESS_REPORTING_MESSAGE = "Downloading Docs Blob"
    PROGRESS_REPORTING_CODE = "sync.downloading.docs_blob"

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


class AnsibleContentSaver(ContentSaver):
    """
    A modification of ContentSaver stage that additionally saves Ansible plugin specific items.

    Saves Collection objects related to the CollectionVersion content unit.
    """

    def __init__(self, repository_version, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.repository_version = repository_version

    def _pre_save(self, batch):
        """
        Save a batch of Collection objects.

        Args:
            batch (list of :class:`~pulpcore.plugin.stages.DeclarativeContent`): The batch of
                :class:`~pulpcore.plugin.stages.DeclarativeContent` objects to be saved.

        """
        # Sort the batch by natural key to prevent deadlocks
        # Keep this here until added to Pulpcore
        batch.sort(key=lambda x: "".join(map(str, x.content.natural_key())))
        for d_content in batch:
            if d_content is None:
                continue
            if isinstance(d_content.content, CollectionVersion):
                d_content.content = self._handle_collection_version(d_content)
            elif isinstance(d_content.content, AnsibleNamespaceMetadata):
                name = d_content.content.name
                namespace, created = AnsibleNamespace.objects.get_or_create(name=name)
                d_content.content.namespace = namespace
                if d_content.d_artifacts:
                    da = d_content.d_artifacts[0]
                    # Check to see if avatar failed to download, update metadata if so,
                    # so that the avatar should be attemtped to be downloaded again.
                    if da.deferred_download:
                        d_content.d_artifacts = []
                        d_content.content.avatar_sha256 = None
                        d_content.content.metadata_sha256 = None

    def _handle_collection_version(self, d_content):
        collection_version = d_content.content

        collection, created = Collection.objects.get_or_create(
            namespace=d_content.content.namespace, name=d_content.content.name
        )
        collection_version.collection = collection

        docs_blob = d_content.extra_data.get("docs_blob", {})
        if docs_blob:
            collection_version.docs_blob = docs_blob
        d_artifact_files = d_content.extra_data.get("d_artifact_files", {})

        for d_artifact in d_content.d_artifacts:
            artifact = d_artifact.artifact
            # TODO change logic when implementing normal on-demand syncing
            # Special Case for Git sync w/ metadata_only=True
            if artifact_file_name := d_artifact_files.get(d_artifact):
                artifact_file = open(artifact_file_name, mode="rb")
            else:
                artifact_file = artifact.file.open()
            with tarfile.open(fileobj=artifact_file, mode="r") as tar:
                runtime_metadata = get_file_obj_from_tarball(
                    tar, "meta/runtime.yml", artifact.file.name, raise_exc=False
                )
                if runtime_metadata:
                    runtime_yaml = yaml.safe_load(runtime_metadata)
                    if runtime_yaml:
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
            artifact_file.close()

            # Remove fields not used by this model
            info.pop("license_file")
            info.pop("readme")

            # Update with the additional data from the Collection
            for attr_name, attr_value in info.items():
                if attr_value is None:
                    continue
                setattr(collection_version, attr_name, attr_value)
            return collection_version
