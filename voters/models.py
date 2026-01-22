from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import secrets


class Prospect(models.Model):
    """
    Modelo para almacenar información de prospectos.
    """
    identification_number = models.CharField(
        _('número de identificación'),
        max_length=20,
        unique=True,
        db_index=True,
        help_text=_('Número de identificación único del prospecto')
    )
    first_name = models.CharField(_('nombre'), max_length=100)
    last_name = models.CharField(_('apellido'), max_length=100)
    phone_number = models.CharField(_('teléfono'), max_length=20)
    created_at = models.DateTimeField(_('fecha de creación'), auto_now_add=True)
    updated_at = models.DateTimeField(_('fecha de actualización'), auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_('creado por'),
        related_name='prospects_created'
    )

    class Meta:
        verbose_name = _('prospecto')
        verbose_name_plural = _('prospectos')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.identification_number} - {self.get_full_name()}'

    def get_full_name(self):
        """Retorna el nombre completo del prospecto."""
        return f'{self.first_name} {self.last_name}'.strip()


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
