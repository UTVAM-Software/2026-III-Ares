# [NUEVO] Crea los roles 'Solo lectura' y 'Cliente' con permisos únicamente de consulta.
from django.db import migrations

NUEVOS_ROLES = {
    'Solo lectura': {
        'core': ['robot','mision','asignacion','orden','hallazgo'],
        'telemetria': ['sensor','lectura','evento'],
        'usuarios': ['rol','usuario'],
        'auth': ['user','group','permission'],
    },
    'Cliente': {
        'core': ['mision','hallazgo'],
    },
}

def forwards(apps, schema_editor):
    Group = apps.get_model('auth','Group')
    Permission = apps.get_model('auth','Permission')
    ContentType = apps.get_model('contenttypes','ContentType')
    Rol = apps.get_model('usuarios','Rol')
    for nombre, secciones in NUEVOS_ROLES.items():
        Rol.objects.get_or_create(nombre=nombre)
        grupo, _ = Group.objects.get_or_create(name=nombre)
        permisos = []
        for app, modelos in secciones.items():
            for modelo in modelos:
                ct, _ = ContentType.objects.get_or_create(app_label=app, model=modelo)
                permiso, _ = Permission.objects.get_or_create(content_type=ct, codename='view_'+modelo, defaults={'name':'Can view '+modelo})
                permisos.append(permiso)
        grupo.permissions.set(permisos)

def backwards(apps, schema_editor):
    Group = apps.get_model('auth','Group')
    Rol = apps.get_model('usuarios','Rol')
    Group.objects.filter(name__in=NUEVOS_ROLES).delete()
    Rol.objects.filter(nombre__in=NUEVOS_ROLES, usuarios__isnull=True).delete()

class Migration(migrations.Migration):
    dependencies = [('core','0003_security_data'), ('usuarios','0002_loginthrottle_alter_rol_options_and_more'), ('auth','0012_alter_user_first_name_max_length'), ('contenttypes','0002_remove_content_type_name')]
    operations = [migrations.RunPython(forwards, backwards)]