"""
Utilidades para la app voters.
"""
from .models import Prospect


def should_trigger_celery_task(prospect):
    """
    Verifica si se debe ejecutar la tarea de Celery para un prospecto.
    
    La tarea se ejecuta si alguno de los orígenes del prospecto tiene
    enable_consult_polling_station=True.
    
    Args:
        prospect: Instancia del modelo Prospect
    
    Returns:
        bool: True si se debe ejecutar la tarea, False en caso contrario
    """
    if not prospect or not prospect.pk:
        return False
    
    # Verificar si alguno de los orígenes tiene enable_consult_polling_station=True
    return prospect.origins.filter(enable_consult_polling_station=True).exists()
