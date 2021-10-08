# Generated by Django 3.2.7 on 2021-10-08 13:17

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0076_remove_reserved_resource'),
        ('ansible', '0036_update_repository_content'),
    ]

    operations = [
        migrations.CreateModel(
            name='GitRemote',
            fields=[
                ('remote_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, related_name='ansible_gitremote', serialize=False, to='core.remote')),
                ('metadata_only', models.BooleanField(default=False)),
            ],
            options={
                'default_related_name': '%(app_label)s_%(model_name)s',
            },
            bases=('core.remote',),
        ),
    ]
