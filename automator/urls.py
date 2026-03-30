from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('start/', views.start_automation, name='start_automation'),
    path('stop/', views.stop_automation, name='stop_automation'),
    path('logs/', views.get_logs, name='get_logs'),
    path('accounts/', views.get_accounts, name='get_accounts'),
    path('browsers/', views.browsers, name='browsers'),
    path('status/', views.status, name='status'),  
    path('start_browser/', views.start_browser, name='start_browser'),
]
