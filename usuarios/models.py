from django.db import models
from django.conf import settings
from django.urls import reverse

class Rol(models.Model):
    id = models.SmallAutoField(primary_key=True)
    nombre = models.CharField(max_length=20, unique=True, verbose_name="Nombre del Rol")

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ['id']

    def __str__(self):
        return self.nombre

    def get_absolute_url(self):
        return reverse('usuarios:rol_list')

    @property
    def total_usuarios(self):
        """Retorna la cantidad de usuarios vinculados a este rol."""
        return self.usuarios.count()


class Usuario(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="perfil_ares")
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name="usuarios")
    email = models.EmailField(max_length=254, unique=True, verbose_name="Correo Institucional")
    nombre = models.CharField(max_length=100, verbose_name="Nombre Completo")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.email} ({self.rol.nombre})"

    def get_absolute_url(self):
        return reverse('usuarios:usuario_list')

    @property
    def es_administrador(self):
        """Indica si el usuario tiene rol de Administrador."""
        return bool(self.rol and self.rol.nombre.strip().lower() == 'administrador')

    @property
    def es_operador(self):
        """Indica si el usuario tiene rol de Operador."""
        return bool(self.rol and self.rol.nombre.strip().lower() == 'operador')

    @property
    def es_observador(self):
        """Indica si el usuario tiene rol de Observador."""
        return bool(self.rol and self.rol.nombre.strip().lower() == 'observador')


class LoginThrottle(models.Model):
    """Contadores internos, sin contraseñas ni identificadores en claro."""
    clave = models.CharField(max_length=64, unique=True)
    intentos = models.PositiveIntegerField(default=0)
    ventana = models.DateTimeField()
