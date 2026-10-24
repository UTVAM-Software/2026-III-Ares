from django import forms
from core.forms import ActorForm
from core.models import Mision,Robot
from core.security import scoped,writable_missions
from .models import Sensor,Lectura,Evento
from .validation import validate_reading_value

class SensorForm(ActorForm):
    class Meta:
        model=Sensor
        fields=['robot','canal','tipo','unidad']
    def clean(self):
        data=super().clean()
        if not self.instance._state.adding:
            old=Sensor.objects.get(pk=self.instance.pk)
            if old.lecturas.exists() and data.get('robot')!=old.robot:
                raise forms.ValidationError('Un sensor con lecturas no puede trasladarse a otro robot.')
        return data

class LecturaForm(ActorForm):
    class Meta:
        model=Lectura
        fields=['sensor','mision','valor']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.actor:
            self.fields['mision'].queryset=writable_missions(self.actor)
            self.fields['sensor'].queryset=scoped(self.actor,Sensor)
        else: self.fields['mision'].queryset=Mision.objects.exclude(estado='cerrada')
        if not self.instance._state.adding:
            self.fields['sensor'].disabled=True
            self.fields['mision'].disabled=True
    def clean(self):
        data=super().clean()
        sensor,mission,value=data.get('sensor'),data.get('mision'),data.get('valor')
        if not self.instance._state.adding and not self.instance.simulada: raise forms.ValidationError('Las lecturas del dispositivo son evidencia de solo consulta.')
        if value is not None:
            try:
                validate_reading_value(value, sensor)
            except forms.ValidationError as exc:
                self.add_error('valor', exc)
        if mission:
            mission=Mision.objects.select_for_update().get(pk=mission.pk)
            if mission.estado=='cerrada': raise forms.ValidationError('La misión está cerrada.')
            if sensor and sensor.robot_id!=mission.robot_id: raise forms.ValidationError('El sensor no pertenece al robot de la misión.')
        self.instance.simulada=True
        return data

class EventoForm(ActorForm):
    class Meta:
        model=Evento
        fields=['robot','mision','accion','resultado']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['mision'].queryset=Mision.objects.exclude(estado='cerrada')
        if not self.instance._state.adding:
            self.fields['mision'].disabled=True
            self.fields['robot'].disabled=True
    def clean(self):
        data=super().clean()
        mission,robot=data.get('mision'),data.get('robot')
        if self.instance.es_sistema: raise forms.ValidationError('La bitácora automática es inmutable.')
        if mission:
            mission=Mision.objects.select_for_update().get(pk=mission.pk)
            if mission.estado=='cerrada': raise forms.ValidationError('La misión está cerrada.')
            if robot and robot.pk!=mission.robot_id: raise forms.ValidationError('Robot y misión no corresponden.')
        return data
