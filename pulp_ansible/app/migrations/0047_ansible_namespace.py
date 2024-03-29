# Generated by Django 3.2.17 on 2023-02-08 21:50

import django.contrib.postgres.fields.hstore
from django.db import migrations, models
import django.db.models.deletion
import django_lifecycle.mixins
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0099_versions_field'),
        ('ansible', '0046_add_fulltext_search_fix'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnsibleNamespace',
            fields=[
                ('pulp_id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('pulp_created', models.DateTimeField(auto_now_add=True)),
                ('pulp_last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('name', models.CharField(max_length=64, unique=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(django_lifecycle.mixins.LifecycleModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='AnsibleNamespaceMetadata',
            fields=[
                ('content_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, related_name='ansible_ansiblenamespacemetadata', serialize=False, to='core.content')),
                ('name', models.CharField(max_length=64)),
                ('company', models.CharField(blank=True, default='', max_length=64)),
                ('email', models.CharField(blank=True, default='', max_length=256)),
                ('description', models.CharField(blank=True, default='', max_length=256)),
                ('resources', models.TextField(blank=True, default='')),
                ('links', django.contrib.postgres.fields.hstore.HStoreField(default=dict)),
                ('avatar_sha256', models.CharField(max_length=64, null=True)),
                ('metadata_sha256', models.CharField(db_index=True, max_length=64)),
                ('namespace', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='metadatas', to='ansible.ansiblenamespace')),
            ],
            options={
                'default_related_name': '%(app_label)s_%(model_name)s',
                'unique_together': {('metadata_sha256',)},
            },
            bases=('core.content',),
        ),
    ]
