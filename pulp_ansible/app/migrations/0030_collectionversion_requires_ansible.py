# Generated by Django 2.2.17 on 2020-12-09 20:22
import logging
import json
import tarfile
import yaml
from json import JSONDecodeError
from yaml.error import YAMLError
from django.db import migrations, models

from pulp_ansible.app.tasks.utils import get_file_obj_from_tarball

log = logging.getLogger(__name__)


def set_requires_ansible_and_manifest_and_files_json(apps, schema_editor):
    CollectionVersion = apps.get_model("ansible", "CollectionVersion")
    for collection_version in CollectionVersion.objects.all():
        artifact = collection_version.contentartifact_set.get().artifact
        with artifact.file.open() as artifact_file, tarfile.open(fileobj=artifact_file, mode="r") as tar:
            runtime_metadata = get_file_obj_from_tarball(
                tar, "meta/runtime.yml", artifact.file.name, raise_exc=False
            )
            if runtime_metadata:
                try:
                    runtime_yaml = yaml.safe_load(runtime_metadata)
                except YAMLError:
                    log.warning(
                        "CollectionVersion: '{namespace}.{name}-{version}' - 'meta/runtime.yml' is invalid yaml.".format(
                            namespace=collection_version.namespace, name=collection_version.name, version=collection_version.version
                        )
                    )
                else:
                    try:
                        collection_version.requires_ansible = runtime_yaml.get("requires_ansible")
                    except AttributeError:
                        log.warning(
                            "CollectionVersion: '{namespace}.{name}-{version}' - 'meta/runtime.yml' is missing key 'requires_ansible'.".format(
                                namespace=collection_version.namespace, name=collection_version.name, version=collection_version.version
                            )
                        )

            manifest = get_file_obj_from_tarball(tar, "MANIFEST.json", artifact.file.name, raise_exc=False)
            if manifest:
                try:
                    collection_version.manifest = json.load(manifest)
                except JSONDecodeError:
                    log.warning(
                        "CollectionVersion: '{namespace}.{name}-{version}' - 'MANIFEST.json' is invalid json.".format(
                            namespace=collection_version.namespace, name=collection_version.name, version=collection_version.version
                        )
                    )

            files = get_file_obj_from_tarball(tar, "FILES.json", artifact.file.name, raise_exc=False)
            if files:
                try:
                    collection_version.files = json.load(files)
                except JSONDecodeError:
                    log.warning(
                        "CollectionVersion: '{namespace}.{name}-{version}' - 'FILES.json' is invalid json.".format(
                            namespace=collection_version.namespace, name=collection_version.name, version=collection_version.version
                        )
                    )
            collection_version.save()


class Migration(migrations.Migration):

    dependencies = [
        ('ansible', '0029_manifest_and_files_json_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='collectionversion',
            name='requires_ansible',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.RunPython(code=set_requires_ansible_and_manifest_and_files_json,
                             reverse_code=migrations.RunPython.noop)
    ]
