from django.urls import path
from . import views
from . import webhook_views
from . import chat_views

app_name = 'voters'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('prospects/', views.prospect_list, name='prospect_list'),
    path('prospects/create/', views.prospect_create, name='prospect_create'),
    path('prospects/bulk-upload/', views.prospect_bulk_upload, name='prospect_bulk_upload'),
    path('prospects/bulk-upload/template/', views.download_csv_template, name='download_csv_template'),
    path('prospects/<int:pk>/', views.prospect_detail, name='prospect_detail'),
    path('prospects/<int:pk>/edit/', views.prospect_update, name='prospect_update'),
    path('prospects/<int:pk>/delete/', views.prospect_delete, name='prospect_delete'),
    path('webhooks/twilio/whatsapp/', webhook_views.twilio_whatsapp_webhook, name='twilio_whatsapp_webhook'),
    path('chat/', chat_views.chat_conversation_list, name='chat_list'),
    path('chat/<int:account_id>/', chat_views.chat_conversation_detail, name='chat_conversation'),
]
