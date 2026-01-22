from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Prospect


class ProspectForm(forms.ModelForm):
    """
    Formulario para crear y editar prospectos.
    """
    class Meta:
        model = Prospect
        fields = ['identification_number', 'first_name', 'last_name', 'phone_number']
        widgets = {
            'identification_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Ej: 1234567890'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Nombre'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Apellido'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Ej: 3001234567'
            }),
        }
        labels = {
            'identification_number': _('Número de Identificación'),
            'first_name': _('Nombre'),
            'last_name': _('Apellido'),
            'phone_number': _('Teléfono'),
        }


class ProspectSearchForm(forms.Form):
    """
    Formulario para buscar prospectos por número de identificación.
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
