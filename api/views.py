import json, logging, locale, re, sys

from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import ListView, DetailView
from django.core.serializers import serialize#, JSONSerializer
from django.core.serializers.json import DjangoJSONEncoder
#from django.core.signing import Signer
from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY, authenticate, login
from django.contrib.auth.decorators import login_required, login_not_required
from django.views.decorators.csrf import csrf_exempt, csrf_protect, requires_csrf_token, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.core.paginator import EmptyPage, Paginator
from django.conf import settings
from django.db.models import F, Q, Sum
from django.utils.dateparse import parse_datetime
from django.shortcuts import get_object_or_404
from django.template import Context, Template

from users.models import User, RoleField
from refs.models import Company, Customer, DocType, Product, PrintTemplates
from core.models import Doc, Record, Register


@csrf_exempt
@login_not_required
@require_http_methods(['POST'])
def url_login(request):
    if request.method == 'POST':
        if request.session.test_cookie_worked() or True:
            try:
                request.session.delete_test_cookie()
            except Exception as e:
                if settings.DEBUG:
                    logging.debug(e)
                request.session.set_test_cookie()
            try:
                data = json.loads(request.body)
            except (json.decoder.JSONDecodeError, Exception) as e:
                logging.error(e)
                return JsonResponse({'result':'error: unknown data'}, status=400)
            exclude_flds = ['id', 'username', 'password']
            user_name = data.get('username', '')
            user_password = data.get('password', '')
            user = authenticate(request, username=user_name, password=user_password)
            if user:
                login(request, user)
                return JsonResponse({'result':'success', 'user':user.to_dict(exclude_flds)})
            else:
                try:
                    u = User.objects.get(username=user_name)
                except Exception as e:
                    logging.error(f'{e}; user_name={user_name}')
                    return JsonResponse({'result':'error', 'description': f'{user_name} not found'}, status=404)
                else:
                    if u and u.check_password(user_password):
                        request.session[SESSION_KEY] = f'{u.id}'
                        request.session[BACKEND_SESSION_KEY] = settings.AUTHENTICATION_BACKENDS[0]
                        request.session[HASH_SESSION_KEY] = u.get_session_auth_hash()
                        #request.session[HASH_SESSION_KEY] = Signer().sign_object(data)
                        return JsonResponse({'result':'success', 'user':user.to_dict(exclude_flds)})
            return JsonResponse({'result':"error: Your username and password didn't match."}, status=403)
        else:
            return JsonResponse({'result':'error: Please enable cookies and try again.'}, status=401)
    request.session.set_test_cookie()
    return JsonResponse({'result':'error: only POST supported'}, status=400)

@csrf_exempt
@require_http_methods(['POST'])
def url_logout(request):
    try:
        del request.session[HASH_SESSION_KEY]
    except KeyError as e:
        logging.error(f'{e}')
    return JsonResponse({'success':"You're logged out."})


class LogMixin():
    logging.disable(logging.NOTSET)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    def logi(self, *args):
        msg = f'ℹ{self.__class__.__name__}.{sys._getframe().f_back.f_code.co_name}'
        for arg in args:
            msg += f'::{arg}'
        self.logger.info(msg)

    def logw(self, *args):
        msg = f'⚠{self.__class__.__name__}.{sys._getframe().f_back.f_code.co_name}'
        for arg in args:
            msg += f'::{arg}'
        self.logger.warning(msg)

    def logd(self, *args):
        msg = f'‼{self.__class__.__name__}.{sys._getframe().f_back.f_code.co_name}'
        for arg in args:
            msg += f'::{arg}'
        self.logger.debug(msg)

    def loge(self, err, *args):
        msg = f'🆘{self.__class__.__name__}.{err.__traceback__.tb_frame.f_code.co_name}::{err}::LINE={err.__traceback__.tb_lineno}'
        for arg in args:
            msg += f'::{arg}'
        self.logger.error(msg)


