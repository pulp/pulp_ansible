# Generated by Django 4.2.1 on 2023-05-31 20:46

from django.db import migrations, models
import django_lifecycle.mixins
import pulpcore.app.models.base


class Migration(migrations.Migration):
    dependencies = [
        ("ansible", "0052_alter_ansiblecollectiondeprecated_content_ptr_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="CollectionDownloadCount",
            fields=[
                (
                    "pulp_id",
                    models.UUIDField(
                        default=pulpcore.app.models.base.pulp_uuid,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("pulp_created", models.DateTimeField(auto_now_add=True)),
                ("pulp_last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("namespace", models.CharField(editable=False, max_length=64)),
                ("name", models.CharField(editable=False, max_length=64)),
                ("download_count", models.BigIntegerField(default=0)),
            ],
            options={
                "unique_together": {("namespace", "name")},
            },
            bases=(django_lifecycle.mixins.LifecycleModelMixin, models.Model),
        ),
    ]