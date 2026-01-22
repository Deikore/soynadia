#!/bin/bash

set -e

echo "Waiting for PostgreSQL to be ready..."
while ! nc -z $DB_HOST $DB_PORT; do
    sleep 0.5
done
echo "PostgreSQL is ready!"

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "Creating superuser if it doesn't exist..."
python manage.py shell << END
from django.contrib.auth import get_user_model
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
END

echo "Starting application with Supervisor..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
