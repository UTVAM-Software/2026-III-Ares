import uuid
from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User, Group, Permission

from usuarios.models import Rol, Usuario
from core.models import Robot, Mision, Asignacion, Orden, Hallazgo
from telemetria.models import Sensor, Lectura, Evento

class AresOwaspA01SecurityTests(TestCase):
    """
    Pruebas de Seguridad y Mitigación OWASP Top 10 A01:2021 (Broken Access Control).
    Verifica que las vistas no puedan ser accedidas directamente por URL sin autenticación,
    que los roles restringidos no puedan mutar datos ni ver recursos ajenos (Anti-IDOR),
    y que los flujos de Login/Logout funcionen correctamente.
    """

    def setUp(self):
        self.client = Client()

        # 1. Crear Roles y Grupos
        self.rol_admin = Rol.objects.get_or_create(nombre="Administrador")[0]
        self.rol_operador = Rol.objects.get_or_create(nombre="Operador")[0]
        self.rol_observador = Rol.objects.get_or_create(nombre="Observador")[0]

        self.grp_admin = Group.objects.get_or_create(name="Administrador")[0]
        self.grp_operador = Group.objects.get_or_create(name="Operador")[0]
        self.grp_observador = Group.objects.get_or_create(name="Observador")[0]

        # Asignar permisos básicos
        for codename in ['view_mision', 'add_mision', 'change_mision', 'view_robot', 'view_orden', 'add_orden', 'view_hallazgo', 'add_hallazgo']:
            p = Permission.objects.filter(codename=codename).first()
            if p:
                self.grp_operador.permissions.add(p)

        for codename in ['view_mision', 'view_robot', 'view_sensor', 'view_lectura', 'view_evento']:
            p = Permission.objects.filter(codename=codename).first()
            if p:
                self.grp_observador.permissions.add(p)

        # 2. Crear Usuarios de Prueba
        self.u_admin = User.objects.create_superuser('admin_test', 'admin@test.com', 'AdminPass123!')
        self.u_admin.groups.add(self.grp_admin)
        self.biz_admin = Usuario.objects.create(nombre="Admin Test", email=self.u_admin.email, user=self.u_admin, rol=self.rol_admin)

        self.u_operador1 = User.objects.create_user('operador1_test', 'op1@test.com', 'OpPass123!')
        self.u_operador1.groups.add(self.grp_operador)
        self.biz_operador1 = Usuario.objects.create(nombre="Operador 1", email=self.u_operador1.email, user=self.u_operador1, rol=self.rol_operador)

        self.u_operador2 = User.objects.create_user('operador2_test', 'op2@test.com', 'OpPass123!')
        self.u_operador2.groups.add(self.grp_operador)
        self.biz_operador2 = Usuario.objects.create(nombre="Operador 2", email=self.u_operador2.email, user=self.u_operador2, rol=self.rol_operador)

        self.u_observador = User.objects.create_user('observador_test', 'obs@test.com', 'ObsPass123!')
        self.u_observador.groups.add(self.grp_observador)
        self.biz_observador = Usuario.objects.create(nombre="Observador", email=self.u_observador.email, user=self.u_observador, rol=self.rol_observador)

        # 3. Crear Robot y Misión
        self.robot = Robot.objects.create(
            codigo="ROBOT-TEST-01",
            nombre="Robot de Prueba",
            credencial="token123",
            creador=self.biz_admin
        )

        self.mision_op1 = Mision.objects.create(
            nombre="Misión Operador 1",
            zona="Zona Alfa",
            robot=self.robot,
            creador=self.biz_operador1,
            operador_responsable=self.biz_operador1,
            estado="en_curso"
        )
        self.asig_op1 = Asignacion.objects.create(usuario=self.biz_operador1, mision=self.mision_op1)

    def test_bloqueo_url_directa_sin_autenticacion(self):
        """
        Criterio de Evaluación Docente:
        'se verificará que no se pueda acceder a vistas restringidas escribiendo directamente la URL en el navegador'
        """
        urls_protegidas = [
            reverse('core:dashboard'),
            reverse('core:mision_list'),
            reverse('core:mision_create'),
            reverse('core:robot_list'),
            reverse('core:orden_list'),
            reverse('core:hallazgo_list'),
            reverse('usuarios:auth_user_list'),
            reverse('usuarios:auth_group_list'),
            reverse('telemetria:sensor_list'),
            reverse('telemetria:lectura_list'),
            reverse('telemetria:evento_list'),
        ]

        for url in urls_protegidas:
            resp = self.client.get(url)
            # Debe redirigir de inmediato a la vista de login con ?next=
            self.assertEqual(
                resp.status_code, 302,
                f"Fallo de seguridad OWASP A01: La URL {url} no bloqueó el acceso no autenticado."
            )
            self.assertIn('/login/', resp.url)

    def test_flujo_login_logout(self):
        """
        Verifica el correcto flujo de inicio y cierre de sesión.
        """
        # Credenciales incorrectas
        resp_bad = self.client.post(reverse('login'), {'username': 'operador1_test', 'password': 'wrongpassword'})
        self.assertEqual(resp_bad.status_code, 200)
        self.assertFalse('_auth_user_id' in self.client.session)

        # Credenciales correctas
        resp_ok = self.client.post(reverse('login'), {'username': 'operador1_test', 'password': 'OpPass123!'})
        self.assertEqual(resp_ok.status_code, 302)
        self.assertTrue('_auth_user_id' in self.client.session)

        # Cierre de sesión (Logout)
        resp_logout = self.client.post(reverse('logout'))
        self.assertEqual(resp_logout.status_code, 302)
        self.assertFalse('_auth_user_id' in self.client.session)

    def test_observador_no_puede_modificar_ni_eliminar(self):
        """
        Observador tiene permiso estrictamente de solo lectura.
        Intentar crear o eliminar debe resultar en 403 Forbidden.
        """
        self.client.login(username='observador_test', password='ObsPass123!')

        # Intentar acceder a creación de misión
        resp_create = self.client.get(reverse('core:mision_create'))
        self.assertEqual(resp_create.status_code, 403)

        # Intentar eliminar misión
        resp_del = self.client.post(reverse('core:mision_delete', kwargs={'pk': self.mision_op1.pk}))
        self.assertEqual(resp_del.status_code, 403)

        # Intentar acceder a gestión de usuarios (solo admin)
        resp_users = self.client.get(reverse('usuarios:auth_user_list'))
        self.assertEqual(resp_users.status_code, 403)

    def test_anti_idor_operador_misiones_ajenas(self):
        """
        Mitigación IDOR (OWASP A01):
        El Operador 2 NO está asignado a la misión del Operador 1.
        Si intenta acceder al detalle de la misión manipulando el UUID en la URL, se bloquea con 403.
        """
        self.client.login(username='operador2_test', password='OpPass123!')

        # Operador 2 intenta ver la consola de la misión de Operador 1
        resp = self.client.get(reverse('core:mision_detail', kwargs={'pk': self.mision_op1.pk}))
        self.assertIn(
            resp.status_code, (403,404),
            "Fallo Anti-IDOR: Operador 2 pudo acceder a una misión en la que no está asignado."
        )

    def test_propiedades_y_metodos_modelo(self):
        """
        Verifica el funcionamiento de @property y métodos personalizados requeridos.
        """
        # Lectura reciente (<= 5s)
        sensor = Sensor.objects.create(robot=self.robot, canal="bat", tipo="Batería", unidad="%")
        lec = Lectura.objects.create(sensor=sensor, mision=self.mision_op1, valor=90.0)
        self.assertTrue(lec.es_reciente)

        # Orden vencida
        orden_vencida = Orden.objects.create(
            asignacion=self.asig_op1,
            secuencia=1,
            accion="avanzar",
            vencimiento=timezone.now() - timedelta(minutes=10)
        )
        self.assertTrue(orden_vencida.esta_vencida)

        # Métodos de estado de Misión
        self.mision_op1.pausar()
        self.assertEqual(self.mision_op1.estado, 'pausada')

        self.mision_op1.iniciar()
        self.assertEqual(self.mision_op1.estado, 'en_curso')
        self.assertTrue(self.mision_op1.is_activa)

        self.mision_op1.cerrar()
        self.assertEqual(self.mision_op1.estado, 'cerrada')
        self.assertIsNotNone(self.mision_op1.fin)
