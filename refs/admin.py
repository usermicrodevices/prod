from decimal import Decimal
from io import BytesIO, StringIO
from datetime import datetime, timedelta
try:
    from zoneinfo import available_timezones, ZoneInfo
except:
    from backports.zoneinfo import available_timezones, ZoneInfo

from django.utils import timezone as django_timezone
from django.utils.translation import gettext as _
from django.utils.html import format_html, format_html_join
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib import admin, messages
from django import forms
from django.http import StreamingHttpResponse, FileResponse, HttpResponseRedirect
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.db.models import F, Q, Min, Max, Value, Count, IntegerField, TextField, CharField, OuterRef, Subquery
from django.db.models.query import QuerySet
from django.db import connections
from django.contrib.admin.models import LogEntry
from django.contrib.admin.widgets import AutocompleteSelect
from django.shortcuts import render
from django.views.generic.edit import FormView
from django.core.cache import caches
from django.conf import settings
from django.apps import apps as django_apps

from .models import CustomAbstractModel, Unit, Currency, Country, Region, City, Nds, CompanyType, Company, SalePoint, Manufacturer, ProductModel, BarCode, QrCode, Product
from users.models import User

def get_model(app_model):
	app_name, model_name = app_model.split('.')
	return django_apps.get_app_config(app_name).get_model(model_name)

def get_queryset_by_company(super, request):
    qs = super.get_queryset(request)
    user = request.user
    if user.is_superuser:
        return qs
    return qs.filter(Q(company__in=user.companies.all()) | Q(company_id__in=user.sale_points.values_list('company_id', flat=True))).distinct()

def get_queryset_by_sale_point(super, request):
    qs = super.get_queryset(request)
    user = request.user
    if user.is_superuser:
        return qs
    return qs.filter(Q(sale_point__company__in=user.companies.all()) | Q(sale_point__in=user.sale_points.all())).distinct()


class DropDownFilter(admin.SimpleListFilter):
    template = 'dropdown_filter_from_memory.html'


class UploadFileForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    file = forms.FileField(widget=forms.ClearableFileInput(attrs={'allow_multiple_selected': True}))


class CityFilter(DropDownFilter):
    title = _('City')
    parameter_name = 'city'

    def lookups(self, request, model_admin):
        res = []
        queryset = City.objects.only('id', 'name')
        for it in queryset:
            res.append((it.id, it.name))
        return res

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(city=self.value())


class UnitFilter(DropDownFilter):
    title = _('Unit')
    parameter_name = 'unit'

    def lookups(self, request, model_admin):
        res = []
        queryset = Unit.objects.only('id', 'name')
        for it in queryset:
            res.append((it.id, it.name))
        return res

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(unit=self.value())


class CurrencyFilter(DropDownFilter):
    title = _('Currency')
    parameter_name = 'currency'

    def lookups(self, request, model_admin):
        res = []
        queryset = Currency.objects.only('id', 'name')
        for it in queryset:
            res.append((it.id, it.name))
        return res

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(currency=self.value())


class NdsFilter(DropDownFilter):
    title = _('Nds')
    parameter_name = 'nds'

    def lookups(self, request, model_admin):
        res = []
        queryset = Nds.objects.only('id', 'name')
        for it in queryset:
            res.append((it.id, it.name))
        return res

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(nds=self.value())


class ProductModelFilter(DropDownFilter):
    title = _('ProductModel')
    parameter_name = 'model'

    def lookups(self, request, model_admin):
        res = []
        queryset = ProductModel.objects.only('id', 'name')
        for it in queryset:
            res.append((it.id, it.name))
        return res

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(model=self.value())


class CompanyTypeFilter(DropDownFilter):
    title = _('Company Type')
    parameter_name = 'type'

    def lookups(self, request, model_admin):
        user = request.user
        res = []
        queryset = CompanyType.objects.only('id', 'name')
        if not user.is_superuser:
            queryset = queryset.filter(Q(type__company__in=user.companies.all()) | Q(type__company__id__in=user.sale_points.values_list('company_id', flat=True)))
        for it in queryset:
            res.append((it.id, it.name))
        return res

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(type=self.value())


class CompanyFilter(DropDownFilter):
    title = _('Company')
    parameter_name = 'company'

    def lookups(self, request, model_admin):
        user = request.user
        res = []
        queryset = Company.objects.only('id', 'name')
        if not user.is_superuser:
            queryset = queryset.filter(Q(pk__in=user.companies.all()) | Q(id__in=user.sale_points.values_list('company_id', flat=True)))
        for it in queryset:
            res.append((it.id, it.name))
        return res

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(company=self.value())


class TypeCompanyFilter(CompanyFilter):

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(type__company=self.value())


class SalePointCompanyFilter(CompanyFilter):

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(sale_point__company=self.value())


