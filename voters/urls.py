from django.urls import path
from . import views
from . import webhook_views
from . import chat_views

app_name = 'voters'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('prospects/', views.prospect_list, name='prospect_list'),
    path('prospects/export/', views.prospect_export_excel, name='prospect_export_excel'),
    path('prospects/create/', views.prospect_create, name='prospect_create'),
    path('prospects/bulk-upload/', views.prospect_bulk_upload, name='prospect_bulk_upload'),
    path('prospects/bulk-upload/template/', views.download_csv_template, name='download_csv_template'),
    path('prospects/<int:pk>/', views.prospect_detail, name='prospect_detail'),
    path('prospects/<int:pk>/edit/', views.prospect_update, name='prospect_update'),
    path('prospects/<int:pk>/delete/', views.prospect_delete, name='prospect_delete'),
    path('webhooks/twilio/whatsapp/', webhook_views.twilio_whatsapp_webhook, name='twilio_whatsapp_webhook'),
    path('chat/', chat_views.chat_conversation_list, name='chat_list'),
    path('chat/<int:account_id>/', chat_views.chat_conversation_detail, name='chat_conversation'),
    path('resumen/', views.resumen, name='resumen'),
    path('resumen/export/', views.resumen_export_excel, name='resumen_export_excel'),
    path('sms/', views.sms_campaign, name='sms_campaign'),
    path('sms/onurix-balance/', views.sms_onurix_balance, name='sms_onurix_balance'),
    path('sms/bulk-export/<str:provider_id>/', views.download_sms_bulk_export, name='download_sms_bulk_export'),
]
