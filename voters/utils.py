"""
Utilidades para la app voters.
"""
import re
import logging
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .models import Prospect, WhatsAppAccount, OriginProspect

logger = logging.getLogger(__name__)


def normalize_digits_only(value):
    """
    Elimina todos los caracteres no numéricos de una cadena.
    
    Args:
        value: Cadena que puede contener caracteres no numéricos
    
    Returns:
        str: Cadena con solo dígitos, o cadena vacía si value es None o vacío
    """
    if not value:
        return ''
    return re.sub(r'\D', '', str(value))


def validate_and_normalize_phone(phone):
    """
    Valida y normaliza un número de teléfono colombiano.
    Retorna el número normalizado (10 dígitos) o None si está vacío.
    Lanza ValidationError si el número es inválido.
    """
    if not phone or not phone.strip():
        return None

    # Eliminar todos los caracteres no numéricos
    normalized = normalize_digits_only(phone)
    
    # Quitar prefijo 57 si existe (después de eliminar caracteres no numéricos, +57 se convierte en 57)
    if normalized.startswith('57') and len(normalized) == 12:
        normalized = normalized[2:]

    if not normalized.isdigit() or len(normalized) != 10:
        raise ValidationError(
            _('Número inválido. Debe tener 10 dígitos. Ejemplos: +57 313 400 0000, 3134000000')
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


def get_sms_filter_options():
    """
    Devuelve opciones para los filtros de la campaña SMS y lista de prospectos:
    departamentos, municipios, orígenes, sexo y enlace (valores distintos no vacíos).
    """
    departments = list(
        Prospect.objects.exclude(department__in=[None, ''])
        .values_list('department', flat=True)
        .distinct()
        .order_by('department')
    )
    municipalities = list(
        Prospect.objects.exclude(municipality__in=[None, ''])
        .values_list('municipality', flat=True)
        .distinct()
        .order_by('municipality')
    )
    origins = list(
        OriginProspect.objects.filter(is_active=True).order_by('name').values_list('id', 'name')
    )
    sexos = list(
        Prospect.objects.exclude(sexo__in=[None, ''])
        .values_list('sexo', flat=True)
        .distinct()
        .order_by('sexo')
    )
    enlaces = list(
        Prospect.objects.exclude(enlace__in=[None, ''])
        .values_list('enlace', flat=True)
        .distinct()
        .order_by('enlace')
    )
    department_choices = [(d, d) for d in departments if d and str(d).strip() and str(d) != 'None']
    municipality_choices = [(m, m) for m in municipalities if m and str(m).strip() and str(m) != 'None']
    origin_choices = [(str(oid), name) for oid, name in origins]
    sexo_choices = [(s, s) for s in sexos if s and str(s).strip() and str(s) != 'None']
    enlace_choices = [(e, e) for e in enlaces if e and str(e).strip() and str(e) != 'None']
    return department_choices, municipality_choices, origin_choices, sexo_choices, enlace_choices


def get_sms_prospects_queryset(
    department_values=None,
    municipality_values=None,
    origin_ids=None,
    identification_numbers=None,
    sexo_values=None,
    enlace_values=None,
):
    """
    Queryset de prospectos con teléfono no vacío y filtros opcionales por
    departamento, municipio, origen, número de cédula, sexo y enlace.
    """
    qs = Prospect.objects.exclude(phone_number__in=[None, '']).exclude(phone_number='')
    if department_values:
        qs = qs.filter(department__in=department_values)
    if municipality_values:
        qs = qs.filter(municipality__in=municipality_values)
    if origin_ids:
        qs = qs.filter(origins__id__in=origin_ids).distinct()
    if identification_numbers:
        qs = qs.filter(identification_number__in=identification_numbers)
    if sexo_values:
        qs = qs.filter(sexo__in=sexo_values)
    if enlace_values:
        qs = qs.filter(enlace__in=enlace_values)
    return qs.order_by('full_name')


def get_prospect_list_queryset(
    department_values=None,
    municipality_values=None,
    origin_ids=None,
    identification_numbers=None,
    full_name_values=None,
    sexo_values=None,
    enlace_values=None,
):
    """
    Queryset de prospectos para la lista y exportación, con filtros opcionales.
    No restringe por teléfono (a diferencia de get_sms_prospects_queryset).
    identification_numbers: lista de cédulas (coincidencia exacta).
    full_name_values: lista de strings; filtro OR por full_name__icontains.
    """
    qs = Prospect.objects.all()
    if department_values:
        qs = qs.filter(department__in=department_values)
    if municipality_values:
        qs = qs.filter(municipality__in=municipality_values)
    if origin_ids:
        qs = qs.filter(origins__id__in=origin_ids).distinct()
    if identification_numbers:
        normalized = [v.strip() for v in identification_numbers if v and str(v).strip()]
        if normalized:
            qs = qs.filter(identification_number__in=normalized)
    if full_name_values:
        stripped = [v.strip() for v in full_name_values if v and str(v).strip()]
        if stripped:
            q = Q()
            for v in stripped:
                q |= Q(full_name__icontains=v)
            qs = qs.filter(q)
    if sexo_values:
        qs = qs.filter(sexo__in=sexo_values)
    if enlace_values:
        qs = qs.filter(enlace__in=enlace_values)
    return qs.order_by('-created_at')


def get_prospects_with_valid_phone(queryset):
    """
    De un queryset de prospectos, devuelve lista de (prospect, phone_normalized)
    solo para aquellos cuyo phone_number pasa validate_and_normalize_phone.
    """
    result = []
    for prospect in queryset:
        if not prospect.phone_number:
            continue
        try:
            normalized = validate_and_normalize_phone(prospect.phone_number)
            if normalized:
                result.append((prospect, normalized))
        except ValidationError:
            continue
    return result


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


def check_and_trigger_on_id_change(prospect, old_identification_number, trigger_task=True):
    """
    Verifica si cambió el identification_number y resetea campos de información electoral.
    Si cambió y el prospecto tiene origen con enable_consult_polling_station=True, dispara la tarea
    (o retorna el ID si trigger_task=False).
    
    Args:
        prospect: Instancia del modelo Prospect (ya guardado)
        old_identification_number: Número de identificación anterior (None si es nuevo)
        trigger_task: Si True, dispara la tarea de Celery. Si False, retorna prospect.id para disparar después.
    
    Returns:
        bool | int: True si se disparó la tarea, prospect.id si trigger_task=False y debe dispararse, False en caso contrario
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
    # Si ambos son None o ambos son iguales, no hay cambio
    if current_id == old_identification_number:
        return False
    
    # Si alguno es None, no resetear (solo resetear cuando ambos tienen valor y son diferentes)
    if not current_id or not old_identification_number:
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
        if trigger_task:
            from .tasks import process_prospect
            process_prospect.delay(prospect.id)
            return True
        return prospect.id
    
    return False


def trigger_polling_station_consult(prospect, trigger_task=True):
    """
    Verifica si debe disparar la consulta de lugar de votación para un prospecto.
    Solo dispara si tiene origen habilitado, aún no se ha consultado y tiene identification_number.
    NO resetea campos de información electoral (solo se resetean cuando cambia el ID).
    
    Args:
        prospect: Instancia del modelo Prospect (ya guardado)
        trigger_task: Si True, dispara la tarea de Celery. Si False, retorna prospect.id para disparar después.
    
    Returns:
        bool | int: True si se disparó la tarea, prospect.id si trigger_task=False y debe dispararse, False en caso contrario
    """
    if not prospect or not prospect.pk:
        return False
    
    # Verificar si tiene número de identificación
    if not prospect.identification_number:
        return False
    
    # Recargar el prospecto con las relaciones ManyToMany para asegurar que estén disponibles
    prospect = Prospect.objects.prefetch_related('origins').get(pk=prospect.pk)
    
    # Verificar si tiene origen habilitado
    if not should_trigger_celery_task(prospect):
        return False
    
    # Verificar si ya se ha consultado
    if prospect.polling_station_consulted:
        return False
    
    if trigger_task:
        from .tasks import process_prospect
        process_prospect.delay(prospect.id)
        return True
    return prospect.id


def associate_whatsapp_account(prospect):
    """
    Busca y asocia un WhatsAppAccount con un Prospect si hay match por número de teléfono.
    Solo asocia si el WhatsAppAccount no tiene prospect asociado.
    
    Args:
        prospect: Instancia del modelo Prospect (debe estar guardado en BD)
    
    Returns:
        WhatsAppAccount o None: La cuenta asociada, o None si no se encontró o ya tenía prospect
    """
    if not prospect or not prospect.pk:
        return None
    
    if not prospect.phone_number:
        return None
    
    try:
        # Buscar WhatsAppAccount por número exacto
        account = WhatsAppAccount.objects.filter(
            phone_number=prospect.phone_number
        ).first()
        
        if account and not account.prospect:
            # Asociar el prospect si la cuenta no tiene uno
            account.prospect = prospect
            account.save(update_fields=['prospect'])
            return account
    except Exception as e:
        logger.error("Error al asociar WhatsAppAccount con Prospect %s: %s", prospect.pk, e, exc_info=True)
    
    return None
