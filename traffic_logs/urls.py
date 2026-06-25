from django.urls import path

from . import views

app_name = 'traffic_logs'

urlpatterns = [
    path('', views.log_list, name='list'),
    path('new/', views.log_create, name='create'),
    path('<int:pk>/delete/', views.log_delete, name='delete'),
]
