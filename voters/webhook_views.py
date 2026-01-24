"""
Vistas para webhooks externos.
"""
import os
import re
import json
import logging
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import transaction
from twilio.request_validator import RequestValidator
from .models import WhatsAppOptIn, Prospect

logger = logging.getLogger(__name__)


def normalize_phone_number(phone):
    """
    Normaliza un número de teléfono para búsqueda.
    Elimina espacios, guiones, paréntesis y el prefijo +57 o 57.
    
    Args:
        phone: Número de teléfono en cualquier formato
    
    Returns:
        str: Número normalizado (solo dígitos) o None si está vacío
    """
    if not phone:
        return None
    
    # Eliminar espacios, guiones, paréntesis
    normalized = re.sub(r'[\s\-\(\)]', '', phone.strip())
    
    # Eliminar prefijo +57 o 57
    if normalized.startswith('+57'):
        normalized = normalized[3:]
    elif normalized.startswith('57') and len(normalized) > 10:
        normalized = normalized[2:]
    
    # Eliminar el prefijo whatsapp: si existe
    if normalized.startswith('whatsapp:'):
        normalized = normalized[9:]
    
    return normalized if normalized else None


def determine_event_type(body):
    """
    Determina el tipo de evento basado en el contenido del mensaje.
    
    Args:
        body: Contenido del mensaje
    
    Returns:
        str: Tipo de evento ('opt-in', 'opt-out', 'message', 'status')
    """
    if not body:
        return 'message'
    
    body_upper = body.upper().strip()
    
    # Palabras clave para opt-in
    opt_in_keywords = ['START', 'SI', 'YES', 'UNIRSE', 'ACTIVAR', 'SUBSCRIBIR', 'SUBSCRIBE']
    if any(keyword in body_upper for keyword in opt_in_keywords):
        return 'opt-in'
    
    # Palabras clave para opt-out
    opt_out_keywords = ['STOP', 'NO', 'CANCELAR', 'DESACTIVAR', 'UNSUBSCRIBE', 'SALIR']
    if any(keyword in body_upper for keyword in opt_out_keywords):
        return 'opt-out'
    
    return 'message'


def find_prospect_by_phone(phone_number):
    """
    Busca un prospecto por número de teléfono normalizado.
    
    Args:
        phone_number: Número de teléfono a buscar
    
    Returns:
        Prospect o None
    """
    if not phone_number:
        return None
    
    normalized = normalize_phone_number(phone_number)
    if not normalized:
        return None
    
    try:
        # Buscar por número exacto normalizado
        prospect = Prospect.objects.filter(phone_number=normalized).first()
        if prospect:
            return prospect
        
        # Buscar por número que contenga el normalizado (para casos con prefijos)
        prospects = Prospect.objects.filter(phone_number__contains=normalized)
        if prospects.exists():
            return prospects.first()
        
    except Exception as e:
        logger.error(f"Error al buscar prospecto por teléfono {phone_number}: {e}")
    
    return None


