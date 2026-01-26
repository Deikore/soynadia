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
from twilio.rest import Client
from .models import WhatsAppMessage, WhatsAppAccount, Prospect

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


def send_whatsapp_template(phone_number_normalized, template_sid):
    """
    Envía una plantilla de Twilio a un número de teléfono normalizado.
    
    Args:
        phone_number_normalized: Número nacional (sin whatsapp:, sin prefijo país)
        template_sid: SID de la plantilla de Twilio
    
    Returns:
        bool: True si se envió correctamente, False en caso contrario
    """
    try:
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER')
        
        if not account_sid or not auth_token or not whatsapp_number:
            logger.error("[Twilio] Faltan variables de entorno para enviar plantilla: ACCOUNT_SID=%s, AUTH_TOKEN=%s, WHATSAPP_NUMBER=%s", 
                        bool(account_sid), bool(auth_token), bool(whatsapp_number))
            return False
        
        # Construir número en formato whatsapp:+cc...
        # Necesitamos el código de país. Asumimos Colombia (+57) si no está claro
        # En producción, deberías detectar el país del número normalizado
        if not phone_number_normalized.startswith('+'):
            # Asumir Colombia si no tiene prefijo
            to_number = f'whatsapp:+57{phone_number_normalized}'
        else:
            to_number = f'whatsapp:{phone_number_normalized}'
        
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            content_sid=template_sid,
            from_=whatsapp_number,
            to=to_number
        )
        logger.info("[Twilio] Plantilla enviada: SID=%s, to=%s, template=%s", message.sid, to_number, template_sid)
        return True
    except Exception as e:
        logger.error("[Twilio] Error al enviar plantilla a %s: %s", phone_number_normalized, e, exc_info=True)
        return False


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
        
        # Normalizar número para búsqueda
        phone_number_normalized = normalize_whatsapp_from_number(from_number)
        if not phone_number_normalized:
            logger.warning("[Twilio] No se pudo normalizar número: %s", from_number)
            phone_number_normalized = ''
        
        # Buscar Prospect por número (siempre, en cada mensaje)
        prospect = None
        if phone_number_normalized:
            try:
                prospect = Prospect.objects.filter(phone_number=phone_number_normalized).first()
                if not prospect:
                    # Búsqueda flexible si no hay match exacto
                    prospects = Prospect.objects.filter(phone_number__contains=phone_number_normalized)
                    if prospects.exists():
                        prospect = prospects.first()
            except Exception as e:
                logger.error("[Twilio] Error al buscar prospecto por teléfono %s: %s", phone_number_normalized, e)
        
        # Detectar respuesta de quick reply
        button_text = request.POST.get('ButtonText', '').strip().upper()
        button_payload = request.POST.get('ButtonPayload', '').strip().upper()
        is_quick_reply = bool(button_text or button_payload)
        is_si = 'SI' in button_text or 'SI' in button_payload or button_payload == 'SI'
        is_no = 'NO' in button_text or 'NO' in button_payload or button_payload == 'NO'
        
        with transaction.atomic():
            # Buscar o crear WhatsAppAccount
            account = None
            account_created = False
            if phone_number_normalized:
                defaults = {
                    'optin_whatsapp': False,
                    'optout_whatsapp': False,
                }
                if prospect:
                    defaults['prospect'] = prospect
                account, account_created = WhatsAppAccount.objects.get_or_create(
                    phone_number=phone_number_normalized,
                    defaults=defaults
                )
            
            # Verificar y actualizar asociación (si el account ya existe pero no tiene prospect asociado)
            if account and prospect and not account.prospect:
                account.prospect = prospect
                account.save(update_fields=['prospect'])
            
            # Detectar "primera vez" (no existe WhatsAppAccount para este número)
            is_first_time = account_created if phone_number_normalized else False
            
            # Si es primera vez y no es un quick reply, enviar plantilla de opt-in
            if is_first_time and not is_quick_reply and phone_number_normalized:
                optin_template_sid = os.getenv('TWILIO_OPTIN_TEMPLATE_SID', 'HXc3259a2a93ad765cb532b2919bc2b1dd')
                send_whatsapp_template(phone_number_normalized, optin_template_sid)
            
            # Procesar respuesta de quick reply
            if is_quick_reply and account:
                if is_si:
                    account.optin_whatsapp = True
                    account.optout_whatsapp = False
                    account.save(update_fields=['optin_whatsapp', 'optout_whatsapp', 'updated_at'])
                    # Enviar segunda plantilla de confirmación
                    confirmed_template_sid = os.getenv('TWILIO_OPTIN_CONFIRMED_TEMPLATE_SID', 'HXf790520f9af4858389bec0ac00cf0b87')
                    send_whatsapp_template(phone_number_normalized, confirmed_template_sid)
                elif is_no:
                    account.optin_whatsapp = False
                    account.optout_whatsapp = True
                    account.save(update_fields=['optin_whatsapp', 'optout_whatsapp', 'updated_at'])
            
            # Guardar mensaje en WhatsAppMessage
            message, created = WhatsAppMessage.objects.update_or_create(
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
                    'phone_number_normalized': phone_number_normalized,
                    'raw_data': raw_data,
                }
            )

        # Retornar respuesta TwiML válida
        twiml_response = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
        return HttpResponse(twiml_response, content_type='text/xml')
        
    except Exception as e:
        logger.error("[Twilio] Error al procesar webhook: %s", e, exc_info=True)
        return HttpResponse('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', content_type='text/xml')
