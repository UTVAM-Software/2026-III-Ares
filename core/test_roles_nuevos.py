# [NUEVO] Pruebas de los perfiles 'Solo lectura' y 'Cliente'.
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User,Group
from usuarios.models import Usuario,Rol
from core.models import Robot,Mision,Asignacion,Hallazgo
from core.security import role
from telemetria.models import Sensor,Lectura,Evento

class NuevosRolesTests(TestCase):
    def setUp(self):
        admin=User.objects.create_superuser('admin_roles','admin_roles@example.test','StrongPassword1!')
        self.pa=Usuario.objects.create(user=admin,email=admin.email,nombre='Admin',rol=Rol.objects.get(nombre='Administrador'))
        self.op,self.pop=self.account('operador1','Operador')
        self.solo,_=self.account('consulta1','Solo lectura')
        self.cliente,_=self.account('cliente1','Cliente')
        self.robot=Robot.objects.create(codigo='ROL-ROBOT',nombre='Robot',creador=self.pa,credencial='',ultima_conexion=timezone.now())
        self.robot.set_credential('test-device-token-with-32-characters');self.robot.save()
        self.mission=Mision.objects.create(nombre='Mision Visible',zona='Zona A',robot=self.robot,creador=self.pa,operador_responsable=self.pop,estado='en_curso')
        self.assignment=Asignacion.objects.create(mision=self.mission,usuario=self.pop)
        self.finding=Hallazgo.objects.create(asignacion=self.assignment,descripcion='Evidencia original')
        self.sensor=Sensor.objects.create(robot=self.robot,canal='bat',tipo='Bateria',unidad='%')
        Lectura.objects.create(mision=self.mission,sensor=self.sensor,valor=5)
        Evento.objects.create(mision=self.mission,accion='Evento privado',resultado='ok')
    def account(self,name,role_name):
        user=User.objects.create_user(name,name+'@example.test','StrongPassword1!')
        user.groups.add(Group.objects.get(name=role_name))
        profile=Usuario.objects.create(user=user,email=user.email,nombre=name,rol=Rol.objects.get(nombre=role_name))
        return user,profile
    def get(self,name,pk=None): return self.client.get(reverse(name,kwargs={'pk':pk} if pk else None))

    # ---------- Solo lectura ----------
    def test_solo_lectura_tiene_rol_valido(self):
        self.assertEqual(role(self.solo),'Solo lectura')
    def test_solo_lectura_ve_todo_el_sistema(self):
        self.client.force_login(self.solo)
        for name in ['core:dashboard','core:mision_list','core:robot_list','core:asignacion_list','core:hallazgo_list','core:orden_list',
                     'telemetria:sensor_list','telemetria:lectura_list','telemetria:evento_list','telemetria:evento_admin_list',
                     'usuarios:auth_user_list','usuarios:auth_group_list','usuarios:auth_permission_list','usuarios:rol_list','usuarios:usuario_list']:
            with self.subTest(name=name): self.assertEqual(self.get(name).status_code,200)
        self.assertEqual(self.get('core:mision_detail',self.mission.pk).status_code,200)
        self.assertContains(self.get('core:mision_list'),'Mision Visible')
        self.assertContains(self.get('telemetria:evento_list'),'Evento privado')
    def test_solo_lectura_no_puede_crear(self):
        self.client.force_login(self.solo)
        for name in ['core:mision_create','core:robot_create','core:hallazgo_create','core:orden_create','core:asignacion_create',
                     'telemetria:sensor_create','telemetria:lectura_create','telemetria:evento_create',
                     'usuarios:auth_user_create','usuarios:auth_group_create','usuarios:rol_create','usuarios:usuario_create']:
            with self.subTest(name=name): self.assertEqual(self.get(name).status_code,403)
    def test_solo_lectura_no_puede_editar_ni_eliminar(self):
        self.client.force_login(self.solo)
        response=self.client.post(reverse('core:hallazgo_update',kwargs={'pk':self.finding.pk}),{'asignacion':self.assignment.pk,'descripcion':'cambiado','estado':'pendiente'})
        self.assertEqual(response.status_code,403)
        self.finding.refresh_from_db();self.assertEqual(self.finding.descripcion,'Evidencia original')
        self.assertEqual(self.client.post(reverse('core:robot_delete',kwargs={'pk':self.robot.pk})).status_code,403)
        self.assertEqual(self.client.post(reverse('core:mision_cambiar_estado',kwargs={'pk':self.mission.pk}),{'accion':'pausar'}).status_code,403)
        self.assertTrue(Robot.objects.filter(pk=self.robot.pk).exists())
        self.mission.refresh_from_db();self.assertEqual(self.mission.estado,'en_curso')
    def test_solo_lectura_no_ve_botones_de_edicion(self):
        self.client.force_login(self.solo)
        self.assertNotContains(self.get('core:mision_list'),reverse('core:mision_create'))
        self.assertNotContains(self.get('core:mision_list'),reverse('core:mision_update',kwargs={'pk':self.mission.pk}))
        self.assertNotContains(self.get('core:hallazgo_list'),reverse('core:hallazgo_update',kwargs={'pk':self.finding.pk}))

    # ---------- Cliente ----------
    def test_cliente_tiene_rol_valido(self):
        self.assertEqual(role(self.cliente),'Cliente')
    def test_cliente_ve_misiones_y_hallazgos(self):
        self.client.force_login(self.cliente)
        for name in ['core:dashboard','core:mision_list','core:hallazgo_list']:
            with self.subTest(name=name): self.assertEqual(self.get(name).status_code,200)
        self.assertEqual(self.get('core:mision_detail',self.mission.pk).status_code,200)
        self.assertContains(self.get('core:mision_list'),'Mision Visible')
        self.assertContains(self.get('core:hallazgo_list'),'Evidencia original')
    def test_cliente_no_ve_secciones_internas(self):
        self.client.force_login(self.cliente)
        for name in ['core:robot_list','core:asignacion_list','core:orden_list','telemetria:sensor_list','telemetria:lectura_list',
                     'telemetria:evento_list','telemetria:evento_admin_list','usuarios:auth_user_list','usuarios:auth_group_list',
                     'usuarios:auth_permission_list','usuarios:rol_list','usuarios:usuario_list']:
            with self.subTest(name=name): self.assertEqual(self.get(name).status_code,403)
    def test_cliente_no_puede_escribir(self):
        self.client.force_login(self.cliente)
        for name in ['core:mision_create','core:hallazgo_create','core:orden_create']:
            with self.subTest(name=name): self.assertEqual(self.get(name).status_code,403)
        response=self.client.post(reverse('core:hallazgo_update',kwargs={'pk':self.finding.pk}),{'asignacion':self.assignment.pk,'descripcion':'cambiado','estado':'pendiente'})
        self.assertEqual(response.status_code,403)
        self.finding.refresh_from_db();self.assertEqual(self.finding.descripcion,'Evidencia original')
    def test_cliente_menu_y_panel_sin_enlaces_internos(self):
        self.client.force_login(self.cliente)
        response=self.get('core:dashboard')
        for name in ['core:robot_list','core:orden_list','telemetria:sensor_list','telemetria:evento_list','usuarios:auth_user_list']:
            with self.subTest(name=name): self.assertNotContains(response,reverse(name))
        self.assertNotContains(response,'Evento privado')

    # ---------- Roles anteriores sin cambios ----------
    def test_operador_sigue_igual(self):
        self.client.force_login(self.op)
        self.assertEqual(self.get('core:hallazgo_create').status_code,200)
        self.assertEqual(self.get('usuarios:auth_user_list').status_code,403)