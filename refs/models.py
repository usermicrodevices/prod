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


class Unit(models.Model):
    label = models.CharField(max_length=191, unique=True, null=False, blank=False, default='', verbose_name=_('label of unit'))
    name = models.CharField(max_length=191, verbose_name=_('name of unit'))

    def __str__(self):
        return f'({self.id}){self.label}'

    class Meta:
        verbose_name = f'👾{_("Unit")}'
        verbose_name_plural = f'👾{_("Units")}'


class Tax(models.Model):
    name = models.CharField(max_length=191, unique=True, null=False, blank=False, default='', verbose_name=_('name'))
    alias = models.CharField(max_length=191, null=True, blank=True, default='', verbose_name=_('alias'))
    value = models.IntegerField(default=None, null=True, blank=True, verbose_name=_('value'), help_text=_('percentage value of tax'))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = f'󠀥󠀥󠀥󠀥󠀥󠀥💯{_("Tax")}'
        verbose_name_plural = f'💯{_("Taxes")}'
        ordering = ['name']


class Currency(models.Model):
    name = models.CharField(max_length=191, unique=True, null=False, blank=False, default='₽')
    alias = models.CharField(max_length=191, null=True, blank=True, default='rub')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = f'💱{_("Currency")}'
        verbose_name_plural = f'💱{_("Currencies")}'
        ordering = ['name']


class Country(models.Model):
    name = models.CharField(max_length=191, unique=True, null=False, blank=False, default='')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = f'🌎{_("Country")}'
        verbose_name_plural = f'🌎{_("Countries")}'
        ordering = ['name']


class Region(models.Model):
    name = models.CharField(max_length=191, null=False, blank=False, default='')
    country = models.ForeignKey(Country, null=False, blank=False, default=1, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ('name', 'country')
        verbose_name = f'🌎{_("Region")}'
        verbose_name_plural = f'🌎{_("Regions")}'
        ordering = ['name']


class City(models.Model):
    name = models.CharField(max_length=191, null=False, blank=False, default='')
    region = models.ForeignKey(Region, null=False, blank=False, default=1, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ('name', 'region')
        verbose_name = f'🌎{_("City")}'
        verbose_name_plural = f'🌎{_("Cities")}'
        ordering = ['name']


class Manufacturer(models.Model):
    name = models.CharField(max_length=191, default='', unique=True, verbose_name=_('caption'), help_text=_('Caption of manufacturer'))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = f'🖥️{_("Manufacturer")}'
        verbose_name_plural = f'🖥️{_("Manufacturers")}'
        ordering = ['name']


class ProductModel(models.Model):
    name = models.CharField(max_length=191, default='', unique=True, verbose_name=_('caption'), help_text=_('Caption of model'))
    manufacturer = models.ForeignKey(Manufacturer, default=None, null=True, blank=True, on_delete=models.PROTECT)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = f'🖥{_("Product Model")}'
        verbose_name_plural = f'🖥{_("Product Models")}'
        ordering = ['name']


class CompanyType(models.Model):
    name = models.CharField(max_length=191, default='', unique=True, verbose_name=_('name'), help_text=_('Type of company'))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = f'™️{_("Company Type")}'
        verbose_name_plural = f'™️{_("Company Types")}'
        ordering = ['name']


class Company(CustomAbstractModel):
    name = models.CharField(max_length=191, default='', unique=True, verbose_name=_('caption'), help_text=_('Caption of company'))
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('created date'), help_text=_('Date of creation on server'))
    contact_people = models.CharField(max_length=191, default=None, null=True, blank=True, verbose_name=_('contact people'), help_text=_('Contact people of company'))
    phone = models.CharField(max_length=191, default=None, null=True, blank=True, verbose_name=_('phone'), help_text=_('Contact people phone of company'))
    emails = models.EmailField(max_length=191, default=None, null=True, blank=True, verbose_name=_('email'), help_text=_('Email of company'))
    city = models.ForeignKey(City, default=None, null=True, blank=True, on_delete=models.SET_NULL)
    type = models.ForeignKey(CompanyType, default=None, null=True, blank=True, on_delete=models.SET_NULL)
    currency = models.ForeignKey(Currency, null=True, blank=True, default=1, on_delete=models.SET_NULL)
    extinfo = JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = f'™️{_("Company")}'
        verbose_name_plural = f'™️{_("Companies")}'
        ordering = ['name']

    def __str__(self):
        return self.name


class SalePoint(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name=_('company'))
    name = models.CharField(max_length=191, default='', verbose_name=_('caption'), help_text=_('Caption of object'))
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('created date'), help_text=_('Date of creation on server'))
    address = models.CharField(max_length=191, default=None, null=True, blank=True, verbose_name=_('address'), help_text=_('Address of object'))
    map_point = models.CharField(max_length=191, default=None, null=True, blank=True, verbose_name=_('map point'), help_text=_('Coords on map'))
    city = models.ForeignKey(City, default=1, null=True, blank=True, on_delete=models.SET_NULL)
    person = models.CharField(max_length=191, default=None, null=True, blank=True, verbose_name=_('person'), help_text=_('Person on object'))
    emails = models.EmailField(max_length=191, default=None, null=True, blank=True, verbose_name=_('email'), help_text=_('Email on object'))
    phone = models.CharField(max_length=191, default=None, null=True, blank=True, verbose_name=_('phone'), help_text=_('Phone on object'))
    extinfo = JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('name', 'company')
        verbose_name = f'™️{_("Sale Point")}'
        verbose_name_plural = f'™️{_("Sale Points")}'
        ordering = ['name']

    def __str__(self):
        return '[{}]{}'.format(self.id, self.name)


