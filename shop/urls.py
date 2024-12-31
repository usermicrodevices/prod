from django.urls import path
from django.contrib import admin
from django.conf import settings
from django.http import HttpResponse

def favicon(request):
    return HttpResponse(settings.FAVICON_BASE64, content_type='image/svg+xml')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('favicon.ico', favicon)
]
