from django.urls import path

from . import views

app_name = 'visitors'

urlpatterns = [
    path('', views.visitor_list, name='list'),
    path('new/', views.visitor_create, name='create'),
    path('<int:pk>/', views.visitor_detail, name='detail'),
    path('<int:pk>/qr.svg', views.visitor_qr_svg, name='qr_svg'),
    path('<int:pk>/pass/', views.visitor_pass, name='pass'),
    path('<int:pk>/pass.pdf', views.visitor_pass_pdf, name='pass_pdf'),
    path('<int:pk>/sms/', views.visitor_send_sms, name='send_sms'),
    path('<int:pk>/incident/', views.visitor_flag_incident, name='flag_incident'),
    path('<int:pk>/attachments/', views.visitor_upload_attachment, name='upload_attachment'),
    path('<int:pk>/edit/', views.visitor_update, name='edit'),
    path('<int:pk>/delete/', views.visitor_delete, name='delete'),
    path('<int:pk>/approve/', views.visitor_approve, name='approve'),
    path('<int:pk>/deny/', views.visitor_deny, name='deny'),
    path('<int:pk>/alert-host/', views.visitor_alert_host, name='alert_host'),
    path('<int:pk>/main-gate-checkin/', views.visitor_main_gate_checkin, name='main_gate_checkin'),
    path('<int:pk>/unit-checkin/', views.visitor_unit_checkin, name='unit_checkin'),
    path('<int:pk>/confirm-checkin/', views.visitor_confirm_checkin, name='confirm_checkin'),
    path('<int:pk>/request-checkout/', views.visitor_request_checkout, name='request_checkout'),
    path('<int:pk>/unit-release-exit/', views.visitor_unit_release_exit, name='unit_release_exit'),
    path('<int:pk>/main-gate-checkout/', views.visitor_main_gate_checkout, name='main_gate_checkout'),
    path('<int:pk>/redirect/', views.visitor_redirect, name='redirect'),
    path('parking/', views.parking_list, name='parking'),
    path('parking/new/', views.parking_create, name='parking_create'),
    path('parking/<int:pk>/edit/', views.parking_update, name='parking_edit'),
    path('watchlist/', views.watchlist_list, name='watchlist'),
    path('watchlist/new/', views.watchlist_create, name='watchlist_create'),
    path('watchlist/<int:pk>/edit/', views.watchlist_update, name='watchlist_edit'),
]
