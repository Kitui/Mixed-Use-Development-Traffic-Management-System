from django.contrib import admin

from .models import SystemSettings


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('estate_name', 'contact_phone', 'contact_email', 'default_theme', 'updated_at')
