# Generated by Django 3.2.14 on 2022-07-15 22:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ansible', '0042_ansiblerepository_gpgkey'),
    ]

    operations = [
        migrations.AddField(
            model_name='collectionversion',
            name='sha256',
            field=models.CharField(default='', max_length=64),
            preserve_default=False,
        ),
    ]
