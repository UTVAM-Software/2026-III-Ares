from django.contrib.auth.models import Group, Permission
from .models import Rol

def ensure_roles():
    for name in ('Administrador','Operador','Observador'):
        Rol.objects.get_or_create(nombre=name)
        group,created=Group.objects.get_or_create(name=name)
        if created:
            perms=Permission.objects.filter(content_type__app_label__in=['core','telemetria','usuarios','auth'])
            if name!='Administrador':
                perms=perms.filter(content_type__app_label__in=['core','telemetria'])
                codes=['view_'+m for m in ['robot','mision','asignacion','orden','hallazgo','sensor','lectura','evento']]
                if name=='Operador': codes += [a+'_'+m for a in ('add','change') for m in ('mision','orden','hallazgo','lectura')]
                perms=perms.filter(codename__in=codes)
            group.permissions.set(perms)
