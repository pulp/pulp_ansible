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
    Repository,
    RepositoryVersion,
)

from pulp_ansible.app.models import Collection, CollectionRemote


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

    repository_spec_strings = remote.whitelist.split(' ')

    def nowhere(*args, **kwargs):
        pass

    collections_pks = []

    with RepositoryVersion.create(repository) as new_version:
        with tempfile.TemporaryDirectory() as temp_ansible_path:

            # workaround: mazer logs errors without this dir  https://pulp.plan.io/issues/4999
            os.mkdir(temp_ansible_path + os.sep + 'ansible_collections')

            galaxy_context = GalaxyContext(
                collections_path=temp_ansible_path,
                server={
                    'url': remote.url,
                    'ignore_certs': False,
                },
            )

            install_repository_specs_loop(
                display_callback=nowhere,
                galaxy_context=galaxy_context,
                repository_spec_strings=repository_spec_strings,
            )

            content_walk_generator = os.walk(temp_ansible_path)
            for dirpath, dirnames, filenames in content_walk_generator:
                if 'MANIFEST.json' in filenames:
                    with open(dirpath + os.path.sep + 'MANIFEST.json') as manifest_file:
                        manifest_data = json.load(manifest_file)
                    info = manifest_data['collection_info']
                    filename = '{namespace}-{name}-{version}'.format(
                        namespace=info['namespace'],
                        name=info['name'],
                        version=info['version'],
                    )
                    tarfile_path = temp_ansible_path + os.path.sep + filename + '.tar.gz'
                    with tarfile.open(name=tarfile_path, mode='w|gz') as newtar:
                        newtar.add(dirpath, arcname=filename)

                    with transaction.atomic():
                        collection, created = Collection.objects.get_or_create(
                            namespace=info['namespace'],
                            name=info['name'],
                            version=info['version']
                        )

                        if created:
                            artifact = Artifact.init_and_validate(newtar.name)
                            artifact.save()

                            ContentArtifact.objects.create(
                                artifact=artifact,
                                content=collection,
                                relative_path=collection.relative_path,
                            )

                            collections_pks.append(collection)

        collections = Collection.objects.filter(pk__in=collections_pks)
        new_version.add_content(collections)
