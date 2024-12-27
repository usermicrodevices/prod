import inspect, logging, sys
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from django.db.models.signals import post_migrate
from django.db.backends.signals import connection_created

def post_init_app():
    from .models import create_default_role_fields, Role, RoleModel
    exclude_classes = ['CustomAbstractModel', 'Role', 'RoleModel', 'RoleField']
    models = inspect.getmembers(sys.modules['refs.models'], inspect.isclass) + inspect.getmembers(sys.modules['core.models'], inspect.isclass)
    for _, model_class in models:
        if model_class.__name__ not in exclude_classes and model_class.__module__ in ['refs.models', 'core.models'] and 'CacheManager' not in model_class.__name__:
            try:
                rmodel = RoleModel.objects.get(app = model_class.__module__.split('.')[0], model = model_class.__name__)
            except:
                try:
                    logging.info('{} :: PRINT CLASS NAME {}.{}'.format(sys._getframe().f_code.co_name, model_class.__module__, model_class.__name__))
                except Exception as e:
                    logging.warning('{} :: {} : {}'.format(sys._getframe().f_code.co_name, model_class, e))
                try:
                    rmodel = RoleModel(app = model_class.__module__.split('.')[0], model = model_class.__name__)
                except Exception as e:
                    logging.error('{} :: {} : {}'.format(sys._getframe().f_code.co_name, model_class, e))
                else:
                    rmodel.save()
            else:
                if rmodel:
                    for r in Role.objects.all():
                        create_default_role_fields(r, rmodel)


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
    verbose_name = _('Users')

    def ready(self):
        if 'runserver' in sys.argv:
            logging.info('🏁 {}.{} :: {} 🏁'.format(self.__class__.__name__, sys._getframe().f_code.co_name, sys.argv))
            post_init_app()
