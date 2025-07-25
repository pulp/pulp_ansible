# Generated by Django 4.2.22 on 2025-07-01 14:04

from django.db import migrations, models
import django.db.models.deletion
import pulpcore.app.util


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0123_upstreampulp_q_select"),
        ("ansible", "0063_domain_support"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="collection",
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name="collectiondownloadcount",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="ansiblenamespace",
            name="pulp_domain",
            field=models.ForeignKey(
                default=pulpcore.app.util.get_domain_pk,
                on_delete=django.db.models.deletion.PROTECT,
                to="core.domain",
            ),
        ),
        migrations.AddField(
            model_name="collection",
            name="pulp_domain",
            field=models.ForeignKey(
                default=pulpcore.app.util.get_domain_pk,
                on_delete=django.db.models.deletion.PROTECT,
                to="core.domain",
            ),
        ),
        migrations.AddField(
            model_name="collectiondownloadcount",
            name="pulp_domain",
            field=models.ForeignKey(
                default=pulpcore.app.util.get_domain_pk,
                on_delete=django.db.models.deletion.PROTECT,
                to="core.domain",
            ),
        ),
        migrations.AlterField(
            model_name="ansiblenamespace",
            name="name",
            field=models.CharField(max_length=64),
        ),
        migrations.AlterUniqueTogether(
            name="ansiblenamespace",
            unique_together={("pulp_domain", "name")},
        ),
        migrations.AlterUniqueTogether(
            name="collection",
            unique_together={("pulp_domain", "namespace", "name")},
        ),
        migrations.AlterUniqueTogether(
            name="collectiondownloadcount",
            unique_together={("pulp_domain", "namespace", "name")},
        ),
    ]
