from rest_framework import authentication
from rest_framework import exceptions
from django.utils.translation import gettext_lazy as _
from .models import ApiKey


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """
    Autenticación personalizada basada en API Key.
    
    Los clientes deben incluir un header:
    Authorization: Api-Key <api_key_value>
    """
    keyword = 'Api-Key'

    def authenticate(self, request):
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth:
            return None

        try:
            keyword, key = auth.split()
        except ValueError:
            raise exceptions.AuthenticationFailed(_('Formato de autorización inválido'))

        if keyword != self.keyword:
            return None

        return self.authenticate_credentials(key)

    def authenticate_credentials(self, key):
        try:
            api_key = ApiKey.objects.select_related('user').get(key=key, is_active=True)
        except ApiKey.DoesNotExist:
            raise exceptions.AuthenticationFailed(_('API Key inválida o inactiva'))

        if not api_key.user.is_active:
            raise exceptions.AuthenticationFailed(_('Usuario inactivo'))

        return (api_key.user, api_key)

    def authenticate_header(self, request):
        return self.keyword
