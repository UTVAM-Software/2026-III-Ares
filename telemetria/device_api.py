"""Contrato HTTP del dispositivo. No simula hardware ni confirma una orden desde la web."""
import json
from datetime import timedelta
from functools import wraps
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction,IntegrityError
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.models import Robot,Mision,Orden
from core.audit import record
from core.security import role
from .models import Sensor,Lectura
from .validation import validate_reading_value


def device_endpoint(view):
    @csrf_exempt
    @require_POST
    @wraps(view)
    def wrapped(request,code):
        # Solo credenciales por dispositivo, jamás cookies de sesión.
        authorization=request.headers.get('Authorization','')
        if not authorization.startswith('Bearer ') or len(authorization)>512:
            return JsonResponse({'error':'Credencial no válida.'},status=401)
        with transaction.atomic():
            robot=Robot.objects.select_for_update().filter(codigo=code,activo=True).first()
            if not robot or not robot.check_credential(authorization[7:]):
                return JsonResponse({'error':'Credencial no válida.'},status=401)
            try:
                data=json.loads(request.body or b'{}')
                if not isinstance(data,dict): raise ValueError()
                response=view(request,robot,data)
                return response
            except (ValueError,TypeError,KeyError,ValidationError):
                return JsonResponse({'error':'Datos no válidos.'},status=400)
    return wrapped

@device_endpoint
def poll(request,robot,data):
    now=timezone.now()
    connected=robot.conectado
    robot.ultima_conexion=now
    robot.save(update_fields=['ultima_conexion'])
    mission=Mision.objects.select_for_update().filter(robot=robot,estado='en_curso').first()
    if not mission: return JsonResponse({'ordenes':[],'estado':'sin_mision'})
    # Tras recuperar enlace nunca reactivar movimiento pendiente antiguo.
    pending=Orden.objects.filter(asignacion__mision=mission,resultado='pendiente',enviada_en__isnull=True)
    stale=pending.filter(creada_en__lt=now-timedelta(seconds=2))
    stale.update(resultado='vencida')
    pending.filter(vencimiento__lte=now).update(resultado='vencida')
    if not connected: pending.exclude(accion='parar').update(resultado='rechazada')
    if not mission.operador_responsable_id or not mission.operador_responsable.activo or not mission.operador_responsable.user_id or role(mission.operador_responsable.user)!='Operador' or not mission.asignaciones.filter(usuario_id=mission.operador_responsable_id).exists():
        pending.update(resultado='rechazada')
        return JsonResponse({'ordenes':[],'estado':'sin_operador_activo'})
    pending.exclude(asignacion__usuario_id=mission.operador_responsable_id).update(resultado='rechazada')
    order=pending.order_by('secuencia').first()
    if not order: return JsonResponse({'ordenes':[],'estado':'conectado'})
    order.enviada_en=now; order.save(update_fields=['enviada_en'])
    return JsonResponse({'ordenes':[{'id':str(order.pk),'mision':str(mission.pk),'secuencia':order.secuencia,'accion':order.accion,'duracion_ms':order.duracion_ms,'vencimiento':order.vencimiento.isoformat()}],'estado':'conectado'})

@device_endpoint
def acknowledge(request,robot,data):
    # La confirmación no puede cambiar a otra misión ni confirmar órdenes no enviadas.
    order=Orden.objects.select_related('asignacion__mision').filter(pk=data['id'],asignacion__mision__robot=robot).first()
    if not order: return JsonResponse({'error':'Orden no disponible.'},status=404)
    mission=Mision.objects.select_for_update().get(pk=order.asignacion.mision_id)
    order=Orden.objects.select_for_update().get(pk=order.pk)
    result=data['resultado']
    if result not in ('aceptada','rechazada'): raise ValueError()
    if order.confirmada_en:
        return JsonResponse({'resultado':order.resultado},status=200 if result==order.resultado else 409)
    if mission.estado=='cerrada' or not order.enviada_en or order.esta_vencida:
        return JsonResponse({'error':'Confirmación tardía o no autorizada; estado desconocido.'},status=409)
    order.resultado=result; order.confirmada_en=timezone.now();order.save(update_fields=['resultado','confirmada_en'])
    record(None,'Confirmación de dispositivo',result,mission,robot)
    return JsonResponse({'resultado':result})

@device_endpoint
def reading(request,robot,data):
    mission=Mision.objects.select_for_update().filter(pk=data['mision'],robot=robot,estado='en_curso').first()
    sensor=Sensor.objects.filter(pk=data['sensor'],robot=robot).first()
    if not mission or not sensor: return JsonResponse({'error':'Misión o sensor no autorizado.'},status=403)
    if isinstance(data['valor'],bool): raise ValueError()
    value=float(data['valor'])
    validate_reading_value(value, sensor)
    sample=Lectura.objects.create(sensor=sensor,mision=mission,valor=value,simulada=False)
    robot.ultima_conexion=timezone.now();robot.save(update_fields=['ultima_conexion'])
    return JsonResponse({'id':sample.pk,'capturada_en':sample.capturada_en.isoformat()},status=201)
