from django.shortcuts import render,redirect,get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView,DetailView,CreateView,UpdateView,DeleteView,View
from django.contrib import messages
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,IntegrityError
from django.db.models import Count, Q
from .listing import MissionFilters, OrderFilters, filter_dates
from .models import Robot,Mision,Asignacion,Orden,Hallazgo
from .forms import RobotForm,MisionForm,AsignacionForm,OrdenForm,HallazgoForm
from .permissions import AccessMixin,AresLoginRequiredMixin,SafeDeleteMixin
from .security import allowed,is_admin,role,business_user,scoped,missions,object_mission
from .audit import record
from telemetria.models import Sensor,Lectura,Evento

class SaveAuditMixin:
    def form_valid(self,form):
        try:
            with transaction.atomic():
                response=super().form_valid(form)
                record(self.request.user,f'{self.action} {self.model._meta.label}', 'Correcto',object_mission(self.object))
                messages.success(self.request,'Cambios guardados.')
            return response
        except (IntegrityError,ValidationError) as exc:
            form.add_error(None,'El registro entra en conflicto con datos existentes.' if isinstance(exc,IntegrityError) else exc)
            return self.form_invalid(form)

class DashboardView(AresLoginRequiredMixin,View):
    def get(self,request):
        visible=missions(request.user) if allowed(request.user,Mision) else Mision.objects.none()
        active=visible.filter(estado='en_curso').first()
        context={'mision_activa':active,'robot_activo':active.robot if active and allowed(request.user,Robot) else None,
          'total_misiones':visible.count(),'total_robots':scoped(request.user,Robot).count() if allowed(request.user,Robot) else 0,
          'lecturas_recientes':scoped(request.user,Lectura).filter(mision=active)[:5] if active and allowed(request.user,Lectura) else [],
          'hallazgos_recientes':scoped(request.user,Hallazgo).filter(asignacion__mision=active)[:5] if active and allowed(request.user,Hallazgo) else [],
          'eventos_recientes':scoped(request.user,Evento)[:6] if allowed(request.user,Evento) else [],
          'is_admin':is_admin(request.user),'is_operador':role(request.user)=='Operador',
          'can_control':bool(active and allowed(request.user,Orden,'add') and allowed(request.user,Mision,'change') and (is_admin(request.user) or active.operador_responsable==business_user(request.user)))}
        return render(request,'core/dashboard.html',context)

class MisionDetailView(AccessMixin,DetailView):
    model=Mision
    template_name='core/mision_detail.html'
    context_object_name='mision'
    def get_context_data(self,**kwargs):
        context=super().get_context_data(**kwargs)
        for key,model,lookup,limit in [('asignaciones',Asignacion,'mision',100),('ordenes',Orden,'asignacion__mision',10),('hallazgos',Hallazgo,'asignacion__mision',10),('lecturas',Lectura,'mision',8)]:
            context[key]=scoped(self.request.user,model).filter(**{lookup:self.object})[:limit] if allowed(self.request.user,model) else []
        context['can_control']=self.object.estado!='cerrada' and allowed(self.request.user,Mision,'change') and (is_admin(self.request.user) or self.object.operador_responsable==business_user(self.request.user))
        writable = self.object.estado != 'cerrada' and (is_admin(self.request.user) or self.object.operador_responsable == business_user(self.request.user))
        context['can_add_hallazgo'] = writable and allowed(self.request.user, Hallazgo, 'add')
        context['can_add_orden'] = writable and self.object.estado == 'en_curso' and allowed(self.request.user, Orden, 'add')
        context['can_assign'] = self.object.estado != 'cerrada' and allowed(self.request.user, Asignacion, 'add')
        return context

class MisionCambiarEstadoView(AccessMixin,DetailView):
    model=Mision
    action='change'
    http_method_names=['post']
    def post(self,request,pk):
        mission=self.get_object()
        destination={'iniciar':'en_curso','pausar':'pausada','cerrar':'cerrada'}.get(request.POST.get('accion'))
        try:
            mission.cambiar_estado(destination)
            record(request.user,'Estado de misión',mission.estado,mission)
            messages.success(request,'Estado actualizado.')
        except ValidationError as exc:
            messages.error(request,' '.join(exc.messages))
        return redirect('core:mision_detail',pk=pk)

