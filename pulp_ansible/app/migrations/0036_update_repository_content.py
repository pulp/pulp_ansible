# Generated by Django 2.2.24 on 2021-07-07 17:46

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0068_add_timestamp_of_interest'),
        ('ansible', '0035_deprecation_content'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='ansiblecollectiondeprecated',
            unique_together={('namespace', 'name')},
        ),
        migrations.RemoveField(model_name="ansiblecollectiondeprecated", name="collection_id"),
        migrations.RemoveField(model_name="ansiblecollectiondeprecated", name="repository_id"),
        migrations.RemoveField(model_name="ansiblecollectiondeprecated", name="version_added_id"),
    ]