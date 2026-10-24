from django.urls import path
from .views import (
    DjangoUserListView, DjangoUserCreateView, DjangoUserUpdateView, DjangoUserDeleteView,
    DjangoGroupListView, DjangoGroupCreateView, DjangoGroupUpdateView, DjangoGroupDeleteView,
    DjangoPermissionListView, DjangoPermissionCreateView, DjangoPermissionUpdateView, DjangoPermissionDeleteView,
    RolListView, RolCreateView, RolUpdateView, RolDeleteView,
    UsuarioBusinessListView, UsuarioBusinessCreateView, UsuarioBusinessUpdateView, UsuarioBusinessDeleteView
)

app_name = 'usuarios'

urlpatterns = [
    # Gestión Django Auth (User, Group, Permission) - Requerimiento 4
    path('auth/usuarios/', DjangoUserListView.as_view(), name='auth_user_list'),
    path('auth/usuarios/nuevo/', DjangoUserCreateView.as_view(), name='auth_user_create'),
    path('auth/usuarios/<int:pk>/editar/', DjangoUserUpdateView.as_view(), name='auth_user_update'),
    path('auth/usuarios/<int:pk>/eliminar/', DjangoUserDeleteView.as_view(), name='auth_user_delete'),

    path('auth/grupos/', DjangoGroupListView.as_view(), name='auth_group_list'),
    path('auth/grupos/nuevo/', DjangoGroupCreateView.as_view(), name='auth_group_create'),
    path('auth/grupos/<int:pk>/editar/', DjangoGroupUpdateView.as_view(), name='auth_group_update'),
    path('auth/grupos/<int:pk>/eliminar/', DjangoGroupDeleteView.as_view(), name='auth_group_delete'),

    path('auth/permisos/', DjangoPermissionListView.as_view(), name='auth_permission_list'),

    path('auth/permisos/nuevo/', DjangoPermissionCreateView.as_view(), name='auth_permission_create'),
    path('auth/permisos/<int:pk>/editar/', DjangoPermissionUpdateView.as_view(), name='auth_permission_update'),
    path('auth/permisos/<int:pk>/eliminar/', DjangoPermissionDeleteView.as_view(), name='auth_permission_delete'),

    # CRUD Entidad de Negocio Rol
    path('roles/', RolListView.as_view(), name='rol_list'),
    path('roles/nuevo/', RolCreateView.as_view(), name='rol_create'),
    path('roles/<int:pk>/editar/', RolUpdateView.as_view(), name='rol_update'),
    path('roles/<int:pk>/eliminar/', RolDeleteView.as_view(), name='rol_delete'),

    # CRUD Entidad de Negocio Usuario
    path('negocio/usuarios/', UsuarioBusinessListView.as_view(), name='usuario_list'),
    path('negocio/usuarios/nuevo/', UsuarioBusinessCreateView.as_view(), name='usuario_create'),
    path('negocio/usuarios/<int:pk>/editar/', UsuarioBusinessUpdateView.as_view(), name='usuario_update'),
    path('negocio/usuarios/<int:pk>/eliminar/', UsuarioBusinessDeleteView.as_view(), name='usuario_delete'),
]
