import uuid
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.hashers import make_password, check_password, identify_hasher
from django.urls import reverse
from django.utils import timezone
from usuarios.models import Usuario

class Robot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=30, unique=True, verbose_name="Código del Robot")
    nombre = models.CharField(max_length=100, verbose_name="Nombre/Alias")
    credencial = models.CharField(max_length=255, verbose_name="Token/Credencial")
    activo = models.BooleanField(default=True)
    ultima_conexion = models.DateTimeField(null=True, blank=True)
    creador = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="robots_creados")

    class Meta:
        verbose_name = "Robot"
        verbose_name_plural = "Robots"
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    def get_absolute_url(self):
        return reverse('core:robot_list')

    def set_credential(self, raw):
        self.credencial = make_password(raw)

    def check_credential(self, raw):
        return bool(self.activo and raw and check_password(raw, self.credencial))

    @property
    def conectado(self):
        return bool(self.activo and self.ultima_conexion and 0 <= (timezone.now()-self.ultima_conexion).total_seconds() <= 5)

    @property
    def total_misiones(self):
        """Total de misiones asociadas a este robot."""
        return self.misiones.count()

    @property
    def tiene_mision_activa(self):
        """Verifica si el robot tiene actualmente una misión en curso."""
        return self.misiones.filter(estado='en_curso').exists()

    @property
    def total_sensores(self):
        """Cantidad de sensores instalados."""
        return self.sensores.count()


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
    operador_responsable = models.ForeignKey(Usuario, null=True, blank=True, on_delete=models.PROTECT, related_name="misiones_responsables")
    inicio = models.DateTimeField(null=True, blank=True)
    fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Misión"
        verbose_name_plural = "Misiones"
        ordering = ['-inicio', 'nombre']

    def __str__(self):
        return f"{self.nombre} ({self.get_estado_display()})"

    def get_absolute_url(self):
        return reverse('core:mision_detail', kwargs={'pk': self.pk})

    @property
    def is_activa(self):
        """Determina si la misión se encuentra en ejecución activa."""
        return self.estado == 'en_curso'

    @property
    def total_hallazgos(self):
        """Retorna el número de hallazgos registrados durante la misión."""
        return Hallazgo.objects.filter(asignacion__mision=self).count()

    @property
    def total_ordenes(self):
        """Retorna el total de órdenes emitidas en esta misión."""
        return Orden.objects.filter(asignacion__mision=self).count()

    def cambiar_estado(self, destino):
        allowed = {'planificada': {'en_curso', 'cerrada'}, 'en_curso': {'pausada', 'cerrada'}, 'pausada': {'en_curso', 'cerrada'}, 'cerrada': set()}
        with transaction.atomic():
            Robot.objects.select_for_update().get(pk=self.robot_id)
            current = Mision.objects.select_for_update().get(pk=self.pk)
            if destino not in allowed.get(current.estado, set()):
                raise ValidationError('Transición de estado no permitida. Una misión cerrada es de solo consulta.')
            if destino == 'en_curso':
                operator = current.operador_responsable
                if not operator or not operator.activo or not operator.user_id or not operator.user.is_active:
                    raise ValidationError('Asigna un operador responsable activo antes de iniciar.')
                from core.security import role
                if role(operator.user) != 'Operador' or not current.asignaciones.filter(usuario=operator).exists():
                    raise ValidationError('El responsable debe ser un operador asignado a la misión.')
                if not current.robot.activo:
                    raise ValidationError('El robot está desactivado.')
                if Mision.objects.filter(robot_id=current.robot_id,estado='en_curso').exclude(pk=current.pk).exists():
                    raise ValidationError('El robot ya tiene una misión en curso.')
                current.inicio = current.inicio or timezone.now()
            current.estado = destino
            if destino == 'cerrada': current.fin = timezone.now()
            current.save(update_fields=['estado','inicio','fin'])
            self.estado,self.inicio,self.fin=current.estado,current.inicio,current.fin

    def iniciar(self): self.cambiar_estado('en_curso')
    def pausar(self): self.cambiar_estado('pausada')
    def cerrar(self): self.cambiar_estado('cerrada')


class Asignacion(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="asignaciones")
    mision = models.ForeignKey(Mision, on_delete=models.CASCADE, related_name="asignaciones")
    fecha_asignacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Asignación"
        verbose_name_plural = "Asignaciones"
        unique_together = ('usuario', 'mision')
        ordering = ['-fecha_asignacion']

    def __str__(self):
        return f"{self.usuario.email} -> Misión: {self.mision.nombre}"

    def get_absolute_url(self):
        return reverse('core:asignacion_list')

    @property
    def total_ordenes(self):
        return self.ordenes.count()

    @property
    def total_hallazgos(self):
        return self.hallazgos.count()


class Orden(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asignacion = models.ForeignKey(Asignacion, on_delete=models.CASCADE, related_name="ordenes")
    secuencia = models.BigIntegerField()
    accion = models.CharField(max_length=50, verbose_name="Acción (avanzar, girar, parar)")
    vencimiento = models.DateTimeField()
    creada_en = models.DateTimeField(default=timezone.now, editable=False)
    duracion_ms = models.PositiveIntegerField(default=500, validators=[MinValueValidator(1), MaxValueValidator(2000)])
    enviada_en = models.DateTimeField(null=True, blank=True)
    confirmada_en = models.DateTimeField(null=True, blank=True)
    resultado = models.CharField(max_length=20, default='pendiente')

    class Meta:
        verbose_name = "Orden"
        verbose_name_plural = "Órdenes"
        unique_together = ('asignacion', 'secuencia')
        ordering = ['-secuencia']

    def __str__(self):
        return f"Orden #{self.secuencia} {self.accion}"

    @property
    def estado_confirmacion(self):
        if self.confirmada_en: return self.resultado
        if self.esta_vencida: return 'desconocida'
        return 'pendiente'

    def get_absolute_url(self):
        return reverse('core:orden_list')

    @property
    def esta_vencida(self):
        """Comprueba si la orden ha expirado temporalmente (RNF-02/RF-07)."""
        return bool(self.vencimiento and self.vencimiento < timezone.now())


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
        ordering = ['-hora']

    def __str__(self):
        return f"Hallazgo en {self.asignacion.mision.nombre}: {self.descripcion[:30]}"

    def get_absolute_url(self):
        return reverse('core:hallazgo_list')
