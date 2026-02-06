from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import re
from .models import Prospect, OriginProspect


class ProspectForm(forms.ModelForm):
    """
    Formulario para crear y editar prospectos.
    """
    class Meta:
        model = Prospect
        fields = ['identification_number', 'full_name', 'phone_number']
        widgets = {
            'identification_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Ej: 1234567890'
            }),
            'full_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Nombre completo'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Ej: +57 313 400 0000 o 3134000000'
            }),
        }
        labels = {
            'identification_number': _('Número de Identificación (Opcional)'),
            'full_name': _('Nombre Completo'),
            'phone_number': _('Teléfono (Opcional)'),
        }
    
    def clean_phone_number(self):
        """
        Valida y normaliza el número de teléfono colombiano.
        Acepta múltiples formatos y almacena solo números (10 dígitos).
        """
        phone = self.cleaned_data.get('phone_number')
        if not phone:
            return phone  # Opcional, puede estar vacío
        
        # Normalizar: quitar espacios, guiones, paréntesis
        normalized = re.sub(r'[\s\-\(\)]', '', phone.strip())
        
        # Quitar prefijo +57 o 57 si existe
        if normalized.startswith('+57'):
            normalized = normalized[3:]
        elif normalized.startswith('57') and len(normalized) == 12:
            normalized = normalized[2:]
        
        # Validar que sean solo números y longitud correcta
        if not normalized.isdigit() or len(normalized) != 10:
            raise ValidationError(
                _('Número inválido. Debe tener 10 dígitos. Ejemplos: +57 313 400 0000, 3134000000')
            )
        
        # Validar que sea un número colombiano válido
        first_digit = normalized[0]
        
        if first_digit == '3':  # Celulares
            second_digit = normalized[1]
            # Celulares válidos: 300-399, 310-319, 320-329, 350-359
            if second_digit not in ['0', '1', '2', '5']:
                raise ValidationError(
                    _('Número de celular inválido para Colombia. Debe empezar con 300-399, 310-319, 320-329 o 350-359.')
                )
        elif first_digit in ['1', '2', '3', '4', '5', '6', '7', '8']:  # Fijos
            # Números fijos válidos (códigos de área 1-8)
            pass  # Válido
        else:
            raise ValidationError(
                _('Número inválido para Colombia. Debe ser un celular (3XX) o fijo (1-8XX).')
            )
        
        return normalized  # Retornar solo números: 3134155999


class ProspectSearchForm(forms.Form):
    """
    Formulario para buscar prospectos por número de identificación y/o nombre.
    """
    identification_number = forms.CharField(
        label=_('Buscar por Número de Identificación'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Ingrese el número de identificación...',
            'autofocus': True
        })
    )
    full_name = forms.CharField(
        label=_('Buscar por nombre'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': _('Nombre completo o parte del nombre...'),
        })
    )


class BulkUploadForm(forms.Form):
    """
    Formulario para cargar prospectos de manera masiva desde un archivo CSV.
    """
    csv_file = forms.FileField(
        label=_('Archivo CSV'),
        help_text=_('Seleccione un archivo CSV delimitado por punto y coma (;) o coma (,) con los campos: identification_number (opcional), full_name, phone_number, origin'),
        widget=forms.FileInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent',
            'accept': '.csv'
        })
    )
    
    def clean_csv_file(self):
        """
        Valida que el archivo sea CSV y tenga un tamaño razonable.
        """
        file = self.cleaned_data.get('csv_file')
        if not file:
            raise ValidationError(_('Debe seleccionar un archivo.'))
        
        # Validar extensión
        if not file.name.lower().endswith('.csv'):
            raise ValidationError(_('El archivo debe tener extensión .csv'))
        
        # Validar tamaño (10MB máximo)
        max_size = 10 * 1024 * 1024  # 10MB
        if file.size > max_size:
            raise ValidationError(_('El archivo es demasiado grande. El tamaño máximo es 10MB.'))
        
        return file


class SMSFilterForm(forms.Form):
    """
    Formulario de filtros para la campaña SMS: departamento, municipio y origen
    (múltiples valores permitidos).
    """
    department = forms.MultipleChoiceField(
        label=_('Departamento de votación'),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent',
            'size': '5',
        }),
        choices=[],
    )
    municipality = forms.MultipleChoiceField(
        label=_('Municipio de votación'),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent',
            'size': '5',
        }),
        choices=[],
    )
    origin = forms.MultipleChoiceField(
        label=_('Origen'),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent',
            'size': '5',
        }),
        choices=[],
    )
    identification_number = forms.MultipleChoiceField(
        label=_('Número de cédula'),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent',
            'size': '5',
        }),
        choices=[],
    )

    def __init__(self, *args, **kwargs):
        department_choices = kwargs.pop('department_choices', None)
        municipality_choices = kwargs.pop('municipality_choices', None)
        origin_choices = kwargs.pop('origin_choices', None)
        identification_choices = kwargs.pop('identification_choices', None)
        super().__init__(*args, **kwargs)
        if department_choices is not None:
            self.fields['department'].choices = department_choices
        if municipality_choices is not None:
            self.fields['municipality'].choices = municipality_choices
        if origin_choices is not None:
            self.fields['origin'].choices = origin_choices
        if identification_choices is not None:
            self.fields['identification_number'].choices = identification_choices
