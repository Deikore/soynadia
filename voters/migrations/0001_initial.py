# Generated migration

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Prospect',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identification_number', models.CharField(db_index=True, help_text='Número de identificación único del prospecto', max_length=20, unique=True, verbose_name='número de identificación')),
                ('first_name', models.CharField(max_length=100, verbose_name='nombre')),
                ('last_name', models.CharField(max_length=100, verbose_name='apellido')),
                ('phone_number', models.CharField(max_length=20, verbose_name='teléfono')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='fecha de creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='fecha de actualización')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='prospects_created', to=settings.AUTH_USER_MODEL, verbose_name='creado por')),
            ],
            options={
                'verbose_name': 'prospecto',
                'verbose_name_plural': 'prospectos',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ApiKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(db_index=True, max_length=64, unique=True, verbose_name='key')),
                ('name', models.CharField(help_text='Nombre descriptivo para esta API key', max_length=100, verbose_name='nombre')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='fecha de creación')),
                ('is_active', models.BooleanField(default=True, verbose_name='activa')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='api_keys', to=settings.AUTH_USER_MODEL, verbose_name='usuario')),
            ],
            options={
                'verbose_name': 'API Key',
                'verbose_name_plural': 'API Keys',
                'ordering': ['-created_at'],
            },
        ),
    ]
