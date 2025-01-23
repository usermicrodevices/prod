from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RefsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'refs'
    verbose_name = _('References')
