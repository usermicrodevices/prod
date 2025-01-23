import inspect, logging, sys
from django.apps import AppConfig, apps as django_apps
from django.utils.translation import gettext_lazy as _


def get_model(app_model):
    app_name, model_name = app_model.split('.')
    return django_apps.get_app_config(app_name).get_model(model_name)


def post_init_app():
    from django.db.backends.signals import connection_created
    from django.db.backends.postgresql.base import DatabaseWrapper
    from django.dispatch import receiver

    @receiver(connection_created, sender=DatabaseWrapper)
    def initial_connection_to_db(sender, **kwargs):
        from .models import create_default_role_fields
        exclude_classes = ['CustomAbstractModel', 'Role', 'RoleModel', 'RoleField']
        models = inspect.getmembers(sys.modules['refs.models'], inspect.isclass) + inspect.getmembers(sys.modules['core.models'], inspect.isclass)
        for _, model_class in models:
            if model_class.__name__ not in exclude_classes and model_class.__module__ in ['refs.models', 'core.models'] and 'CacheManager' not in model_class.__name__:
                try:
                    rmodel = get_model('users.RoleModel').objects.get(app = model_class.__module__.split('.')[0], model = model_class.__name__)
                except:
                    try:
                        logging.info('{} :: PRINT CLASS NAME {}.{}'.format(sys._getframe().f_code.co_name, model_class.__module__, model_class.__name__))
                    except Exception as e:
                        logging.warning('{} :: {} : {}'.format(sys._getframe().f_code.co_name, model_class, e))
                    try:
                        rmodel = get_model('users.RoleModel')(app = model_class.__module__.split('.')[0], model = model_class.__name__)
                    except Exception as e:
                        logging.error('{} :: {} : {}'.format(sys._getframe().f_code.co_name, model_class, e))
                    else:
                        rmodel.save()
                else:
                    if rmodel:
                        for r in get_model('users.Role').objects.all():
                            create_default_role_fields(r, rmodel)


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
    verbose_name = _('Users')

    def ready(self):
        if 'runserver' in sys.argv:
            logging.info('🏁 {}.{} :: {} 🏁'.format(self.__class__.__name__, sys._getframe().f_code.co_name, sys.argv))
            #post_init_app()
