from django.conf import settings
from django.db import models


class CommunityUnit(models.Model):
    class UnitType(models.TextChoices):
        RESIDENTIAL = 'RESIDENTIAL', 'Residential Estate'
        COMMERCIAL = 'COMMERCIAL', 'Commercial Company'

    name = models.CharField(max_length=120, unique=True)
    unit_type = models.CharField(max_length=20, choices=UnitType.choices)
    contact_phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class Resident(models.Model):
    class PersonType(models.TextChoices):
        RESIDENT = 'RESIDENT', 'Resident'
        EMPLOYEE = 'EMPLOYEE', 'Employee'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    community_unit = models.ForeignKey(CommunityUnit, on_delete=models.PROTECT, blank=True, null=True, related_name='people')
    person_type = models.CharField(max_length=20, choices=PersonType.choices, default=PersonType.RESIDENT)
    full_name = models.CharField(max_length=120)
    house_number = models.CharField(max_length=30, unique=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    emergency_contact = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('house_number', 'full_name')

    def __str__(self):
        return f'{self.full_name} - {self.house_number}'

# Create your models here.
