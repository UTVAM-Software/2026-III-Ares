"""
Configuración principal de URLs de ARES.
Incluye rutas para autenticación, Centro de Operaciones (core),
módulos de telemetría y administración de Django Auth.
"""
from django.contrib import admin
from django.urls import path, include
from usuarios.views import AresLoginView, AresLogoutView

urlpatterns = [
    # Panel nativo de Django
    path('admin/', admin.site.urls),

    # Autenticación principal
    path('login/', AresLoginView.as_view(), name='login'),
    path('logout/', AresLogoutView.as_view(), name='logout'),

    # Centro de operaciones y módulos de negocio
    path('', include('core.urls')),
    path('usuarios/', include('usuarios.urls')),
    path('telemetria/', include('telemetria.urls')),
]