class RobotListView(AccessMixin, ListView):
    model=Robot
    action="view"
    template_name="core/robot_list.html"
    context_object_name="robots"
    paginate_by=15
    def get_queryset(self):
        visible = missions(self.request.user) if allowed(self.request.user, Mision) else Mision.objects.none()
        sensors = scoped(self.request.user, Sensor) if allowed(self.request.user, Sensor) else Sensor.objects.none()
        return super().get_queryset().annotate(
            misiones_visibles=Count('misiones', filter=Q(misiones__in=visible), distinct=True),
            sensores_visibles=Count('sensores', filter=Q(sensores__in=sensors), distinct=True)).order_by('codigo', 'pk')

class RobotCreateView(AccessMixin, SaveAuditMixin, CreateView):
    model=Robot
    action="add"
    template_name="core/robot_form.html"
    success_url=reverse_lazy("core:robot_list")
    form_class=RobotForm

class RobotUpdateView(AccessMixin, SaveAuditMixin, UpdateView):
    model=Robot
    action="change"
    template_name="core/robot_form.html"
    success_url=reverse_lazy("core:robot_list")
    form_class=RobotForm

class RobotDeleteView(AccessMixin, SafeDeleteMixin, DeleteView):
    model=Robot
    action="delete"
    template_name="core/robot_confirm_delete.html"
    success_url=reverse_lazy("core:robot_list")

class MisionListView(AccessMixin, ListView):
    model=Mision
    action="view"
    template_name="core/mision_list.html"
    context_object_name="misiones"
    paginate_by=15
    def get_queryset(self):
        qs=super().get_queryset()
        self.filters = MissionFilters(self.request.GET)
        if not self.filters.is_valid(): return qs.none()
        data = self.filters.cleaned_data
        if data.get('estado'): qs = qs.filter(estado=data['estado'])
        if data.get('q'): qs = qs.filter(Q(nombre__icontains=data['q']) | Q(zona__icontains=data['q']))
        return filter_dates(qs, data, 'inicio')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filters'] = self.filters
        return context

class MisionCreateView(AccessMixin, SaveAuditMixin, CreateView):
    model=Mision
    action="add"
    template_name="core/mision_form.html"
    success_url=reverse_lazy("core:mision_list")
    form_class=MisionForm

class MisionUpdateView(AccessMixin, SaveAuditMixin, UpdateView):
    model=Mision
    action="change"
    template_name="core/mision_form.html"
    success_url=reverse_lazy("core:mision_list")
    form_class=MisionForm

class MisionDeleteView(AccessMixin, SafeDeleteMixin, DeleteView):
    model=Mision
    action="delete"
    template_name="core/mision_confirm_delete.html"
    success_url=reverse_lazy("core:mision_list")
    def form_valid(self,form):
        if self.object.estado!="planificada" or self.object.lecturas.exists() or self.object.asignaciones.filter(ordenes__isnull=False).exists() or self.object.asignaciones.filter(hallazgos__isnull=False).exists():
            messages.error(self.request,"Conserva el historial: solo se elimina una misión planificada sin evidencia.")
            return redirect(self.success_url)
        return super().form_valid(form)

class AsignacionListView(AccessMixin, ListView):
    model=Asignacion
    action="view"
    template_name="core/asignacion_list.html"
    context_object_name="asignaciones"
    paginate_by=15

class AsignacionCreateView(AccessMixin, SaveAuditMixin, CreateView):
    model=Asignacion
    action="add"
    template_name="core/asignacion_form.html"
    success_url=reverse_lazy("core:asignacion_list")
    form_class=AsignacionForm

class AsignacionUpdateView(AccessMixin, SaveAuditMixin, UpdateView):
    model=Asignacion
    action="change"
    template_name="core/asignacion_form.html"
    success_url=reverse_lazy("core:asignacion_list")
    form_class=AsignacionForm

class AsignacionDeleteView(AccessMixin, SafeDeleteMixin, DeleteView):
    model=Asignacion
    action="delete"
    template_name="core/asignacion_confirm_delete.html"
    success_url=reverse_lazy("core:asignacion_list")
    def form_valid(self,form):
        if self.object.mision.operador_responsable_id==self.object.usuario_id or self.object.ordenes.exists() or self.object.hallazgos.exists():
            messages.error(self.request,"La asignación es responsable o conserva evidencia; no puede eliminarse.")
            return redirect(self.success_url)
        return super().form_valid(form)