class ProductView(DetailView, LogMixin):
    model = Product

    def get_obj_or_404(self, *args, **kwargs):
        obj = None
        try:
            obj = self.model.objects.get(**kwargs)
        except self.model.DoesNotExist as e:
            self.logw(e)
        except Exception as e:
            self.loge(e)
        return obj

    def get_obj_count(self, instance):
        SumIncome=Sum('rec__count', filter=Q(rec__doc__type__income=True), default=0)
        SumExpense=Sum('rec__count', filter=Q(rec__doc__type__income=False), default=0)
        try:
            count = Register.objects.filter(rec__product_id=instance.id).aggregate(count=SumIncome-SumExpense)['count']
        except Exception as e:
            self.loge(e)
        else:
            return count
        return 0

    @method_decorator([ensure_csrf_cookie])
    def get(self, request, *args, **kwargs):
        if settings.DEBUG:
            self.logd(request.user)
        if not request.user:
            return JsonResponse({'error':'USER NOT FOUND'}, status=401)
        u = request.user
        if not u.role:
            return JsonResponse({'error':'USER ROLE NOT ACCESSIBLE'}, status=403)
        obj = self.get_obj_or_404(**kwargs)
        if obj:
            role_fields = tuple(RoleField.objects.filter(role=u.role, role_model__app='refs', role_model__model=obj.__class__.__name__, read=True).values_list('value', flat=True))
            data = serialize('json', [obj], fields=role_fields)
            return JsonResponse(data, safe=False, headers={'count':self.get_obj_count(obj)})
        return JsonResponse({'error':'NOT FOUND'}, status=404)

    @method_decorator([ensure_csrf_cookie])
    def head(self, *args, **kwargs):
        count = 0
        obj = self.get_obj_or_404(**kwargs)
        if obj:
            count = self.get_obj_count(obj)
        response = JsonResponse({'status':'success'}, headers={'count': count})
        return response


class PaginatedView(View, LogMixin):
    limit_default = 10
    page_num_default = 1

    def serialize_handler(self, data, field_names='__all__'):
        return serialize('json', data, fields=field_names)

    def paginate(self, data, limit, page_num):
        json_data, http_status = '{}', 200
        paginator = Paginator(data, limit)
        try:
            paginated_data = paginator.page(page_num)
        except EmptyPage as e:
            http_status = 400
            self.logw(e, 'limit', limit, 'page_num', page_num)
            json_data = f'{{"error":"{e}"}}'
        except Exception as e:
            http_status = 400
            self.loge(e, type(e), 'limit', limit, 'page_num', page_num)
            json_data = f'{{"error":"{e}"}}'
        else:
            if settings.DEBUG:
                self.logd(paginated_data.object_list)
            json_data = self.serialize_handler(paginated_data, self.fields)
        return paginator, json_data, http_status

    @method_decorator([ensure_csrf_cookie])
    def get(self, request, *args, **kwargs):
        if settings.DEBUG:
            self.logd('REQUEST.GET', request.GET)
        request.GET._mutable = True
        page_num = int(request.GET.pop('page', [self.page_num_default])[0])
        limit = int(request.GET.pop('limit', [self.limit_default])[0])
        if request.GET:
            filters = {}
            for k, v in request.GET.items():
                if isinstance(v, list):
                    if '__in' in k:
                        v = tuple(v)
                    elif len(v) == 1:
                        v = v[0]
                filters[k] = v
            self.queryset = self.queryset.filter(**filters)
        paginator, json_data, http_status = self.paginate(self.queryset, limit, page_num)
        if settings.DEBUG:
            self.logd('JSON_DATA', json_data)
        rsp_hdrs = {'count':paginator.count, 'num_pages':paginator.num_pages, 'page_min':paginator.page_range.start, 'page_max':paginator.page_range.stop, 'page':page_num, 'limit':limit}
        response = JsonResponse(json_data, safe=False, status=http_status, headers=rsp_hdrs)
        return response


class ProductsView(PaginatedView):
    model = Product
    queryset = model.objects.all()
    fields = ('id', 'article', 'name', 'cost', 'price', 'barcodes', 'currency')


class ProductsCashView(ProductsView):
    queryset = Product.objects.prefetch_related('currency', 'barcodes', 'qrcodes', 'group', 'unit')

    def serialize_handler(self, data, field_names='__all__'):
        list_data = []
        for it in data:
            grp = ''
            if it.group:
                grp = {'id':it.group.id, 'name':it.group.name}
            unit = ''
            if it.unit:
                unit = {'id':it.unit.id, 'label':it.unit.label}
            currency = ''
            if it.currency:
                currency = {'id':it.currency.id, 'name':it.currency.name}
            list_data.append({'id':it.id, 'article':it.article, 'name':it.name, 'cost':0.0, 'price':it.price, 'barcodes':list(it.barcodes.values_list('id', flat=True)), 'qrcodes':list(it.qrcodes.values_list('id', flat=True)), 'currency':currency, 'grp':grp, 'unit':unit})
        return json.dumps(list_data, cls=DjangoJSONEncoder)


class DocView(DetailView, LogMixin):
    context_object_name = 'doc'
    queryset = Doc.objects.none()

    @method_decorator([ensure_csrf_cookie])
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['doc_list'] = Doc.objects.all()
        return context

    @method_decorator([ensure_csrf_cookie])
    def get(self, request, *args, **kwargs):
        data = serialize('json', self.queryset)
        return JsonResponse(data, safe=False)


