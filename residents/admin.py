from django.contrib import admin

from .models import CommunityUnit, Resident


@admin.register(CommunityUnit)
class CommunityUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit_type', 'contact_phone', 'is_active')
    list_filter = ('unit_type', 'is_active')
    search_fields = ('name', 'contact_phone')


@admin.register(Resident)
class ResidentAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'person_type', 'community_unit', 'house_number', 'phone', 'email', 'is_active')
    list_filter = ('person_type', 'community_unit', 'is_active')
    search_fields = ('full_name', 'house_number', 'phone', 'email', 'community_unit__name')
    fieldsets = (
        ('Personal Details', {
            'fields': ('community_unit', 'person_type', 'full_name', 'house_number'),
            'description': 'Add the resident, employee, or reception contact to the Tilisi master list.',
        }),
        ('Contact Details', {
            'fields': ('phone', 'email', 'emergency_contact'),
        }),
        ('Record Status', {
            'fields': ('is_active',),
            'description': 'Inactive records remain in historical logs but are removed from active guard selections.',
        }),
    )

# Register your models here.
