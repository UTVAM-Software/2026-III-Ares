"""Asistente de configuración de ARES (paso 3 de la instalación).

Crea el archivo .env con una clave secreta aleatoria y los datos de la base de datos.
No necesita Django ni librerías extra. Uso:

    python configurar_env.py

Si ya existe un .env, no lo reemplaza.
"""
import secrets
import string
from pathlib import Path

ENV = Path(__file__).resolve().parent / '.env'


def preguntar(texto, por_defecto):
    valor = input(f'{texto} [{por_defecto}]: ').strip()
    return valor or por_defecto


def main():
    if ENV.exists():
        print(f'Ya existe {ENV}. No se modificó. Bórralo primero si quieres generarlo de nuevo.')
        return
    print('Configuración de ARES. Presiona Enter para usar el valor entre corchetes.\n')
    hosts = preguntar('Hosts permitidos (IP o dominio del servidor, separados por comas)', 'localhost,127.0.0.1')
    https = preguntar('¿El servidor tiene HTTPS? (1 = sí, 0 = no)', '0')
    db_name = preguntar('Nombre de la base de datos', 'ares_db')
    db_user = preguntar('Usuario de PostgreSQL', 'postgres')
    db_password = preguntar('Contraseña de PostgreSQL', '')
    db_host = preguntar('Servidor de PostgreSQL', 'localhost')
    db_port = preguntar('Puerto de PostgreSQL', '5432')
    origins = ','.join(f'https://{h.strip()}' for h in hosts.split(',') if h.strip()) if https == '1' else ''
    alfabeto = string.ascii_letters + string.digits + '!@%^&*(-_=+)'
    secreto = ''.join(secrets.choice(alfabeto) for _ in range(50))
    ENV.write_text(
        f'DJANGO_SECRET_KEY={secreto}\n'
        f'DJANGO_DEBUG=0\n'
        f'DJANGO_HTTPS={https}\n'
        f'DJANGO_ALLOWED_HOSTS={hosts}\n'
        f'DB_NAME={db_name}\n'
        f'DB_USER={db_user}\n'
        f'DB_PASSWORD={db_password}\n'
        f'DB_HOST={db_host}\n'
        f'DB_PORT={db_port}\n'
        f'DJANGO_CSRF_TRUSTED_ORIGINS={origins}\n',
        encoding='utf-8')
    print(f'\nListo: se creó {ENV}')


if __name__ == '__main__':
    main()