class DocCashAddView(View, LogMixin):
    context_object_name = 'doc-cash'

    @method_decorator([ensure_csrf_cookie])
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except json.decoder.JSONDecodeError as e:
            self.loge(e)
            return JsonResponse({'result':f'error: {e}'}, status=400)
        except Exception as e:
            self.loge(e)
            return JsonResponse({'result':f'error: {e}'}, status=500)
        sum_final = data.get('sum_final', None)
        records = data.get('records', [])
        registered_at = data.get('registered_at', '')
        if sum_final is not None and records and registered_at:
            id_owner = data.get('owner', request.user.default_company.id if request.user.default_company else 1)
            default_contractor = Company.objects.filter(extinfo__default_cash_contractor=True).first()
            if not default_contractor and request.user.companies.count():
                default_contractor = request.user.companies.first()
            id_contractor = data.get('contractor', default_contractor.id if default_contractor else 2)
            dtype = data.get('type', 'sale')
            doc_type, created = DocType.objects.get_or_create(alias=dtype, defaults={'alias':dtype, 'name':dtype.title()})
            doc = Doc(type=doc_type, registered_at=parse_datetime(registered_at), owner_id=id_owner, contractor_id=id_contractor, author=request.user, sum_final=sum_final)
            id_customer = data.get('customer', None)
            if id_customer:
                doc.customer_id = id_customer
            recs = []
            for r in records:
                try:
                    p = Product.objects.get(pk=r['product'])
                except Exception as e:
                    self.loge(e, r)
                    return JsonResponse({'result':f'error; {r}; {e}'}, status=500)
                else:
                    recs.append(Record(count=r['count'], cost=p.cost, price=r['price'], doc=doc, currency=p.currency, product=p))
            if recs:
                try:
                    doc.save()
                except Exception as e:
                    self.loge(e)
                    return JsonResponse({'result':f'error: {e}'}, status=500)
                else:
                    try:
                        obj_recs = Record.objects.bulk_create(recs)
                    except Exception as e:
                        self.loge(e, doc, recs)
                    else:
                        if settings.DEBUG:
                            self.logd(obj_recs)
                        if doc_type.auto_register and obj_recs:
                            regs = []
                            for obj in obj_recs:
                                regs.append(Register(rec=obj))
                            try:
                                obj_regs = Register.objects.bulk_create(regs)
                            except Exception as e:
                                self.loge(e, doc, regs)
                            else:
                                if settings.DEBUG:
                                    self.logd(obj_regs)
                                for reg in obj_regs:
                                    try:
                                        reg.reset_admin_product_cache()
                                    except Exception as e:
                                        self.loge(e, reg)
                    return JsonResponse({'result':'success', 'doc':f'{doc.id}', 'records_count':len(obj_recs)})
        if settings.DEBUG:
            self.logd(data)
        return JsonResponse({'result':'error; request data invalid'}, status=400)


class DocsView(ListView, LogMixin):
    limit_default = 10
    page_num_default = 1
    model = Doc
    context_object_name = 'docs'
    queryset = model.objects.all()

    @method_decorator([ensure_csrf_cookie])
    def get(self, request, *args, **kwargs):
        user = request.user
        if not user:
            return JsonResponse({'result':'error: Please enable cookies and try again.'}, status=401)
        if not user.is_superuser:
            self.queryset = self.queryset.filter(author=user)
        request.GET._mutable = True
        page_num = int(request.GET.pop('page', [self.page_num_default])[0])
        limit = int(request.GET.pop('limit', [self.limit_default])[0])
        if request.GET:
            filters = {}
            for k, v in request.GET.items():
                if isinstance(v, list):
                    if '__in' in k:
                        v = tuple(v)
                    elif len(v) == 1:
                        v = v[0]
                filters[k] = v
            self.queryset = self.queryset.filter(**filters)
        if settings.DEBUG:
            self.logd(self.queryset.query)
        paginator = Paginator(self.queryset, self.limit_default)
        page_obj = paginator.get_page(page_num)
        if settings.DEBUG:
            self.logd(page_obj.object_list)
        json_data = serialize('json', page_obj, fields=('id', 'created_at', 'registered_at', 'owner', 'contractor', 'customer', 'type', 'tax', 'sale_point', 'sum_final', 'author'))
        if settings.DEBUG:
            self.logd(json_data)
        rsp_hdrs = {'count':paginator.count, 'num_pages':paginator.num_pages, 'page_min':paginator.page_range.start, 'page_max':paginator.page_range.stop, 'page':page_num, 'limit':limit}
        return JsonResponse(json_data, safe=False, headers=rsp_hdrs)


