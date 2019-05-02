from gettext import gettext as _
import json
import logging
import tarfile

from django.db import transaction

from pulpcore.plugin.models import Artifact, ContentArtifact, CreatedResource
from pulp_ansible.app.models import Collection


log = logging.getLogger(__name__)


def import_collection(artifact_pk):
    """
    Create a collection from an uploaded artifact.

    Args:
        artifact_pk (str): The pk or the Artifact to create the Collection from.
    """
    artifact = Artifact.objects.get(pk=artifact_pk)
    with tarfile.open(str(artifact.file.path), "r") as tar:
        log.info(_('Reading MANIFEST.json from {path}').format(path=artifact.file.path))
        file_obj = tar.extractfile('MANIFEST.json')
        manifest_data = json.load(file_obj)
        collection_info = manifest_data['collection_info']

        collection = Collection(
            namespace=collection_info['namespace'],
            name=collection_info['name'],
            version=collection_info['version']
        )
        with transaction.atomic():
            collection.save()
            ContentArtifact.objects.create(
                artifact=artifact,
                content=collection,
                relative_path=collection.relative_path,
            )
            CreatedResource.objects.create(content_object=collection)
