import json, logging

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
from django.core.paginator import Paginator
from django.conf import settings
from django.db.models import F
from django.utils.dateparse import parse_datetime

from users.models import User
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
                logging.error(e)
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


class ProductsView(View):
    queryset = Product.objects.all()

    @method_decorator([ensure_csrf_cookie])
    def get(self, request, *args, **kwargs):
        data = serialize('json', self.queryset, fields=('id', 'article', 'name', 'cost', 'price', 'barcodes', 'currency'))
        return JsonResponse(data, safe=False)


class ProductsCashView(ProductsView):

    @method_decorator([ensure_csrf_cookie])
    def get(self, request, *args, **kwargs):
        #def dflt(item):
            #return False if item[0] == 'id' else True
        #qs = self.queryset.annotate(curr=F('currency__name')).prefetch_related('currency', 'barcodes').values('id', 'article', 'name', 'price', 'barcodes', 'curr')
        #json_data = json.dumps(list(qs), cls=DjangoJSONEncoder)
        #data = {it['id']:dict(filter(dflt, it.items())) for it in qs}
        data = []
        for it in self.queryset.prefetch_related('currency', 'barcodes', 'qrcodes', 'group', 'unit'):
            grp = ''
            if it.group:
                grp = {'id':it.group.id, 'name':it.group.name}
            unit = ''
            if it.unit:
                unit = {'id':it.unit.id, 'label':it.unit.label}
            currency = ''
            if it.currency:
                currency = {'id':it.currency.id, 'name':it.currency.name}
            data.append({'id':it.id, 'article':it.article, 'name':it.name, 'cost':0.0, 'price':it.price, 'barcodes':list(it.barcodes.values_list('id', flat=True)), 'qrcodes':list(it.qrcodes.values_list('id', flat=True)), 'currency':currency, 'grp':grp, 'unit':unit})
        json_data = json.dumps(data, cls=DjangoJSONEncoder)
        return JsonResponse(json_data, safe=False)


class DocView(DetailView):
    context_object_name = 'doc'
    queryset = Doc.objects.none()

    @method_decorator([ensure_csrf_cookie])
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['doc_list'] = Doc.objects.all()
        return context

    @method_decorator([ensure_csrf_cookie])
    def get(self, request, *args, **kwargs):
        data = serialize('json', self.queryset, fields=('id', 'article', 'name', 'cost', 'price', 'barcodes', 'currency'))
        return JsonResponse(data, safe=False)


class DocCashAddView(View):
    context_object_name = 'doc-cash'

    @method_decorator([ensure_csrf_cookie])
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except json.decoder.JSONDecodeError as e:
            logging.error(e)
            return JsonResponse({'result':f'error: {e}'}, status=400)
        except Exception as e:
            logging.error(e)
            return JsonResponse({'result':f'error: {e}'}, status=500)
        sum_final = data.get('sum_final', 0)
        records = data.get('records', [])
        registered_at = data.get('registered_at', '')
        if records and sum_final and registered_at:
            id_owner = data.get('owner', request.user.default_company.id if request.user.default_company else 1)
            default_contractor = Company.objects.filter(extinfo__default_cash_contractor=True).first()
            id_contractor = data.get('contractor', default_contractor.id if default_contractor else 2)
            dtype = data.get('type', 'sale')
            t, created = DocType.objects.get_or_create(alias=dtype, defaults={'alias':dtype, 'name':dtype.title()})
            doc = Doc(type=t, registered_at=parse_datetime(registered_at), owner_id=id_owner, contractor_id=id_contractor, author=request.user, sum_final=sum_final)
            recs = []
            for r in records:
                try:
                    p = Product.objects.get(pk=r['product'])
                except Exception as e:
                    logging.error([r, e])
                    return JsonResponse({'result':f'error; {r}; {e}'}, status=500)
                else:
                    recs.append(Record(count=r['count'], cost=p.cost, price=r['price'], doc=doc, currency=p.currency, product=p))
            if recs:
                try:
                    doc.save()
                except Exception as e:
                    logging.error(e)
                    return JsonResponse({'result':f'error: {e}'}, status=500)
                else:
                    try:
                        obj_recs = Record.objects.bulk_create(recs)
                    except Exception as e:
                        logging.error([doc, recs, e])
                    else:
                        logging.debug(obj_recs)
                        regs = []
                        for obj in obj_recs:
                            regs.append(Register(rec=obj))
                        if regs:
                            try:
                                obj_regs = Register.objects.bulk_create(regs)
                            except Exception as e:
                                logging.error([doc, regs, e])
                            else:
                                logging.debug(obj_regs)
                    return JsonResponse({'result':'success', 'doc':f'{doc.id}', 'records_count':len(obj_recs)})
        return JsonResponse({'result':'error; request data invalid'}, status=400)


class DocsView(ListView):
    paginate_by = 10
    model = Doc
    context_object_name = 'docs'
    queryset = Doc.objects.all()

    @method_decorator([ensure_csrf_cookie])
    def get(self, request, *args, **kwargs):
        if request.GET:
            self.queryset = self.queryset.filter(**request.GET)
        paginator = Paginator(self.queryset, self.paginate_by)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        logging.debug(page_obj.object_list)
        #data = {'page':page_number, 'docs':[self.queryset]}
        #json_data = json.dumps(data, cls=DjangoJSONEncoder)
        json_data = serialize('json', page_obj, fields=('id', 'created_at', 'registered_at', 'owner', 'contractor', 'type', 'tax', 'sale_point', 'sum_final', 'author'))
        logging.debug(json_data)
        return JsonResponse(json_data, safe=False)