class DocViewSalesReceipt(View, LogMixin):
    model = Doc
    queryset = model.objects.none()

    @method_decorator([ensure_csrf_cookie])
    def get(self, request, pk=None):
        obj = get_object_or_404(self.model, pk=pk)
        m = obj.type._meta
        als = f'{m.app_label}.{m.model_name}.{obj.type.alias}'
        template = PrintTemplates.objects.filter(alias=als).first()
        if not template:
            return HttpResponse(f'PRINT TEMPLATE "{als}" NOT FOUND', status=404)
        css_media_style = ''
        if 'css_media_style' in template.extinfo:
            css_media_style = template.extinfo['css_media_style']
        if 'script' in template.extinfo:
            script = template.extinfo['script']
        records = Record.objects.filter(doc=obj).select_related('product')
        body = Template(template.content).render(Context({'doc':obj, 'request':request, 'records':records}))
        if not css_media_style:
            css_media_style = '@media(orientation:portrait) print{html body{width:210mm;height:297mm;visibility:hidden;height:auto;margin:0;padding:0;}} @page{size:A4;margin:0;}'
        body = f'<div id="section-to-print"><style>{css_media_style}</style>' + re.sub('(<!--.*?-->)', '', body, flags=re.DOTALL) + f'</div>{script}'
        locale.setlocale(locale.LC_ALL, '')
        lcl = locale.getlocale(locale.LC_MESSAGES)
        lcode = lcl[0].split('_')[0] if lcl and lcl[0] else 'en'
        pdf_engine = request.GET.get('pdf', '')
        if not pdf_engine:
            response = HttpResponse(f'<!DOCTYPE html><html lang="{lcode}"><head><meta charset="utf-8"><title>{obj}</title></head><body>{body}</body></html>')
        else:
            response = HttpResponse(body)
            #sudo apt install texlive-xetex, wkhtmltopdf, pandoc
            #pandoc --quiet (Suppress warning messages)
            from subprocess import Popen, PIPE, STDOUT
            try:
                #pandoc = Popen(['pandoc', '--from=html', '--to=pdf', '--pdf-engine=xelatex', '--pdf-engine-opt=-recorder', '-V "mainfont:Times New Roman" -V "monofont:Times New Roman Mono"'], stdin=PIPE, stdout=PIPE, stderr=STDOUT)
                pandoc = Popen(['pandoc', '--from=html', '--to=pdf', f'--pdf-engine={pdf_engine}', f'-V lang={lcode}', '-V mainfont="Times New Roman"', '-V sansfont="DejaVu Sans"'], stdin=PIPE, stdout=PIPE, stderr=STDOUT)
            except Exception as e:
                self.logw(e, 'PANDOC-HTML-TO-PDF')
                response.status_code = 400
                response.content = f'<!DOCTYPE html>{e};'
            else:
                response['Content-Type'] = 'application/pdf'
                response['Content-Disposition'] = f'attachment; filename="sales_receipt_{obj.id}.pdf"'
                response.content = pandoc.communicate(input=response.content)
                pos = response.content.find(b'%PDF')
                if pos:
                    response['pdf-errors'] = response.content[:pos].replace(b'\n', b'|').replace(b'\r', b'')
                    response.content = response.content[pos:response.content.find(b'%%EOF')+5]
        return response


class CustomersView(PaginatedView):
    model = Customer
    queryset = model.objects.all()
    fields = ('id', 'name', 'extinfo')

    def serialize_handler(self, data, field_names='__all__'):
        list_data = []
        for it in data:
            list_data.append({'id':it.id, 'name':it.name, 'extinfo':it.extinfo})
        return json.dumps(list_data, cls=DjangoJSONEncoder)

    @method_decorator([ensure_csrf_cookie])
    def post(self, request, *args, **kwargs):
        try:
            items = json.loads(request.body)
        except json.decoder.JSONDecodeError as e:
            self.loge(e)
            return JsonResponse({'result':f'error: {e}'}, status=400)
        except Exception as e:
            self.loge(e)
            return JsonResponse({'result':f'error: {e}'}, status=500)
        new_items = []
        for it in items:
            if it and isinstance(it, dict):
                new_items.append(self.model(**it))
        if new_items:
            try:
                objs = self.model.objects.bulk_create(new_items)
            except Exception as e:
                return JsonResponse({'result':f'error: {e}'}, status=500)
        return JsonResponse({'result':'success'}, safe=False)
