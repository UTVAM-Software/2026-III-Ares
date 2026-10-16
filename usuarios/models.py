from django.db import models

class Rol(models.Model):
    id = models.SmallAutoField(primary_key=True)
    nombre = models.CharField(max_length=20, unique=True, verbose_name="Nombre del Rol")

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.nombre


class Usuario(models.Model):
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name="usuarios")
    email = models.EmailField(max_length=254, unique=True, verbose_name="Correo Institucional")
    nombre = models.CharField(max_length=100, verbose_name="Nombre Completo")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return f"{self.email} ({self.rol.nombre})"