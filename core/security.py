"""Política compartida por vistas, formularios y navegación."""
from usuarios.models import Usuario
ROLES = ('Administrador', 'Operador', 'Observador')

def business_user(user):
    return Usuario.objects.filter(user=user, activo=True).select_related('rol').first() if user.is_authenticated else None

def role(user):
    if not user.is_authenticated or not user.is_active: return None
    if user.is_superuser: return 'Administrador'
    profile = business_user(user)
    if not profile: return None
    groups = list(user.groups.filter(name__in=ROLES).values_list('name', flat=True))
    return groups[0] if len(groups) == 1 and profile.rol.nombre == groups[0] else None

def is_admin(user): return role(user) == 'Administrador'

def allowed(user, model, action='view'):
    current = role(user)
    if not current: return False
    opts = model._meta
    if current != 'Administrador':
        if opts.app_label not in ('core','telemetria'): return False
        if action != 'view' and (current != 'Operador' or action == 'delete' or opts.model_name not in ('mision','orden','hallazgo','lectura')): return False
    return user.has_perm(f'{opts.app_label}.{action}_{opts.model_name}')

def missions(user):
    from core.models import Mision
    qs = Mision.objects.all()
    if not role(user): return qs.none()
    return qs if is_admin(user) else qs.filter(asignaciones__usuario=business_user(user)).distinct()

def scoped(user, model):
    from core.models import Mision, Robot, Asignacion, Orden, Hallazgo
    from telemetria.models import Sensor, Lectura, Evento
    qs = model.objects.all()
    if not role(user): return qs.none()
    if is_admin(user): return qs
    visible = missions(user)
    if model == Mision: return visible
    if model == Robot: return qs.filter(misiones__in=visible).distinct()
    if model == Sensor: return qs.filter(robot__misiones__in=visible).distinct()
    if model == Asignacion: return qs.filter(mision__in=visible)
    if model in (Orden, Hallazgo): return qs.filter(asignacion__mision__in=visible)
    if model in (Lectura, Evento): return qs.filter(mision__in=visible)
    return qs.none()

def writable_missions(user):
    qs = missions(user).exclude(estado='cerrada')
    return qs if is_admin(user) else qs.filter(operador_responsable=business_user(user))

def object_mission(obj):
    from core.models import Mision, Asignacion, Orden, Hallazgo
    from telemetria.models import Lectura, Evento
    if isinstance(obj, Mision): return obj
    if isinstance(obj, (Asignacion,Lectura,Evento)): return obj.mision
    if isinstance(obj, (Orden,Hallazgo)): return obj.asignacion.mision
    return None

def assign_role(user, profile, role_obj):
    from django.contrib.auth.models import Group
    from usuarios.roles import ensure_roles
    ensure_roles()
    user.groups.remove(*Group.objects.filter(name__in=ROLES))
    user.groups.add(Group.objects.get(name=role_obj.nombre))
    profile.rol = role_obj
    profile.save(update_fields=['rol'])
    for attr in ('_perm_cache','_group_perm_cache','_user_perm_cache'): user.__dict__.pop(attr,None)
