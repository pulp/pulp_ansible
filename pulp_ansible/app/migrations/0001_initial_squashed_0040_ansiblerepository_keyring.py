# Generated by Django 4.2.16 on 2024-12-05 13:07

import django.contrib.postgres.fields
import django.contrib.postgres.fields.jsonb
import django.contrib.postgres.search
from django.db import migrations, models
import django.db.models.deletion
import django_lifecycle.mixins
import uuid


class Migration(migrations.Migration):

    replaces = [
        ("ansible", "0001_initial"),
        ("ansible", "0002_advanced_collections"),
        ("ansible", "0003_add_tags_and_collectionversion_fields"),
        ("ansible", "0004_add_fulltext_search_indexes"),
        ("ansible", "0005_collectionversion_is_highest"),
        ("ansible", "0006_remove_whitelist_and_alter_collection_version_name"),
        ("ansible", "0007_collectionversion_is_certified"),
        ("ansible", "0008_collectionremote_requirements_file"),
        ("ansible", "0009_collectionimport"),
        ("ansible", "0010_ansible_related_names"),
        ("ansible", "0011_collectionimport"),
        ("ansible", "0012_auto_20190906_2253"),
        ("ansible", "0013_pulp_fields"),
        ("ansible", "0014_certification_enum"),
        ("ansible", "0015_ansiblerepository"),
        ("ansible", "0016_add_extension"),
        ("ansible", "0017_increase_length_collectionversion_fields"),
        ("ansible", "0018_fix_collection_relative_path"),
        ("ansible", "0019_collection_token"),
        ("ansible", "0020_auto_20200810_1926"),
        ("ansible", "0021_rename_role_remote"),
        ("ansible", "0022_URLField_to_CharField"),
        ("ansible", "0023_alter_requirements_file_field"),
        ("ansible", "0024_remove_collectionversion_certification"),
        ("ansible", "0025_increase_collection_version_version_size"),
        ("ansible", "0026_deprecation_per_repository"),
        ("ansible", "0027_tag_length"),
        ("ansible", "0028_collectionversion_namespace_length"),
        ("ansible", "0029_manifest_and_files_json_fields"),
        ("ansible", "0030_collectionversion_requires_ansible"),
        ("ansible", "0031_ansiblerepository_last_synced_metadata_time"),
        ("ansible", "0032_collectionremote_sync_dependencies"),
        ("ansible", "0033_swap_distribution_model"),
        ("ansible", "0034_handle_jsonfield_warnings"),
        ("ansible", "0035_deprecation_content"),
        ("ansible", "0036_update_repository_content"),
        ("ansible", "0037_gitremote"),
        ("ansible", "0038_collectionversionsignature"),
        ("ansible", "0039_collectionremote_signed_only"),
        ("ansible", "0040_ansiblerepository_keyring"),
    ]

    dependencies = [
        ("core", "0091_systemid"),
    ]

    operations = [
        migrations.CreateModel(
            name="CollectionRemote",
            fields=[
                (
                    "remote_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="core.remote",
                    ),
                ),
                ("whitelist", models.TextField()),
            ],
            options={
                "abstract": False,
            },
            bases=("core.remote",),
        ),
        migrations.CreateModel(
            name="Role",
            fields=[
                (
                    "content_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="core.content",
                    ),
                ),
                ("namespace", models.CharField(max_length=64)),
                ("name", models.CharField(max_length=64)),
                ("version", models.CharField(max_length=128)),
            ],
            options={
                "unique_together": {("version", "name", "namespace")},
            },
            bases=("core.content",),
        ),
        migrations.CreateModel(
            name="AnsibleDistribution",
            fields=[
                (
                    "basedistribution_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="core.basedistribution",
                    ),
                ),
                (
                    "repository",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="core.repository",
                    ),
                ),
                (
                    "repository_version",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="core.repositoryversion",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("core.basedistribution",),
        ),
        migrations.CreateModel(
            name="Collection",
            fields=[
                (
                    "_id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("_created", models.DateTimeField(auto_now_add=True)),
                ("_last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("namespace", models.CharField(editable=False, max_length=64)),
                ("name", models.CharField(editable=False, max_length=64)),
                ("deprecated", models.BooleanField(default=False)),
            ],
            options={
                "unique_together": {("namespace", "name")},
            },
        ),
        migrations.CreateModel(
            name="AnsibleRemote",
            fields=[
                (
                    "remote_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="core.remote",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("core.remote",),
        ),
        migrations.CreateModel(
            name="Tag",
            fields=[
                (
                    "pulp_id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("_created", models.DateTimeField(auto_now_add=True)),
                ("_last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("name", models.CharField(editable=False, max_length=32, unique=True)),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="collectionversion",
            fields=[
                (
                    "content_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="core.content",
                    ),
                ),
                ("version", models.CharField(editable=False, max_length=32)),
                (
                    "contents",
                    django.contrib.postgres.fields.jsonb.JSONField(default=list, editable=False),
                ),
                (
                    "collection",
                    models.ForeignKey(
                        editable=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="ansible.collection",
                    ),
                ),
                (
                    "authors",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(max_length=64),
                        default=list,
                        editable=False,
                        size=None,
                    ),
                ),
                (
                    "dependencies",
                    django.contrib.postgres.fields.jsonb.JSONField(default=dict, editable=False),
                ),
                ("description", models.TextField(blank=True, default="", editable=False)),
                (
                    "docs_blob",
                    django.contrib.postgres.fields.jsonb.JSONField(default=dict, editable=False),
                ),
                (
                    "documentation",
                    models.URLField(blank=True, default="", editable=False, max_length=128),
                ),
                (
                    "homepage",
                    models.URLField(blank=True, default="", editable=False, max_length=128),
                ),
                ("issues", models.URLField(blank=True, default="", editable=False, max_length=128)),
                (
                    "license",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(max_length=32),
                        default=list,
                        editable=False,
                        size=None,
                    ),
                ),
                ("name", models.CharField(default="", editable=False, max_length=32)),
                ("namespace", models.CharField(default="", editable=False, max_length=32)),
                (
                    "repository",
                    models.URLField(blank=True, default="", editable=False, max_length=128),
                ),
                ("tags", models.ManyToManyField(editable=False, to="ansible.tag")),
                ("search_vector", django.contrib.postgres.search.SearchVectorField(default="")),
            ],
            options={
                "unique_together": {("namespace", "name", "version")},
            },
            bases=("core.content",),
        ),
        migrations.RunSQL(
            sql="\nUPDATE ansible_collectionversion AS c\nSET search_vector = (\n    SELECT \n    setweight(to_tsvector(coalesce(namespace,'')), 'A')\n    || setweight(to_tsvector(coalesce(name, '')), 'A')\n    || (\n      SELECT\n        setweight(to_tsvector(\n          coalesce(string_agg(\"ansible_tag\".\"name\", ' '), '')\n        ), 'B')\n      FROM\n        \"ansible_tag\" INNER JOIN \"ansible_collectionversion_tags\" ON (\"ansible_tag\".\"pulp_id\" = \"ansible_collectionversion_tags\".\"tag_id\")\n    )\n    || (\n      SELECT\n        setweight(to_tsvector(\n          coalesce(string_agg(cvc ->> 'name', ' '), '')\n        ), 'C')\n      FROM jsonb_array_elements(cv.contents) AS cvc\n    )\n    || setweight(to_tsvector(coalesce(description, '')), 'D')\n\n    FROM ansible_collectionversion cv\n    WHERE c.content_ptr_id = cv.content_ptr_id\n)\n",
            reverse_sql="",
        ),
        migrations.RunSQL(
            sql="\nCREATE OR REPLACE FUNCTION update_collection_ts_vector()\n    RETURNS TRIGGER AS\n$$\nBEGIN\n    NEW.search_vector := (\n        SELECT \n    setweight(to_tsvector(coalesce(namespace,'')), 'A')\n    || setweight(to_tsvector(coalesce(name, '')), 'A')\n    || (\n      SELECT\n        setweight(to_tsvector(\n          coalesce(string_agg(\"ansible_tag\".\"name\", ' '), '')\n        ), 'B')\n      FROM\n        \"ansible_tag\" INNER JOIN \"ansible_collectionversion_tags\" ON (\"ansible_tag\".\"pulp_id\" = \"ansible_collectionversion_tags\".\"tag_id\")\n    )\n    || (\n      SELECT\n        setweight(to_tsvector(\n          coalesce(string_agg(cvc ->> 'name', ' '), '')\n        ), 'C')\n      FROM jsonb_array_elements(cv.contents) AS cvc\n    )\n    || setweight(to_tsvector(coalesce(description, '')), 'D')\n\n        FROM ansible_collectionversion cv\n        WHERE cv.content_ptr_id = NEW.content_ptr_id\n    );\n    RETURN NEW;\nEND;\n$$ LANGUAGE plpgsql;\nCREATE TRIGGER update_ts_vector\n    BEFORE UPDATE\n    ON ansible_collectionversion\n    FOR EACH ROW\nEXECUTE PROCEDURE update_collection_ts_vector();\n",
            reverse_sql="\nDROP TRIGGER IF EXISTS update_ts_vector ON ansible_collectionversion;\nDROP FUNCTION IF EXISTS update_collection_ts_vector();\n",
        ),
        migrations.AddField(
            model_name="collectionversion",
            name="is_highest",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddConstraint(
            model_name="collectionversion",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_highest", True)),
                fields=("collection", "is_highest"),
                name="unique_is_highest",
            ),
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="name",
            field=models.CharField(editable=False, max_length=64),
        ),
        migrations.RemoveField(
            model_name="collectionremote",
            name="whitelist",
        ),
        migrations.AddField(
            model_name="collectionversion",
            name="is_certified",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="collectionremote",
            name="requirements_file",
            field=models.TextField(max_length=255, null=True),
        ),
        migrations.AlterModelOptions(
            name="ansibledistribution",
            options={"default_related_name": "%(app_label)s_%(model_name)s"},
        ),
        migrations.AlterModelOptions(
            name="ansibleremote",
            options={"default_related_name": "%(app_label)s_%(model_name)s"},
        ),
        migrations.AlterModelOptions(
            name="collectionremote",
            options={"default_related_name": "%(app_label)s_%(model_name)s"},
        ),
        migrations.AlterModelOptions(
            name="collectionversion",
            options={"default_related_name": "%(app_label)s_%(model_name)s"},
        ),
        migrations.AlterModelOptions(
            name="role",
            options={"default_related_name": "%(app_label)s_%(model_name)s"},
        ),
        migrations.AlterField(
            model_name="ansibleremote",
            name="remote_ptr",
            field=models.OneToOneField(
                auto_created=True,
                on_delete=django.db.models.deletion.CASCADE,
                parent_link=True,
                primary_key=True,
                related_name="ansible_ansibleremote",
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
                related_name="ansible_role",
                serialize=False,
                to="core.content",
            ),
        ),
        migrations.CreateModel(
            name="CollectionImport",
            fields=[
                ("messages", models.JSONField(default=list, editable=False)),
                (
                    "task",
                    models.OneToOneField(
                        editable=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="+",
                        serialize=False,
                        to="core.task",
                    ),
                ),
            ],
            options={
                "abstract": False,
                "ordering": ["task__pulp_created"],
            },
        ),
        migrations.RenameField(
            model_name="collection",
            old_name="_created",
            new_name="pulp_created",
        ),
        migrations.RenameField(
            model_name="collection",
            old_name="_id",
            new_name="pulp_id",
        ),
        migrations.RenameField(
            model_name="collection",
            old_name="_last_updated",
            new_name="pulp_last_updated",
        ),
        migrations.RenameField(
            model_name="tag",
            old_name="_created",
            new_name="pulp_created",
        ),
        migrations.RenameField(
            model_name="tag",
            old_name="_last_updated",
            new_name="pulp_last_updated",
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="collection",
            field=models.ForeignKey(
                editable=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="versions",
                to="ansible.collection",
                to_field="pulp_id",
            ),
        ),
        migrations.RemoveField(
            model_name="collectionversion",
            name="is_certified",
        ),
        migrations.AlterField(
            model_name="ansibledistribution",
            name="basedistribution_ptr",
            field=models.OneToOneField(
                auto_created=True,
                on_delete=django.db.models.deletion.CASCADE,
                parent_link=True,
                primary_key=True,
                related_name="ansible_ansibledistribution",
                serialize=False,
                to="core.basedistribution",
            ),
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="documentation",
            field=models.URLField(blank=True, default="", editable=False, max_length=2000),
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="homepage",
            field=models.URLField(blank=True, default="", editable=False, max_length=2000),
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="issues",
            field=models.URLField(blank=True, default="", editable=False, max_length=2000),
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="repository",
            field=models.URLField(blank=True, default="", editable=False, max_length=2000),
        ),
        migrations.AlterField(
            model_name="ansibledistribution",
            name="repository",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ansible_ansibledistribution",
                to="core.repository",
            ),
        ),
        migrations.AddField(
            model_name="collectionremote",
            name="auth_url",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="collectionremote",
            name="token",
            field=models.TextField(max_length=2000, null=True),
        ),
        migrations.RenameModel(
            old_name="AnsibleRemote",
            new_name="RoleRemote",
        ),
        migrations.AlterField(
            model_name="roleremote",
            name="remote_ptr",
            field=models.OneToOneField(
                auto_created=True,
                on_delete=django.db.models.deletion.CASCADE,
                parent_link=True,
                primary_key=True,
                related_name="ansible_roleremote",
                serialize=False,
                to="core.remote",
            ),
        ),
        migrations.AlterField(
            model_name="ansibledistribution",
            name="repository_version",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ansible_ansibledistribution",
                to="core.repositoryversion",
            ),
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="documentation",
            field=models.CharField(blank=True, default="", editable=False, max_length=2000),
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="homepage",
            field=models.CharField(blank=True, default="", editable=False, max_length=2000),
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="issues",
            field=models.CharField(blank=True, default="", editable=False, max_length=2000),
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="repository",
            field=models.CharField(blank=True, default="", editable=False, max_length=2000),
        ),
        migrations.AlterField(
            model_name="collectionremote",
            name="requirements_file",
            field=models.TextField(null=True),
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="version",
            field=models.CharField(editable=False, max_length=128),
        ),
        migrations.CreateModel(
            name="AnsibleCollectionDeprecated",
            fields=[
                (
                    "pulp_id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("pulp_created", models.DateTimeField(auto_now_add=True)),
                ("pulp_last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "collection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="ansible.collection"
                    ),
                ),
                (
                    "repository_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="collection_memberships",
                        to="core.repositoryversion",
                    ),
                ),
            ],
            options={
                "unique_together": {("collection", "repository_version")},
            },
            bases=(django_lifecycle.mixins.LifecycleModelMixin, models.Model),
        ),
        migrations.AlterField(
            model_name="collectionremote",
            name="remote_ptr",
            field=models.OneToOneField(
                auto_created=True,
                on_delete=django.db.models.deletion.CASCADE,
                parent_link=True,
                primary_key=True,
                related_name="ansible_collectionremote",
                serialize=False,
                to="core.remote",
            ),
        ),
        migrations.RemoveField(
            model_name="collection",
            name="deprecated",
        ),
        migrations.AlterField(
            model_name="tag",
            name="name",
            field=models.CharField(editable=False, max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="namespace",
            field=models.CharField(editable=False, max_length=64),
        ),
        migrations.AddField(
            model_name="collectionversion",
            name="files",
            field=models.JSONField(default=dict, editable=False),
        ),
        migrations.AddField(
            model_name="collectionversion",
            name="manifest",
            field=models.JSONField(default=dict, editable=False),
        ),
        migrations.AddField(
            model_name="collectionversion",
            name="requires_ansible",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="content_ptr",
            field=models.OneToOneField(
                auto_created=True,
                on_delete=django.db.models.deletion.CASCADE,
                parent_link=True,
                primary_key=True,
                related_name="ansible_collectionversion",
                serialize=False,
                to="core.content",
            ),
        ),
        migrations.CreateModel(
            name="AnsibleRepository",
            fields=[
                (
                    "repository_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        related_name="ansible_ansiblerepository",
                        serialize=False,
                        to="core.repository",
                    ),
                ),
                ("last_synced_metadata_time", models.DateTimeField(null=True)),
                (
                    "keyring",
                    models.FilePathField(blank=True, path="/etc/pulp/certs/", recursive=True),
                ),
            ],
            options={
                "default_related_name": "%(app_label)s_%(model_name)s",
                "permissions": (
                    ("modify_ansible_repo_content", "Can modify ansible repository content"),
                ),
            },
            bases=("core.repository",),
        ),
        migrations.AddField(
            model_name="collectionremote",
            name="sync_dependencies",
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name="NewAnsibleDistribution",
            fields=[
                (
                    "distribution_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        related_name="ansible_ansibledistribution",
                        serialize=False,
                        to="core.distribution",
                    ),
                ),
            ],
            options={
                "default_related_name": "%(app_label)s_%(model_name)s",
            },
            bases=("core.distribution",),
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="tags",
            field=models.ManyToManyField(
                editable=False, related_name="ansible_collectionversion", to="ansible.tag"
            ),
        ),
        migrations.DeleteModel(
            name="AnsibleDistribution",
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="contents",
            field=models.JSONField(default=list, editable=False),
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="dependencies",
            field=models.JSONField(default=dict, editable=False),
        ),
        migrations.AlterField(
            model_name="collectionversion",
            name="docs_blob",
            field=models.JSONField(default=dict, editable=False),
        ),
        migrations.CreateModel(
            name="NewAnsibleCollectionDeprecated",
            fields=[
                (
                    "content_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        related_name="ansible_ansiblecollectiondeprecated",
                        serialize=False,
                        to="core.content",
                    ),
                ),
                ("namespace", models.CharField(editable=False, max_length=64)),
                ("name", models.CharField(editable=False, max_length=64)),
                ("collection_id", models.UUIDField(editable=False, null=True, serialize=False)),
                ("repository_id", models.UUIDField(editable=False, null=True, serialize=False)),
                ("version_added_id", models.UUIDField(editable=False, null=True, serialize=False)),
            ],
            options={
                "default_related_name": "%(app_label)s_%(model_name)s",
            },
            bases=("core.content",),
        ),
        migrations.RenameModel(
            old_name="NewAnsibleDistribution",
            new_name="AnsibleDistribution",
        ),
        migrations.DeleteModel(
            name="AnsibleCollectionDeprecated",
        ),
        migrations.RenameModel(
            old_name="NewAnsibleCollectionDeprecated",
            new_name="AnsibleCollectionDeprecated",
        ),
        migrations.AlterUniqueTogether(
            name="ansiblecollectiondeprecated",
            unique_together={("namespace", "name")},
        ),
        migrations.RemoveField(
            model_name="ansiblecollectiondeprecated",
            name="collection_id",
        ),
        migrations.RemoveField(
            model_name="ansiblecollectiondeprecated",
            name="repository_id",
        ),
        migrations.RemoveField(
            model_name="ansiblecollectiondeprecated",
            name="version_added_id",
        ),
        migrations.CreateModel(
            name="GitRemote",
            fields=[
                (
                    "remote_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        related_name="ansible_gitremote",
                        serialize=False,
                        to="core.remote",
                    ),
                ),
                ("metadata_only", models.BooleanField(default=False)),
                ("git_ref", models.TextField()),
            ],
            options={
                "default_related_name": "%(app_label)s_%(model_name)s",
            },
            bases=("core.remote",),
        ),
        migrations.CreateModel(
            name="CollectionVersionSignature",
            fields=[
                (
                    "content_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        related_name="ansible_collectionversionsignature",
                        serialize=False,
                        to="core.content",
                    ),
                ),
                ("data", models.BinaryField()),
                ("digest", models.CharField(max_length=64)),
                ("pubkey_fingerprint", models.CharField(max_length=64)),
                (
                    "signed_collection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="signatures",
                        to="ansible.collectionversion",
                    ),
                ),
                (
                    "signing_service",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="signatures",
                        to="core.signingservice",
                    ),
                ),
            ],
            options={
                "default_related_name": "%(app_label)s_%(model_name)s",
                "unique_together": {("pubkey_fingerprint", "signed_collection")},
            },
            bases=("core.content",),
        ),
        migrations.AddField(
            model_name="collectionremote",
            name="signed_only",
            field=models.BooleanField(default=False),
        ),
    ]
