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
from django.utils.html import format_html, format_html_join, html_safe
from django.utils.safestring import mark_safe
from django.urls import path, reverse
from django import forms
from django.http import StreamingHttpResponse, FileResponse, HttpResponseRedirect, JsonResponse
from django.db.models import F, Q, Min, Max, Sum, Value, Count, Case, When, CharField, DecimalField
from django.db.models.query import QuerySet
from django.db import connections
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.contrib import admin, messages
from django.contrib.admin.models import LogEntry
from django.contrib.admin.sites import AdminSite
from django.contrib.admin.views.autocomplete import AutocompleteJsonView
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.shortcuts import render
from django.views.generic.edit import FormView
from django.core.cache import caches
from django.conf import settings
from django.apps import apps as django_apps
from django.template import Context, Template

from .models import Doc, Record, Register
from users.models import User
from refs.admin import CompanyFilter, DocTypeFilter, ProductFilter, CustomerFilter

def get_model(app_model):
    app_name, model_name = app_model.split('.')
    return django_apps.get_app_config(app_name).get_model(model_name)


class DropDownFilter(admin.SimpleListFilter):
    template = 'dropdown_filter_from_memory.html'


class UploadFileForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    file = forms.FileField(widget=forms.ClearableFileInput(attrs={'allow_multiple_selected': True}))


class DocFilter(DropDownFilter):
    title = _('Document')
    parameter_name = 'doc'

    def lookups(self, request, model_admin):
        res = []
        queryset = Doc.objects.only('id', 'registered_at', 'type').select_related('type')
        for it in queryset:
            res.append((it.id, it.registered_at.strftime('%Y-%m-%d %H:%M:%S')+f' {it.type.name}'))
        return res

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(doc=self.value())


class DocRecordFilter(DocFilter):
    title = _('Document')
    parameter_name = 'rec__doc'

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(rec__doc=self.value())


class OwnerCompanyFilter(CompanyFilter):
    title = _('Owner')
    parameter_name = 'owner'

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(owner=self.value())


class ContractorCompanyFilter(CompanyFilter):
    title = _('Contractor')
    parameter_name = 'contractor'

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(contractor=self.value())


class ProductRecordFilter(ProductFilter):
    title = _('Product')
    parameter_name = 'rec__product'

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(rec__product=self.value())


class ProductDocRecFilter(ProductFilter):
    title = _('Product')
    parameter_name = 'record__product'

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        else:
            return queryset.filter(record__product=self.value())


