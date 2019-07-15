from gettext import gettext as _
import json
import logging
import os
import tarfile
import tempfile

from ansible_galaxy.actions.install import install_repository_specs_loop
from ansible_galaxy.models.context import GalaxyContext
from django.db import transaction
from pulpcore.plugin.models import (
    Artifact,
    ContentArtifact,
    CreatedResource,
    ProgressBar,
    Repository,
    RepositoryVersion,
)

from pulp_ansible.app.models import Collection, CollectionRemote, CollectionVersion


log = logging.getLogger(__name__)


def sync(remote_pk, repository_pk):
    """
    Sync Collections with ``remote_pk``, and save a new RepositoryVersion for ``repository_pk``.

    Args:
        remote_pk (str): The remote PK.
        repository_pk (str): The repository PK.

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

    repository_spec_strings = remote.whitelist.split(" ")

    def nowhere(*args, **kwargs):
        pass

    collection_version_pks = []
    download_pb = ProgressBar(message="Downloading Collections", total=len(repository_spec_strings))
    import_pb = ProgressBar(message="Importing Collections", total=len(repository_spec_strings))

    with RepositoryVersion.create(repository) as new_version:
        with tempfile.TemporaryDirectory() as temp_ansible_path:
            with download_pb:
                # workaround: mazer logs errors without this dir https://pulp.plan.io/issues/4999
                os.mkdir(os.path.join(temp_ansible_path, "ansible_collections"))

                galaxy_context = GalaxyContext(
                    collections_path=temp_ansible_path,
                    server={"url": remote.url, "ignore_certs": False},
                )

                install_repository_specs_loop(
                    display_callback=nowhere,
                    galaxy_context=galaxy_context,
                    repository_spec_strings=repository_spec_strings,
                )

                download_pb.done = len(repository_spec_strings)

            with import_pb:
                content_walk_generator = os.walk(temp_ansible_path)
                for dirpath, dirnames, filenames in content_walk_generator:
                    if "MANIFEST.json" in filenames:
                        manifest_path = os.path.join(dirpath, "MANIFEST.json")
                        with open(manifest_path) as manifest_file:
                            manifest_data = json.load(manifest_file)
                        info = manifest_data["collection_info"]
                        filename = "{namespace}-{name}-{version}".format(
                            namespace=info["namespace"], name=info["name"], version=info["version"]
                        )
                        tarfile_path = os.path.join(temp_ansible_path, filename + ".tar.gz")
                        with tarfile.open(name=tarfile_path, mode="w|gz") as newtar:
                            newtar.add(dirpath, arcname=filename)

                        with transaction.atomic():
                            collection, created = Collection.objects.get_or_create(
                                namespace=info["namespace"], name=info["name"]
                            )
                            collection_version, created = CollectionVersion.objects.get_or_create(
                                collection=collection, version=info["version"]
                            )

                            if created:
                                artifact = Artifact.init_and_validate(newtar.name)
                                artifact.save()

                                ContentArtifact.objects.create(
                                    artifact=artifact,
                                    content=collection_version,
                                    relative_path=collection_version.relative_path,
                                )

                            collection_version_pks.append(collection_version)
                        import_pb.increment()

        collection_versions = CollectionVersion.objects.filter(pk__in=collection_version_pks)
        new_version.add_content(collection_versions)


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
            collection_version = CollectionVersion(
                collection=collection, version=collection_info["version"]
            )
            collection_version.save()
            ContentArtifact.objects.create(
                artifact=artifact,
                content=collection_version,
                relative_path=collection_version.relative_path,
            )
            CreatedResource.objects.create(content_object=collection_version)
