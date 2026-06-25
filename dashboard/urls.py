from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('tasks/', views.tasks, name='tasks'),
    path('tasks/unit-movement/', views.record_unit_movement, name='record_unit_movement'),
    path('gate-tasks/', views.gate_tasks, name='gate_tasks'),
    path('gate-tasks/movement/', views.record_gate_movement, name='record_gate_movement'),
    path('gate-tasks/visitor-request/', views.create_gate_visitor_request, name='create_gate_visitor_request'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='notification_read'),
    path('search/', views.global_search, name='search'),
    path('handoff/', views.handoff, name='handoff'),
    path('calendar/', views.expected_calendar, name='calendar'),
    path('board/', views.workflow_board, name='board'),
    path('gates/', views.gate_summary, name='gate_summary'),
    path('bulk-import/', views.bulk_import, name='bulk_import'),
    path('settings/', views.system_settings, name='settings'),
    path('reports/', views.reports, name='reports'),
    path('reports/report.pdf', views.reports_pdf, name='reports_pdf'),
    path('reports/logs.csv', views.export_logs_csv, name='export_logs_csv'),
    path('reports/visitors.csv', views.export_visitors_csv, name='export_visitors_csv'),
    path('reports/vehicles.csv', views.export_vehicles_csv, name='export_vehicles_csv'),
]
