from django.urls import path
from . import views

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
]
