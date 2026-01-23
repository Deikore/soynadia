# Importar Celery app para que se inicialice con Django
from .celery import app as celery_app

__all__ = ('celery_app',)
