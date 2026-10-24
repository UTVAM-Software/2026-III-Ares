from django.db import migrations
from django.contrib.auth.hashers import identify_hasher,make_password

def forwards(apps,schema_editor):
    User=apps.get_model('auth','User');Group=apps.get_model('auth','Group');Permission=apps.get_model('auth','Permission');ContentType=apps.get_model('contenttypes','ContentType')
    Profile=apps.get_model('usuarios','Usuario');Role=apps.get_model('usuarios','Rol')
    Robot=apps.get_model('core','Robot');Mission=apps.get_model('core','Mision');Event=apps.get_model('telemetria','Evento')
    models={'core':['robot','mision','asignacion','orden','hallazgo'],'telemetria':['sensor','lectura','evento'],'usuarios':['rol','usuario'],'auth':['user','group','permission']}
    groups={};roles={}
    for name in ['Administrador','Operador','Observador']:
        roles[name],_=Role.objects.get_or_create(nombre=name)
        groups[name],_=Group.objects.get_or_create(name=name)
        perms=[]
        for app,names in models.items():
            for model in names:
                ct,_=ContentType.objects.get_or_create(app_label=app,model=model)
                for action in ['view','add','change','delete']:
                    permission,_=Permission.objects.get_or_create(content_type=ct,codename=action+'_'+model,defaults={'name':action+' '+model})
                    permitted=name=='Administrador' or (app in ('core','telemetria') and (action=='view' or (name=='Operador' and action in ('add','change') and model in ('mision','orden','hallazgo','lectura'))))
                    if permitted: perms.append(permission)
        groups[name].permissions.set(perms)
    for profile in Profile.objects.filter(user__isnull=True):
        candidates=User.objects.filter(email__iexact=profile.email)
        if candidates.count()==1:
            account=candidates.get()
            if not Profile.objects.filter(user=account).exists():
                profile.user=account;profile.save(update_fields=['user'])
    for account in User.objects.filter(is_superuser=True):
        if not Profile.objects.filter(user=account).exists():
            email=account.email or f'admin-{account.pk}@ares.local'
            if not Profile.objects.filter(email__iexact=email).exists():
                Profile.objects.create(user=account,email=email,nombre=(' '.join([account.first_name,account.last_name]).strip() or account.username),rol=roles['Administrador'],activo=account.is_active)
    for robot in Robot.objects.all():
        try: identify_hasher(robot.credencial)
        except ValueError:
            robot.credencial=make_password(robot.credencial);robot.save(update_fields=['credencial'])
    for mission in Mission.objects.filter(operador_responsable__isnull=True):
        operators=Profile.objects.filter(asignaciones__mision=mission,rol__nombre='Operador',activo=True,user__is_active=True,user__groups__name='Operador').distinct()
        if operators.count()==1:
            mission.operador_responsable=operators.get();mission.save(update_fields=['operador_responsable'])
    Event.objects.all().update(es_sistema=True)

class Migration(migrations.Migration):
    dependencies=[('core','0002_alter_asignacion_options_alter_hallazgo_options_and_more'),('usuarios','0002_loginthrottle_alter_rol_options_and_more'),('telemetria','0002_alter_evento_options_alter_lectura_options_and_more')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
