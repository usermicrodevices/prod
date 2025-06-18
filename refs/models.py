import logging, os, sys, time
from uuid import uuid4
from itertools import chain
from datetime import datetime, timedelta, timezone
from barcode import EAN13

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


def ean13(value:str=None):
    if not value:
        value = f'{round(time.time()*1000)}'
    ean13 = EAN13(value)
    if value != ean13.ean:
        value = ean13.ean
    return value


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
        msg = f'🆘{self.__class__.__name__}.{err.__traceback__.tb_frame.f_code.co_name}'
        for arg in args:
            msg += f'::{arg}'
        msg += f'::{err}::LINE={err.__traceback__.tb_lineno}'
        logging.error(msg)

    def get_fields_names(self):
        opts = self._meta
        return [f.name for f in chain(opts.concrete_fields, opts.private_fields)]


    def to_list(self, exclude_fields='__all__'):
        data = []
        if isinstance(exclude_fields, str) and  exclude_fields == '__all__':
            return data
        opts = self._meta
        for f in chain(opts.concrete_fields, opts.private_fields):
            if f.name in exclude_fields:
                continue
            value = f.value_from_object(self)
            data.append(value)
        return data

    def to_list_strings(self, exclude_fields='__all__'):
        data = []
        if isinstance(exclude_fields, str) and  exclude_fields == '__all__':
            return data
        opts = self._meta
        for f in chain(opts.concrete_fields, opts.private_fields):
            if f.name in exclude_fields:
                continue
            value = f.value_from_object(self)
            if value is None:
                value = ''
            data.append(value if isinstance(value, str) else f'{value}')
        return data

    def to_dict(self, exclude_fields='__all__'):
        data = {}
        if isinstance(exclude_fields, str) and  exclude_fields == '__all__':
            return data
        opts = self._meta
        for f in chain(opts.concrete_fields, opts.private_fields):
            if f.name in exclude_fields:
                continue
            value = f.value_from_object(self)
            data[f.name] = value if isinstance(value, str) else f'{value}'
        for f in opts.many_to_many:
            if f.name in exclude_fields:
                continue
            data[f.name] = [i.id for i in f.value_from_object(self)]
        return data


def default_ptmpl_dict():
    return {"script": "<script>window.onload=function(){document.getElementsByTagName(\"head\")[0].remove();document.body.style.margin=0;document.body.style.padding=0;document.body.style.width=0;document.body.style.height=0;const parea = document.getElementById(\"section-to-print\");while(document.body.firstChild){document.body.removeChild(document.body.firstChild);}document.body.appendChild(parea);setTimeout(function(){window.print();},0);window.onfocus=function(){setTimeout(function(){window.location.reload();},0);}}</script>", "css_media_style": "@media (orientation:portrait) print{html body{width:210mm;height:297mm;visibility:hidden;height:auto;margin:0;padding:0;}} .content{position:absolute;top:0;} .messagelist{margin:0;padding:0;} #section-to-print{text-align:center;background-color:white;display:flex;flex-direction:column;visibility:visible;position:absolute;left:0;top:0;margin:0;padding:0;width:95%;height:95%;} @page{size:A4;margin:0;} .page-pad{break-after:page;} .page-pad:last-of-type{break-after:avoid!important;} html:root{--message-success-bg:unset;} #container{height:max-content;width:max-content;min-width:unset;} ul.messagelist li{display:unset;margin:0;padding:0;background:white;background-size:unset;font-size:unset;word-break:unset;color:black;} header,footer,aside,nav,form,iframe,button,.ad,.success,#header,#content,#toggle-nav-sidebar{display:none;}"}


