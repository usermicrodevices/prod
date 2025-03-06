import json, logging, sys

from django.http import JsonResponse
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

from users.models import User, RoleField
from refs.models import Company, DocType, Product
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
            user_name = data.get('username', '')
            user_password = data.get('password', '')
            user = authenticate(request, username=user_name, password=user_password)
            if user:
                login(request, user)
                return JsonResponse({'result':'success'})
            else:
                try:
                    u = User.objects.get(username=user_name)
                except Exception as e:
                    logging.error(f'{e}; user_name={user_name}')
                    return JsonResponse({'result':'error: user not found'}, status=404)
                else:
                    if u and u.check_password(user_password):
                        request.session[SESSION_KEY] = f'{u.id}'
                        request.session[BACKEND_SESSION_KEY] = settings.AUTHENTICATION_BACKENDS[0]
                        request.session[HASH_SESSION_KEY] = u.get_session_auth_hash()
                        #request.session[HASH_SESSION_KEY] = Signer().sign_object(data)
                        return JsonResponse({'result':'success'})
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

    def logi(self, *args):
        msg = f'ℹ{self.__class__.__name__}.{sys._getframe().f_back.f_code.co_name}'
        for arg in args:
            msg += f'::{arg}'
        logging.info(msg)

    def logw(self, *args):
        msg = f'⚠{self.__class__.__name__}.{sys._getframe().f_back.f_code.co_name}'
        for arg in args:
            msg += f'::{arg}'
        logging.warning(msg)

    def logd(self, *args):
        msg = f'‼{self.__class__.__name__}.{sys._getframe().f_back.f_code.co_name}'
        for arg in args:
            msg += f'::{arg}'
        logging.debug(msg)

    def loge(self, err, *args):
        msg = f'🆘{self.__class__.__name__}.{err.__traceback__.tb_frame.f_code.co_name}::{err}::LINE={err.__traceback__.tb_lineno}'
        for arg in args:
            msg += f'::{arg}'
        logging.error(msg)


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


class ProductsView(View, LogMixin):
    limit_default = 10
    page_num_default = 1
    model = Product
    queryset = model.objects.all()

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
            json_data = self.serialize_handler(paginated_data, ('id', 'article', 'name', 'cost', 'price', 'barcodes', 'currency'))
        return paginator, json_data, http_status

    @method_decorator([ensure_csrf_cookie])
    def get(self, request, *args, **kwargs):
        if settings.DEBUG:
            self.logd('REQUEST.GET', request.GET)
        request.GET._mutable = True
        page_num = int(request.GET.pop('page', [self.page_num_default])[0])
        limit = int(request.GET.pop('limit', [self.limit_default])[0])
        paginator, json_data, http_status = self.paginate(self.queryset.filter(**request.GET), limit, page_num)
        if settings.DEBUG:
            self.logd('JSON_DATA', json_data)
        rsp_hdrs = {'count':paginator.count, 'num_pages':paginator.num_pages, 'page_min':paginator.page_range.start, 'page_max':paginator.page_range.stop, 'page':page_num, 'limit':limit}
        response = JsonResponse(json_data, safe=False, status=http_status, headers=rsp_hdrs)
        return response


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
        sum_final = data.get('sum_final', 0)
        records = data.get('records', [])
        registered_at = data.get('registered_at', '')
        if records and sum_final and registered_at:
            id_owner = data.get('owner', request.user.default_company.id if request.user.default_company else 1)
            default_contractor = Company.objects.filter(extinfo__default_cash_contractor=True).first()
            id_contractor = data.get('contractor', default_contractor.id if default_contractor else 2)
            dtype = data.get('type', 'sale')
            doc_type, created = DocType.objects.get_or_create(alias=dtype, defaults={'alias':dtype, 'name':dtype.title()})
            doc = Doc(type=doc_type, registered_at=parse_datetime(registered_at), owner_id=id_owner, contractor_id=id_contractor, author=request.user, sum_final=sum_final)
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
        return JsonResponse({'result':'error; request data invalid'}, status=400)


class DocsView(ListView, LogMixin):
    paginate_by = 10
    model = Doc
    context_object_name = 'docs'
    queryset = model.objects.none()

    @method_decorator([ensure_csrf_cookie])
    def get(self, request, *args, **kwargs):
        if request.GET:
            self.queryset = self.queryset.filter(**request.GET)
        paginator = Paginator(self.queryset, self.paginate_by)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        if settings.DEBUG:
            self.logd(page_obj.object_list)
        json_data = serialize('json', page_obj, fields=('id', 'created_at', 'registered_at', 'owner', 'contractor', 'customer', 'type', 'tax', 'sale_point', 'sum_final', 'author'))
        if settings.DEBUG:
            self.logd(json_data)
        return JsonResponse(json_data, safe=False)
