"""Acciones visibles; la autorización de las peticiones sigue en las vistas."""
from django import template
from django.contrib.auth.models import User, Group, Permission
from core.security import allowed, is_admin, business_user, object_mission, ROLES
from core.models import Robot, Mision, Asignacion, Orden
from telemetria.models import Sensor, Lectura, Evento
from usuarios.models import Usuario, Rol
from usuarios.forms import protected_permission

register = template.Library()

@register.simple_tag(takes_context=True)
def object_actions(context, obj):
    user = context['request'].user
    actions = {action: allowed(user, type(obj), action) for action in ('change', 'delete')}
    if not any(actions.values()): return actions
    mission = object_mission(obj)
    if mission and mission.estado == 'cerrada': return {'change': False, 'delete': False}
    if not is_admin(user):
        profile = business_user(user)
        if mission and mission.operador_responsable_id != profile.pk: return {'change': False, 'delete': False}
        if hasattr(obj, 'asignacion') and obj.asignacion.usuario_id != profile.pk: return {'change': False, 'delete': False}
    if isinstance(obj, Orden):
        if obj.enviada_en or obj.confirmada_en: actions = {'change': False, 'delete': False}
        elif obj.esta_vencida or obj.resultado != 'pendiente': actions['change'] = False
    elif isinstance(obj, Mision):
        if obj.estado != 'planificada' or obj.lecturas.exists() or obj.asignaciones.filter(ordenes__isnull=False).exists() or obj.asignaciones.filter(hallazgos__isnull=False).exists(): actions['delete'] = False
    elif isinstance(obj, Asignacion):
        if obj.mision.operador_responsable_id == obj.usuario_id or obj.ordenes.exists() or obj.hallazgos.exists(): actions['delete'] = False
    elif isinstance(obj, Lectura) and not obj.simulada:
        actions = {'change': False, 'delete': False}
    elif isinstance(obj, Evento) and obj.es_sistema:
        actions = {'change': False, 'delete': False}
    elif isinstance(obj, Sensor) and obj.lecturas.exists():
        actions['delete'] = False
    elif isinstance(obj, Robot) and obj.misiones.exists():
        actions['delete'] = False
    elif isinstance(obj, User):
        if not user.is_superuser and (obj.is_superuser or obj.is_staff): actions = {'change': False, 'delete': False}
        if obj.pk == user.pk: actions['delete'] = False
    elif isinstance(obj, Usuario):
        account = obj.user
        if account and not user.is_superuser and (account.is_superuser or account.is_staff): actions = {'change': False, 'delete': False}
        if obj.user_id == user.pk or obj.asignaciones.exists() or obj.robots_creados.exists() or obj.misiones_creadas.exists() or obj.misiones_responsables.exists(): actions['delete'] = False
    elif isinstance(obj, Group) and obj.name in ROLES:
        actions['delete'] = False
    elif isinstance(obj, Rol):
        if obj.nombre in ROLES: actions = {'change': False, 'delete': False}
        elif obj.usuarios.exists(): actions['delete'] = False
    elif isinstance(obj, Permission) and protected_permission(obj):
        actions['delete'] = False
    return actions
