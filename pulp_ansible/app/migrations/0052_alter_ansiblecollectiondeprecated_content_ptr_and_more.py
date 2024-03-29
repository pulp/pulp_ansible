# Generated by Django 4.2.1 on 2023-05-15 14:40

from django.db import migrations, models
import django.db.models.deletion
import pulpcore.app.models.base


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0106_alter_artifactdistribution_distribution_ptr_and_more"),
        ("ansible", "0051_cvindex_build"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ansiblecollectiondeprecated",
            name="content_ptr",
            field=models.OneToOneField(
                auto_created=True,
                on_delete=django.db.models.deletion.CASCADE,
                parent_link=True,
                primary_key=True,
                serialize=False,
                to="core.content",
            ),
        ),
        migrations.AlterField(
            model_name="ansibledistribution",
            name="distribution_ptr",
            field=models.OneToOneField(
                auto_created=True,
                on_delete=django.db.models.deletion.CASCADE,
                parent_link=True,
                primary_key=True,
                serialize=False,
                to="core.distribution",
            ),
        ),
        migrations.AlterField(
            model_name="ansiblenamespace",
            name="pulp_id",
            field=models.UUIDField(
                default=pulpcore.app.models.base.pulp_uuid,
                editable=False,
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.AlterField(
            model_name="ansiblenamespacemetadata",
            name="content_ptr",
            field=models.OneToOneField(
                auto_created=True,
                on_delete=django.db.models.deletion.CASCADE,
                parent_link=True,
                primary_key=True,
                serialize=False,
                to="core.content",
            ),
        ),
        migrations.AlterField(
            model_name="ansiblerepository",
            name="repository_ptr",
            field=models.OneToOneField(
                auto_created=True,
                on_delete=django.db.models.deletion.CASCADE,
                parent_link=True,
                primary_key=True,
                serialize=False,
                to="core.repository",
            ),
        ),
        migrations.AlterField(
            model_name="collection",
            name="pulp_id",
            field=models.UUIDField(
                default=pulpcore.app.models.base.pulp_uuid,
                editable=False,
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.AlterField(
            model_name="collectionremote",
            name="remote_ptr",
            field=models.OneToOneField(
                auto_created=True,
                on_delete=django.db.models.deletion.CASCADE,
                parent_link=True,
                primary_key=True,
                serialize=False,
                to="core.remote",
            ),
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="content_ptr",
            field=models.OneToOneField(
                auto_created=True,
                on_delete=django.db.models.deletion.CASCADE,
                parent_link=True,
                primary_key=True,
                serialize=False,
                to="core.content",
            ),
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="tags",
            field=models.ManyToManyField(editable=False, to="ansible.tag"),
        ),
        migrations.AlterField(
            model_name="collectionversionmark",
            name="content_ptr",
            field=models.OneToOneField(
                auto_created=True,
                on_delete=django.db.models.deletion.CASCADE,
                parent_link=True,
                primary_key=True,
                serialize=False,
                to="core.content",
            ),
        ),
        migrations.AlterField(
            model_name="collectionversionsignature",
            name="content_ptr",
            field=models.OneToOneField(
                auto_created=True,
                on_delete=django.db.models.deletion.CASCADE,
                parent_link=True,
                primary_key=True,
                serialize=False,
                to="core.content",
            ),
        ),
        migrations.AlterField(
            model_name="crossrepositorycollectionversionindex",
            name="collection_version",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="ansible.collectionversion"
            ),
        ),
        migrations.AlterField(
            model_name="crossrepositorycollectionversionindex",
            name="namespace_metadata",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="ansible.ansiblenamespacemetadata",
            ),
        ),
        migrations.AlterField(
            model_name="crossrepositorycollectionversionindex",
            name="repository",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="ansible.ansiblerepository"
            ),
        ),
        migrations.AlterField(
            model_name="crossrepositorycollectionversionindex",
            name="repository_version",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE, to="core.repositoryversion"
            ),
        ),
        migrations.AlterField(
            model_name="downloadlog",
            name="pulp_id",
            field=models.UUIDField(
                default=pulpcore.app.models.base.pulp_uuid,
                editable=False,
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.AlterField(
            model_name="gitremote",
            name="remote_ptr",
            field=models.OneToOneField(
                auto_created=True,
                on_delete=django.db.models.deletion.CASCADE,
                parent_link=True,
                primary_key=True,
                serialize=False,
                to="core.remote",
            ),
        ),
        migrations.AlterField(
            model_name="role",
            name="content_ptr",
            field=models.OneToOneField(
                auto_created=True,
                on_delete=django.db.models.deletion.CASCADE,
                parent_link=True,
                primary_key=True,
                serialize=False,
                to="core.content",
            ),
        ),
        migrations.AlterField(
            model_name="roleremote",
            name="remote_ptr",
            field=models.OneToOneField(
                auto_created=True,
                on_delete=django.db.models.deletion.CASCADE,
                parent_link=True,
                primary_key=True,
                serialize=False,
                to="core.remote",
            ),
        ),
        migrations.AlterField(
            model_name="tag",
            name="pulp_id",
            field=models.UUIDField(
                default=pulpcore.app.models.base.pulp_uuid,
                editable=False,
                primary_key=True,
                serialize=False,
            ),
        ),
    ]
