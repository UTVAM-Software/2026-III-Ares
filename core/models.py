import uuid
from django.db import models
from usuarios.models import Usuario

class Robot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=30, unique=True, verbose_name="Código del Robot")
    nombre = models.CharField(max_length=100, verbose_name="Nombre/Alias")
    credencial = models.CharField(max_length=255, verbose_name="Token/Credencial")
    activo = models.BooleanField(default=True)
    creador = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="robots_creados")

    class Meta:
        verbose_name = "Robot"
        verbose_name_plural = "Robots"

    def __str__(self):
        return self.codigo


class Mision(models.Model):
    ESTADOS = [
        ('planificada', 'Planificada'),
        ('en_curso', 'En Curso'),
        ('pausada', 'Pausada'),
        ('cerrada', 'Cerrada'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la Misión")
    zona = models.CharField(max_length=100, verbose_name="Zona de Práctica")
    estado = models.CharField(max_length=12, choices=ESTADOS, default='planificada')
    robot = models.ForeignKey(Robot, on_delete=models.PROTECT, related_name="misiones")
    creador = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="misiones_creadas")
    inicio = models.DateTimeField(null=True, blank=True)
    fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Misión"
        verbose_name_plural = "Misiones"

    def __str__(self):
        return f"{self.nombre} ({self.get_estado_display()})"


class Asignacion(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="asignaciones")
    mision = models.ForeignKey(Mision, on_delete=models.CASCADE, related_name="asignaciones")
    fecha_asignacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Asignación"
        verbose_name_plural = "Asignaciones"
        unique_together = ('usuario', 'mision')

    def __str__(self):
        return f"{self.usuario.email} -> Misión: {self.mision.nombre}"


class Orden(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asignacion = models.ForeignKey(Asignacion, on_delete=models.CASCADE, related_name="ordenes")
    secuencia = models.BigIntegerField()
    accion = models.CharField(max_length=50, verbose_name="Acción (avanzar, girar, parar)")
    vencimiento = models.DateTimeField()
    resultado = models.CharField(max_length=20, default='pendiente')

    class Meta:
        verbose_name = "Orden"
        verbose_name_plural = "Órdenes"
        unique_together = ('asignacion', 'secuencia')

    def __str__(self):
        return f"Orden #{self.secuencia} - {self.accion}"


class Hallazgo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asignacion = models.ForeignKey(Asignacion, on_delete=models.CASCADE, related_name="hallazgos")
    descripcion = models.TextField(verbose_name="Descripción del Hallazgo")
    estado = models.CharField(max_length=20, default='pendiente')
    posicion = models.CharField(max_length=50, blank=True, null=True, verbose_name="Posición Relativa X/Y")
    hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Hallazgo"
        verbose_name_plural = "Hallazgos"

    def __str__(self):
        return f"Hallazgo en {self.asignacion.mision.nombre}"
    