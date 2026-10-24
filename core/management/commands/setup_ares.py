from django.core.management.base import BaseCommand
from usuarios.roles import ensure_roles
from usuarios.models import Usuario
from core.models import Mision

class Command(BaseCommand):
    help='Crea roles y grupos ausentes; no crea datos de muestra ni restablece contraseñas.'
    def handle(self,*args,**options):
        ensure_roles()
        self.stdout.write(self.style.SUCCESS('Roles ausentes inicializados. Contraseñas y datos conservados.'))
        self.stdout.write(f'Perfiles sin cuenta vinculada: {Usuario.objects.filter(user__isnull=True).count()}')
        self.stdout.write(f'Misiones sin responsable: {Mision.objects.filter(operador_responsable__isnull=True).count()}')
