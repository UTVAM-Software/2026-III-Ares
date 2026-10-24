from django.db import models
from django.urls import reverse
from django.utils import timezone
from usuarios.models import Usuario
from core.models import Robot, Mision

class Sensor(models.Model):
    robot = models.ForeignKey(Robot, on_delete=models.CASCADE, related_name="sensores")
    canal = models.CharField(max_length=20)
    tipo = models.CharField(max_length=50, verbose_name="Tipo (batería, distancia, temp)")
    unidad = models.CharField(max_length=20, verbose_name="Unidad de medida")

    class Meta:
        verbose_name = "Sensor"
        verbose_name_plural = "Sensores"
        unique_together = ('robot', 'canal')
        ordering = ['robot', 'canal']

    def __str__(self):
        return f"{self.robot.codigo} {self.tipo} ({self.canal})"

    def get_absolute_url(self):
        return reverse('telemetria:sensor_list')

    @property
    def total_lecturas(self):
        """Retorna el total de lecturas emitidas por este sensor."""
        return self.lecturas.count()

    @property
    def ultima_lectura(self):
        """Obtiene la lectura más reciente capturada."""
        return self.lecturas.order_by('-capturada_en').first()


class Lectura(models.Model):
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name="lecturas")
    mision = models.ForeignKey(Mision, on_delete=models.CASCADE, related_name="lecturas")
    valor = models.FloatField()
    simulada = models.BooleanField(default=True)
    capturada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lectura"
        verbose_name_plural = "Lecturas"
        unique_together = ('sensor', 'capturada_en')
        ordering = ['-capturada_en']

    def __str__(self):
        return f"{self.sensor.tipo}: {self.valor} {self.sensor.unidad} en {self.mision.nombre}"

    def get_absolute_url(self):
        return reverse('telemetria:lectura_list')

    @property
    def es_reciente(self):
        """RF-08: Considera vigente una lectura si tiene 5 segundos o menos."""
        if not self.capturada_en:
            return False
        return (timezone.now() - self.capturada_en).total_seconds() <= 5.0

    @property
    def edad_segundos(self):
        """Retorna el tiempo transcurrido en segundos desde la captura."""
        if not self.capturada_en:
            return 0
        return round((timezone.now() - self.capturada_en).total_seconds(), 1)


class Evento(models.Model):
    es_sistema = models.BooleanField(default=False, editable=False)
    actor = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    robot = models.ForeignKey(Robot, on_delete=models.SET_NULL, null=True, blank=True)
    mision = models.ForeignKey(Mision, on_delete=models.SET_NULL, null=True, blank=True)
    accion = models.CharField(max_length=100)
    resultado = models.CharField(max_length=50)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evento/Bitácora"
        verbose_name_plural = "Eventos/Bitácoras"
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"[{self.fecha_hora.strftime('%Y-%m-%d %H:%M:%S') if self.fecha_hora else ''}] {self.accion} {self.resultado}"

    def get_absolute_url(self):
        return reverse('telemetria:evento_list')
