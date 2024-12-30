import logging, sys
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
from django.db.models import F, Q, Min, Max, Sum, When, Value, Count, IntegerField, TextField, CharField, OuterRef, Subquery
from django.db.models.query import QuerySet
from django.db import connections
from django.contrib.admin.models import LogEntry
from django.contrib.admin.widgets import AutocompleteSelect
from django.shortcuts import render
from django.views.generic.edit import FormView
from django.core.cache import caches
from django.conf import settings
from django.apps import apps as django_apps

from .models import Unit, Currency, Country, Region, City, Tax, CompanyType, Company, SalePoint, Manufacturer, ProductModel, BarCode, QrCode, DocType, ProductGroup, Product
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


class TaxFilter(DropDownFilter):
    title = _('Tax')
    parameter_name = 'tax'

    def lookups(self, request, model_admin):
        res = []
        queryset = Tax.objects.only('id', 'name')
        for it in queryset:
            res.append((it.id, it.name))
        return res

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(tax=self.value())


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


class BarCodeFilter(DropDownFilter):
    title = _('BarCode')
    parameter_name = 'barcodes__in'

    def lookups(self, request, model_admin):
        res = []
        queryset = BarCode.objects.only('id')
        for it in queryset:
            res.append((it.id, it.id))
        return res

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(barcodes__in=[self.value()])


class QrCodeFilter(DropDownFilter):
    title = _('QrCode')
    parameter_name = 'qrcodes__in'

    def lookups(self, request, model_admin):
        res = []
        queryset = QrCode.objects.only('id')
        for it in queryset:
            res.append((it.id, it.id))
        return res

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(qrcodes__in=[self.value()])


class ProductGroupFilter(DropDownFilter):
    title = _('Product Group')
    parameter_name = 'group'

    def lookups(self, request, model_admin):
        res = []
        queryset = ProductGroup.objects.only('id', 'name')
        for it in queryset:
            res.append((it.id, it.name))
        return res

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(group=self.value())


class ProductManufacturerFilter(DropDownFilter):
    title = _('Product Manufacturer')
    parameter_name = 'model__manufacturer'

    def lookups(self, request, model_admin):
        res = []
        queryset = Manufacturer.objects.only('id', 'name')
        for it in queryset:
            res.append((it.id, it.name))
        return res

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(model__manufacturer=self.value())


class DocTypeFilter(DropDownFilter):
    title = _('Doc Type')
    parameter_name = 'type'

    def lookups(self, request, model_admin):
        res = []
        queryset = DocType.objects.only('id', 'name')
        for it in queryset:
            res.append((it.id, it.name))
        return res

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(type=self.value())


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


class TaxAdmin(CustomModelAdmin):
    list_display = ('id', 'name', 'alias', 'value')
    list_display_links = ('name',)
    search_fields = ('id', 'name', 'alias', 'value')
admin.site.register(Tax, TaxAdmin)


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


class DocTypeAdmin(CustomModelAdmin):
    list_display = ('id', 'alias', 'name', 'income', 'description')
    list_display_links = ('id', 'alias', 'name')
    search_fields = ('id', 'alias', 'name', 'description')
admin.site.register(DocType, DocTypeAdmin)


class CompanyAdmin(CustomModelAdmin):
    list_display = ('id', 'name', 'created_date', 'type', 'currency')
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
    list_display = ['id']
    list_display_links = ['id']
    search_fields = ['id']
admin.site.register(BarCode, BarCodeAdmin)


class QrCodeAdmin(CustomModelAdmin):
    list_display = ['id']
    list_display_links = ['id']
    search_fields = ['id']
admin.site.register(QrCode, QrCodeAdmin)


class ProductGroupAdmin(CustomModelAdmin):
    list_display = ('id', 'name', 'alias', 'description')
    list_display_links = ('id', 'name', 'alias')
    search_fields = ('id', 'name', 'alias', 'description')
admin.site.register(ProductGroup, ProductGroupAdmin)


