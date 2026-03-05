"""
Tareas asíncronas de Celery para la app voters.
"""
import csv
import io
import os
from pathlib import Path
import environ
from celery import shared_task, group, chord
from celery.utils.log import get_task_logger
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from .models import Prospect, OriginProspect, BulkUploadJob
from .utils import (
    normalize_digits_only,
    validate_and_normalize_phone,
    associate_whatsapp_account,
    check_and_trigger_on_id_change,
    should_trigger_celery_task,
    trigger_polling_station_consult,
)
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
        
        # Verificar si tiene número de identificación
        if not prospect.identification_number:
            logger.info(f"Prospecto {prospect.id} sin número de identificación, omitiendo consulta de lugar de votación")
            return "Prospecto sin número de identificación, no se puede consultar lugar de votación"
        
        logger.info(f"Procesando prospecto: {prospect.identification_number} - {prospect.full_name}")
        
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
            update_fields = ['polling_station_consulted', 'notice']
            # Mensaje amigable según tipo de error (API Infovotantes)
            if '404' in str(error_msg) or 'Not Found' in str(error_msg):
                notice_msg = f"El documento de identidad número {prospect.identification_number} no se encuentra en el censo electoral para esta elección."
            elif error_msg == 'No se pudo extraer información de la respuesta':
                notice_msg = f"El documento de identidad número {prospect.identification_number} no se encuentra en el censo para esta elección."
            elif 'censo' in error_msg.lower():
                notice_msg = error_msg
            else:
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


@shared_task
def enqueue_process_prospect_pending():
    """
    Obtiene todos los prospectos con número de identificación y sin consulta de puesto,
    y encola process_prospect para cada uno. Pensada para ser invocada desde el admin
    cuando hay muchos registros pendientes.
    """
    pending = Prospect.objects.filter(
        identification_number__isnull=False
    ).exclude(
        identification_number=''
    ).filter(
        polling_station_consulted=False
    )
    enqueued = 0
    for prospect in pending:
        process_prospect.delay(prospect.id)
        enqueued += 1
    logger.info(f"Encolados {enqueued} prospectos pendientes para process_prospect.")
    return enqueued


@shared_task
def process_bulk_upload(job_id):
    """
    Procesa un archivo CSV de carga masiva de prospectos en segundo plano.
    Lee el archivo del BulkUploadJob, crea/actualiza prospectos y guarda el
    resultado en result_json.
    """
    try:
        job = BulkUploadJob.objects.get(pk=job_id)
    except BulkUploadJob.DoesNotExist:
        logger.error("BulkUploadJob %s no encontrado", job_id)
        return

    job.status = BulkUploadJob.STATUS_PROCESSING
    job.save(update_fields=['status'])

    try:
        with job.file.open('rb') as f:
            content = f.read()
        try:
            content_str = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                content_str = content.decode('utf-8')
            except UnicodeDecodeError:
                content_str = content.decode('latin-1')

        lines = content_str.split('\n')[:3]
        semicolon_count = sum(line.count(';') for line in lines if line.strip())
        comma_count = sum(line.count(',') for line in lines if line.strip())
        delimiter = ';' if semicolon_count >= comma_count else ','

        csv_reader = csv.DictReader(io.StringIO(content_str), delimiter=delimiter)
        required_headers = ['full_name', 'phone_number', 'origin']
        if not csv_reader.fieldnames or not all(h in csv_reader.fieldnames for h in required_headers):
            job.status = BulkUploadJob.STATUS_FAILED
            job.error_message = _(
                'El archivo CSV debe contener los encabezados: full_name, phone_number, origin.'
            )
            job.save(update_fields=['status', 'error_message'])
            return

        results = {'total': 0, 'created': 0, 'updated': 0, 'errors': []}
        prospect_ids_to_process = []

        with transaction.atomic():
            for row_num, row in enumerate(csv_reader, start=2):
                results['total'] += 1
                row_errors = []
                identification_number_raw = (row.get('identification_number') or '').strip()
                full_name = (row.get('full_name') or '').strip()
                phone_number = (row.get('phone_number') or '').strip()
                origin_raw = (row.get('origin') or '').strip()
                sexo_val = (row.get('sexo') or '').strip() or None
                enlace_val = (row.get('enlace') or '').strip() or None

                # Múltiples orígenes separados por coma o punto y coma
                origin_names = [
                    p.strip() for p in origin_raw.replace(';', ',').split(',')
                    if p.strip()
                ]

                identification_number = None
                if identification_number_raw:
                    identification_number_normalized = normalize_digits_only(identification_number_raw)
                    identification_number = identification_number_normalized or None
                if not full_name:
                    row_errors.append(_('full_name es obligatorio'))
                if not origin_names:
                    row_errors.append(_('origin es obligatorio'))
                if row_errors:
                    results['errors'].append({
                        'row': row_num,
                        'identification_number': identification_number or '-',
                        'errors': row_errors,
                    })
                    continue

                normalized_phone = None
                if phone_number:
                    try:
                        normalized_phone = validate_and_normalize_phone(phone_number)
                    except ValidationError as e:
                        results['errors'].append({
                            'row': row_num,
                            'identification_number': identification_number or '-',
                            'errors': [str(e)],
                        })
                        continue

                try:
                    origins_list = []
                    for name in origin_names:
                        origin, _ = OriginProspect.objects.get_or_create(
                            name=name,
                            defaults={
                                'description': 'Origen creado desde carga masiva',
                                'is_active': True,
                            },
                        )
                        origins_list.append(origin)

                    prospect = None
                    old_id = None
                    if identification_number:
                        try:
                            prospect = Prospect.objects.get(identification_number=identification_number)
                            old_id = prospect.identification_number
                        except Prospect.DoesNotExist:
                            pass
                    elif normalized_phone:
                        prospect = Prospect.objects.filter(
                            phone_number=normalized_phone,
                            identification_number__isnull=True,
                        ).first()
                        if prospect:
                            old_id = prospect.identification_number

                    if prospect:
                        prospect.full_name = full_name
                        if normalized_phone is not None:
                            prospect.phone_number = normalized_phone
                        if identification_number:
                            prospect.identification_number = identification_number
                        prospect.sexo = sexo_val
                        prospect.enlace = enlace_val
                        prospect.save()
                        prospect.origins.set(origins_list)
                        associate_whatsapp_account(prospect)
                        result = check_and_trigger_on_id_change(prospect, old_id, trigger_task=False)
                        if result:
                            prospect_ids_to_process.append(
                                result if isinstance(result, int) else prospect.id
                            )
                        else:
                            result2 = trigger_polling_station_consult(prospect, trigger_task=False)
                            if result2:
                                prospect_ids_to_process.append(
                                    result2 if isinstance(result2, int) else prospect.id
                                )
                        results['updated'] += 1
                    else:
                        prospect = Prospect.objects.create(
                            identification_number=identification_number,
                            full_name=full_name,
                            phone_number=normalized_phone,
                            sexo=sexo_val,
                            enlace=enlace_val,
                            created_by=job.user,
                        )
                        prospect.origins.set(origins_list)
                        associate_whatsapp_account(prospect)
                        if should_trigger_celery_task(prospect):
                            prospect_ids_to_process.append(prospect.id)
                        results['created'] += 1
                except Exception as e:
                    results['errors'].append({
                        'row': row_num,
                        'identification_number': identification_number or '-',
                        'errors': [str(e)],
                    })

        for pid in prospect_ids_to_process:
            process_prospect.delay(pid)

        job.result_json = results
        job.status = BulkUploadJob.STATUS_COMPLETED
        job.error_message = ''
        job.save(update_fields=['result_json', 'status', 'error_message'])
        logger.info(
            "BulkUploadJob %s completado: created=%s, updated=%s, errors=%s",
            job_id, results['created'], results['updated'], len(results['errors']),
        )
    except Exception as e:
        logger.exception("BulkUploadJob %s falló: %s", job_id, e)
        job.status = BulkUploadJob.STATUS_FAILED
        job.error_message = str(e)
        job.save(update_fields=['status', 'error_message'])


