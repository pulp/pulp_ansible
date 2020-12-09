import logging

from django.db import transaction
from django.urls import reverse
from galaxy_importer.collection import import_collection as process_collection
from galaxy_importer.collection import CollectionFilename
from galaxy_importer.exceptions import ImporterError
from rq.job import get_current_job

from pulpcore.plugin.models import (
    Artifact,
    ContentArtifact,
    CreatedResource,
    PulpTemporaryFile,
)
from pulp_ansible.app.models import (
    AnsibleRepository,
    Collection,
    CollectionImport,
    CollectionVersion,
    Tag,
)
from pulp_ansible.app.serializers import CollectionVersionSerializer
from pulp_ansible.app.tasks.collections.utils import update_highest_version


log = logging.getLogger(__name__)


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

        update_highest_version(collection_version)

        collection_version.save()  # Save the FK updates
    return collection_version
