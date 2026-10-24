from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.models import User, Group, Permission
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q

from core.permissions import (
    AresLoginRequiredMixin,
    AdminRequiredMixin,
    OperadorOrAdminRequiredMixin
)
from .models import Rol, Usuario
from core.permissions import AccessMixin, SafeDeleteMixin
from core.views import SaveAuditMixin
from core.security import ROLES
from .forms import DjangoPermissionForm, protected_permission
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.utils.crypto import salted_hmac
from .models import LoginThrottle
from .forms import (
    AresAuthenticationForm,
    DjangoUserCreationForm,
    DjangoUserUpdateForm,
    DjangoGroupForm,
    RolForm,
    UsuarioForm
)

# ==============================================================================
# 1. AUTENTICACIÓN (LOGIN & LOGOUT) - REQUERIMIENTO 1 (OWASP A01)
# ==============================================================================

class AresLoginView(LoginView):
    """
    Vista de inicio de sesión de ARES.
    Aplica controles para evitar enumeración de usuarios y redirección segura.
    """
    template_name = 'autenticacion/login.html'
    authentication_form = AresAuthenticationForm
    redirect_authenticated_user = True

    def post(self,request,*args,**kwargs):
        from django.db.models import Q
        raw=request.POST.get('username','')[:254].strip()
        matches=User.objects.filter(Q(username=raw)|Q(email__iexact=raw)).values_list('pk',flat=True)[:2]
        ids=list(matches)
        identity=str(ids[0]) if len(ids)==1 else raw.casefold()
        keys=[('account:'+identity,5),('ip:'+request.META.get('REMOTE_ADDR','unknown'),20)]
        with transaction.atomic():
            buckets=[]
            for key,limit in keys:
                digest=salted_hmac('ares.login',key,algorithm='sha256').hexdigest()
                obj,_=LoginThrottle.objects.get_or_create(clave=digest,defaults={'ventana':timezone.now()})
                obj=LoginThrottle.objects.select_for_update().get(pk=obj.pk)
                if obj.ventana < timezone.now()-timedelta(minutes=5):
                    obj.ventana=timezone.now(); obj.intentos=0; obj.save()
                buckets.append((obj,limit))
            if any(obj.intentos>=limit for obj,limit in buckets):
                form=self.get_form()
                form.add_error(None,'Demasiados intentos. Espera cinco minutos e inténtalo de nuevo.')
                response=self.render_to_response(self.get_context_data(form=form),status=429)
                response['Retry-After']='300'
                return response
            form=self.get_form()
            if form.is_valid():
                buckets[0][0].intentos=0; buckets[0][0].save(update_fields=['intentos'])
                return self.form_valid(form)
            for obj,limit in buckets:
                obj.intentos+=1; obj.save(update_fields=['intentos'])
            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Credenciales no válidas. Verifique su usuario y contraseña.")
        return super().form_invalid(form)


class AresLogoutView(LogoutView):
    """
    Vista de cierre de sesión seguro.
    Invalida completamente la sesión y redirige al login (RF-01).
    """
    next_page = 'login'


# ==============================================================================
# 2. GESTIÓN DE DJANGO AUTH (User, Group, Permission) - REQUERIMIENTO 4
# ==============================================================================

class DjangoUserListView(AccessMixin, ListView):
    action="view"
    """
    Listado de usuarios nativos de Django Auth (`auth.User`).
    """
    model = User
    template_name = 'autenticacion/user_list.html'
    context_object_name = 'usuarios'
    paginate_by = 15

    def get_queryset(self):
        qs = User.objects.all().prefetch_related('groups').order_by('username')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q))
        return qs


class DjangoUserCreateView(AccessMixin, SaveAuditMixin, CreateView):
    action="add"
    """
    Creación de usuario en Django Auth con hash de contraseñas y asignación de rol/grupo.
    """
    model = User
    form_class = DjangoUserCreationForm
    template_name = 'autenticacion/user_form.html'
    success_url = reverse_lazy('usuarios:auth_user_list')

    def form_valid(self, form):
        messages.success(self.request, f"Usuario '{form.instance.username}' creado exitosamente.")
        return super().form_valid(form)


