#!/bin/bash

set -e

echo "Waiting for PostgreSQL to be ready..."
while ! nc -z $DB_HOST $DB_PORT; do
    sleep 0.5
done
echo "PostgreSQL is ready!"

echo "Running migrations..."
python manage.py migrate --noinput

echo "Compiling Tailwind CSS..."
if [ -f /app/static/css/input.css ] && [ -f /usr/local/bin/tailwindcss ]; then
    tailwindcss -i /app/static/css/input.css -o /app/static/css/output.css --minify || echo "Warning: Tailwind compilation failed, using CDN fallback"
fi

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "Creating superuser if it doesn't exist..."
python manage.py shell << END
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from voters.models import OriginProspect
import os

User = get_user_model()
admin_email = os.environ.get('ADMIN_EMAIL', 'admin@soynadia.com')
admin_password = os.environ.get('ADMIN_PASSWORD', 'changeme123456')
admin_first_name = os.environ.get('ADMIN_FIRST_NAME', 'Admin')
admin_last_name = os.environ.get('ADMIN_LAST_NAME', 'User')

if not User.objects.filter(email=admin_email).exists():
    User.objects.create_superuser(
        email=admin_email,
        password=admin_password,
        first_name=admin_first_name,
        last_name=admin_last_name
    )
    print(f'Superuser created: {admin_email}')
else:
    print(f'Superuser already exists: {admin_email}')

# Crear origen "manual" por defecto
OriginProspect.objects.get_or_create(
    name='manual',
    defaults={
        'description': 'Prospecto creado manualmente',
        'is_active': True
    }
)
print('Origin "manual" created or already exists')

# Crear grupo "Puede Eliminar Prospectos" y asignar permiso
group, created = Group.objects.get_or_create(name='Puede Eliminar Prospectos')
if created:
    # Obtener el permiso personalizado
    permission = Permission.objects.get(codename='can_delete_prospects', content_type__app_label='voters')
    group.permissions.add(permission)
    print('Group "Puede Eliminar Prospectos" created with permission')
else:
    print('Group "Puede Eliminar Prospectos" already exists')

# Crear grupo "Puede Editar Prospectos" y asignar permiso
group, created = Group.objects.get_or_create(name='Puede Editar Prospectos')
if created:
    # Obtener el permiso personalizado
    permission = Permission.objects.get(codename='can_edit_prospects', content_type__app_label='voters')
    group.permissions.add(permission)
    print('Group "Puede Editar Prospectos" created with permission')
else:
    print('Group "Puede Editar Prospectos" already exists')

# Crear grupo "Puede Ver Chat" y asignar permiso
group, created = Group.objects.get_or_create(name='Puede Ver Chat')
if created:
    permission = Permission.objects.get(codename='can_view_chat', content_type__app_label='voters')
    group.permissions.add(permission)
    print('Group "Puede Ver Chat" created with permission')
else:
    print('Group "Puede Ver Chat" already exists')

# Crear grupo "Puede Ver SMS" y asignar permiso
group, created = Group.objects.get_or_create(name='Puede Ver SMS')
if created:
    permission = Permission.objects.get(codename='can_view_sms', content_type__app_label='voters')
    group.permissions.add(permission)
    print('Group "Puede Ver SMS" created with permission')
else:
    print('Group "Puede Ver SMS" already exists')
END

echo "Starting application with Supervisor..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
