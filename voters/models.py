from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import secrets
import json


class OriginProspect(models.Model):
    """
    Modelo para categorizar el origen de los prospectos.
    """
    name = models.CharField(
        _('nombre'),
        max_length=100,
        unique=True,
        help_text=_('Nombre del origen del prospecto')
    )
    description = models.TextField(
        _('descripción'),
        blank=True,
        help_text=_('Descripción opcional del origen')
    )
    created_at = models.DateTimeField(_('fecha de creación'), auto_now_add=True)
    is_active = models.BooleanField(_('activo'), default=True)
    enable_consult_polling_station = models.BooleanField(
        _('habilitar consulta puesto de votación'),
        default=False,
        help_text=_('Si está activo, se ejecutará una tarea asíncrona cuando se cree un prospecto con este origen')
    )

    class Meta:
        verbose_name = _('origen de prospecto')
        verbose_name_plural = _('orígenes de prospectos')
        ordering = ['name']

    def __str__(self):
        return self.name


class Prospect(models.Model):
    """
    Modelo para almacenar información de prospectos.
    """
    identification_number = models.CharField(
        _('número de identificación'),
        max_length=20,
        unique=True,
        db_index=True,
        null=True,
        blank=True,
        help_text=_('Número de identificación único del prospecto (opcional)')
    )
    full_name = models.CharField(_('nombre completo'), max_length=200)
    phone_number = models.CharField(_('teléfono'), max_length=20, blank=True, null=True)
    origins = models.ManyToManyField(
        OriginProspect,
        related_name='prospects',
        blank=True,
        verbose_name=_('orígenes'),
        help_text=_('Orígenes del prospecto')
    )
    created_at = models.DateTimeField(_('fecha de creación'), auto_now_add=True)
    updated_at = models.DateTimeField(_('fecha de actualización'), auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_('creado por'),
        related_name='prospects_created'
    )
    
    # Campos de información electoral (solo lectura)
    department = models.CharField(_('departamento'), max_length=100, blank=True, null=True)
    municipality = models.CharField(_('municipio'), max_length=100, blank=True, null=True)
    polling_station = models.CharField(_('puesto'), max_length=100, blank=True, null=True)
    polling_station_address = models.CharField(_('dirección mesa'), max_length=255, blank=True, null=True)
    table = models.CharField(_('mesa'), max_length=100, blank=True, null=True)
    notice = models.CharField(_('novedad'), max_length=255, blank=True, null=True)
    resolution = models.CharField(_('resolución'), max_length=255, blank=True, null=True)
    notice_date = models.CharField(_('fecha de novedad'), max_length=50, blank=True, null=True)
    polling_station_consulted = models.BooleanField(_('consulta puesto votación'), default=False, blank=True)

    accepted_terms = models.BooleanField(
        _('aceptación de términos'),
        default=False,
        blank=True,
        help_text=_('Aceptación de términos desde formulario embebido'),
    )
    authorize_info_sending = models.BooleanField(
        _('autorización envío de información'),
        default=False,
        blank=True,
        help_text=_('Autorización de envío de información desde formulario embebido'),
    )

    class Meta:
        verbose_name = _('prospecto')
        verbose_name_plural = _('prospectos')
        ordering = ['-created_at']
        permissions = [
            ('can_delete_prospects', 'Can delete prospects'),
            ('can_edit_prospects', 'Can edit prospects'),
            ('can_view_chat', 'Can view chat'),
            ('can_view_sms', 'Can view SMS'),
        ]

    def __str__(self):
        id_str = self.identification_number if self.identification_number else "Sin ID"
        return f'{id_str} - {self.get_full_name()}'

    def get_full_name(self):
        """Retorna el nombre completo del prospecto."""
        return self.full_name


class ProspectCommunication(models.Model):
    """
    Registro de comunicaciones enviadas a un prospecto (SMS, WhatsApp, etc.).
    """
    CHANNEL_SMS = 'sms'
    CHANNEL_WHATSAPP = 'whatsapp'
    CHANNEL_CHOICES = [
        (CHANNEL_SMS, _('SMS')),
        (CHANNEL_WHATSAPP, _('WhatsApp')),
    ]

    prospect = models.ForeignKey(
        Prospect,
        on_delete=models.CASCADE,
        related_name='sent_communications',
        verbose_name=_('prospecto'),
    )
    channel = models.CharField(
        _('canal'),
        max_length=20,
        choices=CHANNEL_CHOICES,
    )
    content = models.TextField(_('contenido'), help_text=_('Texto del mensaje enviado'))
    sent_at = models.DateTimeField(_('fecha de envío'), auto_now_add=True)
    provider_id = models.CharField(
        _('proveedor'),
        max_length=50,
        blank=True,
        default='',
        help_text=_('Identificador del proveedor usado (ej. twilio, onurix)'),
    )

    class Meta:
        verbose_name = _('comunicación enviada')
        verbose_name_plural = _('comunicaciones enviadas')
        ordering = ['-sent_at']

    def get_provider_display(self):
        """Devuelve la etiqueta legible del proveedor (Twilio, Onurix, etc.) o '—' si no hay."""
        if not self.provider_id or not self.provider_id.strip():
            return '—'
        from .sms_providers import get_available_providers
        labels = dict(get_available_providers())
        return labels.get(self.provider_id, self.provider_id)

    def __str__(self):
        return f'{self.get_channel_display()} a {self.prospect} ({self.sent_at})'


