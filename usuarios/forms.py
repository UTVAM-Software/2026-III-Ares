from django import forms
from django.contrib.auth.models import User,Group,Permission
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from core.security import ROLES,assign_role
from core.forms import ActorForm
from .models import Rol,Usuario

class AresAuthenticationForm(AuthenticationForm):
    username=forms.CharField(label='Usuario o correo institucional',widget=forms.TextInput(attrs={'class':'ares-input','autocomplete':'username'}))
    password=forms.CharField(label='Contraseña',strip=False,widget=forms.PasswordInput(attrs={'class':'ares-input','autocomplete':'current-password'}))
    error_messages={'invalid_login':'Credenciales no válidas.','inactive':'Credenciales no válidas.'}

class UserBaseForm(ActorForm):
    email=forms.EmailField(label='Correo institucional')
    rol_ares=forms.ModelChoiceField(queryset=Rol.objects.filter(nombre__in=ROLES),label='Rol global ARES')
    groups=forms.ModelMultipleChoiceField(queryset=Group.objects.exclude(name__in=ROLES),required=False,label='Grupos adicionales',widget=forms.CheckboxSelectMultiple)
    user_permissions=forms.ModelMultipleChoiceField(queryset=Permission.objects.select_related('content_type'),required=False,label='Permisos directos adicionales',widget=forms.SelectMultiple,help_text='Selecciona los permisos que quieras añadir a esta cuenta. Usa Ctrl para seleccionar varios o quitar una selección. Esta lista no marca los permisos heredados del rol o de los grupos. Los límites del rol ARES siguen aplicándose.')
    class Meta:
        model=User
        fields=['username','email','first_name','last_name','is_active','groups','user_permissions']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.profile=Usuario.objects.filter(user=self.instance).first() if self.instance.pk else None
        if self.profile: self.fields['rol_ares'].initial=self.profile.rol_id
    def clean_email(self):
        email=self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists(): raise forms.ValidationError('Este correo ya está asociado con una cuenta.')
        qs=Usuario.objects.filter(email__iexact=email)
        if self.profile: qs=qs.exclude(pk=self.profile.pk)
        if qs.exists(): raise forms.ValidationError('Este correo ya corresponde a un perfil ARES; vincúlalo desde la gestión de perfiles.')
        if User.objects.filter(username__iexact=email).exclude(pk=self.instance.pk).exists(): raise forms.ValidationError('El correo coincide con otra identidad de acceso.')
        return email
    def clean_username(self):
        value=self.cleaned_data['username']
        if User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists(): raise forms.ValidationError('El usuario coincide con el correo de otra cuenta.')
        return value
    def clean(self):
        data=super().clean()
        if self.actor and self.instance.pk==self.actor.pk:
            if not data.get('is_active') or data.get('rol_ares') and data['rol_ares'].nombre!='Administrador':
                raise forms.ValidationError('No puedes desactivar ni retirar el rol administrador de tu propia sesión.')
        return data
    @transaction.atomic
    def save(self,commit=True):
        user=super().save(commit=False)
        if self.cleaned_data.get('password'): user.set_password(self.cleaned_data['password'])
        if commit:
            user.save(); self.save_m2m()
            profile=self.profile or Usuario(user=user)
            profile.email=user.email
            profile.nombre=user.get_full_name() or user.username
            profile.activo=user.is_active
            profile.rol=self.cleaned_data['rol_ares']
            profile.save()
            assign_role(user,profile,profile.rol)
        return user

class DjangoUserCreationForm(UserBaseForm):
    password=forms.CharField(label='Contraseña',strip=False,widget=forms.PasswordInput)
    password_confirm=forms.CharField(label='Confirmar contraseña',strip=False,widget=forms.PasswordInput)
    def clean(self):
        data=super().clean()
        password=data.get('password')
        if password!=data.get('password_confirm'): self.add_error('password_confirm','Las contraseñas no coinciden.')
        if password:
            candidate=User(username=data.get('username',''),email=data.get('email',''),first_name=data.get('first_name',''),last_name=data.get('last_name',''))
            try: validate_password(password,candidate)
            except ValidationError as exc: self.add_error('password',exc)
        return data

