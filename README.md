# ARES — aplicación Django

Servidor académico de misiones, roles, telemetría y trazabilidad. PostgreSQL es la base funcional. La integración física del robot no se considera acreditada por las pruebas del servidor.

## Instalación local en Windows

Requiere Python 3.10 o posterior y PostgreSQL. El entorno antiguo `../Ares` contiene una ruta de otra computadora; usar `.venv` dentro de este proyecto.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Completar .env con la conexión EXISTENTE y un secreto aleatorio.
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py setup_ares
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

No reemplazar un `.env` ya configurado. `setup_ares` no crea contraseñas conocidas ni restablece cuentas existentes. Crear un administrador nuevo, solo si es necesario, con `manage.py createsuperuser`; después vincularle un perfil ARES desde la aplicación. Un superusuario puede entrar a la administración sin perfil; necesita perfil para crear misiones.

## Demostración de la entrega 03-B

El robot todavía no está conectado. La batería de demostración y el plano son elementos visuales; la cámara muestra sin señal. No se presentan como mediciones reales. Login/logout, permisos y CRUD se evalúan con datos guardados en PostgreSQL y pueden demostrarse sin hardware. Las lecturas manuales se identifican como simuladas y validan el rango de su unidad.

Los listados permiten recorrer sus páginas conservando filtros. Misiones filtra por estado, nombre/zona y fecha de inicio; órdenes por misión, fecha de creación y acción. La pantalla distingue creador y operador responsable. Los botones respetan permisos y restricciones del registro; las vistas vuelven a comprobarlos ante peticiones directas.

Para evaluar CRUD usar registros de prueba editables: misión planificada sin evidencia, lectura simulada, evento manual, grupo y permiso personalizados. La bitácora automática y los registros históricos protegidos conservan las restricciones descritas abajo. La revisión/aprobación y fusión del PR siguen siendo requisitos de entrega.

## Política de acceso

- Un rol global: Administrador, Operador u Observador. El grupo global y el perfil deben coincidir; una configuración ambigua se deniega.
- Se comprueban permisos `view/add/change/delete` reales. Los permisos directos y grupos adicionales funcionan dentro de los límites del rol; no convierten a un observador en operador.
- Administrador: gestión global, con permisos y reglas de conservación. Operador y observador: únicamente misiones asignadas. Ser creador no sustituye la asignación.
- El operador responsable controla la misión; otro participante no puede editar sus órdenes o hallazgos.
- Una misión cerrada es de solo consulta, también para administración. El cambio de estado valida responsable activo y evita dos misiones en curso por robot, bloqueando filas en PostgreSQL.
- Cambiar el rol desde Cuentas o Perfiles sincroniza el grupo global. El vínculo con la cuenta es una relación uno a uno, no una búsqueda por correo.
- `/admin/` es consulta para superusuarios. Las operaciones se realizan desde la aplicación para aplicar las mismas reglas.

## CRUD y conservación

- Se completaron actualización de asignaciones y lecturas manuales y CRUD de permisos personalizados.
- Actividad es de solo consulta. Los eventos manuales se administran en `/telemetria/administracion/eventos/`; sus cambios generan eventos automáticos.
- La bitácora automática y las lecturas reales del dispositivo no se editan ni eliminan. Los eventos previos a la migración se conservan como protegidos porque su origen no puede inferirse de forma fiable.
- Los permisos nativos conservan su código y modelo; se puede modificar su nombre descriptivo. No se eliminan. Los permisos personalizados admiten CRUD completo.
- No se borran misiones con evidencia, sensores con lecturas ni perfiles/asignaciones que destruirían historial. Esas restricciones son decisiones de integridad; la rúbrica genérica de CRUD debe presentarse con esta justificación.
- `LoginThrottle` es almacenamiento interno de seguridad, no una entidad editable del negocio.

## Autenticación y configuración

Login por usuario o correo único, contraseñas validadas por Django y logout mediante POST con CSRF. Se bloquea durante una ventana de cinco minutos tras cinco fallos de identidad o veinte de IP. Los contadores son persistentes y no guardan identificadores en claro. Se usa la IP directa; no se confía en cabeceras de proxy suministradas por el cliente.