@require_POST
@csrf_exempt
def twilio_whatsapp_webhook(request):
    """
    Webhook para recibir mensajes y opt-ins de WhatsApp desde Twilio.
    
    Este endpoint es público pero valida la firma de Twilio para seguridad.
    """
    try:
        # Logging inicial: solo headers relevantes para Twilio (evitar volcar todo META)
        meta = request.META
        headers_debug = {
            'HTTP_HOST': meta.get('HTTP_HOST'),
            'HTTP_X_FORWARDED_HOST': meta.get('HTTP_X_FORWARDED_HOST'),
            'HTTP_X_FORWARDED_PROTO': meta.get('HTTP_X_FORWARDED_PROTO'),
            'HTTP_X_FORWARDED_FOR': meta.get('HTTP_X_FORWARDED_FOR'),
            'HTTP_X_TWILIO_SIGNATURE': 'presente' if meta.get('HTTP_X_TWILIO_SIGNATURE') else 'ausente',
        }
        logger.info(
            "[Twilio] Webhook recibido: Method=%s, Path=%s, headers=%s",
            request.method,
            request.path,
            headers_debug,
        )

        skip_validation = os.getenv('TWILIO_SKIP_SIGNATURE_VALIDATION', 'False').lower() == 'true'
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        webhook_url = (os.getenv('TWILIO_WEBHOOK_URL') or '').strip() or None
        logger.info(
            "[Twilio] Validación firma: TWILIO_AUTH_TOKEN=%s, TWILIO_SKIP_SIGNATURE_VALIDATION=%s, skip_validation=%s, TWILIO_WEBHOOK_URL=%s",
            "presente" if auth_token else "ausente",
            os.getenv('TWILIO_SKIP_SIGNATURE_VALIDATION', ''),
            skip_validation,
            "presente" if webhook_url else "ausente",
        )

        if auth_token and not skip_validation:
            try:
                validator = RequestValidator(auth_token)
                signature = request.META.get('HTTP_X_TWILIO_SIGNATURE', '')
                logger.info(
                    "[Twilio] Firma recibida: header X-Twilio-Signature=%s, len=%d",
                    "presente" if signature else "ausente",
                    len(signature) if signature else 0,
                )

                if webhook_url:
                    url = webhook_url
                    logger.info("[Twilio] URL usada para validación (TWILIO_WEBHOOK_URL): %s", url)
                else:
                    host = meta.get('HTTP_X_FORWARDED_HOST') or meta.get('HTTP_HOST') or request.get_host()
                    protocol = 'https' if meta.get('HTTP_X_FORWARDED_PROTO') == 'https' or request.is_secure() else 'http'
                    path = request.path
                    url = f"{protocol}://{host}{path}"
                    logger.info(
                        "[Twilio] URL usada para validación (desde request): %s (Host=%s, X-Forwarded-Host=%s, X-Forwarded-Proto=%s, path=%s)",
                        url,
                        meta.get('HTTP_HOST'),
                        meta.get('HTTP_X_FORWARDED_HOST'),
                        meta.get('HTTP_X_FORWARDED_PROTO'),
                        path,
                    )

                params = {k: v for k, v in request.POST.items()}
                logger.info("[Twilio] Params para validación: keys=%s, count=%d", list(params.keys()), len(params))

                if not signature:
                    logger.warning("[Twilio] Validación omitida: no hay X-Twilio-Signature, continuando sin validar")
                else:
                    is_valid = validator.validate(url, params, signature)
                    logger.info("[Twilio] validator.validate(url, params, signature) => %s", is_valid)
                    if not is_valid:
                        logger.warning(
                            "[Twilio] Firma INVÁLIDA. URL usada=%s. Comprueba que la URL en Twilio Console coincida exactamente.",
                            url,
                        )
                        debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'
                        if not debug_mode:
                            logger.warning("[Twilio] Rechazando petición (Invalid signature)")
                            return HttpResponseBadRequest('Invalid signature')
                        logger.warning("[Twilio] DEBUG=true: continuando a pesar de firma inválida")
                    else:
                        logger.info("[Twilio] Firma válida, continuando")
            except Exception as e:
                logger.error("[Twilio] Excepción al validar firma: %s", e, exc_info=True)
        elif skip_validation:
            logger.warning("[Twilio] Validación deshabilitada por TWILIO_SKIP_SIGNATURE_VALIDATION=true")
        else:
            logger.warning("[Twilio] TWILIO_AUTH_TOKEN no configurado, webhook sin validación de firma")
        
        # Logging de parámetros recibidos
        logger.info(f"POST data keys: {list(request.POST.keys())}")
        
        # Extraer parámetros del request
        message_sid = request.POST.get('MessageSid', '')
        account_sid = request.POST.get('AccountSid', '')
        messaging_service_sid = request.POST.get('MessagingServiceSid', '')
        from_number = request.POST.get('From', '')
        to_number = request.POST.get('To', '')
        body = request.POST.get('Body', '')
        profile_name = request.POST.get('ProfileName', '')
        wa_id = request.POST.get('WaId', '')
        
        logger.info(f"Parámetros extraídos: message_sid={message_sid[:10] if message_sid else None}..., from={from_number}")
        
        # Guardar todos los datos recibidos en raw_data
        raw_data = {}
        for key, value in request.POST.items():
            raw_data[key] = value
        
        # Validar que tenemos los campos mínimos
        if not message_sid or not account_sid or not from_number:
            logger.error(f"Webhook recibido sin campos mínimos: message_sid={message_sid}, account_sid={account_sid}, from_number={from_number}")
            return HttpResponseBadRequest('Missing required fields')
        
        # Determinar el tipo de evento
        event_type = determine_event_type(body)
        
        # Determinar si el opt-in está activo
        is_active = True
        if event_type == 'opt-out':
            is_active = False
        elif event_type == 'opt-in':
            is_active = True
        
        # Buscar prospecto relacionado
        prospect = find_prospect_by_phone(from_number)
        
        # Crear o actualizar el registro
        with transaction.atomic():
            opt_in, created = WhatsAppOptIn.objects.update_or_create(
                message_sid=message_sid,
                defaults={
                    'account_sid': account_sid,
                    'messaging_service_sid': messaging_service_sid or None,
                    'from_number': from_number,
                    'to_number': to_number,
                    'body': body,
                    'profile_name': profile_name or None,
                    'wa_id': wa_id or None,
                    'event_type': event_type,
                    'is_active': is_active,
                    'prospect': prospect,
                    'raw_data': raw_data,
                }
            )
            
            if created:
                logger.info(f"Nuevo opt-in creado: {opt_in.message_sid} - {from_number} - {event_type}")
            else:
                logger.info(f"Opt-in actualizado: {opt_in.message_sid} - {from_number} - {event_type}")
        
        # Retornar respuesta TwiML válida
        twiml_response = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
        return HttpResponse(twiml_response, content_type='text/xml')
        
    except Exception as e:
        logger.error(f"Error al procesar webhook de Twilio: {e}", exc_info=True)
        # Retornar respuesta válida incluso en caso de error para que Twilio no reintente
        twiml_response = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
        return HttpResponse(twiml_response, content_type='text/xml')