class OrdenListView(AccessMixin, ListView):
    model=Orden
    action="view"
    template_name="core/orden_list.html"
    context_object_name="ordenes"
    paginate_by=15
    def get_queryset(self):
        qs = super().get_queryset().select_related('asignacion__mision', 'asignacion__usuario')
        self.filters = OrderFilters(self.request.GET, user=self.request.user)
        if not self.filters.is_valid(): return qs.none()
        data = self.filters.cleaned_data
        if data.get('mision'): qs = qs.filter(asignacion__mision=data['mision'])
        if data.get('tipo'): qs = qs.filter(accion=data['tipo'])
        return filter_dates(qs, data, 'creada_en').order_by('-creada_en', '-pk')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filters'] = self.filters
        return context

class OrdenCreateView(AccessMixin, SaveAuditMixin, CreateView):
    model=Orden
    action="add"
    template_name="core/orden_form.html"
    success_url=reverse_lazy("core:orden_list")
    form_class=OrdenForm
    def form_invalid(self,form):
        assignment=form.cleaned_data.get("asignacion")
        record(self.request.user,"Orden rechazada","Validación rechazada",assignment.mision if assignment else None)
        return super().form_invalid(form)

class OrdenUpdateView(AccessMixin, SaveAuditMixin, UpdateView):
    model=Orden
    action="change"
    template_name="core/orden_form.html"
    success_url=reverse_lazy("core:orden_list")
    form_class=OrdenForm

class OrdenDeleteView(AccessMixin, SafeDeleteMixin, DeleteView):
    model=Orden
    action="delete"
    template_name="core/orden_confirm_delete.html"
    success_url=reverse_lazy("core:orden_list")
    def form_valid(self,form):
        if self.object.enviada_en or self.object.confirmada_en:
            raise PermissionDenied("Una orden enviada o confirmada forma parte del historial.")
        return super().form_valid(form)

class HallazgoListView(AccessMixin, ListView):
    model=Hallazgo
    action="view"
    template_name="core/hallazgo_list.html"
    context_object_name="hallazgos"
    paginate_by=15

class HallazgoCreateView(AccessMixin, SaveAuditMixin, CreateView):
    model=Hallazgo
    action="add"
    template_name="core/hallazgo_form.html"
    success_url=reverse_lazy("core:hallazgo_list")
    form_class=HallazgoForm

class HallazgoUpdateView(AccessMixin, SaveAuditMixin, UpdateView):
    model=Hallazgo
    action="change"
    template_name="core/hallazgo_form.html"
    success_url=reverse_lazy("core:hallazgo_list")
    form_class=HallazgoForm

class HallazgoDeleteView(AccessMixin, SafeDeleteMixin, DeleteView):
    model=Hallazgo
    action="delete"
    template_name="core/hallazgo_confirm_delete.html"
    success_url=reverse_lazy("core:hallazgo_list")



class MisionControlView(AccessMixin,DetailView):
    model=Mision
    action='change'
    http_method_names=['post']
    def post(self,request,pk):
        from datetime import timedelta
        from django.utils import timezone
        from django.db.models import Max
        if not allowed(request.user,Orden,'add'): raise PermissionDenied('Sin permiso para emitir órdenes.')
        mission=self.get_object()
        assignment=mission.asignaciones.filter(usuario_id=mission.operador_responsable_id).first()
        if not assignment:
            messages.error(request,'La misión no tiene operador responsable asignado.')
            return redirect('core:dashboard')
        last=Orden.objects.filter(asignacion=assignment).aggregate(last=Max('secuencia'))['last'] or 0
        form=OrdenForm(actor=request.user,data={'asignacion':assignment.pk,'secuencia':last+1,'accion':request.POST.get('accion'),'duracion_ms':500,'vencimiento':(timezone.now()+timedelta(seconds=2)).isoformat()})
        if form.is_valid():
            form.save()
            record(request.user,'Orden solicitada','Pendiente de confirmación',mission)
            messages.success(request,'Solicitud guardada. Esperando confirmación del dispositivo.')
        else:
            record(request.user,'Orden rechazada','Validación rechazada',mission)
            messages.error(request,' '.join(error for errors in form.errors.values() for error in errors))
        return redirect('core:dashboard')


