from django.urls import path

from . import views


urlpatterns = [
    path('login/', views.url_login),
    path('logout/', views.url_logout),
    path('products/', views.ProductView.as_view()),
]
