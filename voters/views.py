import re
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse, HttpResponseBadRequest, Http404, JsonResponse
from .models import Prospect, OriginProspect, BulkUploadJob
from .forms import ProspectForm, ProspectSearchForm, ProspectListFilterForm, BulkUploadForm, SMSFilterForm
from .utils import (
    should_trigger_celery_task,
    check_and_trigger_on_id_change,
    trigger_polling_station_consult,
    validate_and_normalize_phone,
    associate_whatsapp_account,
    get_sms_filter_options,
    get_sms_prospects_queryset,
    get_prospect_list_queryset,
    get_prospects_with_valid_phone,
)
from .tasks import process_prospect, process_bulk_upload
from .sms_providers import get_provider, get_available_providers, get_provider_ids_with_bulk_export

# Patrón para detectar emojis (rangos Unicode comunes de emojis y símbolos similares).
_SMS_EMOJI_PATTERN = re.compile(
    '['
    '\U0001F300-\U0001F9FF'  # Misc Symbols and Pictographs, Supplemental Symbols
    '\U0001F600-\U0001F64F'  # Emoticons
    '\U0001F1E0-\U0001F1FF'  # Flags
    '\u2600-\u26FF'          # Misc symbols
    '\u2700-\u27BF'          # Dingbats
    '\uFE00-\uFE0F'          # Variation selectors
    ']+',
    flags=re.UNICODE,
)


def _sms_contains_emoji(text):
    """Devuelve True si el texto contiene emojis (para validación de SMS)."""
    return bool(_SMS_EMOJI_PATTERN.search(text))


@login_required
def dashboard(request):
    """
    Vista del dashboard principal.
    """
    total_prospects = Prospect.objects.count()
    recent_prospects = Prospect.objects.all()[:5]
    prospects_by_origin = (
        OriginProspect.objects.filter(is_active=True)
        .annotate(prospect_count=Count('prospects'))
        .filter(prospect_count__gt=0)
        .order_by('-prospect_count')
    )
    
    # Verificar si el usuario puede eliminar prospectos
    can_delete = (
        request.user.is_superuser or
        request.user.has_perm('voters.can_delete_prospects') or
        request.user.groups.filter(name='Puede Eliminar Prospectos').exists()
    )
    
    # Verificar si el usuario puede editar prospectos
    can_edit = (
        request.user.is_superuser or
        request.user.has_perm('voters.can_edit_prospects') or
        request.user.groups.filter(name='Puede Editar Prospectos').exists()
    )
    
    context = {
        'total_prospects': total_prospects,
        'recent_prospects': recent_prospects,
        'prospects_by_origin': prospects_by_origin,
        'can_delete_prospects': can_delete,
        'can_edit_prospects': can_edit,
    }
    return render(request, 'voters/dashboard.html', context)


