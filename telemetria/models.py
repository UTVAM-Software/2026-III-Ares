from django.db import models
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

    def __str__(self):
        return f"{self.robot.codigo} - {self.tipo} ({self.canal})"


class Lectura(models.Model):
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name="lecturas")
    mision = models.ForeignKey(Mision, on_delete=models.CASCADE, related_name="lecturas")
    valor = models.FloatField()
    capturada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lectura"
        verbose_name_plural = "Lecturas"
        unique_together = ('sensor', 'capturada_en')

    def __str__(self):
        return f"{self.sensor.tipo}: {self.valor} en {self.mision.nombre}"


class Evento(models.Model):
    actor = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    robot = models.ForeignKey(Robot, on_delete=models.SET_NULL, null=True, blank=True)
    mision = models.ForeignKey(Mision, on_delete=models.SET_NULL, null=True, blank=True)
    accion = models.CharField(max_length=100)
    resultado = models.CharField(max_length=50)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evento/Bitácora"
        verbose_name_plural = "Eventos/Bitácoras"

    def __str__(self):
        return f"[{self.fecha_hora}] {self.accion} - {self.resultado}"