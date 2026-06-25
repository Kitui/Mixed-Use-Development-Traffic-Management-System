from django.contrib import admin

from .models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('plate_number', 'vehicle_type', 'vehicle_class', 'resident_owner', 'visitor_owner', 'make_model', 'color', 'is_active')
    list_filter = ('vehicle_type', 'vehicle_class', 'is_active')
    search_fields = ('plate_number', 'make_model', 'color', 'resident_owner__full_name', 'visitor_owner__full_name')
    autocomplete_fields = ('resident_owner', 'visitor_owner')
    fieldsets = (
        ('Vehicle Details', {
            'fields': ('plate_number', 'vehicle_type', 'vehicle_class', 'make_model', 'color'),
            'description': 'Register cars and motorcycles used by residents, employees, visitors, and service providers.',
        }),
        ('Ownership', {
            'fields': ('resident_owner', 'visitor_owner'),
            'description': 'Select either a resident / employee owner or a visitor owner depending on the vehicle type.',
        }),
        ('Record Status', {
            'fields': ('is_active',),
            'description': 'Inactive vehicles remain in records but are excluded from active movement selection.',
        }),
    )

# Register your models here.
