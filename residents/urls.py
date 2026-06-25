from django.urls import path

from . import views

app_name = 'residents'

urlpatterns = [
    path('developments/', views.development_list, name='developments'),
    path('developments/new/', views.development_create, name='development_create'),
    path('developments/<int:pk>/edit/', views.development_update, name='development_edit'),
    path('developments/<int:pk>/delete/', views.development_delete, name='development_delete'),
    path('', views.resident_list, name='list'),
    path('new/', views.resident_create, name='create'),
    path('<int:pk>/edit/', views.resident_update, name='edit'),
    path('<int:pk>/delete/', views.resident_delete, name='delete'),
]
