"""
Configuración de Celery para el proyecto soynadia.
"""
import os
from celery import Celery

# Establecer el módulo de configuración de Django por defecto
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'soynadia.settings')

app = Celery('soynadia')

# Cargar configuración desde variables de entorno o usar valores por defecto
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descubrir tareas en todas las apps instaladas
app.autodiscover_tasks()

# Configuración de timezone
app.conf.timezone = 'America/Bogota'
app.conf.enable_utc = True