class PrintTemplates(CustomAbstractModel):
    alias = models.CharField(max_length=191, unique=True, null=False, blank=False, default='refs.doctype.sale', verbose_name=_('alias'))
    content = models.TextField(null=False, blank=False, default='''<table class="page-pad" style="border:1px solid black;margin-left:auto;margin-right:auto;border-collapse:collapse;"><caption>{{doc.type.name}} N{{doc.id}} from {{doc.registered_at}}<p style="text-align:left;margin:0;padding:0;">seler: {{doc.owner}}</p><p style="text-align:left;margin:0;padding:0;">purchaser: {{doc.contractor.name}}</p></caption><thead><tr><th style="width:5%;border:2px solid black;">number</th><th style="width:15%;border:2px solid black;">article</th><th style="width:50%;border:2px solid black;">product</th><th style="width:10%;border:2px solid black;">count</th><th style="width:10%;border:2px solid black;">price</th><th style="width:10%;border:2px solid black;">sum</th></tr></thead><tbody>{% for r in records %}<tr><td style="border:2px solid black;">{{forloop.counter}}</td><td style="border:2px solid black;">{{r.product.article}}</td><td style="border:2px solid black;">{{r.product.name}}</td><td style="border:2px solid black;">{{r.count}}</td><td style="border:2px solid black;">{{r.price}}</td><td style="border:2px solid black;">{{r.sum_price}}</td></tr>{% endfor %}<tr><td style="border:2px solid black;text-align:right;" colspan=6>Total: {{doc.sum_final}}</td></tr></tbody></table>''', verbose_name=_('content'))
    extinfo = JSONField(default=default_ptmpl_dict, blank=True)

    class Meta:
        verbose_name = f'🖶{_("Print Template")}'
        verbose_name_plural = f'🖶{_("Print Templates")}'


class Unit(CustomAbstractModel):
    label = models.CharField(max_length=191, unique=True, null=False, blank=False, default='', verbose_name=_('label of unit'))
    name = models.CharField(max_length=191, verbose_name=_('name of unit'))

    def __str__(self):
        return f'({self.id}){self.label}'

    class Meta:
        verbose_name = f'👾{_("Unit")}'
        verbose_name_plural = f'👾{_("Units")}'


class Tax(CustomAbstractModel):
    name = models.CharField(max_length=191, unique=True, null=False, blank=False, default='', verbose_name=_('name'))
    alias = models.CharField(max_length=191, null=True, blank=True, default='', verbose_name=_('alias'))
    value = models.IntegerField(default=None, null=True, blank=True, verbose_name=_('value'), help_text=_('percentage value of tax'))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = f'󠀥󠀥󠀥󠀥󠀥󠀥💯{_("Tax")}'
        verbose_name_plural = f'💯{_("Taxes")}'
        ordering = ['name']


class Currency(CustomAbstractModel):
    name = models.CharField(max_length=191, unique=True, null=False, blank=False, default='₽')
    alias = models.CharField(max_length=191, null=True, blank=True, default='rub')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = f'💱{_("Currency")}'
        verbose_name_plural = f'💱{_("Currencies")}'
        ordering = ['name']


class Country(CustomAbstractModel):
    name = models.CharField(max_length=191, unique=True, null=False, blank=False, default='', verbose_name=_('name'), help_text=_('name of country'))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = f'🌎{_("Country")}'
        verbose_name_plural = f'🌎{_("Countries")}'
        ordering = ['name']


class Region(CustomAbstractModel):
    name = models.CharField(max_length=191, null=False, blank=False, default='', verbose_name=_('name'), help_text=_('name of region'))
    country = models.ForeignKey(Country, null=False, blank=False, default=1, on_delete=models.CASCADE, verbose_name=_('country'), help_text=_('country of region'))

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ('name', 'country')
        verbose_name = f'🌎{_("Region")}'
        verbose_name_plural = f'🌎{_("Regions")}'
        ordering = ['name']


class City(CustomAbstractModel):
    name = models.CharField(max_length=191, null=False, blank=False, default='', verbose_name=_('name'), help_text=_('name of city'))
    region = models.ForeignKey(Region, null=False, blank=False, default=1, on_delete=models.CASCADE, verbose_name=_('region'), help_text=_('region of city'))

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ('name', 'region')
        verbose_name = f'🌎{_("City")}'
        verbose_name_plural = f'🌎{_("Cities")}'
        ordering = ['name']


class Manufacturer(CustomAbstractModel):
    name = models.CharField(max_length=191, default='', unique=True, verbose_name=_('caption'), help_text=_('Caption of manufacturer'))
    city = models.ForeignKey(City, default=None, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_('city'), help_text=_('city of manufacturer'))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = f'🖥️{_("Manufacturer")}'
        verbose_name_plural = f'🖥️{_("Manufacturers")}'
        ordering = ['name']


class ProductModel(CustomAbstractModel):
    name = models.CharField(max_length=191, default='', unique=True, verbose_name=_('caption'), help_text=_('Caption of model'))
    manufacturer = models.ForeignKey(Manufacturer, default=None, null=True, blank=True, on_delete=models.PROTECT, verbose_name=_('manufacturer'), help_text=_('manufacturer of model'))

    def __str__(self):
        try:
            return f'{self.manufacturer.name} {self.name}'
        except Exception as e:
            return self.name

    class Meta:
        verbose_name = f'🖥{_("Product Model")}'
        verbose_name_plural = f'🖥{_("Product Models")}'
        ordering = ['name']