class DjangoUserUpdateView(AccessMixin, SaveAuditMixin, UpdateView):
    action="change"
    """
    Edición de usuario Django Auth, activación/desactivación y permisos.
    """
    model = User
    form_class = DjangoUserUpdateForm
    template_name = 'autenticacion/user_form.html'
    success_url = reverse_lazy('usuarios:auth_user_list')

    def form_valid(self, form):
        messages.success(self.request, f"Usuario '{form.instance.username}' actualizado correctamente.")
        return super().form_valid(form)

    def get_queryset(self):
        qs=super().get_queryset()
        return qs if self.request.user.is_superuser else qs.filter(is_superuser=False,is_staff=False)


class DjangoUserDeleteView(AccessMixin, SafeDeleteMixin, DeleteView):
    action="delete"
    """
    Eliminación segura de usuario Django Auth (requiere POST).
    """
    model = User
    template_name = 'autenticacion/user_confirm_delete.html'
    success_url = reverse_lazy('usuarios:auth_user_list')

    def post(self, request, *args, **kwargs):
        user = self.get_object()
        if user == request.user:
            messages.error(request, "No puedes eliminar tu propia cuenta de administrador en sesión.")
            return redirect('usuarios:auth_user_list')
        messages.success(request, f"Usuario '{user.username}' eliminado exitosamente.")
        with transaction.atomic():
            Usuario.objects.filter(user=user).update(activo=False)
            return super().post(request,*args,**kwargs)


# --- Grupos / Roles de Django Auth ---
    def get_queryset(self):
        qs=super().get_queryset()
        return qs if self.request.user.is_superuser else qs.filter(is_superuser=False,is_staff=False)


class DjangoGroupListView(AccessMixin, ListView):
    action="view"
    """
    Listado de Grupos (Roles de seguridad) de Django Auth.
    """
    model = Group
    template_name = 'autenticacion/group_list.html'
    context_object_name = 'grupos'
    paginate_by = 15

    def get_queryset(self):
        return Group.objects.all().prefetch_related('permissions').order_by('name')


class DjangoGroupCreateView(AccessMixin, SaveAuditMixin, CreateView):
    action="add"
    """
    Creación de grupos y asignación directa de permisos de Django.
    """
    model = Group
    form_class = DjangoGroupForm
    template_name = 'autenticacion/group_form.html'
    success_url = reverse_lazy('usuarios:auth_group_list')

    def form_valid(self, form):
        messages.success(self.request, f"Grupo '{form.instance.name}' creado con sus permisos.")
        return super().form_valid(form)


class DjangoGroupUpdateView(AccessMixin, SaveAuditMixin, UpdateView):
    action="change"
    """
    Edición de grupo y actualización de permisos asociados.
    """
    model = Group
    form_class = DjangoGroupForm
    template_name = 'autenticacion/group_form.html'
    success_url = reverse_lazy('usuarios:auth_group_list')

    def form_valid(self, form):
        messages.success(self.request, f"Grupo '{form.instance.name}' actualizado correctamente.")
        return super().form_valid(form)


class DjangoGroupDeleteView(AccessMixin, SafeDeleteMixin, DeleteView):
    action="delete"
    """
    Eliminación de grupo/rol de Django.
    """
    model = Group
    template_name = 'autenticacion/group_confirm_delete.html'
    success_url = reverse_lazy('usuarios:auth_group_list')

    def post(self, request, *args, **kwargs):
        if self.get_object().name in ROLES:
            raise PermissionDenied("Los grupos globales no se eliminan.")
        messages.success(request, "Grupo eliminado exitosamente.")
        return super().post(request, *args, **kwargs)


# --- Inspección y Auditoría de Permisos Nativos ---

class DjangoPermissionListView(AccessMixin, ListView):
    action="view"
    """
    Consulta y auditoría de permisos del sistema Django (`auth.Permission`).
    """
    model = Permission
    template_name = 'autenticacion/permission_list.html'
    context_object_name = 'permisos'
    paginate_by = 25

    def get_queryset(self):
        qs = Permission.objects.select_related('content_type').order_by('content_type__app_label', 'codename')
        app = self.request.GET.get('app')
        if app:
            qs = qs.filter(content_type__app_label=app)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['apps'] = ['core', 'telemetria', 'usuarios', 'auth', 'admin']
        context['current_app'] = self.request.GET.get('app', '')
        return context


# ==============================================================================
# 3. CRUD DE MODELOS DE NEGOCIO: ROL Y USUARIO (ARES)
# ==============================================================================

