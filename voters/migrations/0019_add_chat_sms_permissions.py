# Generated migration

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('voters', '0018_whatsappmessage_direction_account'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='prospect',
            options={
                'ordering': ['-created_at'],
                'permissions': [
                    ('can_delete_prospects', 'Can delete prospects'),
                    ('can_edit_prospects', 'Can edit prospects'),
                    ('can_view_chat', 'Can view chat'),
                    ('can_view_sms', 'Can view SMS'),
                ],
                'verbose_name': 'prospecto',
                'verbose_name_plural': 'prospectos',
            },
        ),
    ]