class CompanyType(CustomAbstractModel):
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
    city = models.ForeignKey(City, default=None, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_('city'), help_text=_('city of company'))
    type = models.ForeignKey(CompanyType, default=None, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_('type'), help_text=_('type of company'))
    currency = models.ForeignKey(Currency, null=True, blank=True, default=1, on_delete=models.SET_NULL, verbose_name=_('currency'), help_text=_('currency of company'))
    extinfo = JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = f'™️{_("Company")}'
        verbose_name_plural = f'™️{_("Companies")}'
        ordering = ['name']

    def __str__(self):
        return self.name


class SalePoint(CustomAbstractModel):
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


class BarCode(CustomAbstractModel):
    id = models.CharField(primary_key=True, max_length=191, unique=True, default=ean13, null=False, blank=False, verbose_name=_('value'), help_text=_('product barcode'))

    class Meta:
        verbose_name = f'Ⅲ{_("Bar Code")}'
        verbose_name_plural = f'Ⅲ{_("Bar Codes")}'


class QrCode(CustomAbstractModel):
    id = models.CharField(primary_key=True, max_length=191, unique=True, default=uuid4, null=False, blank=False, verbose_name=_('value'), help_text=_('product qrcode'))

    class Meta:
        verbose_name = f'𝍌{_("Qr Code")}'
        verbose_name_plural = f'𝍌{_("Qr Codes")}'


class DocType(CustomAbstractModel):
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


class ProductImage(CustomAbstractModel):

    def uploadto(self, filename):
        # uploaded to MEDIA_ROOT/products/
        return f'products/{django_timezone.now().strftime("%Y%m%d%H%M%S")}_{filename}'

    #ImageField required pillow and not support some new formats - better use FileField directly
    #file = models.ImageField(upload_to=uploadto, default=None, null=True, blank=True)
    file = models.FileField(upload_to=uploadto, max_length=255, default=None, null=True, blank=True, verbose_name=_('file'))
    created_at = models.DateTimeField(_('date created'), auto_now_add=True, editable=False)
    extinfo = JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = f'📄{_("Product Image")}'
        verbose_name_plural = f'📄{_("Product Images")}'


@receiver(post_delete, sender=ProductImage)
def product_image_post_delete(sender, instance, **kwargs):
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)


@receiver(pre_save, sender=ProductImage)
def product_image_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        return False
    try:
        file_was = ProductImage.objects.get(pk=instance.pk).file
    except ProductImage.DoesNotExist:
        return False
    if file_was and file_was != instance.file:
        if os.path.isfile(file_was.path):
            os.remove(file_was.path)


class ProductGroup(CustomAbstractModel):
    parent = models.ForeignKey('self', default=None, null=True, blank=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=191, unique=True, default=_('Products'), verbose_name=_('name'), help_text=_('name of products group'))
    alias = models.CharField(max_length=191, default=None, null=True, blank=True, verbose_name=_('alias'), help_text=_('alias of products group'))
    description = models.CharField(max_length=191, default=None, null=True, blank=True, verbose_name=_('description'), help_text=_('description of products group'))
    extinfo = JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = f'📚{_("Product Group")}'
        verbose_name_plural = f'📚{_("Product Groups")}'
        ordering = ['name']


class Product(CustomAbstractModel):
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
    thumbnail = models.TextField(default=None, null=True, blank=True, verbose_name=_('thumbnail'), help_text=_('image as')+' BASE64')
    images = models.ManyToManyField(ProductImage, default=None, blank=True, verbose_name=_('images'), help_text=_('list images of product'))

    class Meta:
        unique_together = ('article', 'name')
        verbose_name = f'📦{_("Product")}'
        verbose_name_plural = f'📦{_("Products")}'
        ordering = ['name']

    def __str__(self):
        return self.name


class Customer(CustomAbstractModel):
    name = models.CharField(max_length=191, default='', null=False, blank=False, unique=True, verbose_name=_('name'), help_text=_('Caption of item'))
    extinfo = JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = f'🕵{_("Customer")}'
        verbose_name_plural = f'🕵{_("Customers")}'
        ordering = ['name']

    def __str__(self):
        return self.name
