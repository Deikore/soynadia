# Generated migration

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('voters', '0002_originprospect'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='prospect',
            options={
                'ordering': ['-created_at'],
                'permissions': [('can_delete_prospects', 'Can delete prospects')],
                'verbose_name': 'prospecto',
                'verbose_name_plural': 'prospectos',
            },
        ),
    ]
