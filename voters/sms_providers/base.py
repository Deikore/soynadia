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

    def send_sms_batch(self, phone_list: list, body: str):
        """
        Envía SMS a varios números. Implementación por defecto: llama a send_sms
        por cada número y acumula sent/failed/errors. Los proveedores pueden
        sobrescribir este método para enviar en un solo request cuando la API
        lo permita (ej. Onurix con phone separado por comas).

        Args:
            phone_list: Lista de números normalizados (ej. 10 dígitos Colombia).
            body: Texto del mensaje.

        Returns:
            tuple: (sent: int, failed: int, errors: list[str])
        """
        sent = 0
        failed = 0
        errors = []
        for phone in phone_list:
            success, result = self.send_sms(phone, body)
            if success:
                sent += 1
            else:
                failed += 1
                errors.append(f"{phone}: {result}")
        return sent, failed, errors

    def get_balance(self):
        """
        Consulta el saldo/créditos disponibles del proveedor (opcional).
        No es abstracto: proveedores que no soporten consulta de saldo no lo implementan.

        Returns:
            tuple: (success: bool, balance: int | None)
                - (True, N) si se pudo obtener el saldo y hay N créditos.
                - (False, None) si no se pudo obtener o el proveedor no lo soporta.
        """
        return False, None
