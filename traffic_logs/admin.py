from django.contrib import admin

from .models import TrafficLog


@admin.register(TrafficLog)
class TrafficLogAdmin(admin.ModelAdmin):
    list_display = ('checkpoint_type', 'subject_type', 'direction', 'community_unit', 'resident', 'visitor', 'vehicle', 'gate', 'recorded_by', 'recorded_at')
    list_filter = ('checkpoint_type', 'subject_type', 'direction', 'community_unit', 'gate', 'recorded_at')
    search_fields = ('resident__full_name', 'visitor__full_name', 'visitor__vehicle_plate', 'vehicle__plate_number', 'gate', 'community_unit__name')
    autocomplete_fields = ('resident', 'visitor', 'vehicle', 'community_unit', 'recorded_by')

# Register your models here.
