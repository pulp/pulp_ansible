import uuid

from django.contrib.postgres import fields as psql_fields
from django.db import migrations
from django.db import models


def migrate_collections(apps, schema_editor):
    Collection = apps.get_model("ansible", "Collection")
    CollectionVersion = apps.get_model("ansible", "CollectionVersion")
    versions = CollectionVersion.objects.order_by("namespace", "name").all()
    for version in versions:
        collection, _ = Collection.objects.get_or_create(
            namespace=version.namespace, name=version.name
        )
        version.collection = collection
        # Reset `_type` value to regenerate it on `save()`.
        version._type = None
        version.save()


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial"), ("ansible", "0001_initial")]

    operations = [
        migrations.RenameModel(old_name="collection", new_name="collectionversion"),
        migrations.AlterField(
            model_name="collectionversion",
            name="version",
            field=models.CharField(max_length=128, editable=False),
        ),
        migrations.AddField(
            model_name="collectionversion",
            name="contents",
            field=psql_fields.JSONField(default=list, editable=False),
        ),
        migrations.AddField(
            model_name="collectionversion",
            name="metadata",
            field=psql_fields.JSONField(default=dict, editable=False),
        ),
        migrations.AddField(
            model_name="collectionversion",
            name="quality_score",
            field=models.FloatField(null=True, editable=False),
        ),
        migrations.CreateModel(
            name="Collection",
            fields=[
                (
                    "_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("_created", models.DateTimeField(auto_now_add=True)),
                ("_last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("namespace", models.CharField(max_length=64, editable=False)),
                ("name", models.CharField(max_length=64, editable=False)),
                ("deprecated", models.BooleanField(default=False)),
            ],
            options={"unique_together": {("namespace", "name")}},
        ),
        migrations.AddField(
            model_name="collectionversion",
            name="collection",
            field=models.ForeignKey(
                to="ansible.Collection",
                on_delete=models.CASCADE,
                related_name="versions",
                null=True,
            ),
        ),
        migrations.RunPython(code=migrate_collections),
        migrations.AlterField(
            model_name="collectionversion",
            name="collection",
            field=models.ForeignKey(
                to="ansible.Collection",
                on_delete=models.CASCADE,
                related_name="versions",
                editable=False,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="collectionversion", unique_together={("collection", "version")}
        ),
        migrations.RemoveField(model_name="collectionversion", name="name"),
        migrations.RemoveField(model_name="collectionversion", name="namespace"),
    ]
