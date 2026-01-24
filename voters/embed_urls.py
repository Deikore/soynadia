"""
URLs para vistas embebibles (formularios en iframe, GoDaddy, etc.).
"""
from django.urls import path
from . import embed_views

urlpatterns = [
    path('prospectos/', embed_views.embed_prospect_form),
]
