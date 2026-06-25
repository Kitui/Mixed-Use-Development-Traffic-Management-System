from django.urls import path

from . import views

app_name = 'vehicles'

urlpatterns = [
    path('', views.vehicle_list, name='list'),
    path('new/', views.vehicle_create, name='create'),
    path('<int:pk>/edit/', views.vehicle_update, name='edit'),
    path('<int:pk>/delete/', views.vehicle_delete, name='delete'),
]
