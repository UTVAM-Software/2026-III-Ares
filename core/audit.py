from .security import business_user

def record(user,action,result='Correcto',mission=None,robot=None):
    from telemetria.models import Evento
    # No registrar cuerpos HTTP, contraseñas ni tokens.
    return Evento.objects.create(actor=business_user(user) if user else None,mision=mission,
        robot=robot or (mission.robot if mission else None),accion=action[:100],resultado=result[:50],es_sistema=True)
