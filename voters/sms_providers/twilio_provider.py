"""
Proveedor de SMS vía API de Twilio.
"""
import os
import logging
from twilio.rest import Client

from .base import BaseSMSProvider

logger = logging.getLogger(__name__)


def _format_e164(phone_normalized):
    """
    Formato E.164 para Colombia: +57 + 10 dígitos.
    """
    if not phone_normalized:
        return None
    phone = str(phone_normalized).strip()
    if not phone.isdigit():
        return None
    if len(phone) == 10:
        return f'+57{phone}'
    if len(phone) == 12 and phone.startswith('57'):
        return f'+{phone}'
    return None


class TwilioSMSProvider(BaseSMSProvider):
    """
    Envío de SMS usando Twilio Messages API (SMS estándar, no WhatsApp).
    Usa TWILIO_SMS_PHONE_NUMBER; si no está definido, fallback a
    TWILIO_WHATSAPP_NUMBER sin prefijo whatsapp: (solo para desarrollo).
    """

    def send_sms(self, phone_normalized: str, body: str):
        if not body or not str(body).strip():
            return False, 'El mensaje no puede estar vacío'

        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_SMS_PHONE_NUMBER') or self._fallback_from_number()

        if not account_sid or not auth_token or not from_number:
            logger.error(
                "[Twilio SMS] Faltan variables: ACCOUNT_SID=%s, AUTH_TOKEN=%s, FROM=%s",
                bool(account_sid), bool(auth_token), bool(from_number)
            )
            return False, 'Configuración de Twilio SMS incompleta'

        to_number = _format_e164(phone_normalized)
        if not to_number:
            return False, 'Número de teléfono inválido'

        try:
            client = Client(account_sid, auth_token)
            message = client.messages.create(
                body=body.strip(),
                from_=from_number,
                to=to_number
            )
            logger.info("[Twilio SMS] Enviado: SID=%s, to=%s", message.sid, to_number)
            return True, message.sid
        except Exception as e:
            logger.error(
                "[Twilio SMS] Error al enviar a %s: %s",
                phone_normalized, e, exc_info=True
            )
            return False, str(e)

    def _fallback_from_number(self):
        """Fallback para desarrollo: usar número WhatsApp sin prefijo whatsapp:."""
        wa = os.getenv('TWILIO_WHATSAPP_NUMBER')
        if not wa:
            return None
        s = str(wa).strip()
        if s.lower().startswith('whatsapp:'):
            return s[9:].strip()
        return s