`.env` está excluido de Git. `DJANGO_DEBUG=1` permite desarrollo HTTP local. Para demostración HTTPS: `DJANGO_DEBUG=0`, un secreto largo, hosts y `DJANGO_CSRF_TRUSTED_ORIGINS` reales, certificado y terminación TLS correctamente configurados. Producción activa redirección HTTPS, cookies Secure/HttpOnly/SameSite, HSTS y protección de contenido. No habilitar confianza en un proxy sin controlar sus cabeceras.

El historial Git anterior puede contener secretos: retirar una clave del archivo actual no la borra de commits previos. La clave de sesión local se renovó; las sesiones anteriores deberán iniciar de nuevo. La contraseña PostgreSQL se conservó para mantener la conexión existente; rotarla requiere coordinar también la cuenta de PostgreSQL.

## Contrato de dispositivo

Las credenciales nuevas requieren al menos 24 caracteres y se guardan con hash. El formulario nunca muestra el token guardado. Guardar una credencial nueva la sustituye; desactivar el robot revoca sus peticiones. Usar HTTPS fuera del desarrollo local.

Todas las rutas son POST y exigen `Authorization: Bearer <credencial>`; no aceptan autenticación por cookies. La exención CSRF está limitada a estas rutas por dispositivo.

- `/telemetria/dispositivo/<codigo>/consultar/`: JSON `{}`; actualiza contacto y entrega como máximo una orden pendiente. Cada orden se entrega una sola vez. No se reenvía movimiento antiguo al reconectar.
- `/telemetria/dispositivo/<codigo>/confirmar/`: JSON con `id` UUID y `resultado` `aceptada` o `rechazada`. Solo se confirman órdenes enviadas, vigentes y del robot correspondiente.
- `/telemetria/dispositivo/<codigo>/lecturas/`: JSON con UUID `mision`, entero `sensor` y número finito `valor`. Valida pertenencia de sensor/robot y misión en curso; registra hora del servidor y origen real.

Cada orden limita duración a 1–2000 ms, acción conocida, secuencia positiva única por asignación y vencimiento de hasta 30 segundos; los botones del panel usan 500 ms y dos segundos de vigencia. Un envío pendiente no equivale a ejecución. Sin confirmación se muestra estado desconocido al vencer. Al perder enlace se bloquean movimientos; solicitar parada no afirma que el dispositivo la haya recibido.

El firmware debe implementar recepción/confirmación, autenticación, temporizador local <=2 s, rechazo de secuencias repetidas/vencidas y ausencia de reanudación automática. Esto no se sustituye con Django y aún necesita prueba física. El transporte implementado es HTTP de consulta; no se afirma cumplir WebSockets ni latencia de motores <50 ms. El video permanece como “sin señal” hasta integrar una cámara autorizada. Las lecturas introducidas por formulario se marcan simuladas.

## Pruebas

Sin tocar PostgreSQL:

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=ares_project.test_settings
```

Con PostgreSQL, usando exclusivamente una base de prueba nueva:

```powershell
$env:ARES_TEST_DB='test_ares_isolated'
.\.venv\Scripts\python.exe manage.py test --settings=ares_project.pg_test_settings --noinput
```

Nunca usar el nombre de la base funcional en `ARES_TEST_DB`. El ejecutor crea y destruye la base de prueba. La suite cubre aislamiento por objeto, los tres roles, CRUD, contraseñas, limitación de acceso, CSRF, reglas de misión, dispositivo y todas las rutas HTML. `makemigrations --check --dry-run` verifica que el esquema coincide con los modelos.

## Migración y pendientes de evaluación

Las migraciones añaden campos sin eliminar registros: vinculan perfiles solo cuando el correo identifica una cuenta inequívoca y asignan responsable solo si hay exactamente un operador activo ya asignado. Los casos ambiguos quedan sin vincular y deben revisarse desde administración. La migración establece la matriz base de permisos de los tres grupos globales. Los tokens existentes se convierten a hash conservando la credencial de acceso; esto es irreversible, por lo que debe guardarse una copia de la base antes de migrar.

La validación del servidor no acredita la integración física, el rendimiento del robot, las cinco desconexiones, el video, una certificación OWASP/CWE ni una entrega en Classroom. PR revisado/aprobado, HTTPS real y evaluación de los RF/RNF restantes son pasos de entrega separados. No se publican cambios automáticamente.
