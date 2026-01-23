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


@csrf_exempt
@require_POST
def twilio_whatsapp_webhook(request):
    """
    Webhook para recibir mensajes y opt-ins de WhatsApp desde Twilio.
    
    Este endpoint es público pero valida la firma de Twilio para seguridad.
    """
    try:
        # Validar firma de Twilio (opcional pero recomendado)
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        if auth_token:
            validator = RequestValidator(auth_token)
            signature = request.META.get('HTTP_X_TWILIO_SIGNATURE', '')
            url = request.build_absolute_uri()
            
            # Twilio envía los datos como form-data, necesitamos construir el dict
            params = {}
            for key, value in request.POST.items():
                params[key] = value
            
            if not validator.validate(url, params, signature):
                logger.warning(f"Firma de Twilio inválida para webhook")
                return HttpResponseBadRequest('Invalid signature')
        
        # Extraer parámetros del request
        message_sid = request.POST.get('MessageSid', '')
        account_sid = request.POST.get('AccountSid', '')
        messaging_service_sid = request.POST.get('MessagingServiceSid', '')
        from_number = request.POST.get('From', '')
        to_number = request.POST.get('To', '')
        body = request.POST.get('Body', '')
        profile_name = request.POST.get('ProfileName', '')
        wa_id = request.POST.get('WaId', '')
        
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
