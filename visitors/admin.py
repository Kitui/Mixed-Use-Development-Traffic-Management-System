from django.contrib import admin

from .models import Notification, ParkingSlot, Visitor, VisitorAttachment, VisitorEvent, WatchlistEntry


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'guest_type',
        'id_number',
        'phone',
        'destination',
        'host',
        'main_gate',
        'vehicle_class',
        'vehicle_plate',
        'status',
        'expected_arrival',
        'expected_departure',
        'incident_flagged',
        'created_at',
    )
    list_filter = ('guest_type', 'status', 'vehicle_class', 'main_gate', 'destination', 'incident_flagged', 'created_at')
    search_fields = (
        'full_name',
        'id_number',
        'phone',
        'host__full_name',
        'host__house_number',
        'destination__name',
        'vehicle_plate',
        'incident_reason',
    )
    autocomplete_fields = ('host', 'destination', 'redirected_from')


@admin.register(VisitorEvent)
class VisitorEventAdmin(admin.ModelAdmin):
    list_display = ('visitor', 'title', 'status', 'actor', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('visitor__full_name', 'title', 'note', 'actor__username')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'visitor', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('user__username', 'title', 'message', 'visitor__full_name')


@admin.register(VisitorAttachment)
class VisitorAttachmentAdmin(admin.ModelAdmin):
    list_display = ('visitor', 'title', 'uploaded_by', 'created_at')
    search_fields = ('visitor__full_name', 'title', 'uploaded_by__username')


@admin.register(ParkingSlot)
class ParkingSlotAdmin(admin.ModelAdmin):
    list_display = ('name', 'community_unit', 'assigned_visitor', 'is_active')
    list_filter = ('is_active', 'community_unit')
    search_fields = ('name', 'assigned_visitor__full_name', 'notes')


@admin.register(WatchlistEntry)
class WatchlistEntryAdmin(admin.ModelAdmin):
    list_display = ('entry_type', 'value', 'reason', 'is_active', 'created_by', 'created_at')
    list_filter = ('entry_type', 'is_active')
    search_fields = ('value', 'reason', 'created_by__username')

# Register your models here.