class CoreBaseAdmin():

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

    def logd(self, *args):
        msg = f'⚠{self.__class__.__name__}.{sys._getframe().f_back.f_code.co_name}'
        for arg in args:
            msg += f'::{arg}'
        logging.debug(msg)

    def loge(self, err, *args):
        msg = f'🆘{self.__class__.__name__}.{err.__traceback__.tb_frame.f_code.co_name}'
        for arg in args:
            msg += f'::{arg}'
        msg += f'::{err}::LINE={err.__traceback__.tb_lineno}'
        logging.error(msg)

    def noselect_actions(self, request, auto_selectable_actions=[]):
        if 'action' in request.POST and request.POST['action'] in auto_selectable_actions:
            if not request.POST.getlist(ACTION_CHECKBOX_NAME):
                post = request.POST.copy()
                post.update({ACTION_CHECKBOX_NAME:'0'})
                request._set_post(post)
        return request

    def worksheet_cell_write(self, worksheet, row, col, value, type_value = None, fmt = None):
        func_write = worksheet.write
        if type_value == 'as_number':
            func_write = worksheet.write_number
        elif type_value == 'as_datetime':
            func_write = worksheet.write_datetime
        try:
            if fmt:
                func_write(row, col, value, fmt)
            else:
                func_write(row, col, value)
        except Exception as e:
            try:
                if fmt:
                    func_write(row, col, repr(value), fmt)
                else:
                    func_write(row, col, repr(value))
            except Exception as e:
                self.loge(e, row, col)
        return col + 1

    def fill_workbook(self, workbook, queryset, fields, field_names, header={}, sheet_name=''):
        worksheet = workbook.add_worksheet(sheet_name)
        cell_format_bold = workbook.add_format({'align':'center', 'valign':'vcenter', 'bold':True})
        cell_format_left = workbook.add_format({'align':'left', 'valign':'vcenter'})
        row = 0
        for column, content in header.items():
            value = content.get('value')
            if value is not None:
                cell_fmt = content.get('format')
                if cell_fmt:
                    cell_fmt = workbook.add_format(cell_fmt)
                else:
                    cell_fmt = cell_format_bold
                self.worksheet_cell_write(worksheet, row, column, value, fmt=cell_fmt)
        row += 1
        col = 0
        for field_name in field_names:
            field_title = field_name
            if field_name in fields:
                width = fields[field_name].get('width', None)
                if width is not None:
                    worksheet.set_column(col, col, width)
                field_title = fields[field_name].get('title', field_title)
            col = self.worksheet_cell_write(worksheet, row, col, _(field_title), fmt=cell_format_bold)
        row += 1
        for item in queryset:
            worksheet.set_row(row, None, cell_format_left)
            col = 0
            for field_name in field_names:
                if not hasattr(item, field_name):
                    col += 1
                    continue
                else:
                    if not field_name:
                        col += 1
                        continue
                try:
                    value = getattr(item, field_name)
                except AttributeError as e:
                    col += 1
                    self.loge(e)
                except Exception as e:
                    col += 1
                    self.loge(e)
                else:
                    if not value:
                        col += 1
                    else:
                        format_value = None
                        tvalue = None
                        if isinstance(value, datetime):
                            value = f'{value.strftime("%Y.%m.%d %H:%M:%S")}'
                        elif isinstance(value, (int, float)):
                            tvalue = 'as_number'
                        elif not isinstance(value, str):
                            value = f'{value}'
                        col = self.worksheet_cell_write(worksheet, row, col, value, tvalue, format_value)
            row += 1

    def queryset_to_xls(self, queryset, fields={}, exclude_fields=['id'], header={}, sheet_name=''):
        import xlsxwriter
        output = None
        if queryset.count():
            field_names = list(fields.keys())
            if not field_names:
                for field in queryset.model._meta.get_fields():
                    if field.name and field.name not in exclude_fields:
                        field_names.append(field.name)
            output = BytesIO()
            wbk = xlsxwriter.Workbook(output, {'in_memory': True})
            self.fill_workbook(wbk, queryset, fields, field_names, header, sheet_name)
            wbk.close()
            output.seek(0)
        return output


class CustomStackedInline(CoreBaseAdmin, admin.StackedInline):
    pass

class CustomTabularInline(CoreBaseAdmin, admin.TabularInline):
    pass

class CustomModelAdmin(CoreBaseAdmin, admin.ModelAdmin):
    pass


