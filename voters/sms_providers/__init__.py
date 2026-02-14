"""
Proveedores de envío de SMS. Interfaz común y registry para permitir
cambiar de proveedor (Twilio hoy, otros en el futuro) sin tocar la UI.
"""
from .base import BaseSMSProvider
from .twilio_provider import TwilioSMSProvider
from .onurix_provider import OnurixSMSProvider

# Registry: provider_id -> (display_label, provider_class, bulk_export_slug)
# bulk_export_slug: None si no tiene descarga masiva, o identificador (ej. 'onurix') si sí.
# Orden: el primero es el predeterminado en la UI (Onurix).
SMS_PROVIDER_REGISTRY = {
    'onurix': ('Onurix', OnurixSMSProvider, 'onurix'),
    'twilio': ('Twilio', TwilioSMSProvider, None),
}


def get_provider(provider_id):
    """
    Devuelve una instancia del proveedor dado por provider_id.
    Si el id no existe, devuelve None.
    """
    entry = SMS_PROVIDER_REGISTRY.get(provider_id)
    if not entry:
        return None
    _, provider_class, _ = entry
    return provider_class()


def get_available_providers():
    """
    Devuelve lista de (provider_id, display_label) para el selector en la UI.
    """
    return [(pid, label) for pid, (label, _, _) in SMS_PROVIDER_REGISTRY.items()]


def get_provider_ids_with_bulk_export():
    """
    Devuelve la lista de provider_id que tienen descarga masiva (bulk_export_slug no nulo).
    """
    return [pid for pid, (_, _, slug) in SMS_PROVIDER_REGISTRY.items() if slug is not None]
