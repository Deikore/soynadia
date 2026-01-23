from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Prospect, ApiKey, OriginProspect
from .utils import should_trigger_celery_task
from .tasks import process_prospect


@admin.register(OriginProspect)
class OriginProspectAdmin(admin.ModelAdmin):
    """
    Admin para el modelo OriginProspect.
    """
    list_display = ('name', 'description', 'is_active', 'enable_consult_polling_station', 'created_at')
    list_filter = ('is_active', 'enable_consult_polling_station', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)
    fieldsets = (
        (_('Información del Origen'), {
            'fields': ('name', 'description', 'is_active', 'enable_consult_polling_station')
        }),
        (_('Metadata'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Asegurar que el origen "manual" siempre exista
        OriginProspect.objects.get_or_create(
            name='manual',
            defaults={
                'description': 'Prospecto creado manualmente',
                'is_active': True
            }
        )


@admin.register(Prospect)
class ProspectAdmin(admin.ModelAdmin):
    """
    Admin para el modelo Prospect.
    """
    list_display = ('identification_number', 'first_name', 'last_name', 'phone_number', 'polling_station_consulted', 'created_at', 'display_created_by')
    list_filter = ('created_at', 'updated_at', 'origins', 'polling_station_consulted')
    search_fields = ('identification_number', 'first_name', 'last_name', 'phone_number')
    readonly_fields = (
        'created_at', 
        'updated_at', 
        'created_by',
        'department',
        'municipality',
        'polling_station',
        'polling_station_address',
        'table',
        'notice',
        'resolution',
        'notice_date',
        'polling_station_consulted',
    )
    filter_horizontal = ('origins',)
    fieldsets = (
        (_('Información del Prospecto'), {
            'fields': ('identification_number', 'first_name', 'last_name', 'phone_number', 'origins')
        }),
        (_('Información Electoral'), {
            'fields': (
                'department',
                'municipality',
                'polling_station',
                'polling_station_address',
                'table',
                'notice',
                'resolution',
                'notice_date',
                'polling_station_consulted',
            ),
            'classes': ('collapse',)
        }),
        (_('Metadata'), {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:  # Si es un nuevo objeto
            obj.created_by = request.user
            # Si no tiene orígenes asignados, asignar "manual" por defecto
            super().save_model(request, obj, form, change)
            if not obj.origins.exists():
                manual_origin, _ = OriginProspect.objects.get_or_create(
                    name='manual',
                    defaults={
                        'description': 'Prospecto creado manualmente',
                        'is_active': True
                    }
                )
                obj.origins.add(manual_origin)
            
            # Verificar si se debe ejecutar la tarea de Celery
            if should_trigger_celery_task(obj):
                process_prospect.delay(obj.id)
        else:
            super().save_model(request, obj, form, change)
    
    def has_change_permission(self, request, obj=None):
        """
        Solo usuarios del grupo "Puede Editar Prospectos" o con el permiso can_edit_prospects pueden editar.
        Los superusuarios siempre pueden editar.
        """
        if request.user.is_superuser:
            return True
        if request.user.has_perm('voters.can_edit_prospects'):
            return True
        if request.user.groups.filter(name='Puede Editar Prospectos').exists():
            return True
        return False
    
    def display_created_by(self, obj):
        """Muestra el nombre completo del usuario que creó el prospecto."""
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return '-'
    display_created_by.short_description = _('Creado Por')
    
    def has_delete_permission(self, request, obj=None):
        """
        Solo usuarios del grupo "Puede Eliminar Prospectos" o con el permiso can_delete_prospects pueden eliminar.
        Los superusuarios siempre pueden eliminar.
        """
        if request.user.is_superuser:
            return True
        if request.user.has_perm('voters.can_delete_prospects'):
            return True
        if request.user.groups.filter(name='Puede Eliminar Prospectos').exists():
            return True
        return False


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
