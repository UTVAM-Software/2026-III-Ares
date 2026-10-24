from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from usuarios.models import Rol, Usuario
from core.models import Robot, Mision
from telemetria.models import Sensor, Lectura, Evento

class AresTelemetriaTests(TestCase):
    """
    Pruebas para los modelos y vistas de Telemetría (Sensor, Lectura, Evento).
    """

    def setUp(self):
        self.client = Client()

        self.rol_admin = Rol.objects.get_or_create(nombre="Administrador")[0]
        self.grp_admin = Group.objects.get_or_create(name="Administrador")[0]
        self.user_admin = User.objects.create_superuser('admin_tele', 'admin@tele.com', 'Pass123!')
        self.user_admin.groups.add(self.grp_admin)
        self.biz_admin = Usuario.objects.create(nombre="Admin Tele", email=self.user_admin.email, user=self.user_admin, rol=self.rol_admin)

        self.robot = Robot.objects.create(
            codigo="ROBOT-TEL-01",
            nombre="Robot Telemetría",
            credencial="token-tele",
            creador=self.biz_admin
        )
        self.mision = Mision.objects.create(
            nombre="Misión Telemetría",
            zona="Zona Beta",
            robot=self.robot,
            creador=self.biz_admin
        )

    def test_sensor_crud(self):
        self.client.login(username='admin_tele', password='Pass123!')

        # Crear sensor
        resp = self.client.post(reverse('telemetria:sensor_create'), {
            'robot': self.robot.pk,
            'canal': 'ch_test_1',
            'tipo': 'Ultrasonido',
            'unidad': 'cm'
        })
        self.assertEqual(resp.status_code, 302)
        sensor = Sensor.objects.filter(canal='ch_test_1').first()
        self.assertIsNotNone(sensor)

        # Listar sensores
        resp_list = self.client.get(reverse('telemetria:sensor_list'))
        self.assertEqual(resp_list.status_code, 200)

    def test_lectura_y_evento_list(self):
        self.client.login(username='admin_tele', password='Pass123!')

        sensor = Sensor.objects.create(robot=self.robot, canal="bat", tipo="Batería", unidad="%")
        Lectura.objects.create(sensor=sensor, mision=self.mision, valor=88.5)

        resp_lec = self.client.get(reverse('telemetria:lectura_list'))
        self.assertEqual(resp_lec.status_code, 200)

        # Bitácora
        Evento.objects.create(
            actor=self.biz_admin,
            robot=self.robot,
            mision=self.mision,
            accion="Test evento",
            resultado="Éxito"
        )
        resp_ev = self.client.get(reverse('telemetria:evento_list'))
        self.assertEqual(resp_ev.status_code, 200)