# ---------------------------------------------------------------------------
# [NUEVO] Control WiFi del robot: lo usan el Administrador y el Operador
# responsable de una misión en curso. Usa las mismas órdenes y validaciones
# que el resto de ARES (el robot las recoge con su credencial).
# ---------------------------------------------------------------------------
def wifi_mission(user, pk=None):
    """Misión en curso que el usuario puede controlar (Administrador: cualquiera; Operador: solo la suya)."""
    current=role(user)
    if current not in ('Administrador','Operador') or not allowed(user,Orden,'add'):
        raise PermissionDenied('El control WiFi es exclusivo para administradores y operadores.')
    qs=Mision.objects.select_related('robot').filter(estado='en_curso')
    if current=='Operador': qs=qs.filter(operador_responsable=business_user(user))
    if pk is not None: qs=qs.filter(pk=pk)
    return qs.order_by('-inicio').first()

class ControlWifiView(AresLoginRequiredMixin,View):
    """Sección siempre visible para quien puede ver órdenes; solo se habilita para quien puede controlar."""
    def get(self,request):
        user=request.user
        if not allowed(user,Orden,'view'): raise PermissionDenied('Sin acceso a la sección de control.')
        puede_mandar=role(user) in ('Administrador','Operador') and allowed(user,Orden,'add')
        mision=wifi_mission(user) if puede_mandar else None
        habilitado=mision is not None
        motivo=''
        if not habilitado:
            # Misión en curso visible para el usuario, solo para mostrar su nombre.
            mision=missions(user).filter(estado='en_curso').select_related('robot').order_by('-inicio').first()
            if not puede_mandar: motivo='Tu rol solo puede consultar esta sección.'
            elif mision: motivo='No eres el operador responsable de la misión en curso.'
            else: motivo='No hay una misión en curso.'
        return render(request,'core/control_wifi.html',{'mision':mision,'habilitado':habilitado,'motivo':motivo})

class ControlWifiOrdenView(AresLoginRequiredMixin,View):
    http_method_names=['post']
    def post(self,request,pk):
        from datetime import timedelta
        from django.http import JsonResponse
        from django.utils import timezone
        from django.db.models import Max
        with transaction.atomic():
            mission=wifi_mission(request.user,pk)
            if not mission: return JsonResponse({'ok':False,'mensaje':'La misión no está en curso o no tienes permiso para controlarla.'},status=404)
            Robot.objects.select_for_update().get(pk=mission.robot_id)
            mission=Mision.objects.select_for_update().get(pk=mission.pk)
            assignment=mission.asignaciones.filter(usuario_id=mission.operador_responsable_id).first()
            if not assignment: return JsonResponse({'ok':False,'mensaje':'La misión no tiene operador responsable asignado.'},status=400)
            last=Orden.objects.filter(asignacion=assignment).aggregate(last=Max('secuencia'))['last'] or 0
            form=OrdenForm(actor=request.user,data={'asignacion':assignment.pk,'secuencia':last+1,'accion':request.POST.get('accion'),
                'duracion_ms':500,'vencimiento':(timezone.now()+timedelta(seconds=2)).isoformat()})
            if form.is_valid():
                order=form.save()
                record(request.user,f'Orden WiFi: {order.accion}','Pendiente de confirmación',mission)
                return JsonResponse({'ok':True,'mensaje':'Orden enviada. Esperando confirmación del robot.'})
            record(request.user,'Orden WiFi rechazada','Validación rechazada',mission)
            return JsonResponse({'ok':False,'mensaje':' '.join(error for errors in form.errors.values() for error in errors)},status=400)

class ControlWifiEstadoView(AresLoginRequiredMixin,View):
    def get(self,request,pk):
        from django.http import JsonResponse
        mission=wifi_mission(request.user,pk)
        if not mission: return JsonResponse({'ok':False,'mensaje':'La misión ya no está en curso.'},status=404)
        last=Orden.objects.filter(asignacion__mision=mission).order_by('-secuencia').first()
        return JsonResponse({'ok':True,'conectado':mission.robot.conectado,
            'ultima':{'accion':last.accion,'estado':last.estado_confirmacion} if last else None})