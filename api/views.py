import json, logging

from django.http import JsonResponse
from django.views import View
from django.core.serializers import serialize#, JSONSerializer
from django.core.serializers.json import DjangoJSONEncoder
#from django.core.signing import Signer
from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY, authenticate, login
from django.contrib.auth.decorators import login_required, login_not_required
from django.views.decorators.csrf import csrf_exempt, csrf_protect, requires_csrf_token, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.db.models import F

from users.models import User
from refs.models import Product


@csrf_exempt
@login_not_required
@require_http_methods(["POST"])
def url_login(request):
    if request.method == "POST":
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
@require_http_methods(["POST"])
def url_logout(request):
    try:
        del request.session[HASH_SESSION_KEY]
    except KeyError as e:
        logging.error(f'{e}')
    return JsonResponse({'success':"You're logged out."})


#import asyncio
class ProductsView(View):
    queryset = Product.objects.all()

    #@method_decorator([login_required, csrf_protect, requires_csrf_token, ensure_csrf_cookie])
    #async def get(self, request, *args, **kwargs):
    @method_decorator([ensure_csrf_cookie])
    def get(self, request, *args, **kwargs):
        #await asyncio.sleep(1)
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
        data = {}
        for it in self.queryset.prefetch_related('currency', 'barcodes', 'qrcodes', 'group', 'unit'):
            data[it.id] = {'article':it.article, 'name':it.name, 'price':it.price, 'barcodes':list(it.barcodes.values_list('id', flat=True)), 'qrcodes':list(it.qrcodes.values_list('id', flat=True)), 'currency':it.currency.name, 'group':it.group.name, 'unit':it.unit.label}
        json_data = json.dumps(data, cls=DjangoJSONEncoder)
        return JsonResponse(json_data, safe=False)
