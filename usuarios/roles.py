from django.contrib.auth.models import Group, Permission
from .models import Rol

# [NUEVO] Permisos de consulta de cada rol nuevo.
VISTA_SOLO_LECTURA = {
    'core': ['robot','mision','asignacion','orden','hallazgo'],
    'telemetria': ['sensor','lectura','evento'],
    'usuarios': ['rol','usuario'],
    'auth': ['user','group','permission'],
}
VISTA_CLIENTE = {'core': ['mision','hallazgo']}

# [NUEVO] Devuelve solo permisos "view_" de las secciones indicadas.
def view_permissions(sections):
    perms=Permission.objects.none()
    for app,models in sections.items():
        perms=perms|Permission.objects.filter(content_type__app_label=app,codename__in=['view_'+m for m in models])
    return perms

def ensure_roles():
    # [MODIFICADO] Se agregan 'Solo lectura' y 'Cliente' a la lista de roles.
    for name in ('Administrador','Operador','Observador','Solo lectura','Cliente'):
        Rol.objects.get_or_create(nombre=name)
        group,created=Group.objects.get_or_create(name=name)
        if created:
            # [NUEVO] Los dos roles nuevos reciben únicamente permisos de consulta.
            if name=='Solo lectura':
                group.permissions.set(view_permissions(VISTA_SOLO_LECTURA))
                continue
            if name=='Cliente':
                group.permissions.set(view_permissions(VISTA_CLIENTE))
                continue
            perms=Permission.objects.filter(content_type__app_label__in=['core','telemetria','usuarios','auth'])
            if name!='Administrador':
                perms=perms.filter(content_type__app_label__in=['core','telemetria'])
                codes=['view_'+m for m in ['robot','mision','asignacion','orden','hallazgo','sensor','lectura','evento']]
                if name=='Operador': codes += [a+'_'+m for a in ('add','change') for m in ('mision','orden','hallazgo','lectura')]
                perms=perms.filter(codename__in=codes)
            group.permissions.set(perms)