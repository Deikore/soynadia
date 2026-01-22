from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils.translation import gettext_lazy as _
from .models import Prospect
from .serializers import ProspectSerializer
from .authentication import ApiKeyAuthentication


class ProspectViewSet(viewsets.ModelViewSet):
    """
    ViewSet para el modelo Prospect.
    
    Permite crear, listar, actualizar y eliminar prospectos.
    Requiere autenticación mediante API Key.
    """
    queryset = Prospect.objects.all()
    serializer_class = ProspectSerializer
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Permite filtrar por identification_number mediante query params.
        Ejemplo: /api/prospects/?identification_number=123456
        """
        queryset = super().get_queryset()
        identification_number = self.request.query_params.get('identification_number', None)
        
        if identification_number:
            queryset = queryset.filter(identification_number__icontains=identification_number)
        
        return queryset

    def perform_create(self, serializer):
        """
        Guardar el usuario que creó el prospecto.
        """
        serializer.save(created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        """
        Crear un nuevo prospecto.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            {
                'message': _('Prospecto creado exitosamente'),
                'data': serializer.data
            },
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    def list(self, request, *args, **kwargs):
        """
        Listar todos los prospectos.
        """
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'count': queryset.count(),
            'results': serializer.data
        })

    def retrieve(self, request, *args, **kwargs):
        """
        Obtener un prospecto específico.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        """
        Actualizar un prospecto existente.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            'message': _('Prospecto actualizado exitosamente'),
            'data': serializer.data
        })

    def destroy(self, request, *args, **kwargs):
        """
        Eliminar un prospecto.
        """
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {'message': _('Prospecto eliminado exitosamente')},
            status=status.HTTP_204_NO_CONTENT
        )
