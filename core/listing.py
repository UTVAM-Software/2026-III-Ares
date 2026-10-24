from django import forms
from django.db.models import Q
from .models import Mision
from .security import missions, allowed

class DateFilters(forms.Form):
    desde = forms.DateField(label='Desde', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    hasta = forms.DateField(label='Hasta', required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def clean(self):
        data = super().clean()
        if data.get('desde') and data.get('hasta') and data['desde'] > data['hasta']:
            raise forms.ValidationError('La fecha inicial debe ser anterior a la final.')
        return data

class MissionFilters(DateFilters):
    estado = forms.ChoiceField(label='Estado', required=False, choices=[('', 'Todos')] + Mision.ESTADOS)
    q = forms.CharField(label='Nombre o zona', required=False, max_length=100)

class OrderFilters(DateFilters):
    mision = forms.ModelChoiceField(label='Misión', queryset=Mision.objects.none(), required=False)
    tipo = forms.ChoiceField(label='Acción', required=False, choices=[('', 'Todas')] + [(v, v.replace('_', ' ').capitalize()) for v in ('avanzar', 'retroceder', 'girar_izquierda', 'girar_derecha', 'parar')])

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['mision'].queryset = missions(user) if allowed(user, Mision) else Mision.objects.none()


def filter_dates(queryset, data, field):
    if data.get('desde'):
        queryset = queryset.filter(**{field + '__date__gte': data['desde']})
    if data.get('hasta'):
        queryset = queryset.filter(**{field + '__date__lte': data['hasta']})
    return queryset
