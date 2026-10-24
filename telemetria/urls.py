from django.urls import path
from . import device_api
from .views import (
    SensorListView, SensorCreateView, SensorUpdateView, SensorDeleteView,
    LecturaListView, LecturaCreateView, LecturaUpdateView, LecturaDeleteView,
    EventoListView, EventoCreateView, EventoUpdateView, EventoDeleteView, EventoAdminListView
)

app_name = 'telemetria'

urlpatterns = [
    # Sensores
    path('sensores/', SensorListView.as_view(), name='sensor_list'),
    path('sensores/nuevo/', SensorCreateView.as_view(), name='sensor_create'),
    path('sensores/<int:pk>/editar/', SensorUpdateView.as_view(), name='sensor_update'),
    path('sensores/<int:pk>/eliminar/', SensorDeleteView.as_view(), name='sensor_delete'),

    # Lecturas
    path('lecturas/', LecturaListView.as_view(), name='lectura_list'),
    path('lecturas/nueva/', LecturaCreateView.as_view(), name='lectura_create'),
    path('lecturas/<int:pk>/eliminar/', LecturaDeleteView.as_view(), name='lectura_delete'),

    path('lecturas/<int:pk>/editar/', LecturaUpdateView.as_view(), name='lectura_update'),

    # Eventos / Bitácora
    path('actividad/', EventoListView.as_view(), name='evento_list'),
    path('actividad/nuevo/', EventoCreateView.as_view(), name='evento_create'),
    path('administracion/eventos/', EventoAdminListView.as_view(), name='evento_admin_list'),
    path('administracion/eventos/<int:pk>/editar/', EventoUpdateView.as_view(), name='evento_update'),
    path('administracion/eventos/<int:pk>/eliminar/', EventoDeleteView.as_view(), name='evento_delete'),
    path('dispositivo/<slug:code>/consultar/', device_api.poll, name='device_poll'),
    path('dispositivo/<slug:code>/confirmar/', device_api.acknowledge, name='device_ack'),
    path('dispositivo/<slug:code>/lecturas/', device_api.reading, name='device_reading'),
]
