from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.contrib import messages
from django.shortcuts import redirect
from .security import allowed, role, is_admin, business_user, scoped, object_mission
get_current_business_user = business_user

class AresLoginRequiredMixin(LoginRequiredMixin):
    login_url = 'login'
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect_to_login(self.request.get_full_path(), self.get_login_url())
        raise PermissionDenied('No cuentas con autorización para esta operación.')
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not role(request.user): return self.handle_no_permission()
        return super().dispatch(request,*args,**kwargs)

class AccessMixin(AresLoginRequiredMixin):
    http_method_names = ['get','post','head','options']
    action = 'view'
    def dispatch(self, request, *args, **kwargs):
        if not allowed(request.user,self.model,self.action): return self.handle_no_permission()
        with transaction.atomic():
            if self.action != 'view' and kwargs.get('pk') is not None:
                obj = self.get_object()
                mission = object_mission(obj)
                if mission:
                    from .models import Mision,Robot
                    Robot.objects.select_for_update().get(pk=mission.robot_id)
                    mission = Mision.objects.select_for_update().get(pk=mission.pk)
                    if mission.estado == 'cerrada': raise PermissionDenied('La misión está cerrada y es de solo consulta.')
                if not is_admin(request.user):
                    profile = business_user(request.user)
                    if mission and mission.operador_responsable_id != profile.pk: raise PermissionDenied('Solo el operador responsable puede modificar esta misión.')
                    if hasattr(obj,'asignacion') and obj.asignacion.usuario_id != profile.pk: raise PermissionDenied('El registro pertenece a otro operador.')
            return super().dispatch(request,*args,**kwargs)
    def get_queryset(self):
        if self.model._meta.app_label in ('core','telemetria'): return scoped(self.request.user,self.model)
        return super().get_queryset()
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.copy()
        query.pop('page', None)
        context['filter_query'] = query.urlencode()
        return context

    def get_form_kwargs(self):
        kwargs=super().get_form_kwargs()
        if self.form_class and getattr(self.form_class,'accepts_actor',False): kwargs['actor']=self.request.user
        return kwargs

class SafeDeleteMixin:
    def form_valid(self,form):
        from core.audit import record
        label,ident=self.object._meta.label,str(self.object.pk)
        mission=object_mission(self.object)
        from telemetria.models import Sensor
        from usuarios.models import Usuario
        if isinstance(self.object,Sensor) and self.object.lecturas.exists():
            messages.error(self.request,'El sensor conserva lecturas; no puede eliminarse.')
            return redirect(self.get_success_url())
        if isinstance(self.object,Usuario) and self.object.asignaciones.exists():
            messages.error(self.request,'El perfil tiene asignaciones. Desactívalo para conservar la evidencia.')
            return redirect(self.get_success_url())
        try:
            with transaction.atomic():
                response=super().form_valid(form)
                record(self.request.user,f'Eliminar {label}',f'Registro {ident}',mission if mission and label!='core.Mision' else None)
            return response
        except ProtectedError:
            messages.error(self.request,'Existen registros relacionados. Desactiva el registro cuando corresponda.')
            return redirect(self.get_success_url())

class AdminRequiredMixin(AresLoginRequiredMixin):
    def dispatch(self,request,*args,**kwargs):
        if not is_admin(request.user): return self.handle_no_permission()
        return super().dispatch(request,*args,**kwargs)

class OperadorOrAdminRequiredMixin(AresLoginRequiredMixin):
    def dispatch(self,request,*args,**kwargs):
        if role(request.user) not in ('Administrador','Operador'): return self.handle_no_permission()
        return super().dispatch(request,*args,**kwargs)
AresPermissionRequiredMixin=AccessMixin
MisionAccessRequiredMixin=AccessMixin
