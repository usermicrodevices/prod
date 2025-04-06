import logging, sys
from itertools import chain

from django.core.cache import caches
from django.db import models, transaction
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils.translation import gettext_lazy as _
from django.apps import apps as django_apps
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.db.models import Q


def create_default_role_fields(r, rmodel, fread = False, fwrite = False):
    if r.value == 'superadmin':
        fread = True
        fwrite = True
    for field in django_apps.get_app_config(rmodel.app).get_model(rmodel.model)._meta.get_fields():
        if field.__class__.__name__ == 'ManyToOneRel':
            continue
        try:
            rfield = RoleField.objects.get(role = r, role_model = rmodel, value = field.name)
        except:
            try:
                rfield = RoleField(role = r, role_model = rmodel, value = field.name, read = fread, write = fwrite)
            except Exception as e:
                logging.error('{} :: {} : {}'.format(sys._getframe().f_code.co_name, rmodel, e))
            else:
                try:
                    rfield.save()
                except Exception as e:
                    logging.error('{} :: {} : {}'.format(sys._getframe().f_code.co_name, r, rmodel, field, e))
        else:
            if field.__class__.__name__ == 'ManyToOneRel':
                rfield.delete()
            elif field.__class__.__name__ == 'ManyToOneRel':
                rfield.delete()
            elif fread or fwrite:
                if fread:
                    rfield.read = fread
                if fwrite:
                    rfield.write = fwrite
                rfield.save()


def get_users_by_owner(user):
    def cmodel(model_name, app_name='refs'):
        return django_apps.get_app_config(app_name).get_model(model_name)
    perms = user.get_all_permissions()
    conditions = Q(pk=user.id)
    if 'users.can_view_users' in perms:
        company_ids = cmodel('Company').objects.filter(pk__in=user.sale_points.values_list('company_id', flat=True))
        sale_point_ids = cmodel('SalePoint').objects.filter(company_id__in=user.companies.values_list('id', flat=True))
        conditions |= Q(companies__id__in=company_ids) | Q(companies__in=user.companies.all()) | Q(sale_points__id__in=sale_point_ids) | Q(sale_points__in=user.sale_points.all())
    exclude_conditions = Q(is_staff=True) | Q(is_superuser=True)
    return User.objects.filter(role__weight__gt=user.role.weight).filter(conditions).exclude(exclude_conditions).distinct()


class BaseModelWithLogger:

    def logi(self, *args):
        msg = f'{self.__class__.__name__}.{sys._getframe().f_back.f_code.co_name}'
        for arg in args: msg += f'::{arg}'
        logging.info(msg)

    def logd(self, *args):
        msg = f'❕{self.__class__.__name__}.{sys._getframe().f_back.f_code.co_name}'
        for arg in args:
            msg += f'::{arg}'
        logging.debug(msg)

    def logw(self, *args):
        msg = f'{self.__class__.__name__}.{sys._getframe().f_back.f_code.co_name}'
        for arg in args: msg += f'::{arg}'
        logging.warning(msg)

    def loge(self, err, *args):
        msg = f'{self.__class__.__name__}.{err.__traceback__.tb_frame.f_code.co_name}::{err}::LINE={err.__traceback__.tb_lineno}'
        for arg in args: msg += f'::{arg}'
        logging.error(msg)

    def to_list(self, exclude_fields='__all__'):
        data = []
        if isinstance(exclude_fields, str) and  exclude_fields == '__all__':
            return data
        opts = self._meta
        for f in chain(opts.concrete_fields, opts.private_fields):
            if f.name in exclude_fields:
                continue
            value = f.value_from_object(self)
            data.append(value)
        return data

    def to_list_strings(self, exclude_fields='__all__'):
        data = []
        if isinstance(exclude_fields, str) and  exclude_fields == '__all__':
            return data
        opts = self._meta
        for f in chain(opts.concrete_fields, opts.private_fields):
            if f.name in exclude_fields:
                continue
            value = f.value_from_object(self)
            if value is None:
                value = ''
            data.append(value if isinstance(value, str) else f'{value}')
        return data

    def to_dict(self, exclude_fields='__all__'):
        data = {}
        if isinstance(exclude_fields, str) and  exclude_fields == '__all__':
            return data
        opts = self._meta
        for f in chain(opts.concrete_fields, opts.private_fields):
            if f.name in exclude_fields:
                continue
            value = f.value_from_object(self)
            data[f.name] = value if isinstance(value, str) else f'{value}'
        for f in opts.many_to_many:
            if f.name in exclude_fields:
                continue
            data[f.name] = [i.id for i in f.value_from_object(self)]
        return data


class RoleModel(models.Model, BaseModelWithLogger):
    app = models.CharField(max_length=128, null=False, blank=False,  verbose_name=_('application'), help_text=_('name of application'))
    model = models.CharField(max_length=128, null=False, blank=False, verbose_name=_('model'), help_text=_('name of model'))

    class Meta:
        unique_together = ('app', 'model')
        verbose_name = f'🤵{_("Role Model")}'
        verbose_name_plural = f'🤵{_("Role Models")}'

    def __str__(self):
        return f'​✅[{self.id}] {self.app}.{self.model} '

    def as_key(self):
        return f'{self.app}.{self.model}'


