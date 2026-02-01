"""
Servicio para envío de mensajes de WhatsApp vía API de Twilio.
"""
import os
import logging
from django.utils import timezone

from twilio.rest import Client

from .models import WhatsAppMessage, WhatsAppAccount

logger = logging.getLogger(__name__)


def _format_whatsapp_to_number(phone_number_normalized):
    """
    Construye el número en formato whatsapp:+cc... para Twilio.
    Asume Colombia (+57) si no tiene prefijo de país.
    """
    if not phone_number_normalized:
        return None
    phone = str(phone_number_normalized).strip()
    if not phone:
        return None
    if not phone.startswith('+'):
        to_number = f'whatsapp:+57{phone}'
    else:
        to_number = f'whatsapp:{phone}'
    return to_number


def send_whatsapp_text_message(phone_number_normalized, body):
    """
    Envía un mensaje de texto libre a un número de WhatsApp vía API de Twilio
    y lo guarda en WhatsAppMessage con direction='outbound'.

    Args:
        phone_number_normalized: Número nacional (sin whatsapp:, sin prefijo país)
        body: Contenido del mensaje

    Returns:
        tuple: (success: bool, message_sid_or_error: str | None)
            - (True, message_sid) si se envió correctamente
            - (False, error_message) si falló
    """
    if not body or not str(body).strip():
        return False, 'El mensaje no puede estar vacío'

    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER')

    if not account_sid or not auth_token or not whatsapp_number:
        logger.error(
            "[Twilio] Faltan variables de entorno: ACCOUNT_SID=%s, AUTH_TOKEN=%s, WHATSAPP_NUMBER=%s",
            bool(account_sid), bool(auth_token), bool(whatsapp_number)
        )
        return False, 'Configuración de Twilio incompleta'

    to_number = _format_whatsapp_to_number(phone_number_normalized)
    if not to_number:
        return False, 'Número de teléfono inválido'

    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=body.strip(),
            from_=whatsapp_number,
            to=to_number
        )

        # Obtener o crear WhatsAppAccount para asociar el mensaje
        whatsapp_account = WhatsAppAccount.objects.filter(
            phone_number=phone_number_normalized
        ).first()

        WhatsAppMessage.objects.create(
            message_sid=message.sid,
            account_sid=message.account_sid or account_sid,
            messaging_service_sid=message.messaging_service_sid,
            from_number=whatsapp_number,
            to_number=to_number,
            body=body.strip(),
            event_type='message',
            phone_number_normalized=phone_number_normalized,
            direction='outbound',
            whatsapp_account=whatsapp_account,
            received_at=timezone.now(),
        )

        logger.info("[Twilio] Mensaje de texto enviado: SID=%s, to=%s", message.sid, to_number)
        return True, message.sid

    except Exception as e:
        error_msg = str(e)
        logger.error("[Twilio] Error al enviar mensaje a %s: %s", phone_number_normalized, e, exc_info=True)
        return False, error_msg