class ApiKey(models.Model):
    """
    Modelo para almacenar API keys para autenticación de la API REST.
    """
    key = models.CharField(_('key'), max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_('usuario'),
        related_name='api_keys'
    )
    name = models.CharField(_('nombre'), max_length=100, help_text=_('Nombre descriptivo para esta API key'))
    created_at = models.DateTimeField(_('fecha de creación'), auto_now_add=True)
    is_active = models.BooleanField(_('activa'), default=True)

    class Meta:
        verbose_name = _('API Key')
        verbose_name_plural = _('API Keys')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} - {self.user.email}'

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_key():
        """Genera una API key segura de 64 caracteres."""
        return secrets.token_urlsafe(48)[:64]


class WhatsAppAccount(models.Model):
    """
    Modelo para almacenar el estado de opt-in/opt-out de WhatsApp por número de teléfono.
    """
    phone_number = models.CharField(
        _('número de teléfono'),
        max_length=20,
        unique=True,
        db_index=True,
        help_text=_('Número de teléfono normalizado (solo dígitos, sin prefijos)')
    )
    prospect = models.ForeignKey(
        Prospect,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='whatsapp_accounts',
        verbose_name=_('prospecto'),
        help_text=_('Prospecto relacionado si el número de teléfono coincide')
    )
    optin_whatsapp = models.BooleanField(
        _('opt-in WhatsApp'),
        default=False,
        help_text=_('Si el usuario aceptó opt-in')
    )
    optout_whatsapp = models.BooleanField(
        _('opt-out WhatsApp'),
        default=False,
        help_text=_('Si el usuario rechazó opt-in')
    )
    created_at = models.DateTimeField(_('fecha de creación'), auto_now_add=True)
    updated_at = models.DateTimeField(_('fecha de actualización'), auto_now=True)

    class Meta:
        verbose_name = _('Cuenta WhatsApp')
        verbose_name_plural = _('Cuentas WhatsApp')
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.phone_number} - Opt-in: {self.optin_whatsapp}, Opt-out: {self.optout_whatsapp}'


class WhatsAppMessage(models.Model):
    """
    Modelo para almacenar todos los mensajes de WhatsApp (entrantes y salientes) desde Twilio.
    """
    DIRECTION_CHOICES = [
        ('inbound', 'Entrante'),
        ('outbound', 'Saliente'),
    ]
    EVENT_TYPE_CHOICES = [
        ('opt-in', 'Opt-in'),
        ('opt-out', 'Opt-out'),
        ('message', 'Mensaje'),
        ('status', 'Estado'),
    ]
    
    direction = models.CharField(
        _('dirección'),
        max_length=10,
        choices=DIRECTION_CHOICES,
        default='inbound',
        db_index=True,
        help_text=_('Entrante (del contacto) o saliente (enviado por nosotros)')
    )
    whatsapp_account = models.ForeignKey(
        WhatsAppAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages',
        verbose_name=_('cuenta WhatsApp'),
        help_text=_('Cuenta asociada para agrupación de conversaciones')
    )
    message_sid = models.CharField(
        _('Message SID'),
        max_length=34,
        unique=True,
        db_index=True,
        help_text=_('Identificador único del mensaje de Twilio')
    )
    account_sid = models.CharField(
        _('Account SID'),
        max_length=34,
        help_text=_('Identificador de la cuenta de Twilio')
    )
    messaging_service_sid = models.CharField(
        _('Messaging Service SID'),
        max_length=34,
        blank=True,
        null=True,
        help_text=_('Identificador del servicio de mensajería')
    )
    from_number = models.CharField(
        _('número remitente'),
        max_length=64,
        db_index=True,
        help_text=_('Número de WhatsApp del remitente (ej. whatsapp:+573001234567)')
    )
    to_number = models.CharField(
        _('número receptor'),
        max_length=64,
        help_text=_('Número receptor (ej. whatsapp:+573001234567)')
    )
    body = models.TextField(
        _('contenido del mensaje'),
        blank=True,
        help_text=_('Contenido del mensaje recibido')
    )
    profile_name = models.CharField(
        _('nombre del perfil'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Nombre del perfil de WhatsApp')
    )
    wa_id = models.CharField(
        _('WhatsApp ID'),
        max_length=64,
        blank=True,
        null=True,
        help_text=_('Identificador de WhatsApp del contacto')
    )
    event_type = models.CharField(
        _('tipo de evento'),
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
        default='message',
        help_text=_('Tipo de evento recibido')
    )
    phone_number_normalized = models.CharField(
        _('número de teléfono normalizado'),
        max_length=20,
        db_index=True,
        help_text=_('Número de teléfono normalizado (sin whatsapp:, sin prefijo país)')
    )
    received_at = models.DateTimeField(
        _('fecha de recepción'),
        auto_now_add=True,
        db_index=True
    )
    raw_data = models.JSONField(
        _('datos completos'),
        null=True,
        blank=True,
        help_text=_('Datos completos recibidos de Twilio para referencia')
    )

    class Meta:
        verbose_name = _('Mensaje WhatsApp')
        verbose_name_plural = _('Mensajes WhatsApp')
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['message_sid']),
            models.Index(fields=['from_number']),
            models.Index(fields=['phone_number_normalized']),
            models.Index(fields=['received_at']),
        ]

    def __str__(self):
        return f'{self.from_number} - {self.event_type} - {self.received_at.strftime("%Y-%m-%d %H:%M")}'
