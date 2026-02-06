from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse, HttpResponseBadRequest
from django.db import transaction
import csv
import io
from .models import Prospect, OriginProspect
from .forms import ProspectForm, ProspectSearchForm, BulkUploadForm, SMSFilterForm
from .utils import (
    should_trigger_celery_task,
    check_and_trigger_on_id_change,
    trigger_polling_station_consult,
    validate_and_normalize_phone,
    associate_whatsapp_account,
    normalize_digits_only,
    get_sms_filter_options,
    get_sms_prospects_queryset,
    get_prospects_with_valid_phone,
)
from .tasks import process_prospect
from .sms_providers import get_provider, get_available_providers


@login_required
def dashboard(request):
    """
    Vista del dashboard principal.
    """
    total_prospects = Prospect.objects.count()
    recent_prospects = Prospect.objects.all()[:5]
    
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
        'can_delete_prospects': can_delete,
        'can_edit_prospects': can_edit,
    }
    return render(request, 'voters/dashboard.html', context)


@login_required
def prospect_list(request):
    """
    Vista para listar y buscar prospectos.
    """
    search_form = ProspectSearchForm(request.GET)
    prospects = Prospect.objects.all()
    
    # Filtrar por búsqueda si se proporciona
    if search_form.is_valid():
        identification_number = search_form.cleaned_data.get('identification_number')
        full_name = (search_form.cleaned_data.get('full_name') or '').strip()
        if identification_number:
            prospects = prospects.filter(
                Q(identification_number__icontains=identification_number)
            )
        if full_name:
            prospects = prospects.filter(full_name__icontains=full_name)
    
    # Paginación
    paginator = Paginator(prospects, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Query string sin 'page' para enlaces de paginación
    get_copy = request.GET.copy()
    if 'page' in get_copy:
        get_copy.pop('page')
    query_string = get_copy.urlencode()
    
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
        'search_form': search_form,
        'page_obj': page_obj,
        'prospects': page_obj,
        'can_delete_prospects': can_delete,
        'can_edit_prospects': can_edit,
        'query_string': query_string,
    }
    return render(request, 'voters/prospect_list.html', context)


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
    """
    if request.method == 'POST':
        form = BulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            
            # Leer el archivo CSV
            try:
                # Intentar leer con diferentes encodings
                content = csv_file.read()
                try:
                    content_str = content.decode('utf-8-sig')  # UTF-8 con BOM
                except UnicodeDecodeError:
                    try:
                        content_str = content.decode('utf-8')
                    except UnicodeDecodeError:
                        content_str = content.decode('latin-1')
                
                # Detectar el delimitador (punto y coma o coma)
                # Leer las primeras líneas para detectar el delimitador más común
                lines = content_str.split('\n')[:3]  # Primeras 3 líneas
                semicolon_count = sum(line.count(';') for line in lines if line.strip())
                comma_count = sum(line.count(',') for line in lines if line.strip())
                
                # Usar el delimitador que aparezca más veces
                # Si ambos tienen la misma cantidad, preferir punto y coma
                delimiter = ';' if semicolon_count >= comma_count else ','
                
                # Leer CSV con el delimitador detectado
                csv_reader = csv.DictReader(io.StringIO(content_str), delimiter=delimiter)
                
                # Validar encabezados requeridos
                required_headers = ['full_name', 'phone_number', 'origin']
                optional_headers = ['identification_number']
                if not csv_reader.fieldnames:
                    messages.error(request, _('El archivo CSV está vacío o no tiene encabezados válidos.'))
                    form = BulkUploadForm()
                    return render(request, 'voters/prospect_bulk_upload.html', {'form': form})
                
                if not all(header in csv_reader.fieldnames for header in required_headers):
                    messages.error(request, _('El archivo CSV debe contener los siguientes encabezados: full_name, phone_number, origin. El campo identification_number es opcional.'))
                    form = BulkUploadForm()
                    return render(request, 'voters/prospect_bulk_upload.html', {'form': form})
                
                # Procesar cada fila
                results = {
                    'total': 0,
                    'created': 0,
                    'updated': 0,
                    'errors': []
                }
                prospect_ids_to_process = []
                
                with transaction.atomic():
                    for row_num, row in enumerate(csv_reader, start=2):  # Empezar en 2 (después del encabezado)
                        results['total'] += 1
                        row_errors = []
                        
                        # Validar campos obligatorios
                        identification_number_raw = row.get('identification_number', '').strip()
                        full_name = row.get('full_name', '').strip()
                        phone_number = row.get('phone_number', '').strip()
                        origin_name = row.get('origin', '').strip()
                        
                        # Normalizar identification_number: eliminar todos los caracteres no numéricos
                        identification_number = None
                        if identification_number_raw:
                            identification_number_normalized = normalize_digits_only(identification_number_raw)
                            identification_number = identification_number_normalized if identification_number_normalized else None
                        if not full_name:
                            row_errors.append(_('full_name es obligatorio'))
                        if not origin_name:
                            row_errors.append(_('origin es obligatorio'))
                        
                        if row_errors:
                            results['errors'].append({
                                'row': row_num,
                                'identification_number': identification_number or '-',
                                'errors': row_errors
                            })
                            continue
                        
                        # Validar y normalizar phone_number si existe
                        normalized_phone = None
                        if phone_number:
                            try:
                                normalized_phone = validate_and_normalize_phone(phone_number)
                            except ValidationError as e:
                                row_errors.append(str(e))
                                results['errors'].append({
                                    'row': row_num,
                                    'identification_number': identification_number,
                                    'errors': row_errors
                                })
                                continue
                        
                        try:
                            # Buscar o crear el origin
                            origin, created = OriginProspect.objects.get_or_create(
                                name=origin_name,
                                defaults={
                                    'description': f'Origen creado desde carga masiva',
                                    'is_active': True
                                }
                            )
                            
                            # Buscar si el prospecto ya existe
                            prospect = None
                            old_id = None
                            
                            if identification_number:
                                # Si hay identification_number, buscar por ese campo
                                try:
                                    prospect = Prospect.objects.get(identification_number=identification_number)
                                    old_id = prospect.identification_number
                                except Prospect.DoesNotExist:
                                    pass
                            elif normalized_phone:
                                # Si no hay identification_number pero hay phone_number, buscar por phone_number
                                try:
                                    prospect = Prospect.objects.filter(
                                        phone_number=normalized_phone,
                                        identification_number__isnull=True
                                    ).first()
                                    if prospect:
                                        old_id = prospect.identification_number
                                except Exception:
                                    pass
                            
                            if prospect:
                                # Prospecto existe: actualizar campos y agregar origin
                                prospect.full_name = full_name
                                if normalized_phone is not None:
                                    prospect.phone_number = normalized_phone
                                if identification_number:
                                    prospect.identification_number = identification_number
                                prospect.save()
                                prospect.origins.add(origin)
                                
                                # Verificar y asociar WhatsAppAccount si hay match
                                associate_whatsapp_account(prospect)
                                
                                # Recopilar ID para disparar tarea después de la transacción
                                result = check_and_trigger_on_id_change(prospect, old_id, trigger_task=False)
                                if result:
                                    prospect_ids_to_process.append(result if isinstance(result, int) else prospect.id)
                                else:
                                    result2 = trigger_polling_station_consult(prospect, trigger_task=False)
                                    if result2:
                                        prospect_ids_to_process.append(result2 if isinstance(result2, int) else prospect.id)
                                results['updated'] += 1
                            else:
                                # Prospecto no existe: crear nuevo
                                prospect = Prospect.objects.create(
                                    identification_number=identification_number,
                                    full_name=full_name,
                                    phone_number=normalized_phone,
                                    created_by=request.user
                                )
                                prospect.origins.add(origin)
                                
                                # Verificar y asociar WhatsAppAccount si hay match
                                associate_whatsapp_account(prospect)
                                
                                # Recopilar ID para disparar tarea después de la transacción
                                if should_trigger_celery_task(prospect):
                                    prospect_ids_to_process.append(prospect.id)
                                results['created'] += 1
                                
                        except Exception as e:
                            row_errors.append(str(e))
                            results['errors'].append({
                                'row': row_num,
                                'identification_number': identification_number,
                                'errors': row_errors
                            })
                
                # Disparar tareas de Celery después de que la transacción se haya confirmado
                for prospect_id in prospect_ids_to_process:
                    process_prospect.delay(prospect_id)
                
                # Mostrar mensajes de resultado
                if results['created'] > 0:
                    messages.success(request, _('Se crearon {} prospectos exitosamente.').format(results['created']))
                if results['updated'] > 0:
                    messages.success(request, _('Se actualizaron {} prospectos exitosamente.').format(results['updated']))
                if results['errors']:
                    messages.warning(request, _('Se encontraron {} errores durante la carga.').format(len(results['errors'])))
                
                context = {
                    'form': BulkUploadForm(),
                    'results': results,
                }
                return render(request, 'voters/prospect_bulk_upload.html', context)
                
            except Exception as e:
                messages.error(request, _('Error al procesar el archivo CSV: {}').format(str(e)))
        else:
            messages.error(request, _('Por favor, corrija los errores en el formulario.'))
    else:
        form = BulkUploadForm()
    
    context = {
        'form': form,
    }
    return render(request, 'voters/prospect_bulk_upload.html', context)


@login_required
def download_csv_template(request):
    """
    Vista para descargar la plantilla CSV de ejemplo.
    """
    # Crear contenido CSV de ejemplo
    csv_content = 'identification_number;full_name;phone_number;origin\n'
    csv_content += '1234567890;Juan Pérez;3134000000;campaña_2024\n'
    csv_content += '9876543210;María García;3201234567;redes_sociales\n'
    csv_content += '5555555555;Carlos Rodríguez;;evento_publico\n'
    
    response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="plantilla_prospectos.csv"'
    return response


@login_required
@permission_required('voters.can_view_sms', raise_exception=True)
def sms_campaign(request):
    """
    Vista principal de la campaña SMS: filtros (departamento, municipio, origen),
    lista de prospectos con teléfono válido, panel de mensaje, contador y selector de proveedor.
    GET: muestra filtros, lista, textarea, contador y proveedor.
    POST: valida mensaje y filtros, encola tarea Celery para envío masivo.
    """
    dept_choices, muni_choices, origin_choices = get_sms_filter_options()

    if request.method == 'POST':
        department_values = request.POST.getlist('department')
        municipality_values = request.POST.getlist('municipality')
        origin_ids = [int(x) for x in request.POST.getlist('origin') if x.isdigit()]
        identification_values = request.POST.getlist('identification_number')
    else:
        department_values = request.GET.getlist('department')
        municipality_values = request.GET.getlist('municipality')
        origin_ids = [int(x) for x in request.GET.getlist('origin') if x.isdigit()]
        identification_values = request.GET.getlist('identification_number')

    identification_choices = [(v, v) for v in identification_values if v and str(v).strip()]
    filter_form = SMSFilterForm(
        request.GET,
        department_choices=dept_choices,
        municipality_choices=muni_choices,
        origin_choices=origin_choices,
        identification_choices=identification_choices,
    )

    qs = get_sms_prospects_queryset(
        department_values=department_values or None,
        municipality_values=municipality_values or None,
        origin_ids=origin_ids or None,
        identification_numbers=identification_values or None,
    )
    prospects_with_phone = get_prospects_with_valid_phone(qs)
    message_count = len(prospects_with_phone)

    if request.method == 'POST':
        body = (request.POST.get('message_body') or '').strip()
        provider_id = request.POST.get('provider_id') or 'twilio'
        if not body:
            messages.error(request, _('El mensaje no puede estar vacío.'))
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
                    department_values=department_values,
                    municipality_values=municipality_values,
                    origin_ids=origin_ids,
                    identification_numbers=identification_values,
                )
                messages.success(
                    request,
                    _('Se han encolado %(n)s mensajes para envío. El envío se realizará en segundo plano.') % {'n': message_count},
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
        'department_values': department_values,
        'municipality_values': municipality_values,
        'origin_ids': origin_ids,
        'identification_values': identification_values,
    }
    return render(request, 'voters/sms_campaign.html', context)
