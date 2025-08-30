from django.test import TransactionTestCase
from django.apps import apps as django_apps
from django.db.models.functions import Length


def get_model(app_model):
    app_name, model_name = app_model.split('.')
    return django_apps.get_app_config(app_name).get_model(model_name)


class Usr(TransactionTestCase):
    'Refs test case'
    maxDiff = None
    reset_sequences = True


    def test_prods(self):
        product = get_model('refs.Product').objects.filter(article__contains='Y').order_by('-article').first()
        self.assertIsNotNone(product)
        print(product.to_dict())

        product = get_model('refs.Product').objects.annotate(len_article=Length('article')).filter(len_article=5, article__contains='Y').order_by('-article').first()
        self.assertIsNotNone(product)
        print(product.to_dict())

        product = get_model('refs.Product').objects.filter(article__regex=r'^Y[0-9]{1,4}$').order_by('-article').first()
        self.assertIsNotNone(product)
        print(product.to_dict())