class RecordAdmin(CustomModelAdmin):
    user = None
    list_display = ['id', 'get_doc', 'product', 'get_price', 'get_count', 'get_sum_price', 'extinfo']
    list_display_links = ('id',)
    search_fields = ('id', 'doc__owner__name', 'doc__contractor__name', 'doc__type__name', 'doc__tax__name', 'doc__sale_point__name', 'doc__author__username', 'extinfo')
    list_select_related = ('product', 'doc')
    autocomplete_fields = ('product', 'doc')
    list_filter = (ProductFilter, DocFilter, 'doc__type')
    list_editable = ['product']

    def check_cost_permission(self):
        if self.user.is_superuser:
            return True
        model_name = self.__class__.__name__.replace('Admin', '')
        if get_model('users.RoleField').objects.filter(role=self.user.role, role_model__app='core', role_model__model=model_name, read=True, value='cost').exists():
            return True
        return False

    def changelist_view(self, request, extra_context=None):
        self.user = request.user
        if settings.DEBUG:
            self.logd('CURRENT USER', self.user)
        if self.check_cost_permission():
            if 'get_cost' not in self.list_display:
                self.list_display.insert(self.list_display.index('get_price'), 'get_cost')
            if 'get_sum_cost' not in self.list_display:
                self.list_display.insert(self.list_display.index('get_sum_price'), 'get_sum_cost')
        else:
            if 'get_cost' in self.list_display:
                self.list_display.remove('get_cost')
            if 'get_sum_cost' in self.list_display:
                self.list_display.remove('get_sum_cost')
        #request = self.noselect_actions(request, [])
        return super().changelist_view(request, extra_context)

    def get_form(self, request, obj=None, **kwargs):
        self.user = request.user
        if settings.DEBUG:
            self.logd('CURRENT USER', self.user)
        if self.check_cost_permission():
            if self.exclude:
                self.exclude = ()
        else:
            self.exclude = ('cost', 'get_cost')
        form = super().get_form(request, obj, **kwargs)
        form.current_user = self.user
        return form

    def get_doc(self, obj):
        return format_html('<a href="{}/core/doc/?id={}" target="_blank">[{}] {} {}</a>', settings.ADMIN_PATH_PREFIX, obj.doc.id, obj.doc.id, obj.doc.type.name, obj.doc.registered_at.strftime('%Y-%m-%d %H:%M'))
    get_doc.short_description = _('document')

    def product(self, obj):
        return format_html('<a href="{}/refs/product/?id={}" target="_blank">{}</a>', settings.ADMIN_PATH_PREFIX, obj.product.id, obj.product.name)
    product.short_description = _('product')

    def get_count(self, obj):
        color = 'green' if obj.doc.type.income==True else 'red'
        return format_html('<font color="{}" face="Verdana, Geneva, sans-serif">{}</font>', color, obj.count)
    get_count.short_description = _('count')
    get_count.admin_order_field = 'count'

    def get_cost(self, obj):
        if self.check_cost_permission():
            return format_html('<font color="green" face="Verdana, Geneva, sans-serif">{} {}</font>', obj.cost.quantize(Decimal('0.00')), obj.currency.name if obj.currency else '')
        return ''
    get_cost.short_description = _('cost')
    get_cost.admin_order_field = 'cost'

    def get_price(self, obj):
        return format_html('<font color="green" face="Verdana, Geneva, sans-serif">{} {}</font>', obj.price.quantize(Decimal('0.00')), obj.currency.name if obj.currency else '')
    get_price.short_description = _('price')
    get_price.admin_order_field = 'price'

    def get_sum_cost(self, obj):
        if self.check_cost_permission():
            return format_html('<font color="green" face="Verdana, Geneva, sans-serif">{} {}</font>', (obj.cost*obj.count).quantize(Decimal('0.00')), obj.currency.name if obj.currency else '')
        return ''
    get_sum_cost.short_description = _('sum cost')

    def get_sum_price(self, obj):
        return format_html('<font color="green" face="Verdana, Geneva, sans-serif">{} {}</font>', (obj.price*obj.count).quantize(Decimal('0.00')), obj.currency.name if obj.currency else '')
    get_sum_price.short_description = _('sum price')

admin.site.register(Record, RecordAdmin)


