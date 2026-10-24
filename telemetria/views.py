from django import forms
from django.urls import reverse_lazy
from django.views.generic import ListView,CreateView,UpdateView,DeleteView
from django.core.exceptions import PermissionDenied
from core.permissions import AccessMixin,SafeDeleteMixin
from core.views import SaveAuditMixin
from core.security import missions,business_user,scoped,allowed
from django.db.models import Count,Q
from .models import Sensor,Lectura,Evento
from .forms import SensorForm,LecturaForm,EventoForm

class ActivityFilters(forms.Form):
    mision=forms.UUIDField(required=False)
    desde=forms.DateField(required=False)
    hasta=forms.DateField(required=False)
    tipo=forms.CharField(required=False,max_length=100)
    resultado=forms.CharField(required=False,max_length=50)
    q=forms.CharField(required=False,max_length=100)
    def clean(self):
        data=super().clean()
        if data.get('desde') and data.get('hasta') and data['desde']>data['hasta']: raise forms.ValidationError('La fecha inicial debe ser anterior a la final.')
        return data

class FilteredListMixin:
    def get_queryset(self):
        qs=super().get_queryset()
        self.filters=ActivityFilters(self.request.GET)
        if not self.filters.is_valid(): return qs.none()
        data=self.filters.cleaned_data
        if data.get('mision'): qs=qs.filter(mision_id=data['mision'])
        datefield='fecha_hora' if self.model==Evento else 'capturada_en'
        if data.get('desde'): qs=qs.filter(**{datefield+'__date__gte':data['desde']})
        if data.get('hasta'): qs=qs.filter(**{datefield+'__date__lte':data['hasta']})
        if self.model==Evento:
            if data.get('tipo'): qs=qs.filter(accion__icontains=data['tipo'])
            if data.get('resultado'): qs=qs.filter(resultado__icontains=data['resultado'])
            if data.get('q'): qs=qs.filter(accion__icontains=data['q'])
        return qs
    def get_context_data(self,**kwargs):
        ctx=super().get_context_data(**kwargs)
        ctx.update(misiones=missions(self.request.user),selected_mision=self.request.GET.get('mision',''),q=self.request.GET.get('q',''),filters=self.filters)
        query=self.request.GET.copy(); query.pop('page',None)
        ctx['filter_query']=query.urlencode()
        return ctx

class SensorListView(AccessMixin, ListView):
    model=Sensor
    action="view"
    template_name="telemetria/sensor_list.html"
    context_object_name="sensores"
    paginate_by=20
    def get_queryset(self):
        readings = scoped(self.request.user, Lectura) if allowed(self.request.user, Lectura) else Lectura.objects.none()
        return super().get_queryset().annotate(lecturas_visibles=Count('lecturas', filter=Q(lecturas__in=readings), distinct=True)).order_by('robot__codigo', 'canal', 'pk')

class SensorCreateView(AccessMixin, SaveAuditMixin, CreateView):
    model=Sensor
    action="add"
    template_name="telemetria/sensor_form.html"
    success_url=reverse_lazy("telemetria:sensor_list")
    form_class=SensorForm

class SensorUpdateView(AccessMixin, SaveAuditMixin, UpdateView):
    model=Sensor
    action="change"
    template_name="telemetria/sensor_form.html"
    success_url=reverse_lazy("telemetria:sensor_list")
    form_class=SensorForm

class SensorDeleteView(AccessMixin, SafeDeleteMixin, DeleteView):
    model=Sensor
    action="delete"
    template_name="telemetria/sensor_confirm_delete.html"
    success_url=reverse_lazy("telemetria:sensor_list")

class LecturaListView(FilteredListMixin, AccessMixin, ListView):
    model=Lectura
    action="view"
    template_name="telemetria/lectura_list.html"
    context_object_name="lecturas"
    paginate_by=20

class LecturaCreateView(AccessMixin, SaveAuditMixin, CreateView):
    model=Lectura
    action="add"
    template_name="telemetria/lectura_form.html"
    success_url=reverse_lazy("telemetria:lectura_list")
    form_class=LecturaForm

class LecturaUpdateView(AccessMixin, SaveAuditMixin, UpdateView):
    model=Lectura
    action="change"
    template_name="telemetria/lectura_form.html"
    success_url=reverse_lazy("telemetria:lectura_list")
    form_class=LecturaForm
    def get_queryset(self):
        return super().get_queryset().filter(simulada=True)

class LecturaDeleteView(AccessMixin, SafeDeleteMixin, DeleteView):
    model=Lectura
    action="delete"
    template_name="telemetria/lectura_confirm_delete.html"
    success_url=reverse_lazy("telemetria:lectura_list")
    def get_queryset(self):
        return super().get_queryset().filter(simulada=True)

class EventoListView(FilteredListMixin, AccessMixin, ListView):
    model=Evento
    action="view"
    template_name="telemetria/evento_list.html"
    context_object_name="eventos"
    paginate_by=20

class EventoCreateView(AccessMixin, SaveAuditMixin, CreateView):
    model=Evento
    action="add"
    template_name="telemetria/evento_form.html"
    success_url=reverse_lazy("telemetria:evento_list")
    form_class=EventoForm
    def form_valid(self,form):
        form.instance.actor=business_user(self.request.user)
        return super().form_valid(form)

class EventoUpdateView(AccessMixin, SaveAuditMixin, UpdateView):
    model=Evento
    action="change"
    template_name="telemetria/evento_form.html"
    success_url=reverse_lazy("telemetria:evento_list")
    form_class=EventoForm
    def get_queryset(self):
        return super().get_queryset().filter(es_sistema=False)

class EventoDeleteView(AccessMixin, SafeDeleteMixin, DeleteView):
    model=Evento
    action="delete"
    template_name="telemetria/evento_confirm_delete.html"
    success_url=reverse_lazy("telemetria:evento_list")
    def get_queryset(self):
        return super().get_queryset().filter(es_sistema=False)

class EventoAdminListView(EventoListView):
    template_name='telemetria/evento_admin_list.html'
    def dispatch(self,request,*args,**kwargs):
        from core.security import is_admin
        if not is_admin(request.user): return self.handle_no_permission()
        return super().dispatch(request,*args,**kwargs)
    def get_queryset(self):
        return super().get_queryset().filter(es_sistema=False)
