from django.urls import path

from . import views


urlpatterns = [
    path('login/', views.url_login),
    path('logout/', views.url_logout),
    path('products/', views.ProductsView.as_view()),
    path('products/cash/', views.ProductsCashView.as_view(), name='products-cash'),
    path('docs/', views.DocsView.as_view()),
    path('doc/id<int:pk>/', views.DocView.as_view()),
    path('doc/cash/', views.DocCashAddView.as_view(), name='doc-cash')
]
