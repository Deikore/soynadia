"""
Proveedores de envío de SMS. Interfaz común y registry para permitir
cambiar de proveedor (Twilio hoy, otros en el futuro) sin tocar la UI.
"""
from .base import BaseSMSProvider
from .twilio_provider import TwilioSMSProvider

# Registry: provider_id -> (display_label, provider_class)
SMS_PROVIDER_REGISTRY = {
    'twilio': ('Twilio', TwilioSMSProvider),
}


def get_provider(provider_id):
    """
    Devuelve una instancia del proveedor dado por provider_id.
    Si el id no existe, devuelve None.
    """
    entry = SMS_PROVIDER_REGISTRY.get(provider_id)
    if not entry:
        return None
    _, provider_class = entry
    return provider_class()


def get_available_providers():
    """
    Devuelve lista de (provider_id, display_label) para el selector en la UI.
    """
    return [(pid, label) for pid, (label, _) in SMS_PROVIDER_REGISTRY.items()]
