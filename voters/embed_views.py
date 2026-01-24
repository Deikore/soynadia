"""
Vistas públicas para formularios embebibles (ej. GoDaddy).
"""
import os
from urllib.parse import quote

from django import forms
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_exempt
from django.utils.translation import gettext_lazy as _
from django.db import transaction

from .models import Prospect, OriginProspect
from .utils import validate_and_normalize_phone, should_trigger_celery_task
from .tasks import process_prospect


class EmbedProspectForm(forms.Form):
    """Formulario embebible: identificación, nombres, apellidos, teléfono (todos obligatorios)."""

    identification_number = forms.CharField(
        max_length=20,
        required=True,
        label=_('Número de identificación'),
        widget=forms.TextInput(attrs={
            'placeholder': 'Ej: 1234567890',
            'required': True,
            'autocomplete': 'off',
        }),
    )
    first_name = forms.CharField(
        max_length=100,
        required=True,
        label=_('Nombres'),
        widget=forms.TextInput(attrs={
            'placeholder': _('Nombres'),
            'required': True,
            'autocomplete': 'given-name',
        }),
    )
    last_name = forms.CharField(
        max_length=100,
        required=True,
        label=_('Apellidos'),
        widget=forms.TextInput(attrs={
            'placeholder': _('Apellidos'),
            'required': True,
            'autocomplete': 'family-name',
        }),
    )
    phone_number = forms.CharField(
        max_length=20,
        required=True,
        label=_('Teléfono'),
        widget=forms.TextInput(attrs={
            'placeholder': 'Ej: +57 313 416 5999 o 3134165999',
            'required': True,
            'autocomplete': 'tel',
        }),
    )
    accepted_terms = forms.BooleanField(
        required=True,
        label=_('Acepto los términos y condiciones del registro.'),
        widget=forms.CheckboxInput(attrs={'id': 'id_accepted_terms', 'data-embed-check': 'accepted_terms'}),
    )
    authorize_info_sending = forms.BooleanField(
        required=True,
        label=_('Autorizo el envío de información a mi correo y/o teléfono proporcionados.'),
        widget=forms.CheckboxInput(attrs={'id': 'id_authorize_info_sending', 'data-embed-check': 'authorize_info_sending'}),
    )

    def clean_identification_number(self):
        value = (self.cleaned_data.get('identification_number') or '').strip()
        if not value:
            raise forms.ValidationError(_('Este campo es obligatorio.'))
        if Prospect.objects.filter(identification_number=value).exists():
            raise forms.ValidationError(
                _('Ya te inscribiste a nuestra campaña, muchas gracias.')
            )
        return value

    def clean_first_name(self):
        value = (self.cleaned_data.get('first_name') or '').strip()
        if not value:
            raise forms.ValidationError(_('Este campo es obligatorio.'))
        return value

    def clean_last_name(self):
        value = (self.cleaned_data.get('last_name') or '').strip()
        if not value:
            raise forms.ValidationError(_('Este campo es obligatorio.'))
        return value

    def clean_phone_number(self):
        value = self.cleaned_data.get('phone_number')
        if not value or not str(value).strip():
            raise forms.ValidationError(_('Este campo es obligatorio.'))
        return validate_and_normalize_phone(value)

    def clean_accepted_terms(self):
        value = self.cleaned_data.get('accepted_terms')
        if not value:
            raise forms.ValidationError(_('Debes aceptar los términos para continuar.'))
        return value

    def clean_authorize_info_sending(self):
        value = self.cleaned_data.get('authorize_info_sending')
        if not value:
            raise forms.ValidationError(_('Debes autorizar el envío de información para continuar.'))
        return value


@csrf_exempt
@xframe_options_exempt
@require_http_methods(['GET', 'POST'])
def embed_prospect_form(request):
    """
    Formulario público embebible (iframe) para registrar prospectos.
    GET: muestra el formulario. POST: valida, crea Prospect con origen "embed".
    """
    if request.method == 'GET':
        form = EmbedProspectForm()
        return render(
            request,
            'voters/embed_prospect_form.html',
            {'form': form, 'success': False},
        )

    form = EmbedProspectForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            'voters/embed_prospect_form.html',
            {'form': form, 'success': False},
        )

    with transaction.atomic():
        origin, created = OriginProspect.objects.get_or_create(
            name='embed',
            defaults={
                'description': _('Prospecto registrado desde formulario embebible (GoDaddy, etc.)'),
                'is_active': True,
                'enable_consult_polling_station': False,
            },
        )
        prospect = Prospect.objects.create(
            identification_number=form.cleaned_data['identification_number'],
            first_name=form.cleaned_data['first_name'],
            last_name=form.cleaned_data['last_name'],
            phone_number=form.cleaned_data['phone_number'],
            accepted_terms=form.cleaned_data['accepted_terms'],
            authorize_info_sending=form.cleaned_data['authorize_info_sending'],
            created_by=None,
        )
        prospect.origins.add(origin)

    if should_trigger_celery_task(prospect):
        process_prospect.delay(prospect.id)

    wa_number = (os.getenv('EMBED_WHATSAPP_NUMBER') or '').strip()
    wa_message = (os.getenv('EMBED_WHATSAPP_MESSAGE') or '').strip()
    if wa_number and wa_message:
        wa_url = f"https://wa.me/{wa_number}?text={quote(wa_message)}"
        return render(
            request,
            'voters/embed_redirect_whatsapp.html',
            {'wa_url': wa_url},
        )

    return render(
        request,
        'voters/embed_prospect_form.html',
        {'form': EmbedProspectForm(), 'success': True},
    )