class SalePointFilter(DropDownFilter):
    title = _('Sale Point')
    parameter_name = 'sale_point'

    def lookups(self, request, model_admin):
        user = request.user
        res = []
        queryset = SalePoint.objects.only('id', 'name')
        if not user.is_superuser:
            queryset = queryset.filter(Q(company__in=user.companies.all()) | Q(id__in=user.sale_points.values_list('id', flat=True)))
        for it in queryset:
            res.append((it.id, it.name))
        return res

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(sale_point=self.value())


class QrcodeFilter(DropDownFilter):
    title = _('Qrcode')
    parameter_name = 'qrcodes__in'

    def lookups(self, request, model_admin):
        res = []
        queryset = Qrcode.objects.only('id', 'value')
        for it in queryset:
            res.append((it.id, it.name))
        return res

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(qrcodes__in=[self.value()])


class CustomModelAdmin(admin.ModelAdmin):

    def logi(self, *args):
        msg = f'ℹ️{self.__class__.__name__}.{sys._getframe().f_back.f_code.co_name}'
        for arg in args:
            msg += f'::{arg}'
        logging.info(msg)

    def logw(self, *args):
        msg = f'⚠{self.__class__.__name__}.{sys._getframe().f_back.f_code.co_name}'
        for arg in args:
            msg += f'::{arg}'
        logging.warning(msg)

    def loge(self, err, *args):
        msg = f'🆘{self.__class__.__name__}.{err.__traceback__.tb_frame.f_code.co_name}::{err}::LINE={err.__traceback__.tb_lineno}'
        for arg in args:
            msg += f'::{arg}'
        logging.error(msg)


class UnitAdmin(CustomModelAdmin):
    list_display = ('id', 'name', 'label')
    list_editable = ('name', 'label')
    search_fields = ('id', 'name', 'label')
admin.site.register(Unit, UnitAdmin)


class CurrencyAdmin(CustomModelAdmin):
    list_display = ('id', 'name', 'alias')
    list_display_links = ('name',)
    search_fields = ('id', 'name', 'alias')
admin.site.register(Currency, CurrencyAdmin)


class NdsAdmin(CustomModelAdmin):
    list_display = ('id', 'name', 'alias', 'value')
    list_display_links = ('name',)
    search_fields = ('id', 'name', 'alias', 'value')
admin.site.register(Nds, NdsAdmin)


class CountryAdmin(CustomModelAdmin):
    list_display = ['id', 'name']
    list_display_links = ['name']
    search_fields = ['name']
admin.site.register(Country, CountryAdmin)


class RegionAdmin(CustomModelAdmin):
    list_display = ['id', 'name', 'country']
    list_display_links = ['name']
    search_fields = ['name', 'country__name']
    list_select_related = ['country']
    list_filter = ['country']
    autocomplete_fields = ['country']
    raw_id_fields = ['country']
admin.site.register(Region, RegionAdmin)


class CityAdmin(CustomModelAdmin):
    list_display = ['id', 'name', 'region']
    list_display_links = ['id', 'name']
    search_fields = ['id', 'name', 'region__name', 'region__country__name']
    list_select_related = ['region__country']
    list_filter = ['region__country']
    autocomplete_fields = ['region']
    raw_id_fields = ['region']
admin.site.register(City, CityAdmin)


class ManufacturerAdmin(CustomModelAdmin):
    list_display = ('id', 'name')
    list_display_links = ('id', 'name')
    search_fields = ('id', 'name')
admin.site.register(Manufacturer, ManufacturerAdmin)


class ProductModelAdmin(CustomModelAdmin):
    list_display = ('id', 'name', 'manufacturer')
    list_display_links = ('id', 'name')
    search_fields = ('id', 'name', 'manufacturer__name')
admin.site.register(ProductModel, ProductModelAdmin)


class CompanyTypeAdmin(CustomModelAdmin):
    list_display = ('id', 'name')
    list_display_links = ('id', 'name')
    search_fields = ('id', 'name')
admin.site.register(CompanyType, CompanyTypeAdmin)


class CompanyAdmin(CustomModelAdmin):
    list_display = ('id', 'name', 'created_date', 'get_type', 'currency')
    list_display_links = ['id', 'name']
    search_fields = ['id', 'name', 'created_date', 'type__name',  'currency__name', 'currency__alias']
    list_select_related = ['type']
    autocomplete_fields = ['type']
    list_filter = [CompanyTypeFilter,  CurrencyFilter]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        if not user.is_superuser:
            qs = qs.filter(Q(pk__in=user.companies.values_list('id', flat=True)) | Q(pk__in=user.sale_points.values_list('company_id', flat=True))).distinct()
        return qs

    def get_type(self, obj):
        if obj.sd:
            return format_html(f'''<p><font color="green" face="Verdana, Geneva, sans-serif"><a href="https://support.telemetry.work/back/admin/core/company/?id={obj.sd}" target="_blank">{obj.sd}</a></font></p>''')
        else:
            return ''
    get_type.short_description = _('Company Type')
    get_type.admin_order_field = 'type'

