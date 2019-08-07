from django.db import migrations
from django.db import models
from django.db.models import UniqueConstraint, Q
import semantic_version as semver


def migrate_collection_versions(apps, schema_editor):
    Collection = apps.get_model("ansible", "Collection")
    collections = Collection.objects.only('pk').all()
    for collection in collections:
        versions = collection.versions.only('pk', 'version').all()
        highest = max(versions, key=lambda x: semver.Version(x.version))
        highest.is_highest = True
        highest.save()


class Migration(migrations.Migration):
    dependencies = [
        ('ansible', '0004_add_fulltext_search_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='collectionversion',
            name='is_highest',
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddConstraint(
            model_name='collectionversion',
            constraint=UniqueConstraint(
                fields=('collection', 'is_highest'),
                name='unique_is_highest',
                condition=Q(is_highest=True)
            ),
        ),
        migrations.RunPython(code=migrate_collection_versions,
                             reverse_code=migrations.RunPython.noop)
    ]
