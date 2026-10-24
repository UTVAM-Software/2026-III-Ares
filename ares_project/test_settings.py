import os
os.environ['DJANGO_SECRET_KEY']='test-only-not-for-deployment'
from .settings import *
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}}
ALLOWED_HOSTS=['testserver','localhost','127.0.0.1']
DEBUG=False
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']