admin.site.register(Company, CompanyAdmin)


class SalePointAdmin(CustomModelAdmin):
    save_on_top = True
    list_display = ('id', 'name', 'get_company', 'created_date', 'address', 'map_point', 'city')
    list_display_links = ['id', 'name']
    search_fields = ['name', 'company__name', 'created_date', 'address', 'map_point']
    list_select_related = ['company']
    list_filter = [CompanyFilter, CityFilter]
    autocomplete_fields = ['company']
    raw_id_fields = ['city']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        if user.is_superuser:
            return qs
        return qs.filter(Q(company__in=user.companies.all()) | Q(pk__in=user.sale_points.values_list('id', flat=True))).distinct()

    def get_company(self, obj):
        o = obj.company
        if not o:
            return ''
        m = o._meta
        return format_html('''<p><font color="green" face="Verdana, Geneva, sans-serif"><a href="{}" target="_blank">{}</a></font></p>''', reverse('admin:{}_{}_change'.format(m.app_label, m.model_name), args=(o.id,)), o.name)
    get_company.short_description = _('Company')
    get_company.admin_order_field = 'company'

admin.site.register(SalePoint, SalePointAdmin)


class BarCodeAdmin(CustomModelAdmin):
    list_display = ['value']
    list_display_links = ['value']
    search_fields = ['value']
admin.site.register(BarCode, BarCodeAdmin)


class QrCodeAdmin(CustomModelAdmin):
    list_display = ['value']
    list_display_links = ['value']
    search_fields = ['value']
admin.site.register(QrCode, QrCodeAdmin)


class ProductAdmin(CustomModelAdmin):
    list_display = ('id', 'article', 'name', 'get_barcodes', 'get_qrcodes', 'get_cost', 'get_price', 'count', 'extinfo')
    list_display_links = ('id', 'article', 'name')
    search_fields = ('name', 'article', 'extinfo', 'barcodes__value', 'qrcodes__value')
    list_select_related = ('nds', 'model')
    list_filter = (NdsFilter, ProductModelFilter)
    actions = ('from_xls', 'to_xls', 'barcode_generator')

    def get_cost(self, obj):
        return format_html('<font color="green" face="Verdana, Geneva, sans-serif">{} {}</font>', obj.cost.quantize(Decimal('0.00')), obj.currency.name if obj.currency else '')
    get_cost.short_description = _('cost')
    get_cost.admin_order_field = 'cost'

    def get_price(self, obj):
        return format_html('<font color="green" face="Verdana, Geneva, sans-serif">{} {}</font>', obj.price.quantize(Decimal('0.00')), obj.currency.name if obj.currency else '')
    get_price.short_description = _('price')
    get_price.admin_order_field = 'price'

    def get_barcodes(self, obj):
        try:
            idxs = BarCode.objects.filter(product__in=[obj]).annotate(admin_path_prefix=Value(settings.ADMIN_PATH_PREFIX, CharField())).values_list('admin_path_prefix', 'value')
        except Exception as e:
            return ''
        else:
            if not idxs:
                return ''
            content = format_html_join('\n', '<p><font color="green" face="Verdana, Geneva, sans-serif"><a href="{0}/refs/barcode/?value={1}" target="_blank">{1}</a></font></p>', idxs)
            return format_html('<details><summary>{}</summary>{}</details>', idxs[0][1], content)
    get_barcodes.short_description = _('Bar Codes')

    def get_qrcodes(self, obj):
        try:
            idxs = QrCode.objects.filter(product__in=[obj]).annotate(admin_path_prefix=Value(settings.ADMIN_PATH_PREFIX, CharField())).values_list('admin_path_prefix', 'value')
        except Exception as e:
            return ''
        else:
            if not idxs:
                return ''
            content = format_html_join('\n', '<p><font color="green" face="Verdana, Geneva, sans-serif"><a href="{0}/refs/qrcode/?value={1}" target="_blank">{1}</a></font></p>', idxs)
            return format_html('<details><summary>{}</summary>{}</details>', idxs[0][1], content)
    get_qrcodes.short_description = _('Qr Codes')

    def count(self, obj):
        result = 0#get_model('core.Register').objects.filter(product_id=obj.id).count()
        return format_html('<p><font color="green" face="Verdana, Geneva, sans-serif"><a href="{}/core/register/?product={}" target="_blank">{}</a></font></p>', settings.ADMIN_PATH_PREFIX, obj.id, result)
    count.short_description = _('Count')

admin.site.register(Product, ProductAdmin)
