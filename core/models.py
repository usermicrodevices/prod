import logging, sys
from uuid import uuid4
from itertools import chain
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.db import models, transaction
from django.db.models import F, Q, Max, Subquery, Value, IntegerField, JSONField
from django.db.models.signals import pre_save, post_save, post_init, post_delete
from django.dispatch import receiver
from django.utils import timezone as django_timezone
from django.utils.translation import gettext as _
from django.core.cache import caches
from django.db.utils import IntegrityError
try:
    from zoneinfo import available_timezones, ZoneInfo
except:
    from backports.zoneinfo import available_timezones, ZoneInfo


class CustomAbstractModel(models.Model):

    class Meta:
        abstract = True

    def logi(self, *args):
        msg = f'💡{self.__class__.__name__}.{sys._getframe().f_back.f_code.co_name}'
        for arg in args:
            msg += f'::{arg}'
        logging.info(msg)

    def logw(self, *args):
        msg = f'⚠️{self.__class__.__name__}.{sys._getframe().f_back.f_code.co_name}'
        for arg in args:
            msg += f'::{arg}'
        logging.warning(msg)

    def loge(self, err, *args):
        msg = f'🆘{self.__class__.__name__}.{err.__traceback__.tb_frame.f_code.co_name}::{err}::LINE={err.__traceback__.tb_lineno}'
        for arg in args:
            msg += f'::{arg}'
        logging.error(msg)

    def get_fields_names(self):
        opts = self._meta
        return [f.name for f in chain(opts.concrete_fields, opts.private_fields)]

    def to_list(self):
        opts = self._meta
        data = []
        for f in chain(opts.concrete_fields, opts.private_fields):
            value = f.value_from_object(self)
            data.append(value)
        return data

    def to_list_strings(self):
        opts = self._meta
        data = []
        for f in chain(opts.concrete_fields, opts.private_fields):
            value = f.value_from_object(self)
            if value is None:
                value = ''
            data.append(value if isinstance(value, str) else f'{value}')
        return data

    def to_dict(self):
        opts = self._meta
        data = {}
        for f in chain(opts.concrete_fields, opts.private_fields):
            value = f.value_from_object(self)
            if value:
                data[f.name] = value if isinstance(value, str) else f'{value}'
        for f in opts.many_to_many:
            data[f.name] = [i.id for i in f.value_from_object(self)]
        return data


class Doc(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('created date'), help_text=_('Date of creation'))
    registered_at = models.DateTimeField(default=django_timezone.now, null=False, blank=False, verbose_name=_('registered date'), help_text=_('Date of registration'))
    owner = models.ForeignKey('refs.Company', default=1, null=False, blank=False, on_delete=models.CASCADE, related_name='owner_docs', related_query_name='owner_doc', verbose_name=_('owner'), help_text=_('owner of document'))
    contractor = models.ForeignKey('refs.Company', default=2, null=False, blank=False, on_delete=models.CASCADE, related_name='contractor_docs', related_query_name='contractor_doc', verbose_name=_('contractor'), help_text=_('contractor of document'))
    type = models.ForeignKey('refs.DocType', default=1, null=False, blank=False, on_delete=models.CASCADE, verbose_name=_('type'), help_text=_('type of document'))
    tax = models.ForeignKey('refs.Tax', default=1, null=False, blank=False, on_delete=models.CASCADE, verbose_name=_('tax'), help_text=_('tax of document'))
    sale_point = models.ForeignKey('refs.SalePoint', default=None, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_('sale point'), help_text=_('sale point of document'))
    author = models.ForeignKey('users.User', default=1, null=False, blank=False, on_delete=models.CASCADE, verbose_name=_('author'), help_text=_('author of document'))
    extinfo = JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = f'📄{_("Doc")}'
        verbose_name_plural = f'📄{_("Docs")}'
        ordering = ['-registered_at']


class Record(models.Model):
    count = models.DecimalField(max_digits=15, decimal_places=3, default=0, null=False, blank=False, verbose_name=_('count'), help_text=_('count of products'))
    cost = models.DecimalField(max_digits=15, decimal_places=3, default=0, null=False, blank=False, verbose_name=_('cost'), help_text=_('current cost'))
    price = models.DecimalField(max_digits=15, decimal_places=3, default=0, null=False, blank=False, verbose_name=_('price'), help_text=_('current price'))
    doc = models.ForeignKey(Doc, default=1, null=False, blank=False, on_delete=models.CASCADE, verbose_name=_('document'), help_text=_('refernce of document'))
    currency = models.ForeignKey('refs.Currency', null=True, blank=True, default=1, on_delete=models.SET_NULL)
    product = models.ForeignKey('refs.Product', default=1, null=False, blank=False, on_delete=models.CASCADE, verbose_name=_('product'), help_text=_('refernce of product'))
    extinfo = JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = f'®{_("Record")}'
        verbose_name_plural = f'®{_("Records")}'
        ordering = ['-id']


class Register(models.Model):
    rec = models.ForeignKey(Record, default=1, null=False, blank=False, on_delete=models.CASCADE, verbose_name=_('record'), help_text=_('record of document'))

    class Meta:
        verbose_name = f'✅{_("Register")}'
        verbose_name_plural = f'✅{_("Registers")}'
        ordering = ['-id']
