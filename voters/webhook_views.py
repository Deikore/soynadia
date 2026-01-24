"""
Vistas para webhooks externos.
"""
import os
import logging
import phonenumbers
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction
from twilio.request_validator import RequestValidator
from .models import WhatsAppOptIn, Prospect

logger = logging.getLogger(__name__)


def normalize_whatsapp_from_number(from_value):
    """
    Extrae el número nacional a partir del remitente Twilio (From).
    Quita el prefijo 'whatsapp:' y el prefijo de país correspondiente (+57, +1, +52, etc.).
    No asume siempre Colombia.

    Args:
        from_value: Valor de From (ej. whatsapp:+573001234567, whatsapp:+13051234567)

    Returns:
        str: Número nacional (solo dígitos) o None si no se puede parsear
    """
    if not from_value or not str(from_value).strip():
        return None
    s = str(from_value).strip()
    if s.lower().startswith('whatsapp:'):
        s = s[9:].strip()
    if not s:
        return None
    try:
        parsed = phonenumbers.parse(s, None)
        return str(parsed.national_number)
    except phonenumbers.NumberParseException:
        return None


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


def find_prospect_by_phone(from_value):
    """
    Busca un prospecto por el valor From del webhook (whatsapp:+cc...).
    Normaliza quitando whatsapp: y prefijo de país, luego busca por phone_number.

    Args:
        from_value: Valor de From enviado por Twilio

    Returns:
        Prospect o None
    """
    if not from_value:
        return None
    normalized = normalize_whatsapp_from_number(from_value)
    if not normalized:
        return None
    try:
        prospect = Prospect.objects.filter(phone_number=normalized).first()
        if prospect:
            return prospect
        prospects = Prospect.objects.filter(phone_number__contains=normalized)
        if prospects.exists():
            return prospects.first()
    except Exception as e:
        logger.error("Error al buscar prospecto por teléfono %s: %s", from_value, e)
    return None


@require_POST
@csrf_exempt
def twilio_whatsapp_webhook(request):
    """
    Webhook para recibir mensajes y opt-ins de WhatsApp desde Twilio.
    
    Este endpoint es público pero valida la firma de Twilio para seguridad.
    """
    try:
        meta = request.META
        skip_validation = os.getenv('TWILIO_SKIP_SIGNATURE_VALIDATION', 'False').lower() == 'true'
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        webhook_url = (os.getenv('TWILIO_WEBHOOK_URL') or '').strip() or None

        if auth_token and not skip_validation:
            try:
                validator = RequestValidator(auth_token)
                signature = request.META.get('HTTP_X_TWILIO_SIGNATURE', '')
                if webhook_url:
                    url = webhook_url
                else:
                    host = meta.get('HTTP_X_FORWARDED_HOST') or meta.get('HTTP_HOST') or request.get_host()
                    protocol = 'https' if meta.get('HTTP_X_FORWARDED_PROTO') == 'https' or request.is_secure() else 'http'
                    url = f"{protocol}://{host}{request.path}"
                params = {k: v for k, v in request.POST.items()}
                if signature and not validator.validate(url, params, signature):
                    logger.warning("[Twilio] Firma inválida, rechazando petición")
                    return HttpResponseBadRequest('Invalid signature')
            except Exception as e:
                logger.error("[Twilio] Error al validar firma: %s", e, exc_info=True)

        message_sid = request.POST.get('MessageSid', '')
        account_sid = request.POST.get('AccountSid', '')
        messaging_service_sid = request.POST.get('MessagingServiceSid', '')
        from_number = request.POST.get('From', '')
        to_number = request.POST.get('To', '')
        body = request.POST.get('Body', '')
        profile_name = request.POST.get('ProfileName', '')
        wa_id = request.POST.get('WaId', '')
        
        if not message_sid or not account_sid or not from_number:
            logger.error("[Twilio] Webhook sin campos mínimos: message_sid=%s, account_sid=%s, from_number=%s", message_sid, account_sid, from_number)
            return HttpResponseBadRequest('Missing required fields')

        raw_data = {k: v for k, v in request.POST.items()}
        event_type = determine_event_type(body)
        prospect = find_prospect_by_phone(from_number)

        with transaction.atomic():
            if prospect:
                prospect.allow_whatsapp = True
                prospect.save(update_fields=['allow_whatsapp'])
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
                    'prospect': prospect,
                    'raw_data': raw_data,
                }
            )

        # Retornar respuesta TwiML válida
        twiml_response = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
        return HttpResponse(twiml_response, content_type='text/xml')
        
    except Exception as e:
        logger.error("[Twilio] Error al procesar webhook: %s", e, exc_info=True)
        return HttpResponse('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', content_type='text/xml')
