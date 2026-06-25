from django.conf import settings
from django.db import models

from residents.models import CommunityUnit, Resident
from vehicles.models import Vehicle
from visitors.models import MainGate, Visitor


class TrafficLog(models.Model):
    class CheckpointType(models.TextChoices):
        MAIN_GATE = 'MAIN_GATE', 'Main Gate'
        COMMUNITY_UNIT = 'COMMUNITY_UNIT', 'Estate/Company'

    class SubjectType(models.TextChoices):
        RESIDENT = 'RESIDENT', 'Resident'
        VISITOR = 'VISITOR', 'Visitor'
        VEHICLE = 'VEHICLE', 'Vehicle'

    class Direction(models.TextChoices):
        ENTRY = 'ENTRY', 'Entry'
        EXIT = 'EXIT', 'Exit'

    subject_type = models.CharField(max_length=20, choices=SubjectType.choices)
    checkpoint_type = models.CharField(max_length=30, choices=CheckpointType.choices, default=CheckpointType.MAIN_GATE)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    resident = models.ForeignKey(Resident, on_delete=models.SET_NULL, blank=True, null=True)
    visitor = models.ForeignKey(Visitor, on_delete=models.SET_NULL, blank=True, null=True)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, blank=True, null=True)
    gate = models.CharField(max_length=50, choices=MainGate.choices, blank=True, default='')
    community_unit = models.ForeignKey(CommunityUnit, on_delete=models.SET_NULL, blank=True, null=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-recorded_at',)

    def __str__(self):
        checkpoint = self.get_gate_display() if self.gate else self.get_checkpoint_type_display()
        return f'{self.get_direction_display()} at {checkpoint} on {self.recorded_at:%Y-%m-%d %H:%M}'

# Create your models here.
