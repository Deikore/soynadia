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
from .forms import ProspectForm, ProspectSearchForm, BulkUploadForm
from .utils import (
    should_trigger_celery_task,
    check_and_trigger_on_id_change,
    trigger_polling_station_consult,
    validate_and_normalize_phone,
)
from .tasks import process_prospect


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
        if identification_number:
            prospects = prospects.filter(
                Q(identification_number__icontains=identification_number)
            )
    
    # Paginación
    paginator = Paginator(prospects, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
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
            old_id = old_prospect.identification_number
            # Guardar el formulario y obtener la instancia actualizada
            prospect = form.save()
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
                required_headers = ['identification_number', 'first_name', 'last_name', 'phone_number', 'origin']
                if not csv_reader.fieldnames:
                    messages.error(request, _('El archivo CSV está vacío o no tiene encabezados válidos.'))
                    form = BulkUploadForm()
                    return render(request, 'voters/prospect_bulk_upload.html', {'form': form})
                
                if not all(header in csv_reader.fieldnames for header in required_headers):
                    messages.error(request, _('El archivo CSV debe contener los siguientes encabezados: identification_number, first_name, last_name, phone_number, origin'))
                    form = BulkUploadForm()
                    return render(request, 'voters/prospect_bulk_upload.html', {'form': form})
                
                # Procesar cada fila
                results = {
                    'total': 0,
                    'created': 0,
                    'updated': 0,
                    'errors': []
                }
                
                with transaction.atomic():
                    for row_num, row in enumerate(csv_reader, start=2):  # Empezar en 2 (después del encabezado)
                        results['total'] += 1
                        row_errors = []
                        
                        # Validar campos obligatorios
                        identification_number = row.get('identification_number', '').strip()
                        first_name = row.get('first_name', '').strip()
                        last_name = row.get('last_name', '').strip()
                        phone_number = row.get('phone_number', '').strip()
                        origin_name = row.get('origin', '').strip()
                        
                        if not identification_number:
                            row_errors.append(_('identification_number es obligatorio'))
                        if not first_name:
                            row_errors.append(_('first_name es obligatorio'))
                        if not last_name:
                            row_errors.append(_('last_name es obligatorio'))
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
                            try:
                                prospect = Prospect.objects.get(identification_number=identification_number)
                                # Prospecto existe: guardar identification_number anterior
                                # Nota: En bulk upload, el identification_number no cambia porque se busca por ese campo,
                                # pero guardamos old_id para verificar por si en el futuro se permite cambiar
                                old_id = prospect.identification_number
                                # Actualizar campos y agregar origin
                                prospect.first_name = first_name
                                prospect.last_name = last_name
                                if normalized_phone is not None:
                                    prospect.phone_number = normalized_phone
                                prospect.save()
                                prospect.origins.add(origin)
                                # Verificar si cambió el identification_number y disparar tarea si es necesario
                                if not check_and_trigger_on_id_change(prospect, old_id):
                                    # Si no cambió el ID o no disparó la tarea, verificar si debe consultar por otros campos
                                    trigger_polling_station_consult(prospect)
                                results['updated'] += 1
                            except Prospect.DoesNotExist:
                                # Prospecto no existe: crear nuevo
                                prospect = Prospect.objects.create(
                                    identification_number=identification_number,
                                    first_name=first_name,
                                    last_name=last_name,
                                    phone_number=normalized_phone,
                                    created_by=request.user
                                )
                                prospect.origins.add(origin)
                                # Verificar si se debe ejecutar la tarea de Celery
                                if should_trigger_celery_task(prospect):
                                    process_prospect.delay(prospect.id)
                                results['created'] += 1
                                
                        except Exception as e:
                            row_errors.append(str(e))
                            results['errors'].append({
                                'row': row_num,
                                'identification_number': identification_number,
                                'errors': row_errors
                            })
                
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
    csv_content = 'identification_number;first_name;last_name;phone_number;origin\n'
    csv_content += '1234567890;Juan;Pérez;3134000000;campaña_2024\n'
    csv_content += '9876543210;María;García;3201234567;redes_sociales\n'
    csv_content += '5555555555;Carlos;Rodríguez;;evento_publico\n'
    
    response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="plantilla_prospectos.csv"'
    return response
