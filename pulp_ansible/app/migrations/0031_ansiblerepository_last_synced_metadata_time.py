# Generated by Django 2.2.17 on 2021-01-29 18:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ansible', '0030_collectionversion_requires_ansible'),
    ]

    operations = [
        migrations.AddField(
            model_name='ansiblerepository',
            name='last_synced_metadata_time',
            field=models.DateTimeField(null=True),
        ),
    ]
