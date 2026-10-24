from django.contrib import admin
from django.contrib.auth.models import User,Group
from core.admin import ConsultationAdmin
from .models import Rol,Usuario
for model in (User,Group):
    if admin.site.is_registered(model): admin.site.unregister(model)
    admin.site.register(model,ConsultationAdmin)
for model in (Rol,Usuario): admin.site.register(model,ConsultationAdmin)
