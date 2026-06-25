from django.db import models

from residents.models import Resident
from visitors.models import Visitor


class Vehicle(models.Model):
    class VehicleType(models.TextChoices):
        RESIDENT = 'RESIDENT', 'Resident'
        VISITOR = 'VISITOR', 'Visitor'
        SERVICE = 'SERVICE', 'Service'

    class VehicleClass(models.TextChoices):
        CAR = 'CAR', 'Car'
        MOTORCYCLE = 'MOTORCYCLE', 'Motorcycle'

    plate_number = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices, default=VehicleType.RESIDENT)
    vehicle_class = models.CharField(max_length=20, choices=VehicleClass.choices, default=VehicleClass.CAR)
    resident_owner = models.ForeignKey(Resident, on_delete=models.SET_NULL, blank=True, null=True, related_name='vehicles')
    visitor_owner = models.ForeignKey(Visitor, on_delete=models.SET_NULL, blank=True, null=True, related_name='vehicles')
    make_model = models.CharField(max_length=80, blank=True)
    color = models.CharField(max_length=40, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('plate_number',)

    def __str__(self):
        return self.plate_number

# Create your models here.
