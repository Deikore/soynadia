"""
Tareas asíncronas de Celery para la app voters.
"""
from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from .models import Prospect


@shared_task
def process_prospect(prospect_id):
    """
    Tarea asíncrona que procesa un prospecto.
    
    Args:
        prospect_id: ID del prospecto a procesar
    
    Returns:
        str: Mensaje de confirmación o error
    """
    try:
        prospect = Prospect.objects.get(pk=prospect_id)
        print(f"Procesando prospecto: {prospect.identification_number} - {prospect.first_name} {prospect.last_name}")
        return f"Prospecto procesado: {prospect.identification_number} - {prospect.get_full_name()}"
    except ObjectDoesNotExist:
        error_msg = f"Prospecto con ID {prospect_id} no encontrado"
        print(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"Error al procesar prospecto {prospect_id}: {str(e)}"
        print(error_msg)
        return error_msg