class RolListView(AccessMixin, ListView):
    action="view"
    model = Rol
    template_name = 'usuarios/rol_list.html'
    context_object_name = 'roles'
    paginate_by = 15


class RolCreateView(AccessMixin, SaveAuditMixin, CreateView):
    action="add"
    model = Rol
    form_class = RolForm
    template_name = 'usuarios/rol_form.html'
    success_url = reverse_lazy('usuarios:rol_list')

    def form_valid(self, form):
        messages.success(self.request, f"Rol '{form.instance.nombre}' registrado.")
        return super().form_valid(form)


class RolUpdateView(AccessMixin, SaveAuditMixin, UpdateView):
    action="change"
    model = Rol
    form_class = RolForm
    template_name = 'usuarios/rol_form.html'
    success_url = reverse_lazy('usuarios:rol_list')

    def form_valid(self, form):
        messages.success(self.request, f"Rol '{form.instance.nombre}' actualizado.")
        return super().form_valid(form)


class RolDeleteView(AccessMixin, SafeDeleteMixin, DeleteView):
    def form_valid(self,form):
        if self.object.nombre in ROLES: raise PermissionDenied("Los roles globales no se eliminan.")
        return super().form_valid(form)
    action="delete"
    model = Rol
    template_name = 'usuarios/rol_confirm_delete.html'
    success_url = reverse_lazy('usuarios:rol_list')


class UsuarioBusinessListView(AccessMixin, ListView):
    action="view"
    model = Usuario
    template_name = 'usuarios/usuario_list.html'
    context_object_name = 'usuarios_negocio'
    paginate_by = 15

    def get_queryset(self):
        return Usuario.objects.select_related('rol').order_by('nombre')


class UsuarioBusinessCreateView(AccessMixin, SaveAuditMixin, CreateView):
    action="add"
    model = Usuario
    form_class = UsuarioForm
    template_name = 'usuarios/usuario_form.html'
    success_url = reverse_lazy('usuarios:usuario_list')

    def form_valid(self, form):
        messages.success(self.request, f"Usuario de negocio '{form.instance.nombre}' creado.")
        return super().form_valid(form)


class UsuarioBusinessUpdateView(AccessMixin, SaveAuditMixin, UpdateView):
    action="change"
    model = Usuario
    form_class = UsuarioForm
    template_name = 'usuarios/usuario_form.html'
    success_url = reverse_lazy('usuarios:usuario_list')

    def form_valid(self, form):
        messages.success(self.request, f"Usuario de negocio '{form.instance.nombre}' actualizado.")
        return super().form_valid(form)

    def get_queryset(self):
        qs=super().get_queryset()
        return qs if self.request.user.is_superuser else qs.exclude(user__is_superuser=True).exclude(user__is_staff=True)


class UsuarioBusinessDeleteView(AccessMixin, SafeDeleteMixin, DeleteView):
    def form_valid(self,form):
        if self.object.user_id==self.request.user.pk: raise PermissionDenied('No puedes eliminar tu propio perfil.')
        return super().form_valid(form)

    action="delete"
    model = Usuario
    template_name = 'usuarios/usuario_confirm_delete.html'
    success_url = reverse_lazy('usuarios:usuario_list')

    def get_queryset(self):
        qs=super().get_queryset()
        return qs if self.request.user.is_superuser else qs.exclude(user__is_superuser=True).exclude(user__is_staff=True)


class DjangoPermissionCreateView(AccessMixin,SaveAuditMixin,CreateView):
    model=Permission
    action='add'
    form_class=DjangoPermissionForm
    template_name='autenticacion/permission_form.html'
    success_url=reverse_lazy('usuarios:auth_permission_list')

class DjangoPermissionUpdateView(AccessMixin,SaveAuditMixin,UpdateView):
    model=Permission
    action='change'
    form_class=DjangoPermissionForm
    template_name='autenticacion/permission_form.html'
    success_url=reverse_lazy('usuarios:auth_permission_list')

class DjangoPermissionDeleteView(AccessMixin,SafeDeleteMixin,DeleteView):
    model=Permission
    action='delete'
    template_name='autenticacion/permission_confirm_delete.html'
    success_url=reverse_lazy('usuarios:auth_permission_list')
    def form_valid(self,form):
        if protected_permission(self.object): raise PermissionDenied('No se eliminan permisos del sistema.')
        return super().form_valid(form)