class Role(models.Model, BaseModelWithLogger):
    value = models.CharField(max_length=32, unique=True, null=True, default=None)
    description = models.CharField(max_length=191, null=True, default=None)
    group = models.ForeignKey(Group, default=None, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_('group'))
    weight = models.IntegerField(default=0, null=False, blank=False, verbose_name=_('weight'), help_text=_('weight of role for setup priority'))

    class Meta:
        verbose_name = f'🤵{_("Role")}'
        verbose_name_plural = f'🤵{_("Roles")}'
        ordering = ('value',)

    def __str__(self):
        return '%s : %s' % (self.value if self.value else '',  self.description if self.description else '')

    def to_dict(self, exclude_fields=['id']):
        data = super().to_dict(exclude_fields)
        models_fields = {}
        exclude_fields_rf = ['id', 'role', 'role_model', 'value']
        for rf in RoleField.objects.filter(role=self.id):
            key_model = rf.role_model.as_key()
            key_field = rf.value
            if key_model in models_fields:
                models_fields[key_model][key_field] = rf.to_dict(exclude_fields_rf)
            else:
                models_fields[key_model] = {key_field:rf.to_dict(exclude_fields_rf)}
        data['models_fields'] = models_fields
        return data

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        for m in RoleModel.objects.all():
            create_default_role_fields(self, m)

    def users(self):
        return self.user_set.all()

    def users_count(self):
        return self.user_set.count()


class RoleField(models.Model, BaseModelWithLogger):
    value = models.CharField(max_length=191, default='id', null=False, blank=False, verbose_name=_('value'), help_text=_('field of model'))
    role = models.ForeignKey(Role, default=0, null=False, blank=False, on_delete=models.CASCADE, verbose_name=_('role'))
    role_model = models.ForeignKey(RoleModel, default=0, null=False, blank=False, on_delete=models.CASCADE, verbose_name=_('model'))
    read = models.BooleanField(null=False, blank=False, default=False)
    write = models.BooleanField(null=False, blank=False, default=False)

    class Meta:
        unique_together = ('value', 'role', 'role_model')
        verbose_name = f'🤵{_("Role Field")}'
        verbose_name_plural = f'🤵{_("Role Fields")}'
        ordering = ['value']

    # def to_dict(self, exclude_fields=['id']):
    #     data = super().to_dict(exclude_fields)
    #     data['models_fields'] = {rf.value:rf.to_dict() for rf in RoleField.objects.filter(role=self.id)}
    #     return data


class User(AbstractUser, BaseModelWithLogger):
    cache = caches['users']
    role = models.ForeignKey(Role, null=True, on_delete=models.SET_NULL, verbose_name=_('role'))
    companies = models.ManyToManyField(to='refs.Company', blank=True, verbose_name=_('companies'))
    sale_points = models.ManyToManyField(to='refs.SalePoint', blank=True, verbose_name=_('sale points'))
    contract_finished = models.DateTimeField(default=None, null=True, blank=True, verbose_name=_('contract finished date'), help_text=_('Date of contract finished'))
    avatar = models.TextField(default=None, null=True, blank=True, verbose_name=_('avatar'), help_text=_('image as BASE64'))
    default_company = models.ForeignKey('refs.Company', related_name='users', null=True, on_delete=models.SET_NULL, verbose_name=_('default company'))


    class Meta:
        db_table = 'auth_user'
        verbose_name = f'🤵{_("User")}'
        verbose_name_plural = f'🤵{_("Users")}'

    def to_dict(self, exclude_fields='__all__'):
        data = super().to_dict(exclude_fields)
        if 'role' in data:
            data['role'] = self.role.to_dict()
        if 'user_permissions' in data:
            data['user_permissions'] = [x.codename for x in Permission.objects.filter(user=self)]
        if 'groups' in data:
            p = Permission.objects.filter(group__in=data['groups']).distinct()
            data['groups'] = [x.codename for x in p]
        return data

    def sync_from_role_group(self):
        if self.role and self.role.group and self.role.group not in self.groups.all():
            self.groups.add(self.role.group)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        try:
            self.cache.clear()
        except Exception as e:
            self.loge(e)

    def update(self, *args, **kwargs):
        self.logi(args, kwargs)
        super().update(*args, **kwargs)
        try:
            self.cache.clear()
        except Exception as e:
            self.loge(e)

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        try:
            self.cache.clear()
        except Exception as e:
            self.loge(e)

@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, raw, using, update_fields, **kwargs):
    if instance.default_company is None:
        if instance.companies.count():
            User.objects.filter(id = instance.id).update(default_company_id = instance.companies.order_by('id').first().id)
        elif instance.sale_points.count():
            User.objects.filter(id = instance.id).update(default_company_id = instance.sale_points.order_by('id').first().company_id)
    if instance.role and instance.role.group and instance.role.group not in instance.groups.all():
        with transaction.atomic():
            transaction.on_commit(instance.sync_from_role_group)
