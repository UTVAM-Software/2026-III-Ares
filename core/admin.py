from django.contrib import admin
from .models import Robot,Mision,Asignacion,Orden,Hallazgo

class ConsultationAdmin(admin.ModelAdmin):
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False
    def has_view_permission(self,request,obj=None): return request.user.is_active and request.user.is_superuser
    def get_exclude(self,request,obj=None): return ('credencial',) if self.model==Robot else None

for model in (Robot,Mision,Asignacion,Orden,Hallazgo): admin.site.register(model,ConsultationAdmin)
