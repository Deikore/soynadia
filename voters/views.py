from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from .models import Prospect
from .forms import ProspectForm, ProspectSearchForm


@login_required
def dashboard(request):
    """
    Vista del dashboard principal.
    """
    total_prospects = Prospect.objects.count()
    recent_prospects = Prospect.objects.all()[:5]
    
    context = {
        'total_prospects': total_prospects,
        'recent_prospects': recent_prospects,
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
    paginator = Paginator(prospects, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'search_form': search_form,
        'page_obj': page_obj,
        'prospects': page_obj,
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
    context = {
        'prospect': prospect,
    }
    return render(request, 'voters/prospect_detail.html', context)


@login_required
def prospect_update(request, pk):
    """
    Vista para actualizar un prospecto existente.
    """
    prospect = get_object_or_404(Prospect, pk=pk)
    
    if request.method == 'POST':
        form = ProspectForm(request.POST, instance=prospect)
        if form.is_valid():
            form.save()
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
    """
    prospect = get_object_or_404(Prospect, pk=pk)
    
    if request.method == 'POST':
        prospect.delete()
        messages.success(request, _('Prospecto eliminado exitosamente.'))
        return redirect('voters:prospect_list')
    
    context = {
        'prospect': prospect,
    }
    return render(request, 'voters/prospect_confirm_delete.html', context)
