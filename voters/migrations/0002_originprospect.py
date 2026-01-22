# Generated migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voters', '0001_initial'),
    ]

    operations = [
        # Crear modelo OriginProspect
        migrations.CreateModel(
            name='OriginProspect',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Nombre del origen del prospecto', max_length=100, unique=True, verbose_name='nombre')),
                ('description', models.TextField(blank=True, help_text='Descripción opcional del origen', verbose_name='descripción')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='fecha de creación')),
                ('is_active', models.BooleanField(default=True, verbose_name='activo')),
            ],
            options={
                'verbose_name': 'origen de prospecto',
                'verbose_name_plural': 'orígenes de prospectos',
                'ordering': ['name'],
            },
        ),
        # Hacer phone_number opcional
        migrations.AlterField(
            model_name='prospect',
            name='phone_number',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='teléfono'),
        ),
        # Agregar relación ManyToMany
        migrations.AddField(
            model_name='prospect',
            name='origins',
            field=models.ManyToManyField(blank=True, help_text='Orígenes del prospecto', related_name='prospects', to='voters.originprospect', verbose_name='orígenes'),
        ),
    ]