class RegisterAdmin(CustomModelAdmin):
    list_display = ['id', 'rec', 'get_doc', 'get_product', 'get_price', 'get_count', 'get_sum_price']
    list_display_links = ['id']
    search_fields = ('id', 'rec__doc__owner__name', 'rec__doc__contractor__name', 'rec__doc__type__name')
    list_filter = (ProductRecordFilter, DocRecordFilter, 'rec__doc__type')
    list_editable = ['rec']
    autocomplete_fields = ['rec']

    def check_cost_permission(self):
        if self.user.is_superuser:
            return True
        if get_model('users.RoleField').objects.filter(role=self.user.role, role_model__app='core', role_model__model='Record', read=True, value='cost').exists():
            return True
        return False

    def changelist_view(self, request, extra_context=None):
        self.user = request.user
        if settings.DEBUG:
            self.logd('CURRENT USER', self.user)
        if self.check_cost_permission():
            if 'get_cost' not in self.list_display:
                self.list_display.insert(self.list_display.index('get_price'), 'get_cost')
            if 'get_sum_cost' not in self.list_display:
                self.list_display.insert(self.list_display.index('get_sum_price'), 'get_sum_cost')
        else:
            if 'get_cost' in self.list_display:
                self.list_display.remove('get_cost')
            if 'get_sum_cost' in self.list_display:
                self.list_display.remove('get_sum_cost')
        #request = self.noselect_actions(request, [])
        return super().changelist_view(request, extra_context)

    def rec(self, obj):
        return format_html('<a href="{}/core/record/?id={}" target="_blank">R{}</a>', settings.ADMIN_PATH_PREFIX, obj.rec.id, obj.rec.id)
    rec.short_description = _('record')

    def get_doc(self, obj):
        return format_html('<a href="{}/core/doc/?id={}" target="_blank">[{}] {} {}</a>', settings.ADMIN_PATH_PREFIX, obj.rec.doc.id, obj.rec.doc.id, obj.rec.doc.type.name, obj.rec.doc.registered_at.strftime('%Y-%m-%d %H:%M'))
    get_doc.short_description = _('document')

    def get_product(self, obj):
        return format_html('<a href="{}/refs/product/?id={}" target="_blank">{}</a>', settings.ADMIN_PATH_PREFIX, obj.rec.product.id, obj.rec.product.name)
    get_product.short_description = _('product')

    def get_count(self, obj):
        color = 'green' if obj.rec.doc.type.income==True else 'red'
        return format_html('<font color="{}" face="Verdana, Geneva, sans-serif">{}</font>', color, obj.rec.count)
    get_count.short_description = _('count')

    def get_cost(self, obj):
        return format_html('<font color="green" face="Verdana, Geneva, sans-serif">{} {}</font>', obj.rec.cost.quantize(Decimal('0.00')), obj.rec.currency.name if obj.rec.currency else '')
    get_cost.short_description = _('cost')

    def get_price(self, obj):
        return format_html('<font color="green" face="Verdana, Geneva, sans-serif">{} {}</font>', obj.rec.price.quantize(Decimal('0.00')), obj.rec.currency.name if obj.rec.currency else '')
    get_price.short_description = _('price')

    def get_sum_cost(self, obj):
        return format_html('<font color="green" face="Verdana, Geneva, sans-serif">{} {}</font>', (obj.rec.cost*obj.rec.count).quantize(Decimal('0.00')), obj.rec.currency.name if obj.rec.currency else '')
    get_sum_cost.short_description = _('sum cost')

    def get_sum_price(self, obj):
        return format_html('<font color="green" face="Verdana, Geneva, sans-serif">{} {}</font>', (obj.rec.price*obj.rec.count).quantize(Decimal('0.00')), obj.rec.currency.name if obj.rec.currency else '')
    get_sum_price.short_description = _('sum price')

admin.site.register(Register, RegisterAdmin)


@html_safe
class JSProductRelationsSet:
    def __str__(self):
        set_cost_code = 'elem_cost.val(evt.params.data.cost);'
        if settings.ADMIN_SET_DOCUMENT_RECORD_PRICES.get('check_empty_cost', False):
            set_cost_code = f'if(!elem_cost.val() || elem_cost.val()==0) {set_cost_code}'
        set_price_code = 'elem_price.val(evt.params.data.price);'
        if settings.ADMIN_SET_DOCUMENT_RECORD_PRICES.get('check_empty_price', False):
            set_price_code = f'if(!elem_price.val() || elem_price.val()==0) {set_price_code}'
        return r'''<script>'use strict';
window.onload = (event) => {
const $ = django.jQuery;
const field_product = $('div[data-model-ref="product"]');
field_product.on('select2:close', function(evt) {
    field_product.trigger('change.select2');
});
field_product.on('select2:select', function(evt) {
    if(evt.params.data){
        const row_id = evt.target.id.replace(/\D/g, "");
        const elem_count = $('#id_record_set-'+row_id+'-count');
        elem_count.val(function(i, oldval){return parseFloat(oldval)+1;});
        if("cost" in evt.params.data){
            const elem_cost = $('#id_record_set-'+row_id+'-cost');
            ''' + set_cost_code + '''
        }
        if("price" in evt.params.data){
            const elem_price = $('#id_record_set-'+row_id+'-price');
            ''' + set_price_code + '''
        }
        const elem_product = $('#record_set-'+row_id).find('.field-product');
        if(elem_product.length){
            const div_product = elem_product.find('div');
            if("count" in evt.params.data){
                elem_count.attr('title', 'remaining count = '+evt.params.data.count);
                const elem_remaining_count = elem_product.find('#remaining-count-'+row_id);
                if(elem_remaining_count.length){
                    elem_remaining_count.html(evt.params.data.count);
                } else {
                    const new_elem_remaining_count = $('<span id="remaining-count-'+row_id+'">'+evt.params.data.count+'</span>');
                    if(div_product.length){
                        div_product.css('margin-bottom','0');
                        div_product.append(new_elem_remaining_count);
                    } else {
                        elem_product.append(new_elem_remaining_count);
                    }
                }
            }
            if("unit" in evt.params.data){
                const elem_product_unit = elem_product.find('#product-unit-'+row_id);
                if(elem_product_unit.length){
                    elem_product_unit.html(evt.params.data.unit);
                } else {
                    const new_elem_product_unit = $('<span id="product-unit-'+row_id+'">'+evt.params.data.unit+'</span>');
                    if(div_product.length){
                        div_product.append(new_elem_product_unit);
                    } else {
                        elem_product.append(new_elem_product_unit);
                    }
                }
            }
        }
        ''' + settings.BEHAVIOR_COUNT.get('select_focus', '') + r'''
    }
});
field_product.on('select2:clear', function(evt) {
    const row_id = evt.target.id.replace(/\D/g, "");
    $('#id_record_set-'+row_id+'-count').val();
    $('#id_record_set-'+row_id+'-cost').val();
    $('#id_record_set-'+row_id+'-price').val();
});
}</script>'''


