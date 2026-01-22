from rest_framework import serializers
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
            'created_at',
            'updated_at',
            'created_by_email',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by_email', 'full_name']

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
