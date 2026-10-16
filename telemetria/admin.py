from django.contrib import admin
from .models import Sensor, Lectura, Evento

admin.site.register(Sensor)
admin.site.register(Lectura)
admin.site.register(Evento)