class ProductAutocompleteJsonView(CoreBaseAdmin, AutocompleteJsonView):
    def serialize_result(self, obj, to_field_name):
        ext_data = {}
        last_reg = None
        if settings.BEHAVIOR_COST.get('select_from_register', False):
            last_reg = Register.objects.filter(rec__product_id=obj.id).order_by('-rec__doc__registered_at').select_related('rec').first()
            if last_reg:
                ext_data['cost'] = last_reg.rec.cost
        elif obj.cost:
            ext_data['cost'] = obj.cost
        if settings.BEHAVIOR_PRICE.get('select_from_register', False):
            if not last_reg:
                last_reg = Register.objects.filter(rec__product_id=obj.id).order_by('-rec__doc__registered_at').select_related('rec').first()
            if last_reg:
                ext_data['price'] = last_reg.rec.price
        elif obj.price:
            ext_data['price'] = obj.price
        if settings.BEHAVIOR_COUNT.get('select_from_register', False):
            SumIncome=Sum('rec__count', filter=Q(rec__doc__type__income=True), default=0)
            SumExpense=Sum('rec__count', filter=Q(rec__doc__type__income=False), default=0)
            try:
                ext_data['count'] = get_model('core.Register').objects.filter(rec__product_id=obj.id).aggregate(count=SumIncome-SumExpense)['count']
            except Exception as e:
                self.loge(e)
        if obj.unit:
            ext_data['unit'] = obj.unit.label
        result = super().serialize_result(obj, to_field_name)
        if ext_data:
            result |= ext_data
        return result


def autocomplete_view(request):
    if request.GET['model_name'] == 'record':
        #print(request.environ.keys())
        return ProductAutocompleteJsonView.as_view(admin_site=admin.site)(request)
    return AutocompleteJsonView.as_view(admin_site=admin.site)(request)
admin.site.autocomplete_view = autocomplete_view


class RecordInlines(CustomTabularInline):
    model = Record
    fields = ['product', 'count', 'price']
    list_select_related = ('product',)
    autocomplete_fields = ('product',)
    extra = 0


