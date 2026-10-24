from django.contrib import admin
from core.admin import ConsultationAdmin
from .models import Sensor,Lectura,Evento
for model in (Sensor,Lectura,Evento): admin.site.register(model,ConsultationAdmin)
