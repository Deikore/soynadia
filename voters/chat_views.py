"""
Vistas para la sección de chat de WhatsApp.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Prefetch
from django.http import JsonResponse

from .models import WhatsAppAccount, WhatsAppMessage
from .whatsapp_service import send_whatsapp_text_message


@login_required
def chat_conversation_list(request):
    """
    Lista de conversaciones agrupadas por cuentas WhatsApp.
    Muestra cuentas con al menos un mensaje o con opt-in activo.
    """
    accounts = WhatsAppAccount.objects.filter(
        Q(messages__isnull=False) | Q(optin_whatsapp=True)
    ).distinct().select_related('prospect').prefetch_related(
        Prefetch(
            'messages',
            queryset=WhatsAppMessage.objects.order_by('-received_at'),
        )
    ).order_by('-updated_at')

    # Construir lista con último mensaje para cada cuenta
    conversations = []
    for account in accounts:
        last_msg = account.messages.first()
        display_name = (
            account.prospect.get_full_name()
            if account.prospect
            else account.phone_number
        )
        conversations.append({
            'account': account,
            'last_message': last_msg,
            'display_name': display_name,
        })

    context = {
        'conversations': conversations,
    }
    return render(request, 'voters/chat_list.html', context)


@login_required
def chat_conversation_detail(request, account_id):
    """
    Detalle de una conversación con un número WhatsApp.
    Muestra mensajes y permite enviar nuevos.
    """
    account = get_object_or_404(WhatsAppAccount, pk=account_id)

    # Mensajes por número (incluye los que no tengan whatsapp_account asociado)
    msg_list = WhatsAppMessage.objects.filter(
        phone_number_normalized=account.phone_number
    ).order_by('received_at')

    display_name = (
        account.prospect.get_full_name()
        if account.prospect
        else account.phone_number
    )
    can_send = account.optin_whatsapp

    form_error = None
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.accepts('application/json')
    )

    # Procesar envío de mensaje
    if request.method == 'POST' and can_send:
        body = (request.POST.get('body') or '').strip()
        if body:
            if len(body) > 4000:
                form_error = 'El mensaje no puede exceder 4000 caracteres.'
            else:
                success, result = send_whatsapp_text_message(
                    account.phone_number,
                    body,
                )
                if success:
                    if is_ajax:
                        msg = WhatsAppMessage.objects.get(message_sid=result)
                        return JsonResponse({
                            'success': True,
                            'message': {
                                'body': msg.body,
                                'received_at': msg.received_at.strftime('%d/%m/%Y %H:%M'),
                                'event_type': msg.event_type,
                            },
                        })
                    return redirect('voters:chat_conversation', account_id=account_id)
                else:
                    form_error = f'Error al enviar: {result}'
        else:
            form_error = 'El mensaje no puede estar vacío.'

        if is_ajax and form_error:
            return JsonResponse({'success': False, 'error': form_error})

    context = {
        'account': account,
        'chat_messages': msg_list,
        'display_name': display_name,
        'can_send': can_send,
        'form_error': form_error,
    }
    return render(request, 'voters/chat_conversation.html', context)
