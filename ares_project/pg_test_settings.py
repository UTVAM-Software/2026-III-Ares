from .settings import *
import os
DATABASES['default']['TEST']={'NAME':os.environ.get('ARES_TEST_DB','test_ares_isolated')}
ALLOWED_HOSTS=['testserver','localhost','127.0.0.1']
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']

if DATABASES['default']['TEST']['NAME'] == DATABASES['default']['NAME']:
    raise RuntimeError('La base de prueba debe ser distinta de la funcional.')