@shared_task
def send_single_sms(provider_id, prospect_id, phone_normalized, body):
    """
    Tarea asíncrona que envía un solo SMS a un destinatario.

    Args:
        provider_id: Identificador del proveedor (ej. 'onurix', 'twilio').
        prospect_id: ID del prospecto destinatario.
        phone_normalized: Número de teléfono normalizado.
        body: Texto del mensaje SMS.

    Returns:
        dict: {'ok': bool, 'error': str or None}
    """
    from .sms_providers import get_provider
    from .models import ProspectCommunication

    provider = get_provider(provider_id)
    if not provider:
        logger.error("[SMS] Proveedor no encontrado: %s", provider_id)
        return {'ok': False, 'error': f'Proveedor no encontrado: {provider_id}'}

    success, result = provider.send_sms(phone_normalized, body)

    try:
        prospect = Prospect.objects.get(pk=prospect_id)
        ProspectCommunication.objects.create(
            prospect=prospect,
            channel=ProspectCommunication.CHANNEL_SMS,
            content=body,
            provider_id=provider_id,
        )
    except ObjectDoesNotExist:
        logger.warning("[SMS] Prospecto %s no encontrado al registrar comunicación", prospect_id)

    if success:
        logger.info("[SMS] Enviado a prospect_id=%s", prospect_id)
        return {'ok': True, 'error': None}
    logger.warning("[SMS] Fallo envío a prospect_id=%s: %s", prospect_id, result)
    return {'ok': False, 'error': result}


# Tamaño de cada chunk en campañas SMS masivas (configurable por SMS_CAMPAIGN_CHUNK_SIZE).
SMS_CAMPAIGN_CHUNK_SIZE = getattr(settings, 'SMS_CAMPAIGN_CHUNK_SIZE', 500)
# Límite de mensajes de error devueltos en el resultado (evitar payloads enormes).
SMS_CAMPAIGN_ERRORS_LIMIT = getattr(settings, 'SMS_CAMPAIGN_ERRORS_LIMIT', 100)


