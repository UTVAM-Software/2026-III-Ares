from django.apps import apps
from .security import allowed,is_admin,role

def access(request):
    permissions={}
    for app in ('core','telemetria','usuarios','auth'):
        for model in apps.get_app_config(app).get_models():
            for action in ('view','add','change','delete'):
                permissions[action+'_'+model._meta.model_name]=allowed(request.user,model,action)
    return {'ares_can':permissions,'ares_admin':is_admin(request.user),'ares_role':role(request.user)}
