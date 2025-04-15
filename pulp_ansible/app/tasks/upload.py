import json
import logging
import tarfile

from django.db import transaction

from galaxy_importer.collection import import_collection
from pulpcore.plugin.models import Task
from pulpcore.plugin.util import get_url

from pulp_ansible.app.models import Collection, CollectionImport
from pulp_ansible.app.tasks.utils import CollectionFilename, get_file_obj_from_tarball

log = logging.getLogger(__name__)


def process_collection_artifact(artifact, namespace, name, version):
    """
    Helper method to extract a Collection's metadata.

    This is called from ``CollectionVersionUploadSerializer.deferred_validate()``.
    """
    # Avoid circular import
    from .collections import _get_backend_storage_url

    # Set up logging for CollectionImport object
    CollectionImport.objects.get_or_create(task_id=Task.current().pulp_id)
    user_facing_logger = logging.getLogger(
        "pulp_ansible.app.tasks.upload.process_collection_artifact"
    )

    artifact_url = get_url(artifact)
    filename = CollectionFilename(namespace, name, version)
    log.info(f"Processing collection {filename} from {artifact_url}")

    # Extra CollectionVersion metadata
    with artifact.file.open() as artifact_file:
        url = _get_backend_storage_url(artifact_file)
        importer_result = import_collection(
            artifact_file, filename=filename, file_url=url, logger=user_facing_logger
        )
        artifact_file.seek(0)
        with tarfile.open(fileobj=artifact_file, mode="r") as tar:
            manifest_data = json.load(
                get_file_obj_from_tarball(tar, "MANIFEST.json", artifact.file.name)
            )
            files_data = json.load(get_file_obj_from_tarball(tar, "FILES.json", artifact.file.name))

    # Set CollectionVersion metadata
    collection_info = importer_result["metadata"]
    collection_info["sha256"] = artifact.sha256

    with transaction.atomic():
        collection, created = Collection.objects.get_or_create(
            namespace=collection_info["namespace"], name=collection_info["name"]
        )
    collection_info["collection"] = collection
    collection_info["manifest"] = manifest_data
    collection_info["files"] = files_data
    collection_info["requires_ansible"] = importer_result.get("requires_ansible")
    collection_info["contents"] = importer_result["contents"]
    collection_info["docs_blob"] = importer_result["docs_blob"]
    # Remove fields not used by this model
    collection_info.pop("license_file")
    collection_info.pop("readme")
    # the importer returns many None values. We need to let the defaults in the model prevail
    for key in ["description", "documentation", "homepage", "issues", "repository"]:
        if collection_info[key] is None:
            collection_info.pop(key)

    collection_info["relative_path"] = (
        f"{collection_info['namespace']}-{collection_info['name']}-{collection_info['version']}"
        ".tar.gz"
    )
    return collection_info
