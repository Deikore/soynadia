from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Prospect, ApiKey


@admin.register(Prospect)
class ProspectAdmin(admin.ModelAdmin):
    """
    Admin para el modelo Prospect.
    """
    list_display = ('identification_number', 'first_name', 'last_name', 'phone_number', 'created_at', 'created_by')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('identification_number', 'first_name', 'last_name', 'phone_number')
    readonly_fields = ('created_at', 'updated_at', 'created_by')
    fieldsets = (
        (_('Información del Prospecto'), {
            'fields': ('identification_number', 'first_name', 'last_name', 'phone_number')
        }),
        (_('Metadata'), {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:  # Si es un nuevo objeto
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    """
    Admin para el modelo ApiKey.
    """
    list_display = ('name', 'user', 'key_preview', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'user__email', 'key')
    readonly_fields = ('key', 'created_at')
    fieldsets = (
        (_('Información de la API Key'), {
            'fields': ('name', 'user', 'key', 'is_active')
        }),
        (_('Metadata'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def key_preview(self, obj):
        """Muestra solo los primeros y últimos caracteres de la key."""
        if obj.key:
            return f'{obj.key[:8]}...{obj.key[-8:]}'
        return '-'
    key_preview.short_description = _('Key Preview')
