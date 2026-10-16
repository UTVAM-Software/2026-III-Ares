from django.contrib import admin
from .models import Robot, Mision, Asignacion, Orden, Hallazgo

admin.site.register(Robot)
admin.site.register(Mision)
admin.site.register(Asignacion)
admin.site.register(Orden)
admin.site.register(Hallazgo)