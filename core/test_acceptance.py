import re
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import Group,Permission
from core import test_security
from core.models import Robot,Mision,Asignacion,Orden,Hallazgo
from telemetria.models import Lectura,Sensor
from usuarios.models import Usuario,Rol

class PdfAcceptanceChecks(TestCase):
    setUp=test_security.SecurityRegressionTests.setUp
    account=test_security.SecurityRegressionTests.account
    login=test_security.SecurityRegressionTests.login
    post=test_security.SecurityRegressionTests.post

    def test_demo_battery_is_identified_as_simulated(self):
        self.login()
        Lectura.objects.create(sensor=self.sensor,mision=self.mission,valor=12)
        response=self.client.get(reverse('core:dashboard'))
        self.assertContains(response, 'Batería de demostración')
        self.assertContains(response, 'Dato simulado')

    def test_expired_confirmed_order_keeps_acceptance_visible(self):
        self.login()
        self.order.resultado='aceptada';self.order.confirmada_en=timezone.now()-timedelta(seconds=3);self.order.vencimiento=timezone.now()-timedelta(seconds=1);self.order.save()
        html=self.client.get(reverse('core:orden_list')).content.decode()
        self.assertTrue('aceptada' in html,'Una orden confirmada se muestra solo como Vencida.')

    def test_expired_unconfirmed_order_shows_unknown(self):
        self.login()
        self.order.vencimiento=timezone.now()-timedelta(seconds=1);self.order.save()
        html=self.client.get(reverse('core:orden_list')).content.decode()
        self.assertTrue('desconocida' in html,'Una orden sin confirmacion se muestra solo como Vencida.')

    def test_manual_percentage_range(self):
        self.login()
        response=self.post('telemetria:lectura_create',data={'sensor':self.sensor.pk,'mision':self.mission.pk,'valor':150})
        self.assertFalse(Lectura.objects.filter(valor=150).exists(),f'La interfaz acepta una bateria de 150 %, HTTP {response.status_code}.')

    def test_order_history_mission_filter(self):
        self.login()
        other=Mision.objects.create(nombre='Other Mission',zona='Z',robot=self.robot,creador=self.pa,operador_responsable=self.p1)
        assignment=Asignacion.objects.create(mision=other,usuario=self.p1)
        Orden.objects.create(asignacion=assignment,secuencia=1,accion='parar',vencimiento=timezone.now())
        response=self.client.get(reverse('core:orden_list'),{'mision':str(self.mission.pk)})
        self.assertTrue(all(o.asignacion.mision_id==self.mission.pk for o in response.context['ordenes']),'El parametro mision no filtra las ordenes.')

    def test_order_history_has_next_page_link(self):
        self.login()
        for number in range(2,18): Orden.objects.create(asignacion=self.assignment,secuencia=number,accion='parar',vencimiento=timezone.now())
        response=self.client.get(reverse('core:orden_list'))
        self.assertTrue(response.context['is_paginated'])
        self.assertTrue('page=2' in response.content.decode(),'Hay mas de una pagina, pero no hay enlace para avanzar.')

    def test_mission_pagination_retains_state_filter(self):
        self.login()
        for n in range(17): Mision.objects.create(nombre=f'Planned {n}',zona='Z',robot=self.robot,creador=self.pa,operador_responsable=self.p1)
        response=self.client.get(reverse('core:mision_list'),{'estado':'planificada'})
        links=re.findall(r'href="([^"]+)"',response.content.decode())
        next_links=[link for link in links if 'page=2' in link]
        self.assertTrue(next_links and all('estado=planificada' in link for link in next_links),'La pagina siguiente pierde el filtro de estado.')

    def test_operator_does_not_see_forbidden_delete(self):
        self.login(self.op)
        response=self.client.get(reverse('core:orden_list'))
        delete_url=reverse('core:orden_delete',kwargs={'pk':self.order.pk})
        self.assertFalse(delete_url in response.content.decode(),'El operador ve Eliminar aunque la accion devuelve 403.')

    def test_robot_mission_count_respects_assignment(self):
        self.login(self.op)
        Mision.objects.create(nombre='Private Mission',zona='Z',robot=self.robot,creador=self.pa,operador_responsable=self.p2)
        response=self.client.get(reverse('core:robot_list'))
        robot=list(response.context['robots'])[0]
        self.assertEqual(robot.misiones_visibles,1,'El total incluye una mision a la que el operador no esta asignado.')

    def test_sensor_reading_count_respects_assignment(self):
        self.login(self.op)
        hidden=Mision.objects.create(nombre='Private Mission',zona='Z',robot=self.robot,creador=self.pa,operador_responsable=self.p2)
        Lectura.objects.create(sensor=self.sensor,mision=hidden,valor=7)
        response=self.client.get(reverse('telemetria:sensor_list'))
        self.assertEqual(list(response.context['sensores'])[0].lecturas_visibles,0,'El total incluye lecturas de una mision no asignada.')

    def test_responsible_label_uses_responsible_not_creator(self):
        self.login()
        html=self.client.get(reverse('core:mision_detail',kwargs={'pk':self.mission.pk})).content.decode()
        label=re.search(r'Creador / Responsable:</span>\s*<strong>(.*?)</strong>',html,re.S)
        self.assertIsNone(label)
        self.assertIn('Operador responsable:', html)
        self.assertIn('<strong>'+self.p1.nombre+'</strong>', html)

    def test_order_filters_date_type_and_invalid_inputs(self):
        self.login()
        old = Orden.objects.create(asignacion=self.assignment, secuencia=2, accion='parar', vencimiento=timezone.now(), creada_en=timezone.now()-timedelta(days=3))
        route = reverse('core:orden_list')
        response = self.client.get(route, {'desde': timezone.localdate().isoformat(), 'tipo': 'avanzar'})
        self.assertEqual(list(response.context['ordenes']), [self.order])
        for query in ({'mision':'invalid'}, {'desde':'invalid'}, {'desde':'2026-10-25','hasta':'2026-10-20'}):
            response = self.client.get(route, query)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context['filters'].is_valid())
            self.assertEqual(len(response.context['ordenes']), 0)

    def test_order_filter_choices_hide_foreign_missions(self):
        self.login(self.other)
        response = self.client.get(reverse('core:orden_list'))
        self.assertNotContains(response, self.mission.nombre)
        response = self.client.get(reverse('core:orden_list'), {'mision': str(self.mission.pk)})
        self.assertEqual(len(response.context['ordenes']), 0)

    def test_manual_range_accepts_boundaries_rejects_negative_distance(self):
        self.login()
        for value in (0,100):
            self.assertEqual(self.post('telemetria:lectura_create',data={'sensor':self.sensor.pk,'mision':self.mission.pk,'valor':value}).status_code,302)
        self.sensor.unidad = 'cm';self.sensor.save()
        response = self.post('telemetria:lectura_create',data={'sensor':self.sensor.pk,'mision':self.mission.pk,'valor':-1})
        self.assertEqual(response.status_code,200)
        self.assertIn('valor',response.context['form'].errors)

    def test_all_paginated_lists_have_navigation(self):
        self.login()
        for n in range(31):
            robot=Robot.objects.create(codigo=f'PAGED-{n}',nombre='Demo',creador=self.pa,credencial='unusable')
            Sensor.objects.create(robot=robot,canal='test',tipo='Demo',unidad='%')
            profile=Usuario.objects.create(nombre=f'Profile {n}',email=f'profile{n}@example.test',rol=self.po.rol)
            Asignacion.objects.create(mision=self.mission,usuario=profile)
            Hallazgo.objects.create(asignacion=self.assignment,descripcion=f'Finding {n}')
            Group.objects.create(name=f'Group {n}')
            Rol.objects.create(nombre=f'Role {n}')
        for name in ('core:robot_list','core:asignacion_list','core:hallazgo_list','telemetria:sensor_list','usuarios:usuario_list','usuarios:auth_group_list','usuarios:rol_list','usuarios:auth_permission_list'):
            with self.subTest(name=name):
                response=self.client.get(reverse(name))
                self.assertTrue(response.context['is_paginated'])
                self.assertContains(response,'page=2')
                self.assertEqual(self.client.get(reverse(name),{'page':2}).status_code,200)

    def test_reading_pagination_keeps_dates(self):
        self.login()
        captured = timezone.now()
        for n in range(22):
            with patch('django.utils.timezone.now', return_value=captured+timedelta(microseconds=n)):
                Lectura.objects.create(sensor=self.sensor,mision=self.mission,valor=5)
        today=timezone.localdate().isoformat()
        response=self.client.get(reverse('telemetria:lectura_list'),{'desde':today,'mision':str(self.mission.pk)})
        links=re.findall(r'href="([^"]+)"',response.content.decode())
        link=next(link for link in links if 'page=2' in link)
        self.assertIn('desde='+today,link)
        self.assertIn('mision='+str(self.mission.pk),link)

    def test_ui_checks_each_permission_for_admin(self):
        manager,profile=self.account('limited-manager','Administrador')
        group=Group.objects.get(name='Administrador')
        group.permissions.remove(*Permission.objects.filter(codename__startswith='add_'))
        group.permissions.remove(*Permission.objects.filter(codename__startswith='change_'))
        group.permissions.remove(*Permission.objects.filter(codename__startswith='delete_'))
        self.login(manager)
        for prefix,stem in [('core','robot'),('core','mision'),('core','asignacion'),('core','hallazgo'),('core','orden'),('telemetria','sensor'),('telemetria','lectura'),('usuarios','auth_user'),('usuarios','auth_group'),('usuarios','auth_permission'),('usuarios','usuario'),('usuarios','rol')]:
            with self.subTest(stem=stem):
                response=self.client.get(reverse(prefix+':'+stem+'_list'))
                self.assertEqual(response.status_code,200)
                self.assertNotContains(response,reverse(prefix+':'+stem+'_create'))

    def test_sent_orders_and_closed_objects_do_not_offer_edits(self):
        self.login()
        self.order.enviada_en=timezone.now();self.order.save()
        response=self.client.get(reverse('core:orden_list'))
        self.assertNotContains(response,reverse('core:orden_update',kwargs={'pk':self.order.pk}))
        self.assertNotContains(response,reverse('core:orden_delete',kwargs={'pk':self.order.pk}))
        self.mission.cerrar()
        response=self.client.get(reverse('core:hallazgo_list'))
        self.assertNotContains(response,reverse('core:hallazgo_update',kwargs={'pk':self.finding.pk}))

    def test_native_permissions_keep_name_edit_but_hide_delete(self):
        self.login()
        permission=Permission.objects.get(codename='view_mision')
        response=self.client.get(reverse('usuarios:auth_permission_list'),{'app':'core'})
        self.assertContains(response,reverse('usuarios:auth_permission_update',kwargs={'pk':permission.pk}))
        self.assertNotContains(response,reverse('usuarios:auth_permission_delete',kwargs={'pk':permission.pk}))

    def test_business_crud_round_trips_without_hardware(self):
        self.login()
        scenarios = [
            ('core:robot', Robot, {'codigo':'CRUD-ROBOT','nombre':'Demo','creador':self.pa.pk,'credencial':'a-long-demo-device-credential-123','activo':True}, {'nombre':'Updated','credencial':''}, 'nombre', 'Updated'),
            ('core:mision', Mision, {'nombre':'CRUD mission','zona':'A','robot':self.robot.pk,'operador_responsable':self.p1.pk}, {'nombre':'Updated mission'}, 'nombre', 'Updated mission'),
            ('core:asignacion', Asignacion, {'mision':self.mission.pk,'usuario':self.po.pk}, {'usuario':self.p2.pk}, 'usuario_id', self.p2.pk),
            ('core:hallazgo', Hallazgo, {'asignacion':self.assignment.pk,'descripcion':'Created','estado':'pendiente','posicion':''}, {'descripcion':'Updated finding'}, 'descripcion', 'Updated finding'),
            ('telemetria:sensor', Sensor, {'robot':self.robot.pk,'canal':'crud','tipo':'Temperatura','unidad':'C'}, {'tipo':'Updated sensor'}, 'tipo', 'Updated sensor'),
            ('telemetria:lectura', Lectura, {'mision':self.mission.pk,'sensor':self.sensor.pk,'valor':25}, {'valor':30}, 'valor', 30),
            ('usuarios:rol', Rol, {'nombre':'Custom role'}, {'nombre':'Updated role'}, 'nombre', 'Updated role'),
            ('usuarios:usuario', Usuario, {'nombre':'New profile','email':'profile-crud@example.test','rol':self.po.rol_id,'activo':True,'user':''}, {'nombre':'Updated profile'}, 'nombre', 'Updated profile'),
        ]
        for route,model,data,changes,field,expected in scenarios:
            with self.subTest(route=route):
                before=set(model.objects.values_list('pk',flat=True))
                response=self.client.post(reverse(route+'_create'),data)
                self.assertEqual(response.status_code,302,getattr(response,'context',None) and response.context['form'].errors)
                obj=model.objects.exclude(pk__in=before).get()
                response=self.client.post(reverse(route+'_update',kwargs={'pk':obj.pk}),dict(data,**changes))
                self.assertEqual(response.status_code,302,getattr(response,'context',None) and response.context['form'].errors)
                obj.refresh_from_db();self.assertEqual(getattr(obj,field),expected)
                self.assertEqual(self.client.get(reverse(route+'_list')).status_code,200)
                self.assertEqual(self.client.post(reverse(route+'_delete',kwargs={'pk':obj.pk})).status_code,302)
                self.assertFalse(model.objects.filter(pk=obj.pk).exists())

    def test_pending_order_crud_without_robot_connection(self):
        self.login(self.op)
        data={'asignacion':self.assignment.pk,'secuencia':2,'accion':'parar','duracion_ms':500,'vencimiento':(timezone.now()+timedelta(seconds=25)).isoformat()}
        self.assertEqual(self.client.post(reverse('core:orden_create'),data).status_code,302)
        order=Orden.objects.get(asignacion=self.assignment,secuencia=2)
        data['duracion_ms']=600
        self.assertEqual(self.client.post(reverse('core:orden_update',kwargs={'pk':order.pk}),data).status_code,302)
        order.refresh_from_db();self.assertEqual(order.duracion_ms,600)
        self.login()
        self.assertEqual(self.client.post(reverse('core:orden_delete',kwargs={'pk':order.pk})).status_code,302)
        self.assertFalse(Orden.objects.filter(pk=order.pk).exists())
