"""
Interfaz base para proveedores de SMS.
"""
from abc import ABC, abstractmethod


class BaseSMSProvider(ABC):
    """
    Interfaz común para envío de SMS. Todas las implementaciones
    (Twilio, futuros proveedores) deben exponer send_sms con esta firma.
    """

    @abstractmethod
    def send_sms(self, phone_normalized: str, body: str):
        """
        Envía un SMS al número dado.

        Args:
            phone_normalized: Número normalizado (ej. 10 dígitos para Colombia).
            body: Texto del mensaje.

        Returns:
            tuple: (success: bool, message_id_or_error: str)
                - (True, message_sid_or_id) si se envió correctamente
                - (False, error_message) si falló
        """
        pass
