from django.urls import path
from .views import (
    DashboardView, MisionControlView,
    MisionListView, MisionDetailView, MisionCreateView, MisionUpdateView, MisionDeleteView, MisionCambiarEstadoView,
    RobotListView, RobotCreateView, RobotUpdateView, RobotDeleteView,
    AsignacionListView, AsignacionCreateView, AsignacionUpdateView, AsignacionDeleteView,
    OrdenListView, OrdenCreateView, OrdenUpdateView, OrdenDeleteView,
    HallazgoListView, HallazgoCreateView, HallazgoUpdateView, HallazgoDeleteView
)

app_name = 'core'

urlpatterns = [
    # Centro de operaciones / Dashboard
    path('', DashboardView.as_view(), name='dashboard'),

    # Misiones
    path('misiones/', MisionListView.as_view(), name='mision_list'),
    path('misiones/nueva/', MisionCreateView.as_view(), name='mision_create'),
    path('misiones/<uuid:pk>/', MisionDetailView.as_view(), name='mision_detail'),
    path('misiones/<uuid:pk>/editar/', MisionUpdateView.as_view(), name='mision_update'),
    path('misiones/<uuid:pk>/eliminar/', MisionDeleteView.as_view(), name='mision_delete'),
    path('misiones/<uuid:pk>/estado/', MisionCambiarEstadoView.as_view(), name='mision_cambiar_estado'),

    # Robots
    path('robots/', RobotListView.as_view(), name='robot_list'),
    path('robots/nuevo/', RobotCreateView.as_view(), name='robot_create'),
    path('robots/<uuid:pk>/editar/', RobotUpdateView.as_view(), name='robot_update'),
    path('robots/<uuid:pk>/eliminar/', RobotDeleteView.as_view(), name='robot_delete'),

    # Asignaciones
    path('asignaciones/', AsignacionListView.as_view(), name='asignacion_list'),
    path('asignaciones/nueva/', AsignacionCreateView.as_view(), name='asignacion_create'),
    path('asignaciones/<int:pk>/eliminar/', AsignacionDeleteView.as_view(), name='asignacion_delete'),

    path('asignaciones/<int:pk>/editar/', AsignacionUpdateView.as_view(), name='asignacion_update'),

    # Órdenes
    path('ordenes/', OrdenListView.as_view(), name='orden_list'),
    path('ordenes/nueva/', OrdenCreateView.as_view(), name='orden_create'),
    path('ordenes/<uuid:pk>/editar/', OrdenUpdateView.as_view(), name='orden_update'),
    path('ordenes/<uuid:pk>/eliminar/', OrdenDeleteView.as_view(), name='orden_delete'),

    # Hallazgos
    path('hallazgos/', HallazgoListView.as_view(), name='hallazgo_list'),
    path('hallazgos/nuevo/', HallazgoCreateView.as_view(), name='hallazgo_create'),
    path('hallazgos/<uuid:pk>/editar/', HallazgoUpdateView.as_view(), name='hallazgo_update'),
    path('hallazgos/<uuid:pk>/eliminar/', HallazgoDeleteView.as_view(), name='hallazgo_delete'),
    path('misiones/<uuid:pk>/control/', MisionControlView.as_view(), name='mision_control'),
]
