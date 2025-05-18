from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _

from users.models import Role, RoleField, User
from users.apps import create_default_role_models
from refs.models import Company, CompanyType, Currency, DocType, PrintTemplates, Tax, Unit


class Command(BaseCommand):
    help = 'load default data'

    def handle(self, *args, **options):
        Currency().save()
        PrintTemplates().save()

        Unit(label=_('pcs'), name=_('pieces')).save()
        Unit(label=_('kg'), name=_('kilograms')).save()

        Tax(name=_('Without tax'), alias='NO').save()
        Tax(name=_('Tax 0%'), alias='VAT0', value=0).save()
        Tax(name=_('Tax 10%'), alias='VAT10', value=10).save()
        Tax(name=_('Tax 20%'), alias='VAT20', value=20).save()

        DocType(alias='receipt', name=_('Receipt'), income=True, auto_register=True).save()
        DocType(alias='balance', name=_('Balance'), income=True, auto_register=True).save()
        DocType(alias='sale', name=_('Sale'), income=False, auto_register=True).save()
        DocType(alias='expense', name=_('Expense'), income=False, auto_register=True).save()
        DocType(alias='order', name=_('Order'), income=True, auto_register=False).save()
        DocType(alias='order_customer', name=_('Order Customer'), income=True, auto_register=False).save()

        cmp_type_owner = CompanyType('owner')
        cmp_type_owner.save()
        cmp_type_order_contractor = CompanyType('order_contractor')
        cmp_type_order_contractor.save()
        cmp_type_customer = CompanyType('customer')
        cmp_type_customer.save()

        company_owner = Company('Own Company', type=cmp_type_owner, extinfo={"phone":"+00000000000 People", "adress":"city Aaaa, street Bbbb, house 0", "advertisement":"products"})
        company_owner.save()
        company_order_contractor = Company('Order Contractor', type=cmp_type_order_contractor, extinfo={"default_order_contractor":True})
        company_order_contractor.save()
        company_customer = Company('Customer', type=cmp_type_customer, extinfo={"default_cash_contractor":True, "default_order_customer_contractor":True})
        company_customer.save()

        grp_admin = Group('admin')
        grp_admin.save()
        grp_kassa = Group('kassa')
        grp_kassa.save()

        role_admin = Role('admin', group=grp_admin)
        role_admin.save()
        role_kassa = Role('kassa', group=grp_kassa, weight=1)
        role_kassa.save()

        create_default_role_models()
        RoleField.objects.filter(role=role_admin).update(read=True, write=True)
        RoleField.objects.filter(role=role_kassa).update(read=False, write=False)

        user_admin = User(
            username = 'admin',
            password = 'admin',
            groups = [role_admin.group],
            role = role_admin,
            default_company = company_owner,
            companies = [company_order_contractor, company_customer],
            is_superuser = True
        )
        user_admin.save()

        user_kassa = User(
            username = 'kassa',
            password = 'kassa',
            groups = [role_kassa.group],
            role = role_kassa,
            default_company = company_owner,
            companies = [company_customer]
        )
        user_kassa.save()

        self.stdout.write(self.style.SUCCESS('SUCCESS LOADED DEFAULT DATA'))
