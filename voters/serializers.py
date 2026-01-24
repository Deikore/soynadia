from rest_framework import serializers
import re
from .models import Prospect


class ProspectSerializer(serializers.ModelSerializer):
    """
    Serializer para el modelo Prospect.
    """
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = Prospect
        fields = [
            'id',
            'identification_number',
            'first_name',
            'last_name',
            'full_name',
            'phone_number',
            'department',
            'municipality',
            'polling_station',
            'polling_station_address',
            'table',
            'notice',
            'resolution',
            'notice_date',
            'polling_station_consulted',
            'allow_whatsapp',
            'created_at',
            'updated_at',
            'created_by_email',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'created_by_email',
            'full_name',
            'department',
            'municipality',
            'polling_station',
            'polling_station_address',
            'table',
            'notice',
            'resolution',
            'notice_date',
            'polling_station_consulted',
            'allow_whatsapp',
        ]

    def validate_identification_number(self, value):
        """
        Validar que el número de identificación sea único.
        """
        instance = self.instance
        if instance and instance.identification_number == value:
            # Si estamos actualizando y el número no cambió, está bien
            return value
        
        if Prospect.objects.filter(identification_number=value).exists():
            raise serializers.ValidationError(
                'Ya existe un prospecto con este número de identificación.'
            )
        return value
    
    def validate_phone_number(self, value):
        """
        Valida y normaliza el número de teléfono colombiano.
        Acepta múltiples formatos y almacena solo números (10 dígitos).
        """
        if not value:
            return value  # Opcional, puede estar vacío
        
        # Normalizar: quitar espacios, guiones, paréntesis
        normalized = re.sub(r'[\s\-\(\)]', '', value.strip())
        
        # Quitar prefijo +57 o 57 si existe
        if normalized.startswith('+57'):
            normalized = normalized[3:]
        elif normalized.startswith('57') and len(normalized) == 12:
            normalized = normalized[2:]
        
        # Validar que sean solo números y longitud correcta
        if not normalized.isdigit() or len(normalized) != 10:
            raise serializers.ValidationError(
                'Número inválido. Debe tener 10 dígitos. Ejemplos: +57 313 416 5999, 3134165999'
            )
        
        # Validar que sea un número colombiano válido
        first_digit = normalized[0]
        
        if first_digit == '3':  # Celulares
            second_digit = normalized[1]
            # Celulares válidos: 300-399, 310-319, 320-329, 350-359
            if second_digit not in ['0', '1', '2', '5']:
                raise serializers.ValidationError(
                    'Número de celular inválido para Colombia. Debe empezar con 300-399, 310-319, 320-329 o 350-359.'
                )
        elif first_digit in ['1', '2', '3', '4', '5', '6', '7', '8']:  # Fijos
            # Números fijos válidos (códigos de área 1-8)
            pass  # Válido
        else:
            raise serializers.ValidationError(
                'Número inválido para Colombia. Debe ser un celular (3XX) o fijo (1-8XX).'
            )
        
        return normalized  # Retornar solo números: 3134165999