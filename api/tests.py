import json
from datetime import datetime

from django.test import TransactionTestCase
from django.core.exceptions import MultipleObjectsReturned
from django.contrib.auth import get_user_model
#from django.contrib.auth.models import Group
from django.contrib.auth.hashers import make_password
from django.utils import timezone as django_timezone
from django.apps import apps as django_apps
from django.test import Client

from html.parser import HTMLParser


def get_model(app_model):
    app_name, model_name = app_model.split('.')
    return django_apps.get_app_config(app_name).get_model(model_name)


class CSRFParser(HTMLParser):
    csrfmiddlewaretoken = ''
    def handle_starttag(self, tag, attrs):
        if tag == 'input':
            kwargs = dict(attrs)
            if set(['type', 'name', 'value']) <= set(kwargs.keys()) and kwargs['name'] == 'csrfmiddlewaretoken':
                self.csrfmiddlewaretoken = kwargs['value']
                #print("Encountered a start tag:", tag, kwargs)


class Usr(TransactionTestCase):
    'User test case'
    maxDiff = None
    reset_sequences = True
    csrfmiddlewaretoken = ''

    def setUp(self):
        user_name = f'test_{int(django_timezone.now().timestamp())}'
        self.test_password = 't0#e9@s8$t7'
        self.user = get_user_model()(username=user_name, password=make_password(self.test_password), email='test@test.test', first_name='Test', last_name='tesT', is_staff=True, is_active=True, is_superuser=True, role = get_model('users.Role').objects.get(value='kassa'))
        #self.user.save()
        ##self.user.groups.add(Group.objects.get(id=1))
        print(self.user.id, self.user, self.test_password)
        print()

        self.client = Client()
        url = '/admin/login/'
        print('⚽GET', url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        print(self.client.cookies)
        parser = CSRFParser()
        parser.feed(response.content.decode('utf-8'))
        self.csrfmiddlewaretoken = parser.csrfmiddlewaretoken
        print('csrfmiddlewaretoken', self.csrfmiddlewaretoken)
        self.login()

    def tearDown(self):
        self.client.logout()
        if self.user.id:
            self.user.delete()

    def login(self):
        print()
        url = '/api/login/'
        data = json.dumps({'username':self.user.username, 'password':self.test_password})
        print('⚽POST', url, data)# headers={"host": "127.0.0.1:8000"}
        response = self.client.post(url, data, 'json', headers={'X-CSRFToken':self.csrfmiddlewaretoken})
        self.assertEqual(response.status_code, 200)
        print(self.client.cookies)
        print('Request♥', response.request)
        print('Response♡', json.dumps(response.json(), ensure_ascii=False).encode('utf-8'))
        print('DATA⋆', eval(response.content))

    def test_products(self):
        print()
        url = '/api/products/'
        print('⚽GET', url)
        response = self.client.get(url, headers={'X-CSRFToken':self.csrfmiddlewaretoken})
        self.assertEqual(response.status_code, 200)
        print('Request♥', response.request)
        print('Response♡', response, response.headers)
        print('DATA⋆', eval(response.content))
        print()
        url = '/api/products/cash/'
        print('⚽GET', url)
        response = self.client.get(url, headers={'X-CSRFToken':self.csrfmiddlewaretoken})
        self.assertEqual(response.status_code, 200)
        print('Request♥', response.request)
        print('Response♡', response, response.headers)
        print('DATA⋆', eval(response.content))
        print()
        url = '/api/products/?page=1'
        print('⚽GET', url)
        response = self.client.get(url, headers={'X-CSRFToken':self.csrfmiddlewaretoken})
        self.assertEqual(response.status_code, 200)
        print('Request♥', response.request)
        print('Response♡', response, response.headers)
        print('DATA⋆', eval(response.content))
        print()
        url = '/api/products/?page=0'
        print('⚽GET', url)
        response = self.client.get(url, headers={'X-CSRFToken':self.csrfmiddlewaretoken})
        self.assertEqual(response.status_code, 400)
        print('Request♥', response.request)
        print('Response♡', response, response.headers)
        print('DATA⋆', eval(response.content))
        print()
        url = f'/api/products/?page={int(response.headers['page_max']) + 1}'
        print('⚽GET', url)
        response = self.client.get(url, headers={'X-CSRFToken':self.csrfmiddlewaretoken})
        self.assertEqual(response.status_code, 400)
        print('Request♥', response.request)
        print('Response♡', response, response.headers)
        print('DATA⋆', eval(response.content))
        print()
        prod_id = get_model('refs.Product').objects.first().id
        url = f'/api/product/{prod_id}/'
        print('⚽GET', url)
        response = self.client.get(url, headers={'X-CSRFToken':self.csrfmiddlewaretoken})
        #self.assertEqual(response.status_code, 200)
        print('Request♥', response.request)
        print('Response♡', response, response.headers)
        print('DATA⋆', eval(response.content.decode('utf8').replace('null', 'None')))
        print()
        url = f'/api/product/{prod_id}/'
        print('⚽HEAD', url)
        response = self.client.head(url, headers={'X-CSRFToken':self.csrfmiddlewaretoken})
        #self.assertEqual(response.status_code, 200)
        print('Request♥', response.request)
        print('Response♡', response, response.headers)

    def test_docs(self):
        print()
        url = '/api/docs/'
        print('⚽GET', url)
        response = self.client.get(url, headers={'X-CSRFToken':self.csrfmiddlewaretoken})
        self.assertEqual(response.status_code, 200)
        print('Request♥', response.request)
        print('Response♡', response, response.headers)
        print('Content⋆', response.content.decode('utf8').replace('\\', ''))
        docs = eval(response.content.decode('utf8').replace('\\', '').replace('null', 'None').strip('"'))
        print('DATA⋆', docs)
        print()
        url = '/api/doc/cash/'
        prods = get_model('refs.Product').objects.all()[:5]
        data = json.dumps({'sum_final':1000, 'registered_at':datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S %z'), 'records':[{'product':p.id, 'count':10, 'price':f'{p.price}'} for p in prods]})
        print('⚽POST', url, data)
        response = self.client.post(url, data, 'json', headers={'X-CSRFToken':self.csrfmiddlewaretoken})
        print('CONTENT♡', response.content)
        self.assertEqual(response.status_code, 200)
        print('Request♥', response.request)
        print('Response♡', response, response.headers)
        print('DATA⋆', eval(response.content))
        print()
        if docs:
            print('⚽docs[0]', docs[0])
            url = f'/api/doc/{docs[0].get("pk", 1)}/sales_receipt'
            print('⚽GET', url)
            response = self.client.get(url, headers={'X-CSRFToken':self.csrfmiddlewaretoken})
            print('Request♥', response.request)
            print('Response♡', response, response.headers)
            print('HTML⋆', response.content.decode('utf8'))
            self.assertInHTML('<!DOCTYPE html>', response.content.decode('utf8'))

    def test_customers(self):
        print()
        url = '/api/customers/'
        print('⚽GET', url)
        response = self.client.get(url, headers={'X-CSRFToken':self.csrfmiddlewaretoken})
        self.assertEqual(response.status_code, 200)
        print('Request♥', response.request)
        print('Response♡', response, response.headers)
        print('DATA⋆', eval(response.content.decode('utf8').replace('null', 'None')))
        print()
        data = json.dumps([{'name':'John Doe', 'extinfo':{'test':'key'}}, {'name':'Test Name', 'extinfo':{'key':'value'}}])
        print('⚽POST', url, data)
        response = self.client.post(url, data, 'json', headers={'X-CSRFToken':self.csrfmiddlewaretoken})
        print('CONTENT♡', response.content)
        self.assertEqual(response.status_code, 200)
        print('Request♥', response.request)
        print('Response♡', response, response.headers)
        print('DATA⋆', eval(response.content))
