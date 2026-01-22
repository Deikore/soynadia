from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import PermissionDenied
from .models import Prospect, OriginProspect
from .forms import ProspectForm, ProspectSearchForm


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
            form.save_m2m()  # Guardar relaciones many-to-many
            
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
            form.save()
            form.save_m2m()  # Guardar relaciones many-to-many
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
