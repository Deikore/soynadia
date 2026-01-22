from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import ProspectViewSet

router = DefaultRouter()
router.register(r'prospects', ProspectViewSet, basename='prospect')

urlpatterns = [
    path('', include(router.urls)),
]
