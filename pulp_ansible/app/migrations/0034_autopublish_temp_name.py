# Generated by Django 2.2.19 on 2021-04-06 21:51

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0062_add_new_distribution_mastermodel'),
        ('ansible', '0033_move_to_new_distribution_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnsiblePublication',
            fields=[
                ('publication_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, related_name='ansible_ansiblepublication', serialize=False, to='core.Publication')),
            ],
            options={
                'default_related_name': '%(app_label)s_%(model_name)s',
            },
            bases=('core.publication',),
        ),
        migrations.AddField(
            model_name='ansiblerepository',
            name='autopublish',
            field=models.BooleanField(default=False),
        ),
    ]
