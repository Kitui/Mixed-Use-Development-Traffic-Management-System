import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from residents.models import CommunityUnit, Resident


class MainGate(models.TextChoices):
    CHUNGA_MALI = 'CHUNGA_MALI', 'Chunga Mali - Ngecha Road'
    NAIROBI_NAKURU = 'NAIROBI_NAKURU', 'Nairobi-Nakuru Highway'
    LIMURU_ROAD = 'LIMURU_ROAD', 'Limuru Road'


class Visitor(models.Model):
    class GuestType(models.TextChoices):
        VISITOR = 'VISITOR', 'Visitor'
        DELIVERY = 'DELIVERY', 'Delivery'
        SERVICE_PROVIDER = 'SERVICE_PROVIDER', 'Service Provider'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Approval'
        APPROVED = 'APPROVED', 'Approved'
        DENIED = 'DENIED', 'Denied'
        ARRIVED_MAIN_GATE = 'ARRIVED_MAIN_GATE', 'Arrived at Main Gate'
        REDIRECTED = 'REDIRECTED', 'Redirected'
        UNIT_CONFIRMED = 'UNIT_CONFIRMED', 'Estate/Company Confirmed'
        CHECKED_IN = 'CHECKED_IN', 'Checked In'
        CHECKOUT_REQUESTED = 'CHECKOUT_REQUESTED', 'Checkout Requested'
        UNIT_EXIT_CONFIRMED = 'UNIT_EXIT_CONFIRMED', 'Released to Main Gate'
        CHECKED_OUT = 'CHECKED_OUT', 'Checked Out'

    class Recurrence(models.TextChoices):
        NONE = 'NONE', 'No repeat'
        DAILY = 'DAILY', 'Daily'
        WEEKLY = 'WEEKLY', 'Weekly'
        MONTHLY = 'MONTHLY', 'Monthly'

    class VehicleClass(models.TextChoices):
        CAR = 'CAR', 'Car'
        MOTORCYCLE = 'MOTORCYCLE', 'Motorcycle'

    guest_type = models.CharField(max_length=30, choices=GuestType.choices, default=GuestType.VISITOR)
    full_name = models.CharField(max_length=120)
    id_number = models.CharField(max_length=50)
    phone = models.CharField(max_length=20)
    host = models.ForeignKey(Resident, on_delete=models.PROTECT, related_name='visitors')
    destination = models.ForeignKey(CommunityUnit, on_delete=models.PROTECT, blank=True, null=True, related_name='visitors')
    purpose = models.CharField(max_length=160)
    company_name = models.CharField(max_length=120, blank=True)
    vehicle_class = models.CharField(max_length=20, choices=VehicleClass.choices, blank=True)
    vehicle_plate = models.CharField(max_length=20, blank=True)
    vehicle_make_model = models.CharField(max_length=80, blank=True)
    vehicle_color = models.CharField(max_length=40, blank=True)
    main_gate = models.CharField(max_length=30, choices=MainGate.choices, blank=True)
    redirected_from = models.ForeignKey(CommunityUnit, on_delete=models.SET_NULL, blank=True, null=True, related_name='redirected_visitors')
    alert_sent = models.BooleanField(default=False)
    expected_arrival = models.DateTimeField(blank=True, null=True)
    expected_departure = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    approval_notes = models.TextField(blank=True)
    incident_flagged = models.BooleanField(default=False)
    incident_reason = models.CharField(max_length=220, blank=True)
    incident_reported_at = models.DateTimeField(blank=True, null=True)
    recurrence = models.CharField(max_length=20, choices=Recurrence.choices, default=Recurrence.NONE)
    recurrence_until = models.DateField(blank=True, null=True)
    qr_token = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.full_name} visiting {self.host.house_number}'

    @property
    def is_inside(self):
        return self.status in {
            self.Status.ARRIVED_MAIN_GATE,
            self.Status.REDIRECTED,
            self.Status.UNIT_CONFIRMED,
            self.Status.CHECKED_IN,
            self.Status.CHECKOUT_REQUESTED,
            self.Status.UNIT_EXIT_CONFIRMED,
        }

    @property
    def is_overdue(self):
        return bool(self.expected_departure and self.is_inside and timezone.now() > self.expected_departure)


class VisitorEvent(models.Model):
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    title = models.CharField(max_length=120)
    note = models.CharField(max_length=220, blank=True)
    status = models.CharField(max_length=30, choices=Visitor.Status.choices, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at',)

    def __str__(self):
        return f'{self.visitor.full_name}: {self.title}'


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='traffic_notifications')
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, blank=True, null=True, related_name='notifications')
    title = models.CharField(max_length=120)
    message = models.CharField(max_length=240)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return self.title


class VisitorAttachment(models.Model):
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name='attachments')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    title = models.CharField(max_length=120)
    document = models.FileField(upload_to='visitor_attachments/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return self.title


class ParkingSlot(models.Model):
    name = models.CharField(max_length=40, unique=True)
    community_unit = models.ForeignKey(CommunityUnit, on_delete=models.SET_NULL, blank=True, null=True, related_name='parking_slots')
    assigned_visitor = models.ForeignKey(Visitor, on_delete=models.SET_NULL, blank=True, null=True, related_name='parking_slots')
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class WatchlistEntry(models.Model):
    class EntryType(models.TextChoices):
        PERSON = 'PERSON', 'Person'
        PLATE = 'PLATE', 'Vehicle Plate'

    entry_type = models.CharField(max_length=20, choices=EntryType.choices)
    value = models.CharField(max_length=120)
    reason = models.CharField(max_length=220)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        unique_together = ('entry_type', 'value')

    def __str__(self):
        return f'{self.get_entry_type_display()}: {self.value}'