@shared_task
def send_sms_campaign_chunk(provider_id, body, chunk_data):
    """
    Envía SMS a un lote de prospectos (chunk). Usado por send_sms_campaign en paralelo.

    Args:
        provider_id: Identificador del proveedor (ej. 'onurix').
        body: Texto del mensaje SMS.
        chunk_data: Lista de [prospect_id, phone] para este chunk.

    Returns:
        dict: {'sent': N, 'failed': M, 'errors': [...]}
    """
    from .sms_providers import get_provider
    from .models import ProspectCommunication

    provider = get_provider(provider_id)
    if not provider:
        logger.error("[SMS] Proveedor no encontrado: %s", provider_id)
        return {'sent': 0, 'failed': len(chunk_data), 'errors': [f'Proveedor no encontrado: {provider_id}']}

    if not chunk_data:
        return {'sent': 0, 'failed': 0, 'errors': []}

    phone_list = [item[1] for item in chunk_data]
    prospect_ids = [item[0] for item in chunk_data]

    sent, failed, errors = provider.send_sms_batch(phone_list, body)

    communications = [
        ProspectCommunication(
            prospect_id=prospect_id,
            channel=ProspectCommunication.CHANNEL_SMS,
            content=body,
            provider_id=provider_id,
        )
        for prospect_id in prospect_ids
    ]
    if communications:
        ProspectCommunication.objects.bulk_create(communications)

    logger.info("[SMS] Chunk finalizado: enviados=%s, fallidos=%s (total=%s)", sent, failed, len(chunk_data))
    return {'sent': sent, 'failed': failed, 'errors': errors}


@shared_task
def send_sms_campaign_aggregate(results):
    """
    Callback de un chord: recibe la lista de resultados de los chunks y devuelve
    el agregado (sent, failed, errors). No llamar directamente.
    """
    total_sent = sum(r.get('sent', 0) for r in results)
    total_failed = sum(r.get('failed', 0) for r in results)
    all_errors = []
    for r in results:
        all_errors.extend(r.get('errors', []))
    if len(all_errors) > SMS_CAMPAIGN_ERRORS_LIMIT:
        extra = len(all_errors) - SMS_CAMPAIGN_ERRORS_LIMIT
        all_errors = all_errors[:SMS_CAMPAIGN_ERRORS_LIMIT]
        all_errors.append(f'... y {extra} errores más (total failed={total_failed})')
    logger.info("[SMS] Campaña finalizada: enviados=%s, fallidos=%s", total_sent, total_failed)
    return {'sent': total_sent, 'failed': total_failed, 'errors': all_errors}


@shared_task
def send_sms_campaign(
    provider_id,
    body,
    department_values=None,
    municipality_values=None,
    origin_ids=None,
    identification_numbers=None,
    sexo_values=None,
    enlace_values=None,
):
    """
    Tarea asíncrona que envía SMS masivos a los prospectos que cumplen los filtros,
    usando el proveedor indicado (ej. onurix). Parte el lote en chunks y los procesa
    en paralelo con varias tareas Celery.

    Args:
        provider_id: Identificador del proveedor (ej. 'onurix').
        body: Texto del mensaje SMS.
        department_values: Lista de departamentos (opcional).
        municipality_values: Lista de municipios (opcional).
        origin_ids: Lista de IDs de origen (opcional).
        identification_numbers: Lista de números de cédula (opcional).
        sexo_values: Lista de valores de sexo (opcional).
        enlace_values: Lista de valores de enlace (opcional).

    Returns:
        dict: {'sent': N, 'failed': M, 'errors': [...]}
    """
    from .sms_providers import get_provider
    from .utils import get_sms_prospects_queryset, get_prospects_with_valid_phone

    provider = get_provider(provider_id)
    if not provider:
        logger.error("[SMS] Proveedor no encontrado: %s", provider_id)
        return {'sent': 0, 'failed': 0, 'errors': [f'Proveedor no encontrado: {provider_id}']}

    qs = get_sms_prospects_queryset(
        department_values=department_values,
        municipality_values=municipality_values,
        origin_ids=origin_ids,
        identification_numbers=identification_numbers,
        sexo_values=sexo_values,
        enlace_values=enlace_values,
    )
    prospects_with_phone = get_prospects_with_valid_phone(qs)

    if not prospects_with_phone:
        logger.info("[SMS] Campaña sin prospectos con teléfono válido")
        return {'sent': 0, 'failed': 0, 'errors': []}

    chunk_size = SMS_CAMPAIGN_CHUNK_SIZE
    chunks = []
    for i in range(0, len(prospects_with_phone), chunk_size):
        chunk = prospects_with_phone[i : i + chunk_size]
        chunk_data = [[p.pk, phone] for p, phone in chunk]
        chunks.append(chunk_data)

    # Usar chord: no se puede llamar result.get() dentro de una tarea, así que
    # despachamos el chord y un callback agrega los resultados cuando terminen los chunks.
    chord(
        group(
            send_sms_campaign_chunk.s(provider_id, body, chunk_data) for chunk_data in chunks
        ),
        send_sms_campaign_aggregate.s(),
    ).apply_async()

    logger.info("[SMS] Campaña despachada: %s chunks", len(chunks))
    return {'status': 'dispatched', 'chunks': len(chunks)}