class DjangoUserUpdateForm(UserBaseForm):
    pass

class DjangoGroupForm(ActorForm):
    class Meta:
        model=Group
        fields=['name','permissions']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.instance.name in ROLES: self.fields['name'].disabled=True
    def clean_name(self):
        name=self.cleaned_data['name'].strip()
        if Group.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists(): raise forms.ValidationError('Ya existe un grupo con ese nombre.')
        if self.instance._state.adding and name.casefold() in [r.casefold() for r in ROLES]: raise forms.ValidationError('Ese nombre está reservado para un rol global.')
        return name

class RolForm(ActorForm):
    class Meta:
        model=Rol
        fields=['nombre']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.instance.nombre in ROLES: self.fields['nombre'].disabled=True
    def clean_nombre(self):
        name=self.cleaned_data['nombre'].strip()
        if Rol.objects.filter(nombre__iexact=name).exclude(pk=self.instance.pk).exists(): raise forms.ValidationError('Ya existe ese rol.')
        return name

class UsuarioForm(ActorForm):
    class Meta:
        model=Usuario
        fields=['user','nombre','email','rol','activo']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['rol'].queryset=Rol.objects.filter(nombre__in=ROLES)
        available=User.objects.filter(perfil_ares__isnull=True)
        if self.instance.user_id: available=User.objects.filter(pk=self.instance.user_id)
        if self.actor and not self.actor.is_superuser: available=available.filter(is_superuser=False)
        self.fields['user'].queryset=available
        self.fields['user'].label='Cuenta de acceso (Django Auth)'
        self.fields['user'].help_text='Vincula una cuenta existente que todavía no tenga perfil ARES. Cada cuenta puede tener un solo perfil. Un perfil sin cuenta vinculada no permite iniciar sesión.'
        if self.instance.user_id:
            self.fields['user'].disabled=True
            self.fields['user'].help_text='Esta es la cuenta vinculada al perfil. Sus credenciales se administran desde Usuarios (Django Auth).'
        elif not available.exists():
            self.fields['user'].empty_label='No hay cuentas sin perfil disponibles'
            self.fields['user'].help_text='No hay cuentas disponibles para vincular. Las cuentas creadas desde Usuarios (Django Auth) reciben su perfil automáticamente; puedes editarlo en el listado de usuarios de negocio.'
        else:
            self.fields['user'].empty_label='Sin cuenta vinculada (opcional)'
    def clean(self):
        data=super().clean()
        account=data.get('user'); email=data.get('email','').lower()
        if account and email!=account.email.lower(): self.add_error('email','Usa el correo de la cuenta vinculada; modifica el correo desde Cuentas.')
        if Usuario.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists(): self.add_error('email','El correo ya existe.')
        if account and self.actor and account.pk==self.actor.pk and (not data.get('activo') or data.get('rol') and data['rol'].nombre!='Administrador'):
            raise forms.ValidationError('No puedes retirar tu propio acceso administrativo.')
        data['email']=email
        return data
    @transaction.atomic
    def save(self,commit=True):
        profile=super().save(commit=commit)
        if commit and profile.user_id:
            profile.user.is_active=profile.activo
            profile.user.save(update_fields=['is_active'])
            assign_role(profile.user,profile,profile.rol)
        return profile

def protected_permission(permission):
    model=permission.content_type.model_class()
    if not model: return False
    protected={f'{action}_{model._meta.model_name}' for action in model._meta.default_permissions}
    protected.update(code for code,label in model._meta.permissions)
    return permission.codename in protected

class DjangoPermissionForm(ActorForm):
    class Meta:
        model=Permission
        fields=['name','content_type','codename']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.instance.pk and protected_permission(self.instance):
            self.fields['content_type'].disabled=True
            self.fields['codename'].disabled=True
    def clean(self):
        data=super().clean()
        code=data.get('codename','')
        import re
        if code and not re.fullmatch(r'[a-z][a-z0-9_]*',code): self.add_error('codename','Usa letras minúsculas, números y guion bajo.')
        return data
