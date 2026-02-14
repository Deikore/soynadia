"""
Proveedor de SMS vía API de Onurix.
Un request por número (envío individual).
"""
import os
import logging
import requests

from .base import BaseSMSProvider

logger = logging.getLogger(__name__)

ONURIX_SEND_URL = 'https://www.onurix.com/api/v1/sms/send'


def _format_phone(phone_normalized):
    """
    Formato para Onurix: Colombia 57 + 10 dígitos (sin + para form-urlencoded).
    """
    if not phone_normalized:
        return None
    phone = str(phone_normalized).strip()
    if not phone.isdigit():
        return None
    if len(phone) == 10:
        return f'57{phone}'
    if len(phone) == 12 and phone.startswith('57'):
        return phone
    return None


class OnurixSMSProvider(BaseSMSProvider):
    """
    Envío de SMS usando la API de Onurix. Cada envío es un request con un solo número.
    Variables de entorno: ONURIX_CLIENT, ONURIX_KEY; opcional: ONURIX_GROUPS.
    """

    def send_sms(self, phone_normalized: str, body: str):
        if not body or not str(body).strip():
            return False, 'El mensaje no puede estar vacío'

        client = os.getenv('ONURIX_CLIENT')
        key = os.getenv('ONURIX_KEY')

        if not client or not key:
            logger.error(
                "[Onurix SMS] Faltan variables: CLIENT=%s, KEY=%s",
                bool(client), bool(key)
            )
            return False, 'Configuración de Onurix incompleta (ONURIX_CLIENT, ONURIX_KEY)'

        phone_formatted = _format_phone(phone_normalized)
        if not phone_formatted:
            logger.warning("[Onurix SMS] Número inválido: %s", phone_normalized)
            return False, 'Número de teléfono inválido'

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
        }
        data = {
            'client': client,
            'key': key,
            'phone': phone_formatted,
            'sms': body.strip(),
        }
        groups = os.getenv('ONURIX_GROUPS')
        if groups:
            data['groups'] = groups

        try:
            r = requests.post(ONURIX_SEND_URL, headers=headers, data=data, timeout=30)
            if r.ok:
                logger.info(
                    "[Onurix SMS] Envío exitoso: %s, response=%s",
                    phone_formatted, r.text[:200] if r.text else ''
                )
                return True, 'ok'
            try:
                err_body = r.json()
                err_msg = str(err_body)
            except Exception:
                err_msg = r.text or f'HTTP {r.status_code}'
            logger.warning("[Onurix SMS] Error en envío: %s", err_msg)
            return False, err_msg
        except requests.RequestException as e:
            logger.error("[Onurix SMS] Error de red al enviar: %s", e, exc_info=True)
            return False, str(e)
