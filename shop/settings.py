from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-6qvh@36kg8xyr5$=3m=fhm-0y$#u0vc!)+maftswc=%l7sq$t*'

DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'shop.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'libraries': {'staticfiles':'django.templatetags.static'},
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            'loaders': [
                ('django.template.loaders.cached.Loader', [
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                ]),
                ('django.template.loaders.locmem.Loader', {
                    'dropdown_filter_from_memory.html': '''{%load i18n%}<script type="text/javascript">var $=django.jQuery; var jQuery=django.jQuery; var go_from_select=function(opt){window.location=window.location.pathname+opt;}; $(document).ready(function(){try{$(".second-style-selector").select2();}catch(e){console.log(e);};});</script><h3>{%blocktrans with title as filter_title%} By {{filter_title}} {%endblocktrans %}</h3><ul class="admin-filter-{{title|cut:' '}}">{%if choices|slice:"4:"%}<li><select class="form-control second-style-selector" style="width:95%;margin-left:2%;" onchange="go_from_select(this.options[this.selectedIndex].value)">{%for choice in choices%}<option {%if choice.selected%} selected="selected"{%endif%} value="{{choice.query_string|iriencode}}">{{choice.display}}</option>{%endfor%}</select></li>{% else%}{%for choice in choices%}<li {%if choice.selected%} class="selected"{%endif%}><a href="{{choice.query_string|iriencode}}">{{choice.display}}</a></li>{%endfor%}{%endif%}</ul>''',
                    'admin_select_file_form.html':'''{%extends "admin/base_site.html"%}{%block content%}<form enctype="multipart/form-data" action="" method="post">{%csrf_token%}{{form}}<ul>{{items|unordered_list}}</ul><input type="hidden" name="action" value="{{current_action}}" /><input type="submit" name="apply" value="Save" /><button onclick="window.location.href='{{request.path}}'">GoBack</button></form>{%endblock%}'''
                }),
			],
        },
    },
]

WSGI_APPLICATION = 'shop.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ashop',
        'USER': 'ashop',
        'PASSWORD': '',
        'HOST': '127.0.0.1',
        'PORT': '5432',
        'TEST':{'MIRROR':'default'}
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

DATA_UPLOAD_MAX_NUMBER_FIELDS = 102400
