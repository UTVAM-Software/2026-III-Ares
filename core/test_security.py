import json
from datetime import timedelta
from django.test import TestCase,Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User,Group,Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.template.loader import get_template
from django.conf import settings
from usuarios.models import Usuario,Rol,LoginThrottle
from usuarios.forms import DjangoUserCreationForm,DjangoUserUpdateForm
from core.models import Robot,Mision,Asignacion,Orden,Hallazgo
from core.security import role
from telemetria.models import Sensor,Lectura,Evento

class SecurityRegressionTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser('admin_reg','admin_reg@example.test','StrongPassword1!')
        self.pa=Usuario.objects.create(user=self.admin,email=self.admin.email,nombre='Admin',rol=Rol.objects.get(nombre='Administrador'))
        self.op,self.p1=self.account('one','Operador')
        self.other,self.p2=self.account('two','Operador')
        self.observer,self.po=self.account('reader','Observador')
        self.robot=Robot.objects.create(codigo='TEST-ROBOT',nombre='Robot',creador=self.pa,credencial='',ultima_conexion=timezone.now())
        self.robot.set_credential('test-device-token-with-32-characters');self.robot.save()
        self.mission=Mision.objects.create(nombre='Assigned Mission',zona='Zone',robot=self.robot,creador=self.pa,operador_responsable=self.p1,estado='en_curso')
        self.assignment=Asignacion.objects.create(mision=self.mission,usuario=self.p1)
        self.order=Orden.objects.create(asignacion=self.assignment,secuencia=1,accion='avanzar',vencimiento=timezone.now()+timedelta(seconds=25))
        self.finding=Hallazgo.objects.create(asignacion=self.assignment,descripcion='Evidence')
        self.sensor=Sensor.objects.create(robot=self.robot,canal='bat',tipo='Bateria',unidad='%')
    def account(self,name,role_name):
        user=User.objects.create_user(name,name+'@example.test','StrongPassword1!')
        user.groups.add(Group.objects.get(name=role_name))
        profile=Usuario.objects.create(user=user,email=user.email,nombre=name,rol=Rol.objects.get(nombre=role_name))
        return user,profile
    def login(self,user=None): self.client.force_login(user or self.admin)
    def post(self,name,pk=None,data=None): return self.client.post(reverse(name,kwargs={'pk':pk} if pk else None),data or {})
    def order_data(self,**extra):
        data={'asignacion':self.assignment.pk,'secuencia':2,'accion':'avanzar','duracion_ms':500,'vencimiento':(timezone.now()+timedelta(seconds=20)).isoformat()}
        data.update(extra);return data
    def device(self,name,data=None,token='test-device-token-with-32-characters'):
        return self.client.post(reverse('telemetria:'+name,kwargs={'code':self.robot.codigo}),data=json.dumps(data or {}),content_type='application/json',HTTP_AUTHORIZATION='Bearer '+token)

    def test_no_role_blocked_all_lists(self):
        user=User.objects.create_user('none','none@example.test','StrongPassword1!');self.login(user)
        for name in ['core:dashboard','core:mision_list','core:robot_list','core:asignacion_list','core:hallazgo_list','core:orden_list','telemetria:sensor_list','telemetria:lectura_list','telemetria:evento_list']:
            with self.subTest(name=name): self.assertEqual(self.client.get(reverse(name)).status_code,403)
    def test_unassigned_observer_cannot_see_mission(self):
        self.login(self.observer)
        self.assertEqual(self.client.get(reverse('core:mision_detail',kwargs={'pk':self.mission.pk})).status_code,404)
        self.assertNotContains(self.client.get(reverse('core:mision_list')),self.mission.nombre)
    def test_assigned_observer_reads_but_cannot_write(self):
        Asignacion.objects.create(mision=self.mission,usuario=self.po);self.login(self.observer)
        self.assertEqual(self.client.get(reverse('core:mision_detail',kwargs={'pk':self.mission.pk})).status_code,200)
        self.assertEqual(self.post('core:hallazgo_update',self.finding.pk,{'descripcion':'stolen'}).status_code,403)
    def test_foreign_order_cannot_be_changed(self):
        self.login(self.other)
        self.assertIn(self.post('core:orden_update',self.order.pk,self.order_data(accion='parar',secuencia=1)).status_code,(403,404))
        self.order.refresh_from_db();self.assertEqual(self.order.accion,'avanzar')
    def test_foreign_finding_cannot_be_changed(self):
        self.login(self.other)
        self.assertIn(self.post('core:hallazgo_update',self.finding.pk,{'asignacion':self.assignment.pk,'descripcion':'stolen','estado':'pendiente'}).status_code,(403,404))
        self.finding.refresh_from_db();self.assertEqual(self.finding.descripcion,'Evidence')
    def test_foreign_reading_rejected(self):
        self.login(self.other)
        response=self.post('telemetria:lectura_create',data={'mision':self.mission.pk,'sensor':self.sensor.pk,'valor':1})
        self.assertEqual(response.status_code,200);self.assertFalse(Lectura.objects.exists())
    def test_forms_hide_unassigned_choices(self):
        self.login(self.other)
        response=self.client.get(reverse('core:orden_create'))
        self.assertNotContains(response,self.mission.nombre)
    def test_all_related_lists_and_dashboard_hide_foreign_data(self):
        Lectura.objects.create(mision=self.mission,sensor=self.sensor,valor=5)
        Evento.objects.create(mision=self.mission,accion='Private action',resultado='ok')
        self.login(self.other)
        for name,marker in [('core:dashboard',self.mission.nombre),('core:hallazgo_list','Evidence'),('core:asignacion_list',self.mission.nombre),('telemetria:evento_list','Private action'),('telemetria:lectura_list',self.mission.nombre)]:
            with self.subTest(name=name): self.assertNotContains(self.client.get(reverse(name)),marker)
    def test_explicit_permission_removed_is_enforced(self):
        group=Group.objects.get(name='Operador');group.permissions.remove(Permission.objects.get(codename='view_mision'))
        self.login(self.op);self.assertEqual(self.client.get(reverse('core:mision_list')).status_code,403)
    def test_direct_permission_can_restore_allowed_action(self):
        permission=Permission.objects.get(codename='view_mision');self.op.groups.get(name='Operador').permissions.remove(permission);self.op.user_permissions.add(permission)
        self.login(self.op);self.assertEqual(self.client.get(reverse('core:mision_list')).status_code,200)
    def test_observer_cannot_gain_write_with_direct_permission(self):
        self.observer.user_permissions.add(Permission.objects.get(codename='change_hallazgo'));self.login(self.observer)
        self.assertEqual(self.post('core:hallazgo_update',self.finding.pk).status_code,403)
    def test_closed_mission_blocks_edits_state_and_children(self):
        self.mission.cerrar();self.login()
        for name,pk in [('core:mision_update',self.mission.pk),('core:mision_delete',self.mission.pk),('core:hallazgo_update',self.finding.pk),('core:orden_update',self.order.pk),('core:asignacion_update',self.assignment.pk)]:
            with self.subTest(name=name): self.assertEqual(self.post(name,pk).status_code,403)
        self.assertEqual(self.post('core:mision_cambiar_estado',self.mission.pk,{'accion':'iniciar'}).status_code,403)
        with self.assertRaises(ValidationError): self.mission.iniciar()
    def test_mission_start_requires_responsible(self):
        self.mission.estado='planificada';self.mission.operador_responsable=None;self.mission.save()
        with self.assertRaises(ValidationError): self.mission.iniciar()
    def test_two_active_missions_rejected(self):
        second=Mision.objects.create(nombre='Second',zona='Z',robot=self.robot,creador=self.pa,operador_responsable=self.p1)
        Asignacion.objects.create(mision=second,usuario=self.p1)
        with self.assertRaises(ValidationError): second.iniciar()
    def test_create_mission_assigns_responsible(self):
        self.login();response=self.post('core:mision_create',data={'nombre':'New','zona':'Z','robot':self.robot.pk,'operador_responsable':self.p1.pk})
        self.assertEqual(response.status_code,302)
        mission=Mision.objects.get(nombre='New');self.assertEqual(mission.estado,'planificada');self.assertTrue(mission.asignaciones.filter(usuario=self.p1).exists())
    def test_valid_order_stays_pending_and_cannot_spoof_result(self):
        self.login(self.op)
        response=self.post('core:orden_create',data=self.order_data(resultado='aceptada'))
        self.assertEqual(response.status_code,302)
        order=Orden.objects.get(secuencia=2);self.assertEqual(order.resultado,'pendiente');self.assertIsNone(order.confirmada_en)
    def test_expired_excessive_duration_and_invalid_action_rejected(self):
        self.login(self.op)
        for extra in [{'vencimiento':(timezone.now()-timedelta(seconds=1)).isoformat()},{'duracion_ms':2001},{'accion':'arbitrary'},{'secuencia':-1}]:
            with self.subTest(extra=extra): self.assertEqual(self.post('core:orden_create',data=self.order_data(**extra)).status_code,200)
        self.assertEqual(Orden.objects.count(),1)
    def test_duplicate_sequence_rejected(self):
        self.login(self.op);self.assertEqual(self.post('core:orden_create',data=self.order_data(secuencia=1)).status_code,200);self.assertEqual(Orden.objects.count(),1)
    def test_lost_link_blocks_movement(self):
        self.robot.ultima_conexion=None;self.robot.save();self.login(self.op)
        self.assertEqual(self.post('core:orden_create',data=self.order_data()).status_code,200)
    def test_reading_sensor_must_match_robot(self):
        robot=Robot.objects.create(codigo='OTHER',nombre='Other',creador=self.pa,credencial='fake')
        sensor=Sensor.objects.create(robot=robot,canal='x',tipo='T',unidad='C');self.login()
        self.assertEqual(self.post('telemetria:lectura_create',data={'sensor':sensor.pk,'mision':self.mission.pk,'valor':5}).status_code,200)
        self.assertFalse(Lectura.objects.exists())
    def test_weak_password_rejected(self):
        form=DjangoUserCreationForm(data={'username':'weak','email':'weak@example.test','password':'1','password_confirm':'1','rol_ares':self.p1.rol_id,'is_active':True})
        self.assertFalse(form.is_valid());self.assertIn('password',form.errors)
    def test_email_login_and_generic_failure(self):
        response=self.client.post(reverse('login'),{'username':self.op.email,'password':'StrongPassword1!'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(int(self.client.session['_auth_user_id']),self.op.pk)
    def test_login_throttle(self):
        for i in range(5): self.client.post(reverse('login'),{'username':self.op.username,'password':'wrong'})
        self.assertEqual(self.client.post(reverse('login'),{'username':self.op.username,'password':'StrongPassword1!'}).status_code,429)
        LoginThrottle.objects.update(ventana=timezone.now()-timedelta(minutes=6))
        self.assertEqual(self.client.post(reverse('login'),{'username':self.op.username,'password':'StrongPassword1!'}).status_code,302)
    def test_role_change_removes_previous_global_group(self):
        user,profile=self.account('manager','Administrador')
        form=DjangoUserUpdateForm(instance=user,data={'username':user.username,'email':user.email,'rol_ares':self.p1.rol_id,'is_active':True})
        self.assertTrue(form.is_valid(),form.errors);form.save();self.assertEqual(role(user),'Operador');self.assertFalse(user.groups.filter(name='Administrador').exists())
    def test_email_change_preserves_profile_assignments(self):
        form=DjangoUserUpdateForm(instance=self.op,data={'username':self.op.username,'email':'changed@example.test','rol_ares':self.p1.rol_id,'is_active':True})
        self.assertTrue(form.is_valid(),form.errors);form.save();self.p1.refresh_from_db()
        self.assertEqual(self.p1.email,'changed@example.test');self.assertTrue(Asignacion.objects.filter(pk=self.assignment.pk,usuario=self.p1).exists())
    def test_business_deactivation_revokes_access(self):
        self.login(self.op);self.p1.activo=False;self.p1.save()
        self.assertEqual(self.client.get(reverse('core:dashboard')).status_code,403)
    def test_manual_event_crud_and_system_event_immutable(self):
        self.login();response=self.post('telemetria:evento_create',data={'mision':self.mission.pk,'robot':self.robot.pk,'accion':'Manual','resultado':'Nota'})
        self.assertEqual(response.status_code,302)
        manual=Evento.objects.get(accion='Manual');automatic=Evento.objects.filter(es_sistema=True).first()
        self.assertEqual(self.post('telemetria:evento_update',manual.pk,{'accion':'Corrected','resultado':'Nota'}).status_code,302)
        self.assertEqual(self.post('telemetria:evento_delete',automatic.pk).status_code,404)
        self.assertEqual(self.post('telemetria:evento_delete',manual.pk).status_code,302)
    def test_permission_crud_protects_builtin(self):
        self.login();ct=ContentType.objects.get_for_model(Mision)
        self.assertEqual(self.post('usuarios:auth_permission_create',data={'name':'Export','codename':'export_mission','content_type':ct.pk}).status_code,302)
        permission=Permission.objects.get(codename='export_mission')
        self.assertEqual(self.post('usuarios:auth_permission_update',permission.pk,{'name':'Export updated','codename':'export_mission','content_type':ct.pk}).status_code,302)
        self.assertEqual(self.post('usuarios:auth_permission_delete',permission.pk).status_code,302)
        self.assertEqual(self.post('usuarios:auth_permission_delete',Permission.objects.get(codename='view_mision').pk).status_code,403)
    def test_date_filter_and_invalid_uuid(self):
        self.login();old=Evento.objects.create(mision=self.mission,accion='Old marker',resultado='ok');Evento.objects.filter(pk=old.pk).update(fecha_hora=timezone.now()-timedelta(days=5))
        response=self.client.get(reverse('telemetria:evento_list'),{'desde':timezone.localdate().isoformat()});self.assertNotContains(response,'Old marker')
        self.assertEqual(self.client.get(reverse('telemetria:evento_list'),{'mision':'invalid'}).status_code,200)
    def test_device_authentication_and_revocation(self):
        self.assertEqual(self.device('device_poll',token='wrong').status_code,401)
        self.robot.activo=False;self.robot.save();self.assertEqual(self.device('device_poll').status_code,401)
    def test_device_delivery_once_and_ack(self):
        response=self.device('device_poll');self.assertEqual(response.status_code,200);self.assertEqual(len(response.json()['ordenes']),1)
        self.assertEqual(self.device('device_poll').json()['ordenes'],[])
        self.assertEqual(self.device('device_ack',{'id':str(self.order.pk),'resultado':'aceptada'}).status_code,200)
        self.order.refresh_from_db();self.assertIsNotNone(self.order.confirmada_en)
    def test_device_cannot_ack_unsent_or_late_order(self):
        self.assertEqual(self.device('device_ack',{'id':str(self.order.pk),'resultado':'aceptada'}).status_code,409)
        self.order.enviada_en=timezone.now();self.order.vencimiento=timezone.now()-timedelta(seconds=1);self.order.save()
        self.assertEqual(self.device('device_ack',{'id':str(self.order.pk),'resultado':'aceptada'}).status_code,409)
    def test_device_real_reading_is_readonly(self):
        response=self.device('device_reading',{'mision':str(self.mission.pk),'sensor':self.sensor.pk,'valor':80})
        self.assertEqual(response.status_code,201);sample=Lectura.objects.get(pk=response.json()['id']);self.assertFalse(sample.simulada)
        self.login();self.assertEqual(self.post('telemetria:lectura_delete',sample.pk).status_code,404)
    def test_device_reconnect_does_not_resume_old_movement(self):
        self.robot.ultima_conexion=timezone.now()-timedelta(minutes=1);self.robot.save()
        self.assertEqual(self.device('device_poll').json()['ordenes'],[])
        self.order.refresh_from_db();self.assertEqual(self.order.resultado,'rechazada')
    def test_csrf_required_for_browser_writes(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        self.assertEqual(client.post(reverse('core:robot_create'),{}).status_code,403)
        self.assertEqual(client.post(reverse('logout')).status_code,403)
    def test_all_templates_compile(self):
        for path in (settings.BASE_DIR/'templates').rglob('*.html'):
            with self.subTest(path=path.name): get_template(path.relative_to(settings.BASE_DIR/'templates').as_posix())
    def test_protected_delete_is_handled_without_500(self):
        self.login();self.assertEqual(self.post('core:robot_delete',self.robot.pk).status_code,302)
        self.assertTrue(Robot.objects.filter(pk=self.robot.pk).exists())
    def test_native_admin_does_not_bypass_mission_protection(self):
        self.login();self.assertEqual(self.client.post(reverse('admin:core_mision_change',args=[self.mission.pk]),{'nombre':'bypass'}).status_code,403)

    def test_unsupported_delete_method_cannot_bypass_guards(self):
        self.login()
        permission=Permission.objects.get(codename='view_mision')
        response=self.client.delete(reverse('usuarios:auth_permission_delete',kwargs={'pk':permission.pk}))
        self.assertEqual(response.status_code,405);self.assertTrue(Permission.objects.filter(pk=permission.pk).exists())
    def test_new_assignment_update_and_manual_reading_update(self):
        assignment=Asignacion.objects.create(mision=self.mission,usuario=self.po)
        self.login()
        self.assertEqual(self.post('core:asignacion_update',assignment.pk,{'mision':self.mission.pk,'usuario':self.p2.pk}).status_code,302)
        assignment.refresh_from_db();self.assertEqual(assignment.usuario_id,self.p2.pk)
        sample=Lectura.objects.create(mision=self.mission,sensor=self.sensor,valor=12,simulada=True)
        self.assertEqual(self.post('telemetria:lectura_update',sample.pk,{'valor':15}).status_code,302)
        sample.refresh_from_db();self.assertEqual(sample.valor,15)
    def test_control_button_creates_real_pending_record(self):
        self.login(self.op)
        self.assertEqual(self.post('core:mision_control',self.mission.pk,{'accion':'parar'}).status_code,302)
        self.assertTrue(Orden.objects.filter(accion='parar',resultado='pendiente',confirmada_en__isnull=True).exists())
    def test_all_admin_html_routes_render(self):
        from django.urls import get_resolver,URLPattern,URLResolver
        self.login()
        objects={'robot':self.robot,'mision':self.mission,'asignacion':self.assignment,'orden':self.order,'hallazgo':self.finding,'sensor':self.sensor,
            'lectura':Lectura.objects.create(sensor=self.sensor,mision=self.mission,valor=12),'evento':Evento.objects.create(mision=self.mission,accion='Manual',resultado='ok'),
            'user':self.other,'group':Group.objects.get(name='Operador'),'permission':Permission.objects.get(codename='view_mision'),'rol':self.p1.rol,'usuario':self.p1}
        for prefix in ('core','usuarios','telemetria'):
            import importlib
            urls=importlib.import_module(prefix+'.urls').urlpatterns
            for item in urls:
                name=item.name
                if name.startswith('device_') or name in ('mision_cambiar_estado','mision_control'): continue
                pk=None
                if '<' in str(item.pattern):
                    slug=name.replace('auth_','').rsplit('_',1)[0]
                    pk=objects[slug].pk
                with self.subTest(name=name):
                    response=self.client.get(reverse(prefix+':'+name,kwargs={'pk':pk} if pk else None))
                    self.assertEqual(response.status_code,200)