class DocAdmin(CustomModelAdmin):
    user = None
    date_hierarchy = 'registered_at'
    list_display = ['id', 'get_reg', 'created_at', 'registered_at', 'type', 'contractor', 'customer', 'get_records', 'get_sum_price', 'sum_final', 'tax', 'owner', 'author', 'extinfo']
    list_display_links = ('id', 'created_at', 'registered_at')
    search_fields = ('id', 'created_at', 'registered_at', 'owner__name', 'contractor__name', 'type__name', 'tax__name', 'sale_point__name', 'author__username', 'extinfo')
    list_filter = ('registered_at', 'created_at', DocTypeFilter, ContractorCompanyFilter, OwnerCompanyFilter, ProductDocRecFilter, CustomerFilter)
    actions = ('new_incoming_from_orders', 'registration', 'unregistration', 'recalculate_final_sum', 'order_to_xls', 'sales_receipt_to_printer', 'earnings')
    fieldsets = [
    (
        None,
        {'fields': [('registered_at', 'sum_final', 'owner', 'contractor', 'customer', 'type', 'tax')]}
    ),
    (
        'Advanced options',
        {
            'classes': ['collapse'],
            'fields': ['extinfo']
        }
    )
    ]
    inlines = [RecordInlines]
    list_editable = ['type']
    autocomplete_fields = ['type']

    #formfield_overrides = {CharField: {'widget': forms.Select(attrs={'size': '20'})}}

    class Media:
        #extend = False
        js = (JSProductRelationsSet(),)

    def formfield_for_dbfield(self, db_field, **kwargs):
        field = super().formfield_for_dbfield(db_field, **kwargs)
        if db_field.name == 'type':
            field.widget.attrs['style'] = 'width: 10em;'
        return field

    def get_queryset(self, request):
        self.user = request.user
        if settings.DEBUG:
            self.logd('CURRENT USER', self.user)
        queryset = super().get_queryset(request)
        if self.user.is_superuser:
            return queryset
        return queryset.filter(author=self.user)

    def check_cost_permission(self):
        if self.user.is_superuser:
            return True
        if get_model('users.RoleField').objects.filter(role=self.user.role, role_model__app='core', role_model__model='Record', read=True, value='cost').exists():
            return True
        return False

    def changelist_view(self, request, extra_context=None):
        self.user = request.user
        if settings.DEBUG:
            self.logd('CURRENT USER', self.user)
        if self.check_cost_permission():
            if 'get_sum_cost' not in self.list_display:
                self.list_display.insert(self.list_display.index('get_sum_price'), 'get_sum_cost')
        else:
            if 'get_sum_cost' in self.list_display:
                self.list_display.remove('get_sum_cost')
        request = self.noselect_actions(request, ['earnings'])
        return super().changelist_view(request, extra_context)

    def get_form(self, request, obj, **kwargs):
        self.user = request.user
        if settings.DEBUG:
            self.logd('CURRENT USER', self.user)
        if self.check_cost_permission():
            if 'cost' not in self.inlines[0].fields:
                self.inlines[0].fields.insert(self.inlines[0].fields.index('price'), 'cost')
        elif 'cost' in self.inlines[0].fields:
            self.inlines[0].fields.remove('cost')
        # form = super().get_form(request, obj, **kwargs)
        # form.base_fields['type'].widget.attrs['style'] = 'width: 10em;'
        # return form
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, instance, form, change):
        current_user = request.user
        instance = form.save(commit=False)
        if not change or not instance.author:
            instance.author = current_user
        instance.save()
        form.save_m2m()
        return instance

    def get_records(self, obj):
        try:
            idxs = Record.objects.filter(doc=obj).annotate(admin_path_prefix=Value(settings.ADMIN_PATH_PREFIX, CharField())).values_list('admin_path_prefix', 'product_id', 'product__name')
        except Exception as e:
            self.loge(e)
            return ''
        else:
            if not idxs:
                return ''
            content = format_html_join('\n', '<p><font color="green" face="Verdana, Geneva, sans-serif"><a href="{0}/refs/product/?id={1}" target="_blank">{2}</a></font></p>', idxs)
            return format_html('<details><summary>{}</summary>{}</details>', idxs[0][2], content)
    get_records.short_description = _('Products')

    def get_sum_cost(self, obj):
        full_sum = 0
        try:
            full_sum = Record.objects.filter(doc=obj).aggregate(full_sum=Sum(F('count')*F('cost')))['full_sum']
        except Exception as e:
            self.loge(e)
        else:
            if full_sum:
                full_sum = full_sum.quantize(Decimal('0.00'))
            else:
                full_sum = 0
        return format_html('<font color="green" face="Verdana, Geneva, sans-serif">{}</font>', full_sum)
    get_sum_cost.short_description = _('sum cost')

    def get_sum_price(self, obj):
        full_sum = 0
        try:
            full_sum = Record.objects.filter(doc=obj).aggregate(full_sum=Sum(F('count')*F('price')))['full_sum']
        except Exception as e:
            self.loge(e)
        else:
            if full_sum:
                full_sum = full_sum.quantize(Decimal('0.00'))
            else:
                full_sum = 0
        return format_html('<font color="green" face="Verdana, Geneva, sans-serif">{}</font>', full_sum)
    get_sum_price.short_description = _('sum price')

    def get_reg(self, obj):
        return Register.objects.filter(rec__doc=obj).exists()
    get_reg.short_description = '☑'
    get_reg.help_text = _('registered')
    get_reg.boolean = True

    def registration(self, request, queryset):
        updated_count = 0
        for it in queryset.filter(type_id__in=get_model('refs.DocType').objects.filter(auto_register=True).values('id')):
            all_reg = False
            for r in Record.objects.filter(doc=it):
                if not Register.objects.filter(rec=r).exists():
                    try:
                        obj, created = Register.objects.get_or_create(rec=r)
                    except Exception as e:
                        self.loge(e)
                        break
                    else:
                        all_reg = True
            if all_reg:
                updated_count += 1
        self.message_user(request, f'{_("updated")} {updated_count} ☑', messages.SUCCESS)
    registration.short_description = f'✅ {_("registration for accaunting")} 👌'

    def unregistration(self, request, queryset):
        updated_count = 0
        for it in queryset.filter(type_id__in=get_model('refs.DocType').objects.filter(auto_register=True).values('id')):
            records_queryset = Record.objects.filter(doc=it)
            count_delete, del_refs = Register.objects.filter(rec__in=records_queryset.values_list('id', flat=True)).delete()
            if records_queryset.count() == count_delete:
                updated_count += 1
        self.message_user(request, f'{_("updated")} {updated_count} ☑', messages.SUCCESS)
    unregistration.short_description = f'❌ {_("cancel registration")} 👌'

    def recalculate_final_sum(self, request, queryset):
        updated_count = 0
        docs = []
        for it in queryset:
            value = None
            if it.type.income:
                value = Record.objects.filter(doc=it).aggregate(sum_final=Sum(F('count') * F('cost')))['sum_final']
            else:
                value = Record.objects.filter(doc=it).aggregate(sum_final=Sum(F('count') * F('price')))['sum_final']
            if value is not None and it.sum_final != value:
                it.sum_final = value
                docs.append(it)
        if docs:
            try:
                updated_count = Doc.objects.bulk_update(docs, ['sum_final'])
            except Exception as e:
                self.loge(e)
        self.message_user(request, f'{_("updated")} {updated_count}', messages.SUCCESS)
    recalculate_final_sum.short_description = f'🖩 {_("recalculate final sum")} 🖩'

    def order_to_xls(self, request, queryset):
        import xlsxwriter
        if not queryset.count():
            self.message_user(request, _('please select items'), messages.ERROR)
            return

        rcount = Record.objects.filter(doc_id__in=queryset.filter(type__alias='order').values('id')).distinct().count()
        if not rcount:
            self.message_user(request, f'🆗 {_("Finished")}. {_("Documents is empy")}.', messages.SUCCESS)
            return

        ts = django_timezone.now().strftime('%Y%m%d%H%M%S')
        output = BytesIO()
        wbk = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = wbk.add_worksheet(ts)
        cell_format_center_bold = wbk.add_format({'align':'center', 'valign':'vcenter', 'bold':True})
        cell_format_left = wbk.add_format({'align':'left', 'valign':'vcenter'})
        cell_format_left_bold = wbk.add_format({'align':'left', 'valign':'vcenter', 'bold':True, 'bg_color':'#FFFFAA'})
        cell_format_right = wbk.add_format({'align':'right', 'valign':'vcenter'})
        worksheet.set_column(1, 1, 50)
        worksheet.set_column(2, 2, 20)
        row = 0
        col = 0
        col = self.worksheet_cell_write(worksheet, row, col, _('code'), fmt=cell_format_center_bold)
        col = self.worksheet_cell_write(worksheet, row, col, _('name'), fmt=cell_format_center_bold)
        col = self.worksheet_cell_write(worksheet, row, col, _('count'), fmt=cell_format_center_bold)
        row += 1
        for d in queryset:
            row += 2
            dinfo = f'{d.contractor.name} ([{d.type.name} {d.id}] {d.registered_at.strftime('%Y-%m-%d %H:%M:%S')})'
            worksheet.merge_range(f'A{row}:C{row}', dinfo, cell_format_left_bold)
            records = Record.objects.filter(doc=d)
            for r in records:
                fields = {'product':{'width':50}, 'count':{'width':20}}
                col = 0
                col = self.worksheet_cell_write(worksheet, row, col, r.product.id, fmt=cell_format_left)
                col = self.worksheet_cell_write(worksheet, row, col, r.product.name, fmt=cell_format_left)
                col = self.worksheet_cell_write(worksheet, row, col, r.count, fmt=cell_format_right)
                row += 1
        wbk.close()
        output.seek(0)
        fn = f'orders_{ts}.xlsx'
        self.message_user(request, f'🆗 {_("Finished")} ✏️({fn}); {_("unloaded")} {rcount}', messages.SUCCESS)
        return FileResponse(output, as_attachment=True, filename=fn)
    order_to_xls.short_description = f'⚔📋 {_("order to XLS file")} 📋↘'

    def sales_receipt_to_printer(self, request, queryset):
        import re
        docs = ''
        m = None
        templates = {}
        css_media_style = ''
        script = ''
        for it in queryset.filter(Q(type__alias='expense') | Q(type__alias='sale')):
            if not m:
                m = it.type._meta
            als = f'{m.app_label}.{m.model_name}.{it.type.alias}'
            template = templates.get(als)
            if not template:
                template = get_model('refs.PrintTemplates').objects.filter(alias=als).first()
                templates[als] = template
            if template:
                if not css_media_style and 'css_media_style' in template.extinfo:
                    css_media_style = template.extinfo['css_media_style']
                if not script and 'script' in template.extinfo:
                    script = template.extinfo['script']
                records = Record.objects.filter(doc=it).select_related('product')#.annotate(sum=Value(F('count')*F('price'), DecimalField()))
                content = Template(template.content).render(Context({'doc':it, 'request':request, 'records':records}))
                docs += content
        if not css_media_style:
            css_media_style = '@media(orientation:portrait) print{html body{width:210mm;height:297mm;visibility:hidden;height:auto;margin:0;padding:0;}} @page{size:A4;margin:0;}'
        docs = f'<div id="section-to-print"><style>{css_media_style}</style>' + re.sub('(<!--.*?-->)', '', docs, flags=re.DOTALL) + f'</div>{script}'
        self.message_user(request, mark_safe(docs), messages.SUCCESS)
    sales_receipt_to_printer.short_description = f'🖶 {_("print sales receipt")} 🖶'

    def new_incoming_from_orders(self, request, queryset):
        queryset = queryset.filter(type__alias='order')
        if not queryset.count():
            self.message_user(request, _('please select items'), messages.ERROR)
            return
        records = Record.objects.filter(doc_id__in=queryset.values('id')).distinct()
        d, count_records = None, 0
        if records.count():
            company_owner = request.user.default_company
            if not company_owner:
                company_owner = get_model('refs.Company').objects.order_by('id').first()
            d = Doc(contractor=queryset.first().contractor, owner=company_owner, type=get_model('refs.DocType').objects.filter(alias='receipt').first(), author=request.user)
            try:
                d.save()
            except Exception as e:
                self.loge(e)
            else:
                new_recs = {}
                for r in records:
                    if r.product.id not in new_recs:
                        new_recs[r.product.id] = Record(doc=d, product=r.product, count=r.count, cost=r.product.cost, price=r.product.price)
                    else:
                        new_recs[r.product.id].count += r.count
                try:
                    objs = Record.objects.bulk_create(new_recs.values())
                except Exception as e:
                    self.loge(e)
                else:
                    count_records = len(objs)
                    regs = []
                    for o in objs:
                        regs.append(Register(rec=o))
                        d.sum_final += o.count * o.cost
                    try:
                        d.save(update_fields=['sum_final'])
                    except Exception as e:
                        self.loge(e)
                    if regs:
                        try:
                            rgs = Register.objects.bulk_create(regs)
                        except Exception as e:
                            self.loge(e)
        self.message_user(request, f'{_("created document")} {d.id if d else 0}; {_("count records")} {count_records}', messages.SUCCESS)
    new_incoming_from_orders.short_description = f'🪄 {_("new incoming from orders")} ✨'

    def earnings(self, request, queryset):
        docs = Doc.objects
        if queryset.count():
            docs = queryset
        data = docs.aggregate(
            sum_expense = Sum(Case(When(type__income=True, then=F('sum_final')),
                                  default=0, output_field=DecimalField())),
            sum_selling = Sum(Case(When(type__income=False, then=F('sum_final')),
                                  default=0, output_field=DecimalField()))
        )
        msg = f'{_("expense")} = {data["sum_expense"]:.2f}'
        msg += f'; {_("selling")} = {data["sum_selling"]:.2f}'
        msg += f'; {_("earnings")} = {data["sum_selling"]-data["sum_expense"]:.2f}'
        self.message_user(request, mark_safe(msg), messages.SUCCESS)
    earnings.short_description = f'💰 {_("earnings")} 💰'

admin.site.register(Doc, DocAdmin)
