from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

class UsernameOrEmailBackend(ModelBackend):
    def authenticate(self,request,username=None,password=None,**kwargs):
        User=get_user_model()
        if username is None or password is None: return None
        candidates=User.objects.filter(Q(username=username)|Q(email__iexact=username)).distinct()
        if candidates.count()!=1:
            User().set_password(password)
            return None
        user=candidates.get()
        return user if user.check_password(password) and self.user_can_authenticate(user) else None
