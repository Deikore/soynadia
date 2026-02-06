"""
Proveedor de SMS vía API de Onurix.
Permite enviar a varios números en un solo request (phone separado por comas).
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
    Envío de SMS usando la API de Onurix. Soporta envío por lote en un solo
    request (varios teléfonos separados por comas).
    Variables de entorno: ONURIX_CLIENT, ONURIX_KEY; opcional: ONURIX_GROUPS.
    """

    def send_sms(self, phone_normalized: str, body: str):
        sent, failed, errors = self.send_sms_batch([phone_normalized], body)
        if sent == 1:
            return True, 'ok'
        if failed == 1 and errors:
            return False, errors[0]
        return False, errors[0] if errors else 'Error al enviar'

    def send_sms_batch(self, phone_list: list, body: str):
        if not body or not str(body).strip():
            return 0, len(phone_list) if phone_list else 0, ['El mensaje no puede estar vacío']

        client = os.getenv('ONURIX_CLIENT')
        key = os.getenv('ONURIX_KEY')

        if not client or not key:
            logger.error(
                "[Onurix SMS] Faltan variables: CLIENT=%s, KEY=%s",
                bool(client), bool(key)
            )
            n = len(phone_list) if phone_list else 0
            return 0, n, ['Configuración de Onurix incompleta (ONURIX_CLIENT, ONURIX_KEY)']

        if not phone_list:
            return 0, 0, []

        phones_formatted = []
        for phone in phone_list:
            p = _format_phone(phone)
            if not p:
                logger.warning("[Onurix SMS] Número inválido omitido: %s", phone)
                continue
            phones_formatted.append(p)

        if not phones_formatted:
            return 0, len(phone_list), ['Ningún número de teléfono válido']

        phone_param = ','.join(phones_formatted)
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
        }
        data = {
            'client': client,
            'key': key,
            'phone': phone_param,
            'sms': body.strip(),
        }
        groups = os.getenv('ONURIX_GROUPS')
        if groups:
            data['groups'] = groups

        try:
            r = requests.post(ONURIX_SEND_URL, headers=headers, data=data, timeout=30)
            if r.ok:
                logger.info(
                    "[Onurix SMS] Envío batch exitoso: %s números, response=%s",
                    len(phones_formatted), r.text[:200] if r.text else ''
                )
                return len(phones_formatted), 0, []
            try:
                err_body = r.json()
                err_msg = str(err_body)
            except Exception:
                err_msg = r.text or f'HTTP {r.status_code}'
            logger.warning("[Onurix SMS] Error en envío batch: %s", err_msg)
            return 0, len(phones_formatted), [err_msg]
        except requests.RequestException as e:
            logger.error("[Onurix SMS] Error de red al enviar batch: %s", e, exc_info=True)
            return 0, len(phones_formatted), [str(e)]