class ProductAdmin(CustomModelAdmin):
    __last_register__ = None
    list_display = ('id', 'article', 'name', 'get_barcodes', 'get_qrcodes', 'get_cost', 'get_price', 'count', 'get_tax', 'get_model', 'get_group', 'extinfo')
    list_display_links = ('id', 'article', 'name')
    search_fields = ('name', 'article', 'extinfo', 'barcodes__id', 'qrcodes__id', 'group__name')
    list_select_related = ('tax', 'model', 'group')
    list_filter = (ProductGroupFilter, ProductManufacturerFilter, ProductModelFilter, TaxFilter)
    autocomplete_fields = ('tax', 'model', 'group', 'barcodes', 'qrcodes')
    actions = ('from_xls', 'to_xls', 'barcode_generator')

    #class Media:
        #js = ['admin/js/autocomplete.js', 'admin/js/vendor/select2/select2.full.js']

    def get_cost(self, obj):
        if not self.__last_register__:
            try:
                self.__last_register__ = get_model('core.Register').objects.filter(rec__product_id=obj.id).order_by('-rec__doc__registered_at').first()
            except Exception as e:
                self.loge(e)
        value = obj.cost
        if self.__last_register__:
            value = self.__last_register__.rec.cost
        return format_html('<font color="green" face="Verdana, Geneva, sans-serif">{} {}</font>', value, obj.currency.name if obj.currency else '')
    get_cost.short_description = _('cost')
    get_cost.admin_order_field = 'cost'

    def get_price(self, obj):
        if not self.__last_register__:
            try:
                self.__last_register__ = get_model('core.Register').objects.filter(rec__product_id=obj.id).order_by('-rec__doc__registered_at').first()
            except Exception as e:
                self.loge(e)
        value = obj.price
        if self.__last_register__:
            value = self.__last_register__.rec.price
        return format_html('<font color="green" face="Verdana, Geneva, sans-serif">{} {}</font>', value.quantize(Decimal('0.00')), obj.currency.name if obj.currency else '')
    get_price.short_description = _('price')
    get_price.admin_order_field = 'price'

    def get_barcodes(self, obj):
        try:
            idxs = BarCode.objects.filter(product__in=[obj]).annotate(admin_path_prefix=Value(settings.ADMIN_PATH_PREFIX, CharField())).values_list('admin_path_prefix', 'id')
        except Exception as e:
            return ''
        else:
            if not idxs:
                return ''
            content = format_html_join('\n', '<p><font color="green" face="Verdana, Geneva, sans-serif"><a href="{0}/refs/barcode/?id={1}" target="_blank">{1}</a></font></p>', idxs)
            return format_html('<details><summary>{}</summary>{}</details>', idxs[0][1], content)
    get_barcodes.short_description = _('Bar Codes')

    def get_qrcodes(self, obj):
        try:
            idxs = QrCode.objects.filter(product__in=[obj]).annotate(admin_path_prefix=Value(settings.ADMIN_PATH_PREFIX, CharField())).values_list('admin_path_prefix', 'id')
        except Exception as e:
            return ''
        else:
            if not idxs:
                return ''
            content = format_html_join('\n', '<p><font color="green" face="Verdana, Geneva, sans-serif"><a href="{0}/refs/qrcode/?id={1}" target="_blank">{1}</a></font></p>', idxs)
            return format_html('<details><summary>{}</summary>{}</details>', idxs[0][1], content)
    get_qrcodes.short_description = _('Qr Codes')

    def count(self, obj):
        SumIncome=Sum('rec__count', filter=Q(rec__doc__type__income=True), default=0)
        SumExpense=Sum('rec__count', filter=Q(rec__doc__type__income=False), default=0)
        result = get_model('core.Register').objects.filter(rec__product_id=obj.id).aggregate(count=SumIncome-SumExpense)['count']
        color = 'green' if result > 0 else 'red'
        return format_html('<p><a href="{}/core/register/?rec__product={}" target="_blank" style="color:{}">{}</a></p>', settings.ADMIN_PATH_PREFIX, obj.id, color, result)
    count.short_description = _('Count')

    def get_tax(self, obj):
        o = obj.tax
        if not o:
            return ''
        m = o._meta
        return format_html('<a href="{}?id={}" target="_blank">{}</a>', reverse(f'admin:{m.app_label}_{m.model_name}_changelist'), o.id, o.name)
    get_tax.short_description = _('Tax')
    get_tax.admin_order_field = 'tax'

    def get_model(self, obj):
        o = obj.model
        if not o:
            return ''
        m = o._meta
        return format_html('<a href="{}?id={}" target="_blank">{}</a>', reverse(f'admin:{m.app_label}_{m.model_name}_changelist'), o.id, o.name)
    get_model.short_description = _('Model')
    get_model.admin_order_field = 'model'

    def get_group(self, obj):
        o = obj.group
        if not o:
            return ''
        m = o._meta
        return format_html('<a href="{}?id={}" target="_blank">{}</a>', reverse(f'admin:{m.app_label}_{m.model_name}_changelist'), o.id, o.name)
    get_group.short_description = _('Product Group')
    get_group.admin_order_field = 'group'

    def from_xls(self, request, queryset, **kwargs):
        import xlsxwriter
        from transliterate import slugify
        from openpyxl import load_workbook
        form = None
        if 'apply' in request.POST:
            self.logi('💡', request.FILES)
            form = UploadFileForm(request.POST, request.FILES)
            if form.is_valid():
                msg_err = ''
                count_created = 0
                file = form.cleaned_data['file']
                if file:
                    units, groups, ext_attrs, products = {}, {}, {}, []
                    wb = load_workbook(file)
                    for sheetname in wb.sheetnames:
                        self.logi('💡SHEET NAME', sheetname)
                        ws = wb[sheetname]
                        list_rows = list(ws.rows)
                        prefix_cells = list_rows[0]
                        self.logi(prefix_cells)
                        row_index = 0
                        for row in list_rows[1:]:
                            row_index += 1
                            v = list(row)
                            try:
                                p_group, p_code, p_name, p_article, p_unit, p_price, p_cost, p_barcode, p_count = [i.value for i in v]
                            except Exception as e:
                                self.loge(e)
                                msg_err += f'ROW {row_index}: {e}'
                            else:
                                if Product.objects.filter(article=p_article).exists():
                                    self.logi('PRODUCT', p_article, p_name, 'EXISTS')
                                else:
                                    product_kwargs = {'article':p_article, 'name':p_name, 'cost':p_cost, 'price':p_price}
                                    if p_unit:
                                        if p_unit not in units:
                                            units[p_unit], created_unit = Unit.objects.get_or_create(name__icontains=p_unit, defaults={'label':p_unit, 'name':p_unit})
                                        product_kwargs['unit'] = units[p_unit]
                                    if p_group:
                                        if p_group not in groups:
                                            groups[p_group], created_group = ProductGroup.objects.get_or_create(name__icontains=p_group, defaults={'name':p_group})
                                        product_kwargs['group'] = groups[p_group]
                                    products.append(Product(**product_kwargs))
                                    ext_attrs[p_article] = {'barcode':f'{p_barcode}', 'count':p_count}
                    if products:
                        try:
                            objs = Product.objects.bulk_create(products)
                        except Exception as e:
                            self.loge(e)
                            msg_err = f'{e}'
                        else:
                            count_created = len(objs)
                            doc_income, income_mybe_saved = None, True
                            if count_created:
                                for o in objs:
                                    barcode = ext_attrs[o.article]['barcode']
                                    if barcode:
                                        b, created = BarCode.objects.get_or_create(id=barcode)
                                        if b:
                                            o.barcodes.add(b)
                                    p_count = ext_attrs[o.article]['count']
                                    if p_count and income_mybe_saved:
                                        if not doc_income:
                                            t, created = DocType.objects.get_or_create(alias='balance', defaults={'alias':'balance', 'name':'Balance'})
                                            doc_income = get_model('core.Doc')(type=t, author=request.user)
                                            try:
                                                doc_income.save()
                                            except Exception as e:
                                                self.loge(e)
                                                income_mybe_saved = False
                                                doc_income = None
                                        if doc_income:
                                            r = get_model('core.Record')(count=p_count, cost=o.cost, price=o.price, doc=doc_income, product=o)
                                            try:
                                                r.save()
                                            except Exception as e:
                                                self.loge(e)
                                            else:
                                                try:
                                                    get_model('core.Register')(rec=r).save()
                                                except Exception as e:
                                                    self.loge(e)
                self.message_user(request, f'🆗 {file.name} ✏️ FILE SIZE={file.size} ✏️ CREATED={count_created}; {msg_err}', messages.SUCCESS)
                return HttpResponseRedirect(request.get_full_path())
        if not form:
            form = UploadFileForm(initial={'_selected_action': request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME)})
        m = queryset.model._meta
        context = {}
        context['items'] = []
        context['form'] = form
        context['title'] = _('File')
        context['current_action'] = sys._getframe().f_code.co_name
        context['subtitle'] = 'admin_select_file_form'
        context['site_title'] = queryset.model._meta.verbose_name
        context['is_popup'] = True
        context['is_nav_sidebar_enabled'] = True
        context['site_header'] = _('Admin panel')
        context['has_permission'] = True
        context['site_url'] = reverse('admin:{}_{}_changelist'.format(m.app_label, m.model_name))
        context['available_apps'] = (m.app_label,)
        context['app_label'] = m.app_label
        return render(request, 'admin_select_file_form.html', context)
    from_xls.short_description = f'⚔{_("load from XLS file")}🔙'

admin.site.register(Product, ProductAdmin)
