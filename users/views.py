from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from .forms import CustomLoginForm


class CustomLoginView(LoginView):
    """
    Custom login view that uses email-based authentication.
    """
    form_class = CustomLoginForm
    template_name = 'users/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        return reverse_lazy('voters:dashboard')


class CustomLogoutView(View):
    """
    Custom logout view.
    Cierra la sesión y redirige al login.
    """
    def post(self, request):
        logout(request)
        return redirect('users:login')
    
    def get(self, request):
        # También permitir GET para compatibilidad
        logout(request)
        return redirect('users:login')