class BarCode(models.Model):
    id = models.CharField(primary_key=True, max_length=191, unique=True, default=uuid4, null=False, blank=False, verbose_name=_('value'), help_text=_('product barcode'))

    class Meta:
        verbose_name = f'Ⅲ{_("Bar Code")}'
        verbose_name_plural = f'Ⅲ{_("Bar Codes")}'


class QrCode(models.Model):
    id = models.CharField(primary_key=True, max_length=191, unique=True, default=uuid4, null=False, blank=False, verbose_name=_('value'), help_text=_('product qrcode'))

    class Meta:
        verbose_name = f'𝍌{_("Qr Code")}'
        verbose_name_plural = f'𝍌{_("Qr Codes")}'


class DocType(models.Model):
    alias = models.CharField(max_length=191, unique=True, default='receipt', null=False, blank=False)
    name = models.CharField(max_length=191, default=_('Receipt'), verbose_name=_('name'), help_text=_('name of type document'))
    income = models.BooleanField(default=True, null=False, blank=False, verbose_name=_('income'), help_text=_('income or expense'))
    auto_register = models.BooleanField(default=True, null=False, blank=False, verbose_name=_('auto register'), help_text=_('auto register when save document'))
    description = models.CharField(max_length=191, default=None, null=True, blank=True, verbose_name=_('description'), help_text=_('description of type document'))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = f'🏷️{_("Doc Type")}'
        verbose_name_plural = f'🏷️{_("Doc Types")}'
        ordering = ['name']


class ProductGroup(models.Model):
    name = models.CharField(max_length=191, unique=True, default=_('Products'), verbose_name=_('name'), help_text=_('name of products group'))
    alias = models.CharField(max_length=191, default=None, null=True, blank=True, verbose_name=_('alias'), help_text=_('alias of products group'))
    description = models.CharField(max_length=191, default=None, null=True, blank=True, verbose_name=_('description'), help_text=_('description of products group'))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = f'📚{_("Product Group")}'
        verbose_name_plural = f'📚{_("Product Groups")}'
        ordering = ['name']


class Product(models.Model):
    article = models.CharField(max_length=191, default=uuid4, null=False, blank=False, verbose_name=_('article'), help_text=_('product article'))
    name = models.CharField(max_length=191, default='', verbose_name=_('name'), help_text=_('Caption of item'))
    cost = models.DecimalField(max_digits=15, decimal_places=3, default=0, null=False, blank=False, verbose_name=_('cost'), help_text=_('default cost'))
    price = models.DecimalField(max_digits=15, decimal_places=3, default=0, null=False, blank=False, verbose_name=_('price'), help_text=_('default price'))
    currency = models.ForeignKey(Currency, default=1, null=True, blank=True, on_delete=models.SET_NULL)
    model = models.ForeignKey(ProductModel, default=None, null=True, blank=True, on_delete=models.SET_NULL)
    unit = models.ForeignKey(Unit, default=1, null=True, blank=True, on_delete=models.SET_NULL)
    tax = models.ForeignKey(Tax, default=None, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_('tax'), help_text=_('default tax'))
    barcodes = models.ManyToManyField(BarCode, default=None, blank=True, verbose_name=_('barcodes'), help_text=_('list barcodes of product'))
    qrcodes = models.ManyToManyField(QrCode, default=None, blank=True, verbose_name=_('qrcodes'), help_text=_('list qrcodes of product'))
    group = models.ForeignKey(ProductGroup, default=None, null=True, blank=True, on_delete=models.SET_NULL)
    extinfo = JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('article', 'name')
        verbose_name = f'📦{_("Product")}'
        verbose_name_plural = f'📦{_("Products")}'
        ordering = ['name']

    def __str__(self):
        return self.name
