import json

from django.test import TransactionTestCase
from django.core.exceptions import MultipleObjectsReturned
from django.contrib.auth import get_user_model
#from django.contrib.auth.models import Group
from django.contrib.auth.hashers import make_password
from django.test import Client
from django.utils import timezone as django_timezone

from html.parser import HTMLParser


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
        self.test_password = 't0#e9@s8$t7'
        self.user = get_user_model()(username=f'test_{int(django_timezone.now().timestamp())}', password=make_password(self.test_password), email='test@test.test', first_name='Test', last_name='tesT', is_staff=True, is_active=True, is_superuser=True)
        self.user.save()
        #self.user.groups.add(Group.objects.get(id=1))
        print(self.user.id, self.user, self.test_password)
        print()

        self.client = Client()
        url = '/admin/login/'
        print('⚽GET', url)
        response = self.client.post(url, {'username':self.user.username, 'password':self.test_password}, 'json')
        self.assertEqual(response.status_code, 200)
        print(self.client.cookies)
        parser = CSRFParser()
        parser.feed(response.content.decode('utf-8'))
        self.csrfmiddlewaretoken = parser.csrfmiddlewaretoken
        print('csrfmiddlewaretoken', self.csrfmiddlewaretoken)
        self.login()

    def tearDown(self):
        self.client.logout()
        self.user.delete()

    def login(self):
        print()
        url = '/api/login/'
        data = json.dumps({'username':self.user.username, 'password':self.test_password})
        print('⚽GET', url, data)# headers={"host": "127.0.0.1:8000"}
        print(self.client.cookies)
        response = self.client.post(url, data, 'json', headers={'X-CSRFToken':self.csrfmiddlewaretoken})
        self.assertEqual(response.status_code, 200)
        print('Request♥', response.request)
        print('Response♡', json.dumps(response.json(), ensure_ascii=False).encode('utf-8'))
        print(response.content)

    def test_products(self):
        print()
        url = '/api/products/'
        print('⚽GET', url)
        response = self.client.get(url, headers={'X-CSRFToken':self.csrfmiddlewaretoken})
        self.assertEqual(response.status_code, 200)
        print('Request♥', response.request)
        print('Response♡', response, response.headers)
        print('DATA⋆', response.content)
