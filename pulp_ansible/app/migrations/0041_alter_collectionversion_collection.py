# Generated by Django 3.2.12 on 2022-04-01 13:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ansible', '0040_ansiblerepository_keyring'),
    ]

    operations = [
        migrations.AlterField(
            model_name='collectionversion',
            name='collection',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name='versions', to='ansible.collection'),
        ),
    ]
