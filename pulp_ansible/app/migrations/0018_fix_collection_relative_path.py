from django.db import migrations, models


def migrate_artifact_relative_path(apps, schema_editor):
    ContentArtifact = apps.get_model("core", "ContentArtifact")
    CollectionVersion = apps.get_model("ansible", "CollectionVersion")

    artifacts = (
        ContentArtifact.objects.select_related("content", "content__ansible_collectionversion",)
        .filter(content__ansible_collectionversion__isnull=False)
        .only(
            "content__ansible_collectionversion__namespace",
            "content__ansible_collectionversion__name",
            "content__ansible_collectionversion__version",
        )
        .all()
    )

    for artifact in artifacts:
        cv = artifact.content.ansible_collectionversion
        artifact.relative_path = "{namespace}-{name}-{version}.tar.gz".format(
            namespace=cv.namespace, name=cv.name, version=cv.version
        )
    ContentArtifact.objects.bulk_update(artifacts, ["relative_path"])


class Migration(migrations.Migration):

    dependencies = [
        ("ansible", "0017_increase_length_collectionversion_fields"),
    ]

    operations = [
        migrations.RunPython(code=migrate_artifact_relative_path),
    ]
