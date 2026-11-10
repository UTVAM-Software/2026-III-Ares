"""Política compartida por vistas, formularios y navegación."""
from usuarios.models import Usuario
# [MODIFICADO] Se agregan los roles 'Solo lectura' y 'Cliente'.
SOLO_LECTURA = 'Solo lectura'
CLIENTE = 'Cliente'
ROLES = ('Administrador', 'Operador', 'Observador', SOLO_LECTURA, CLIENTE)
# [NUEVO] Secciones que puede consultar el Cliente (usuario externo o visitante).
CLIENTE_MODELOS = (('core', 'mision'), ('core', 'hallazgo'))
# [NUEVO] Aplicaciones que puede consultar el rol Solo lectura (todo el sistema).
SOLO_LECTURA_APPS = ('core', 'telemetria', 'usuarios', 'auth')

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

# [NUEVO] Roles que consultan todos los registros, no solo los de sus misiones asignadas.
def sees_all(user): return role(user) in ('Administrador', SOLO_LECTURA, CLIENTE)

def allowed(user, model, action='view'):
    current = role(user)
    if not current: return False
    opts = model._meta
    # [NUEVO] Solo lectura: únicamente "ver", en todas las secciones del sistema.
    if current == SOLO_LECTURA:
        if action != 'view' or opts.app_label not in SOLO_LECTURA_APPS: return False
    # [NUEVO] Cliente: únicamente "ver" misiones y hallazgos.
    elif current == CLIENTE:
        if action != 'view' or (opts.app_label, opts.model_name) not in CLIENTE_MODELOS: return False
    elif current != 'Administrador':
        if opts.app_label not in ('core','telemetria'): return False
        if action != 'view' and (current != 'Operador' or action == 'delete' or opts.model_name not in ('mision','orden','hallazgo','lectura')): return False
    return user.has_perm(f'{opts.app_label}.{action}_{opts.model_name}')

def missions(user):
    from core.models import Mision
    qs = Mision.objects.all()
    if not role(user): return qs.none()
    # [MODIFICADO] Antes: is_admin(user). Ahora Solo lectura y Cliente también ven todas.
    return qs if sees_all(user) else qs.filter(asignaciones__usuario=business_user(user)).distinct()

def scoped(user, model):
    from core.models import Mision, Robot, Asignacion, Orden, Hallazgo
    from telemetria.models import Sensor, Lectura, Evento
    qs = model.objects.all()
    current = role(user)
    if not current: return qs.none()
    # [NUEVO] El Cliente solo obtiene registros de misiones y hallazgos.
    if current == CLIENTE: return qs if model in (Mision, Hallazgo) else qs.none()
    # [MODIFICADO] Antes: solo Administrador. Ahora Solo lectura también ve todo.
    if current in ('Administrador', SOLO_LECTURA): return qs
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