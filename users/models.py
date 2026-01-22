from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from .managers import CustomUserManager


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model that uses email instead of username for authentication.
    """
    email = models.EmailField(_('correo electrónico'), unique=True)
    first_name = models.CharField(_('nombre'), max_length=150, blank=True)
    last_name = models.CharField(_('apellido'), max_length=150, blank=True)
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Designa si el usuario puede acceder al sitio de administración.'),
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_(
            'Designa si este usuario debe ser tratado como activo. '
            'Deseleccione esto en lugar de eliminar cuentas.'
        ),
    )
    date_joined = models.DateTimeField(_('fecha de registro'), auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        verbose_name = _('usuario')
        verbose_name_plural = _('usuarios')

    def __str__(self):
        return self.email

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = f'{self.first_name} {self.last_name}'
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name
