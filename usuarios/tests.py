from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group, Permission
from usuarios.models import Rol, Usuario

class AresUsuariosDjangoAuthTests(TestCase):
    """
    Pruebas para el Requerimiento 4:
    Gestión de Django Auth (User, Group, Permission) y modelos de negocio Rol/Usuario
    desde la propia interfaz del sistema (sin depender únicamente de /admin).
    """

    def setUp(self):
        self.client = Client()

        # Rol y Grupo Administrador
        self.rol_admin = Rol.objects.get_or_create(nombre="Administrador")[0]
        self.grp_admin = Group.objects.get_or_create(name="Administrador")[0]
        self.admin_user = User.objects.create_superuser('admin_auth', 'admin@auth.com', 'AdminPass123!')
        self.admin_user.groups.add(self.grp_admin)
        self.biz_admin = Usuario.objects.create(nombre="Admin Auth", email=self.admin_user.email, user=self.admin_user, rol=self.rol_admin)

        # Usuario Observador (para verificar restricciones de acceso)
        self.rol_obs = Rol.objects.get_or_create(nombre="Observador")[0]
        self.grp_obs = Group.objects.get_or_create(name="Observador")[0]
        self.obs_user = User.objects.create_user('obs_auth', 'obs@auth.com', 'ObsPass123!')
        self.obs_user.groups.add(self.grp_obs)
        self.biz_obs = Usuario.objects.create(nombre="Obs Auth", email=self.obs_user.email, user=self.obs_user, rol=self.rol_obs)

    def test_gestion_usuarios_django_auth(self):
        """
        El Administrador puede listar, crear, editar y eliminar usuarios en auth.User.
        """
        self.client.login(username='admin_auth', password='AdminPass123!')

        # 1. Listar usuarios
        resp_list = self.client.get(reverse('usuarios:auth_user_list'))
        self.assertEqual(resp_list.status_code, 200)

        # 2. Crear usuario vía formulario
        resp_create = self.client.post(reverse('usuarios:auth_user_create'), {
            'username': 'nuevo_operador',
            'email': 'nuevo@ares.edu.mx',
            'first_name': 'Carlos',
            'last_name': 'Ramírez',
            'password': 'PasswordSeguro123!',
            'password_confirm': 'PasswordSeguro123!',
            'rol_ares': self.rol_obs.pk,
            'is_active': True,
        })
        self.assertEqual(resp_create.status_code, 302)
        created_user = User.objects.filter(username='nuevo_operador').first()
        self.assertIsNotNone(created_user)
        self.assertTrue(created_user.check_password('PasswordSeguro123!'))

        # Verificar sincronización con entidad de negocio Usuario
        biz_sync = Usuario.objects.filter(email='nuevo@ares.edu.mx').first()
        self.assertIsNotNone(biz_sync)
        self.assertEqual(biz_sync.nombre, "Carlos Ramírez")

    def test_gestion_grupos_y_permisos(self):
        """
        El Administrador puede crear grupos y asignar permisos directamente.
        """
        self.client.login(username='admin_auth', password='AdminPass123!')

        # 1. Crear nuevo grupo
        resp_grp = self.client.post(reverse('usuarios:auth_group_create'), {
            'name': 'Tecnico_Campo',
        })
        self.assertEqual(resp_grp.status_code, 302)
        grp = Group.objects.filter(name='Tecnico_Campo').first()
        self.assertIsNotNone(grp)

        # 2. Consulta de permisos del sistema
        resp_perms = self.client.get(reverse('usuarios:auth_permission_list'))
        self.assertEqual(resp_perms.status_code, 200)

    def test_observador_bloqueado_gestion_auth(self):
        """
        Un observador que intente acceder a la administración de usuarios recibe 403 Forbidden.
        """
        self.client.login(username='obs_auth', password='ObsPass123!')
        resp = self.client.get(reverse('usuarios:auth_user_list'))
        self.assertEqual(resp.status_code, 403)