@login_required
def prospect_list(request):
    """
    Vista para listar y buscar prospectos con filtros por departamento,
    municipio, origen, número de cédula y nombre.
    """
    dept_choices, muni_choices, origin_choices, sexo_choices, enlace_choices = get_sms_filter_options()
    department_values = request.GET.getlist('department')
    municipality_values = request.GET.getlist('municipality')
    origin_ids = [int(x) for x in request.GET.getlist('origin') if x.isdigit()]
    identification_values = request.GET.getlist('identification_number')
    full_name_values = request.GET.getlist('full_name')
    sexo_values = request.GET.getlist('sexo')
    enlace_values = request.GET.getlist('enlace')
    identification_choices = [(v, v) for v in identification_values if v and str(v).strip()]
    full_name_choices = [(v, v) for v in full_name_values if v and str(v).strip()]

    filter_form = ProspectListFilterForm(
        request.GET,
        department_choices=dept_choices,
        municipality_choices=muni_choices,
        origin_choices=origin_choices,
        identification_choices=identification_choices,
        full_name_choices=full_name_choices,
        sexo_choices=sexo_choices,
        enlace_choices=enlace_choices,
    )
    prospects = get_prospect_list_queryset(
        department_values=department_values or None,
        municipality_values=municipality_values or None,
        origin_ids=origin_ids or None,
        identification_numbers=identification_values or None,
        full_name_values=full_name_values or None,
        sexo_values=sexo_values or None,
        enlace_values=enlace_values or None,
    )

    paginator = Paginator(prospects, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    get_copy = request.GET.copy()
    if 'page' in get_copy:
        get_copy.pop('page')
    query_string = get_copy.urlencode()

    can_delete = (
        request.user.is_superuser or
        request.user.has_perm('voters.can_delete_prospects') or
        request.user.groups.filter(name='Puede Eliminar Prospectos').exists()
    )
    can_edit = (
        request.user.is_superuser or
        request.user.has_perm('voters.can_edit_prospects') or
        request.user.groups.filter(name='Puede Editar Prospectos').exists()
    )

    context = {
        'filter_form': filter_form,
        'page_obj': page_obj,
        'prospects': page_obj,
        'can_delete_prospects': can_delete,
        'can_edit_prospects': can_edit,
        'query_string': query_string,
    }
    return render(request, 'voters/prospect_list.html', context)


@login_required
def prospect_export_excel(request):
    """
    Exporta los prospectos (con los mismos filtros que la lista) a un archivo Excel.
    La columna Orígenes lleva cada origen separado por comas.
    """
    from openpyxl import Workbook
    from io import BytesIO

    department_values = request.GET.getlist('department')
    municipality_values = request.GET.getlist('municipality')
    origin_ids = [int(x) for x in request.GET.getlist('origin') if x.isdigit()]
    identification_values = request.GET.getlist('identification_number')
    full_name_values = request.GET.getlist('full_name')
    sexo_values = request.GET.getlist('sexo')
    enlace_values = request.GET.getlist('enlace')

    qs = get_prospect_list_queryset(
        department_values=department_values or None,
        municipality_values=municipality_values or None,
        origin_ids=origin_ids or None,
        identification_numbers=identification_values or None,
        full_name_values=full_name_values or None,
        sexo_values=sexo_values or None,
        enlace_values=enlace_values or None,
    )

    headers = [
        'Número de identificación',
        'Nombre completo',
        'Teléfono',
        'Fecha de creación',
        'Fecha de actualización',
        'Departamento',
        'Municipio',
        'Puesto',
        'Dirección mesa',
        'Mesa',
        'Novedad',
        'Resolución',
        'Fecha novedad',
        'Puesto consultado',
        'Aceptación términos',
        'Autorización envío información',
        'Sexo',
        'Enlace',
        'Orígenes',
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = 'Prospectos'
    ws.append(headers)

    for p in qs:
        origins_str = ', '.join(p.origins.values_list('name', flat=True))
        row = [
            p.identification_number or '',
            p.full_name or '',
            p.phone_number or '',
            p.created_at.strftime('%Y-%m-%d %H:%M') if p.created_at else '',
            p.updated_at.strftime('%Y-%m-%d %H:%M') if p.updated_at else '',
            p.department or '',
            p.municipality or '',
            p.polling_station or '',
            p.polling_station_address or '',
            p.table or '',
            p.notice or '',
            p.resolution or '',
            p.notice_date or '',
            'Sí' if p.polling_station_consulted else 'No',
            'Sí' if p.accepted_terms else 'No',
            'Sí' if p.authorize_info_sending else 'No',
            p.sexo or '',
            p.enlace or '',
            origins_str,
        ]
        ws.append(row)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="prospectos.xlsx"'
    return response


@login_required
def prospect_create(request):
    """
    Vista para crear un nuevo prospecto.
    """
    if request.method == 'POST':
        form = ProspectForm(request.POST)
        if form.is_valid():
            prospect = form.save(commit=False)
            prospect.created_by = request.user
            prospect.save()
            
            # Si no tiene orígenes asignados, asignar "manual" por defecto
            if not prospect.origins.exists():
                manual_origin, created = OriginProspect.objects.get_or_create(
                    name='manual',
                    defaults={
                        'description': 'Prospecto creado manualmente',
                        'is_active': True
                    }
                )
                prospect.origins.add(manual_origin)
            
            # Verificar y asociar WhatsAppAccount si hay match
            associate_whatsapp_account(prospect)
            
            # Verificar si se debe ejecutar la tarea de Celery
            if should_trigger_celery_task(prospect):
                process_prospect.delay(prospect.id)
            
            messages.success(request, _('Prospecto creado exitosamente.'))
            return redirect('voters:prospect_list')
    else:
        form = ProspectForm()
    
    context = {
        'form': form,
        'title': _('Crear Prospecto'),
        'button_text': _('Crear'),
    }
    return render(request, 'voters/prospect_form.html', context)


@login_required
def prospect_detail(request, pk):
    """
    Vista para ver los detalles de un prospecto.
    """
    prospect = get_object_or_404(Prospect, pk=pk)
    
    # Verificar si el usuario puede eliminar prospectos
    can_delete = (
        request.user.is_superuser or
        request.user.has_perm('voters.can_delete_prospects') or
        request.user.groups.filter(name='Puede Eliminar Prospectos').exists()
    )
    
    # Verificar si el usuario puede editar prospectos
    can_edit = (
        request.user.is_superuser or
        request.user.has_perm('voters.can_edit_prospects') or
        request.user.groups.filter(name='Puede Editar Prospectos').exists()
    )
    
    context = {
        'prospect': prospect,
        'can_delete_prospects': can_delete,
        'can_edit_prospects': can_edit,
    }
    return render(request, 'voters/prospect_detail.html', context)


@login_required
def prospect_update(request, pk):
    """
    Vista para actualizar un prospecto existente.
    Solo usuarios con el permiso can_edit_prospects o en el grupo "Puede Editar Prospectos" pueden editar.
    Los superusuarios siempre pueden editar.
    """
    prospect = get_object_or_404(Prospect, pk=pk)
    
    # Verificar permisos
    can_edit = (
        request.user.is_superuser or
        request.user.has_perm('voters.can_edit_prospects') or
        request.user.groups.filter(name='Puede Editar Prospectos').exists()
    )
    
    if not can_edit:
        raise PermissionDenied("No tienes permiso para editar prospectos.")
    
    if request.method == 'POST':
        form = ProspectForm(request.POST, instance=prospect)
        if form.is_valid():
            # Obtener el identification_number anterior desde la base de datos antes de actualizar
            # Esto asegura que tenemos el valor real guardado, no el del formulario
            old_prospect = Prospect.objects.get(pk=pk)
            old_id = old_prospect.identification_number if old_prospect.identification_number else None
            # Guardar el formulario y obtener la instancia actualizada
            prospect = form.save()
            
            # Verificar y asociar WhatsAppAccount si hay match
            associate_whatsapp_account(prospect)
            
            # Verificar si cambió el identification_number y disparar tarea si es necesario
            if not check_and_trigger_on_id_change(prospect, old_id):
                # Si no cambió el ID o no disparó la tarea, verificar si debe consultar por otros campos
                trigger_polling_station_consult(prospect)
            messages.success(request, _('Prospecto actualizado exitosamente.'))
            return redirect('voters:prospect_detail', pk=pk)
    else:
        form = ProspectForm(instance=prospect)
    
    context = {
        'form': form,
        'prospect': prospect,
        'title': _('Editar Prospecto'),
        'button_text': _('Actualizar'),
    }
    return render(request, 'voters/prospect_form.html', context)


@login_required
def prospect_delete(request, pk):
    """
    Vista para eliminar un prospecto.
    Solo usuarios con el permiso can_delete_prospects o en el grupo "Puede Eliminar Prospectos" pueden eliminar.
    Los superusuarios siempre pueden eliminar.
    """
    prospect = get_object_or_404(Prospect, pk=pk)
    
    # Verificar permisos
    can_delete = (
        request.user.is_superuser or
        request.user.has_perm('voters.can_delete_prospects') or
        request.user.groups.filter(name='Puede Eliminar Prospectos').exists()
    )
    
    if not can_delete:
        raise PermissionDenied("No tienes permiso para eliminar prospectos.")
    
    if request.method == 'POST':
        prospect.delete()
        messages.success(request, _('Prospecto eliminado exitosamente.'))
        return redirect('voters:prospect_list')
    
    context = {
        'prospect': prospect,
    }
    return render(request, 'voters/prospect_confirm_delete.html', context)


@login_required
def prospect_bulk_upload(request):
    """
    Vista para cargar prospectos de manera masiva desde un archivo CSV.
    POST: valida el archivo, crea un BulkUploadJob, encola la tarea Celery y redirige con job_id.
    GET con job_id: muestra estado (procesando) o resultados (completado/fallido).
    GET sin job_id: muestra el formulario de subida.
    """
    job_id = request.GET.get('job_id')
    if job_id:
        job = get_object_or_404(BulkUploadJob, pk=job_id, user=request.user)
        if job.status == BulkUploadJob.STATUS_COMPLETED:
            context = {
                'form': BulkUploadForm(),
                'results': job.result_json,
                'job_id': job_id,
            }
            return render(request, 'voters/prospect_bulk_upload.html', context)
        if job.status == BulkUploadJob.STATUS_FAILED:
            messages.error(request, _('La carga falló: {}').format(job.error_message))
            return redirect('voters:prospect_bulk_upload')
        # pending o processing: mostrar "Procesando..." con recarga
        context = {
            'form': BulkUploadForm(),
            'job_id': job_id,
            'job_status': job.status,
        }
        return render(request, 'voters/prospect_bulk_upload.html', context)

    if request.method == 'POST':
        form = BulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            job = BulkUploadJob.objects.create(
                user=request.user,
                file=csv_file,
                status=BulkUploadJob.STATUS_PENDING,
            )
            process_bulk_upload.delay(job.id)
            messages.success(request, _('La carga se está procesando. Esta página se actualizará con los resultados.'))
            url = reverse('voters:prospect_bulk_upload') + '?job_id=' + str(job.id)
            return redirect(url)
        messages.error(request, _('Por favor, corrija los errores en el formulario.'))
    else:
        form = BulkUploadForm()

    context = {'form': form}
    return render(request, 'voters/prospect_bulk_upload.html', context)


@login_required
def download_csv_template(request):
    """
    Vista para descargar la plantilla CSV de ejemplo.
    """
    # Crear contenido CSV de ejemplo
    csv_content = 'identification_number;full_name;phone_number;origin;sexo;enlace\n'
    csv_content += '1234567890;Juan Pérez;3134000000;campaña_2024;;\n'
    csv_content += '9876543210;María García;3201234567;redes_sociales,evento_publico;;\n'
    csv_content += '5555555555;Carlos Rodríguez;;evento_publico;;\n'
    
    response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="plantilla_prospectos.csv"'
    return response


@login_required
@permission_required('voters.can_view_sms', raise_exception=True)
def download_sms_bulk_export(request, provider_id):
    """
    Genera y devuelve un Excel con teléfonos (filtros aplicados) y el mensaje del textarea.
    Una fila por prospecto con teléfono válido; columnas Telefonos y Mensaje.
    Solo para proveedores con bulk_export_slug (p. ej. Onurix).
    """
    from openpyxl import Workbook
    from io import BytesIO

    if provider_id not in get_provider_ids_with_bulk_export():
        raise Http404('Proveedor sin descarga masiva')

    if request.method == 'POST':
        data = request.POST
    else:
        data = request.GET

    department_values = data.getlist('department')
    municipality_values = data.getlist('municipality')
    origin_ids = [int(x) for x in data.getlist('origin') if x.isdigit()]
    identification_values = data.getlist('identification_number')
    message_body = (data.get('message_body') or '').strip()

    qs = get_sms_prospects_queryset(
        department_values=department_values or None,
        municipality_values=municipality_values or None,
        origin_ids=origin_ids or None,
        identification_numbers=identification_values or None,
    )
    prospects_with_phone = get_prospects_with_valid_phone(qs)

    # Formatear teléfono según proveedor (Onurix: 57 + 10 dígitos)
    if provider_id == 'onurix':
        from .sms_providers.onurix_provider import _format_phone as format_phone_onurix
        def format_phone(normalized):
            return format_phone_onurix(normalized) or normalized
    else:
        def format_phone(normalized):
            return normalized

    wb = Workbook()
    ws = wb.active
    ws.title = 'SMS masivo'
    ws.append(['Telefonos', 'Mensaje'])

    for _prospect, phone_normalized in prospects_with_phone:
        phone_export = format_phone(phone_normalized)
        if phone_export:
            ws.append([phone_export, message_body])

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f'sms_masivo_{provider_id}.xlsx'
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@permission_required('voters.can_view_sms', raise_exception=True)
def sms_onurix_balance(request):
    """
    GET: devuelve el saldo de créditos Onurix en JSON para la confirmación de envío SMS.
    """
    if request.method != 'GET':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    provider = get_provider('onurix')
    if not provider:
        return JsonResponse({'success': False, 'error': 'Proveedor Onurix no disponible'}, status=400)
    if not hasattr(provider, 'get_balance'):
        return JsonResponse({'success': False, 'error': 'Consulta de saldo no disponible'}, status=400)
    success, balance = provider.get_balance()
    if not success or balance is None:
        return JsonResponse({'success': False, 'error': 'No se pudo verificar el saldo'}, status=200)
    return JsonResponse({'success': True, 'balance': balance})


@login_required
@permission_required('voters.can_view_sms', raise_exception=True)
def sms_campaign(request):
    """
    Vista principal de la campaña SMS: filtros (departamento, municipio, origen),
    lista de prospectos con teléfono válido, panel de mensaje, contador y selector de proveedor.
    GET: muestra filtros, lista, textarea, contador y proveedor.
    POST: valida mensaje y filtros, encola tarea Celery para envío masivo.
    """
    dept_choices, muni_choices, origin_choices, sexo_choices, enlace_choices = get_sms_filter_options()

    if request.method == 'POST':
        department_values = request.POST.getlist('department')
        municipality_values = request.POST.getlist('municipality')
        origin_ids = [int(x) for x in request.POST.getlist('origin') if x.isdigit()]
        identification_values = request.POST.getlist('identification_number')
        sexo_values = request.POST.getlist('sexo')
        enlace_values = request.POST.getlist('enlace')
    else:
        department_values = request.GET.getlist('department')
        municipality_values = request.GET.getlist('municipality')
        origin_ids = [int(x) for x in request.GET.getlist('origin') if x.isdigit()]
        identification_values = request.GET.getlist('identification_number')
        sexo_values = request.GET.getlist('sexo')
        enlace_values = request.GET.getlist('enlace')

    identification_choices = [(v, v) for v in identification_values if v and str(v).strip()]
    filter_form = SMSFilterForm(
        request.GET,
        department_choices=dept_choices,
        municipality_choices=muni_choices,
        origin_choices=origin_choices,
        identification_choices=identification_choices,
        sexo_choices=sexo_choices,
        enlace_choices=enlace_choices,
    )

    qs = get_sms_prospects_queryset(
        department_values=department_values or None,
        municipality_values=municipality_values or None,
        origin_ids=origin_ids or None,
        identification_numbers=identification_values or None,
        sexo_values=sexo_values or None,
        enlace_values=enlace_values or None,
    )
    prospects_with_phone = get_prospects_with_valid_phone(qs)
    message_count = len(prospects_with_phone)

    if request.method == 'POST':
        body = (request.POST.get('message_body') or '').strip()
        provider_id = request.POST.get('provider_id') or 'onurix'
        if not body:
            messages.error(request, _('El mensaje no puede estar vacío.'))
        elif len(body) > 160:
            messages.error(request, _('El mensaje no puede superar 160 caracteres.'))
        elif _sms_contains_emoji(body):
            messages.error(request, _('El mensaje no puede contener emojis.'))
        elif message_count == 0:
            messages.error(request, _('No hay prospectos con teléfono válido para los filtros seleccionados.'))
        else:
            provider = get_provider(provider_id)
            if not provider:
                messages.error(request, _('Proveedor de SMS no válido.'))
            else:
                from .tasks import send_sms_campaign
                send_sms_campaign.delay(
                    provider_id=provider_id,
                    body=body,
                    department_values=department_values or None,
                    municipality_values=municipality_values or None,
                    origin_ids=origin_ids or None,
                    identification_numbers=identification_values or None,
                    sexo_values=sexo_values or None,
                    enlace_values=enlace_values or None,
                )
                messages.success(
                    request,
                    _('Se ha encolado el envío de %(n)s mensajes. El envío se realizará en segundo plano.') % {'n': message_count},
                )
                return redirect('voters:sms_campaign')

    paginator = Paginator(qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'filter_form': filter_form,
        'page_obj': page_obj,
        'prospects': page_obj,
        'message_count': message_count,
        'sms_providers': get_available_providers(),
        'providers_with_bulk_export': get_provider_ids_with_bulk_export(),
        'department_values': department_values,
        'municipality_values': municipality_values,
        'origin_ids': origin_ids,
        'identification_values': identification_values,
        'sexo_values': sexo_values,
        'enlace_values': enlace_values,
    }
    return render(request, 'voters/sms_campaign.html', context)
