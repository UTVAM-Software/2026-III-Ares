from datetime import timedelta
from django import forms
from django.db import transaction
from django.utils import timezone
from .models import Robot, Mision, Asignacion, Orden, Hallazgo
from .security import business_user, is_admin, scoped, writable_missions
from usuarios.models import Usuario

class ActorForm(forms.ModelForm):
    accepts_actor = True
    def __init__(self,*args,actor=None,**kwargs):
        self.actor = actor
        super().__init__(*args,**kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class','ares-input')

class RobotForm(ActorForm):
    credencial = forms.CharField(label='Nueva credencial del dispositivo',required=False,strip=False,widget=forms.PasswordInput(render_value=False),min_length=24)
    class Meta:
        model=Robot
        fields=['codigo','nombre','credencial','activo','creador']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['credencial'].initial=''
        if self.instance._state.adding: self.fields['credencial'].required=True
        self.previous_credential=self.instance.credencial
    def clean_credencial(self):
        value=self.cleaned_data.get('credencial')
        return value or self.previous_credential
    def save(self,commit=True):
        obj=super().save(commit=False)
        raw=self.cleaned_data.get('credencial')
        if raw and raw != self.previous_credential: obj.set_credential(raw)
        if commit: obj.save()
        return obj

class MisionForm(ActorForm):
    class Meta:
        model=Mision
        fields=['nombre','zona','robot','operador_responsable']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['operador_responsable'].required=True
        self.fields['operador_responsable'].queryset=Usuario.objects.filter(activo=True,rol__nombre='Operador',user__is_active=True,user__groups__name='Operador').distinct()
        self.fields['robot'].queryset=Robot.objects.filter(activo=True)
        if self.actor:
            if not is_admin(self.actor):
                self.fields['operador_responsable'].queryset=self.fields['operador_responsable'].queryset.filter(user=self.actor)
                self.fields['robot'].queryset=scoped(self.actor,Robot).filter(activo=True)
            if self.instance._state.adding:
                self.instance.creador=business_user(self.actor)
    def clean(self):
        data=super().clean()
        if self.instance._state.adding and not self.instance.creador_id:
            raise forms.ValidationError('La cuenta necesita un perfil ARES activo para crear una misión.')
        if not self.instance._state.adding:
            old=Mision.objects.select_for_update().get(pk=self.instance.pk)
            if old.estado=='cerrada': raise forms.ValidationError('La misión está cerrada.')
            if old.estado=='en_curso' and (data.get('robot')!=old.robot or data.get('operador_responsable')!=old.operador_responsable):
                raise forms.ValidationError('Pausa la misión antes de cambiar robot o responsable.')
            if data.get('robot')!=old.robot and (old.lecturas.exists() or old.asignaciones.filter(ordenes__isnull=False).exists()):
                raise forms.ValidationError('No puede cambiarse el robot de una misión con evidencia registrada.')
        return data
    @transaction.atomic
    def save(self,commit=True):
        obj=super().save(commit=commit)
        if commit: Asignacion.objects.get_or_create(mision=obj,usuario=obj.operador_responsable)
        return obj

class AsignacionForm(ActorForm):
    class Meta:
        model=Asignacion
        fields=['usuario','mision']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['usuario'].queryset=Usuario.objects.filter(activo=True,user__is_active=True)
        self.fields['mision'].queryset=Mision.objects.exclude(estado='cerrada')
    def clean(self):
        data=super().clean()
        mission=data.get('mision')
        if mission and Mision.objects.select_for_update().get(pk=mission.pk).estado=='cerrada':
            raise forms.ValidationError('La misión está cerrada.')
        if not self.instance._state.adding:
            old=Asignacion.objects.select_related('mision').get(pk=self.instance.pk)
            changed=data.get('usuario')!=old.usuario or mission!=old.mision
            if changed and (old.ordenes.exists() or old.hallazgos.exists() or old.mision.operador_responsable_id==old.usuario_id):
                raise forms.ValidationError('La asignación tiene evidencia o es la del responsable. Crea otra asignación o cambia primero el responsable.')
        return data

class AssignmentForm(ActorForm):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        qs=Asignacion.objects.filter(mision__estado__in=['planificada','en_curso','pausada'],usuario__activo=True)
        if self.actor:
            qs=qs.filter(mision__in=writable_missions(self.actor))
            if not is_admin(self.actor): qs=qs.filter(usuario=business_user(self.actor))
        self.fields['asignacion'].queryset=qs.select_related('mision','usuario')
        if not self.instance._state.adding: self.fields['asignacion'].disabled=True
    def clean(self):
        data=super().clean()
        assignment=data.get('asignacion')
        if assignment:
            mission=Mision.objects.select_for_update().get(pk=assignment.mision_id)
            if mission.estado=='cerrada': raise forms.ValidationError('La misión está cerrada.')
        return data

class OrdenForm(AssignmentForm):
    accion=forms.ChoiceField(choices=[(v,v.replace('_',' ').capitalize()) for v in ['avanzar','retroceder','girar_izquierda','girar_derecha','parar']])
    class Meta:
        model=Orden
        fields=['asignacion','secuencia','accion','duracion_ms','vencimiento']
        widgets={'vencimiento':forms.DateTimeInput(attrs={'type':'datetime-local'},format='%Y-%m-%dT%H:%M:%S')}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['secuencia'].min_value=1
        if self.instance._state.adding: self.fields['vencimiento'].initial=timezone.now()+timedelta(seconds=20)
        self.fields['vencimiento'].widget.attrs['step']='1'
    def clean(self):
        data=super().clean()
        assignment=data.get('asignacion')
        expires=data.get('vencimiento')
        if not self.instance._state.adding:
            old=Orden.objects.get(pk=self.instance.pk)
            if old.enviada_en or old.confirmada_en or old.resultado!='pendiente' or old.esta_vencida:
                raise forms.ValidationError('Solo se editan órdenes pendientes, vigentes y todavía no enviadas.')
        if expires and not timezone.now()<expires<=timezone.now()+timedelta(seconds=30):
            self.add_error('vencimiento','La vigencia debe estar entre ahora y los próximos 30 segundos.')
        if data.get('secuencia',1)<1: self.add_error('secuencia','Debe ser positiva.')
        if assignment:
            mission=Mision.objects.select_for_update().get(pk=assignment.mision_id)
            if mission.estado!='en_curso': raise forms.ValidationError('La misión debe estar en curso.')
            if mission.operador_responsable_id!=assignment.usuario_id: raise forms.ValidationError('La orden debe pertenecer al operador responsable.')
            if not mission.robot.activo: raise forms.ValidationError('El robot está desactivado.')
            if data.get('accion')!='parar' and not mission.robot.conectado: raise forms.ValidationError('Enlace perdido: no se permiten nuevos movimientos.')
        # Aceptación/rechazo solo se recibe del dispositivo autenticado.
        self.instance.resultado='pendiente'
        return data

class HallazgoForm(AssignmentForm):
    estado=forms.ChoiceField(choices=[('pendiente','Pendiente'),('confirmado','Confirmado'),('descartado','Descartado')])
    class Meta:
        model=Hallazgo
        fields=['asignacion','descripcion','estado','posicion']
        widgets={'descripcion':forms.Textarea(attrs={'rows':4})}
    def clean(self):
        data=super().clean()
        state=data.get('estado')
        if self.instance._state.adding and state!='pendiente': self.add_error('estado','Todo hallazgo inicia pendiente de revisión.')
        elif not self.instance._state.adding:
            previous=Hallazgo.objects.get(pk=self.instance.pk).estado
            if previous in ('confirmado','descartado') and state!=previous: self.add_error('estado','La revisión ya fue finalizada.')
        return data
