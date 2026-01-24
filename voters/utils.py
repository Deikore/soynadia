"""
Utilidades para la app voters.
"""
import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Prospect


def validate_and_normalize_phone(phone):
    """
    Valida y normaliza un número de teléfono colombiano.
    Retorna el número normalizado (10 dígitos) o None si está vacío.
    Lanza ValidationError si el número es inválido.
    """
    if not phone or not phone.strip():
        return None

    normalized = re.sub(r'[\s\-\(\)]', '', phone.strip())
    if normalized.startswith('+57'):
        normalized = normalized[3:]
    elif normalized.startswith('57') and len(normalized) == 12:
        normalized = normalized[2:]

    if not normalized.isdigit() or len(normalized) != 10:
        raise ValidationError(
            _('Número inválido. Debe tener 10 dígitos. Ejemplos: +57 313 416 5999, 3134165999')
        )

    first_digit = normalized[0]
    if first_digit == '3':
        second_digit = normalized[1]
        if second_digit not in ['0', '1', '2', '5']:
            raise ValidationError(
                _('Número de celular inválido para Colombia. Debe empezar con 300-399, 310-319, 320-329 o 350-359.')
            )
    elif first_digit not in ['1', '2', '3', '4', '5', '6', '7', '8']:
        raise ValidationError(
            _('Número inválido para Colombia. Debe ser un celular (3XX) o fijo (1-8XX).')
        )

    return normalized


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


def check_and_trigger_on_id_change(prospect, old_identification_number):
    """
    Verifica si cambió el identification_number y resetea campos de información electoral.
    Si cambió y el prospecto tiene origen con enable_consult_polling_station=True, dispara la tarea.
    
    Args:
        prospect: Instancia del modelo Prospect (ya guardado)
        old_identification_number: Número de identificación anterior (None si es nuevo)
    
    Returns:
        bool: True si se disparó la tarea, False en caso contrario
    """
    if not prospect or not prospect.pk:
        return False
    
    # Si old_identification_number es None, es un nuevo prospecto (no hay cambio)
    if old_identification_number is None:
        return False
    
    # Refrescar el objeto desde la base de datos para asegurar que tenemos los valores actualizados
    prospect.refresh_from_db()
    
    # Comparar el identification_number actual con el anterior
    current_id = prospect.identification_number
    if current_id == old_identification_number:
        return False
    
    # El número cambió, resetear todos los campos de información electoral
    update_fields = [
        'department',
        'municipality',
        'polling_station',
        'polling_station_address',
        'table',
        'notice',
        'resolution',
        'notice_date',
        'polling_station_consulted',
    ]
    
    prospect.department = None
    prospect.municipality = None
    prospect.polling_station = None
    prospect.polling_station_address = None
    prospect.table = None
    prospect.notice = None
    prospect.resolution = None
    prospect.notice_date = None
    prospect.polling_station_consulted = False
    
    # Guardar el prospecto con los campos reseteados
    prospect.save(update_fields=update_fields)
    
    # Verificar si se debe ejecutar la tarea de Celery
    # Recargar el prospecto con las relaciones ManyToMany para asegurar que estén disponibles
    prospect = Prospect.objects.prefetch_related('origins').get(pk=prospect.pk)
    
    if should_trigger_celery_task(prospect):
        from .tasks import process_prospect
        process_prospect.delay(prospect.id)
        return True
    
    return False


def trigger_polling_station_consult(prospect):
    """
    Verifica si debe disparar la consulta de lugar de votación para un prospecto.
    Solo dispara si tiene origen habilitado y aún no se ha consultado.
    NO resetea campos de información electoral (solo se resetean cuando cambia el ID).
    
    Args:
        prospect: Instancia del modelo Prospect (ya guardado)
    
    Returns:
        bool: True si se disparó la tarea, False en caso contrario
    """
    if not prospect or not prospect.pk:
        return False
    
    # Recargar el prospecto con las relaciones ManyToMany para asegurar que estén disponibles
    prospect = Prospect.objects.prefetch_related('origins').get(pk=prospect.pk)
    
    # Verificar si tiene origen habilitado
    if not should_trigger_celery_task(prospect):
        return False
    
    # Verificar si ya se ha consultado
    if prospect.polling_station_consulted:
        return False
    
    # Disparar la tarea
    from .tasks import process_prospect
    process_prospect.delay(prospect.id)
    return True
