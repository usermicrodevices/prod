from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'dummy-key-require-replaced-in-production'

DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '192.168.0.1']

X_FRAME_OPTIONS = 'SAMEORIGIN'

CSRF_COOKIE_DOMAIN = '127.0.0.1'
CSRF_TRUSTED_ORIGINS = ['http://127.0.0.1', 'http://127.0.0.1:8000', 'https://127.0.0.1:9443']
CORS_ALLOWED_ORIGINS = ['http://127.0.0.1', 'http://127.0.0.1:8000', 'https://127.0.0.1:9443']

INSTALLED_APPS = [
    "daphne",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'users.apps.UsersConfig',
    'refs.apps.RefsConfig',
    'core.apps.CoreConfig',
    'api.apps.ApiConfig'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.auth.middleware.PersistentRemoteUserMiddleware",
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.locale.LocaleMiddleware'
]

ROOT_URLCONF = 'shop.urls'
LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/admin/login/'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
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
    'testdb': {
        "ENGINE": "django.db.backends.sqlite3",
        'NAME': ':memory:'
    },
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'prod_database',
        'USER': 'prod_user',
        'PASSWORD': '',
        'HOST': '127.0.0.1',
        'PORT': '5432',
        'TEST':{'MIRROR':'testdb'}
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
STATIC_ROOT = f'{BASE_DIR}/static/'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

DATA_UPLOAD_MAX_NUMBER_FIELDS = 102400

CACHES = {
'default':{'BACKEND':'django.core.cache.backends.locmem.LocMemCache', 'OPTIONS':{'MAX_ENTRIES':99999999, 'CULL_FREQUENCY':99999998}},
'users':{'BACKEND':'django.core.cache.backends.locmem.LocMemCache', 'LOCATION':'users', 'TIMEOUT':86400, 'OPTIONS':{'MAX_ENTRIES':99999999, 'CULL_FREQUENCY':99999998}},
}

AUTH_USER_MODEL = 'users.User'

ADMIN_PATH_PREFIX = '/admin'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname:1.1}] | {asctime} | {module} > {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'filters': ['require_debug_true'],
            'formatter': 'verbose'
        }
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'DEBUG'
        }
    }
}

ADMIN_MAIN_MENU_FIRST_ITEMS = ['core', 'refs', 'users']

FAVICON_BASE64 = '''data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'%3E%3Cpath d='M224%20387.814V512L32 320l192-192v126.912C447.375 260.152 437.794 103.016 380.93 0 521.287 151.707 491.48 394.785 224 387.814z'/%3E%3C/svg%3E'''

ADMIN_EAN13_RENDER_OPTIONS = {
'module_width':0.3,
'module_height':6.0,
'quiet_zone':0.5,
'font_size':8,
'font_style_ext':'font-weight:bold;',
'text_distance':2.5,
'show_name':False,
'name_at_top':True,
'name_at_top_x':'center',
'name_at_top_h':8,
'text_wrapped_symbols':15,
'css_media_orientation':'(orientation:landscape)',
'css_media_page_size_ext':'',
'css_media_ext':'html:root{--message-success-bg:unset;} #container{height:max-content;width:max-content;min-width:unset;} ul.messagelist li{display:unset;margin:0;padding:0;background:white;background-size:unset;font-size:unset;word-break:unset;color:black;} header,footer,aside,nav,form,iframe,button,.ad,.success,#header,#content,#toggle-nav-sidebar{display:none;}',
'print_button':'<button id="pbtn" onclick="this.hidden=true;window.print();this.hidden=false;/*window.location.reload()*/">🖶</button>',
'print_script':'''<script>
window.onload = function() {
document.getElementsByTagName("head")[0].remove();
document.body.style.margin = 0;
document.body.style.padding = 0;
document.body.style.width = 0;
document.body.style.height = 0;
const parea = document.getElementById("section-to-print");
while(document.body.firstChild){document.body.removeChild(document.body.firstChild);}
document.body.appendChild(parea);
setTimeout(function(){window.print();},0);
window.onfocus=function(){setTimeout(function(){window.location.reload();},0);}
}
</script>'''
}

ADMIN_SET_DOCUMENT_RECORD_PRICES = {'check_empty_cost':False, 'check_empty_price':False}

#register_change_referece=false - product reference always stay constant
#select_from_register=true - select from last register else from reference
#select_during_... - select value from reference or register when edit document
BEHAVIOR_COST = {'register_change_referece':True, 'select_from_register':False, 'select_during_incoming':True, 'select_during_sale':False}
BEHAVIOR_PRICE = {'register_change_referece':True, 'select_from_register':False, 'select_during_incoming':True, 'select_during_sale':True}
BEHAVIOR_COUNT = {'select_from_register':True, 'select_during_incoming':True, 'select_during_sale':True, 'select_focus':'elem_count.focus();'}

def NEW_ARTICLE_GENERATOR(obj_model, default=''):
    try:
        last_article = obj_model.objects.filter(article__regex=r'^Y[0-9]{1,4}$').order_by('-article').only('article').first().article
    except Exception as e:
        pass
    else:
        if last_article:
            return f'''Y{f'{int(last_article[1:]) + 1}'.zfill(4)}'''
    return default

DEFAUL_IMAGE_THUMBNAIL = '''data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><text y="1em" font-size="26">📄</text></svg>'''
