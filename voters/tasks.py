"""
Tareas asíncronas de Celery para la app voters.
"""
import os
from pathlib import Path
import environ
from celery import shared_task
from celery.utils.log import get_task_logger
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from .models import Prospect
from services.voting_place_query import VotingPlaceQuery

logger = get_task_logger(__name__)

# Configurar django-environ para leer variables del archivo .env (fallback)
# En Docker, las variables se pasan directamente como variables de entorno
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()
try:
    environ.Env.read_env(os.path.join(BASE_DIR, '.env'))
except Exception:
    pass  # Si no existe el archivo .env, usar solo variables de entorno


@shared_task
def process_prospect(prospect_id):
    """
    Tarea asíncrona que procesa un prospecto y consulta el lugar de votación.
    
    Args:
        prospect_id: ID del prospecto a procesar
    
    Returns:
        str: Mensaje de confirmación o error
    """
    try:
        prospect = Prospect.objects.get(pk=prospect_id)
        logger.info(f"Procesando prospecto: {prospect.identification_number} - {prospect.first_name} {prospect.last_name}")
        
        # Obtener API key de 2Captcha desde variables de entorno
        # Configurar en el archivo .env: TWOCAPTCHA_API_KEY=tu-api-key-aqui
        # Obtener la API key en: https://2captcha.com/
        # Intentar leer desde variables de entorno primero (Docker), luego desde .env
        api_key = os.getenv('TWOCAPTCHA_API_KEY') or env('TWOCAPTCHA_API_KEY', default=None)
        
        if not api_key:
            error_msg = (
                "API key de 2Captcha no configurada. "
                "Configure TWOCAPTCHA_API_KEY en el archivo .env o en las variables de entorno. "
                "Obtenga su API key en: https://2captcha.com/"
            )
            logger.error(error_msg)
            return error_msg
        
        query_service = VotingPlaceQuery(api_key, logger=logger)
        resultado = query_service.query(prospect.identification_number)
        
        if not resultado:
            error_msg = "No se pudo obtener información del lugar de votación"
            logger.error(error_msg)
            # Guardar como novedad
            prospect.notice = error_msg
            prospect.polling_station_consulted = True
            prospect.save(update_fields=['notice', 'polling_station_consulted'])
            return error_msg
        
        if not resultado.get('exito', False):
            error_msg = resultado.get('error', 'Error desconocido al consultar lugar de votación')
            logger.error(f"Error en consulta: {error_msg}")
            
            # Guardar el error como novedad
            update_fields = ['polling_station_consulted', 'notice']
            
            # Si el error es "No se pudo extraer información de la respuesta",
            # guardar mensaje específico
            if error_msg == 'No se pudo extraer información de la respuesta':
                notice_msg = f"El documento de identidad número {prospect.identification_number} no se encuentra en el censo para esta elección."
            else:
                # Cualquier otro error se guarda como novedad con el mensaje de error
                notice_msg = f"Error al consultar lugar de votación: {error_msg}"
            
            prospect.notice = notice_msg
            logger.info(f"Guardando novedad: {notice_msg}")
            
            prospect.polling_station_consulted = True
            prospect.save(update_fields=update_fields)
            return f"Error al consultar lugar de votación: {error_msg}"
        
        datos = resultado.get('datos', {})
        tipo = resultado.get('tipo')
        
        update_fields = ['polling_station_consulted']
        
        if tipo == 'lugar_votacion':
            if 'departamento' in datos:
                prospect.department = datos['departamento']
                update_fields.append('department')
            if 'municipio' in datos:
                prospect.municipality = datos['municipio']
                update_fields.append('municipality')
            if 'puesto' in datos:
                prospect.polling_station = datos['puesto']
                update_fields.append('polling_station')
            if 'direccion' in datos:
                prospect.polling_station_address = datos['direccion']
                update_fields.append('polling_station_address')
            if 'mesa' in datos:
                prospect.table = datos['mesa']
                update_fields.append('table')
            
            logger.info(f"✓ Información de lugar de votación actualizada para {prospect.identification_number}")
        
        elif tipo == 'novedad':
            if 'novedad' in datos:
                prospect.notice = datos['novedad']
                update_fields.append('notice')
            if 'resolucion' in datos:
                prospect.resolution = datos['resolucion']
                update_fields.append('resolution')
            if 'fecha_novedad' in datos:
                prospect.notice_date = datos['fecha_novedad']
                update_fields.append('notice_date')
            
            logger.warning(f"⚠ Novedad detectada para {prospect.identification_number}")
        
        prospect.polling_station_consulted = True
        prospect.save(update_fields=update_fields)
        
        success_msg = f"Prospecto procesado exitosamente: {prospect.identification_number} - {prospect.get_full_name()}"
        logger.info(success_msg)
        return success_msg
        
    except ObjectDoesNotExist:
        error_msg = f"Prospecto con ID {prospect_id} no encontrado"
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"Error al procesar prospecto {prospect_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg
