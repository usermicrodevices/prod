from django.urls import path
from django.contrib import admin
from django.conf import settings
from django.http import HttpResponse
from django.conf.urls.static import static


def favicon(request):
    return HttpResponse(settings.FAVICON_BASE64, content_type='image/svg+xml')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('favicon.ico', favicon)
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


def get_app_list(self, request, app_label=None):
    app_dict = self._build_app_dict(request, app_label)
    if not app_dict:
        return
    keys = list(app_dict.keys())
    return [app_dict[k] for k in settings.ADMIN_MAIN_MENU_FIRST_ITEMS if k in keys] + [app_dict[k] for k in keys if k not in settings.ADMIN_MAIN_MENU_FIRST_ITEMS]
admin.AdminSite.get_app_list = get_app_list
