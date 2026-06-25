from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        RESIDENT = 'RESIDENT', 'Resident'
        SECURITY = 'SECURITY', 'Security Guard'
        MAIN_GATE_GUARD = 'MAIN_GATE_GUARD', 'Main Gate Guard'
        UNIT_GUARD = 'UNIT_GUARD', 'Estate/Company Guard'
        RECEPTIONIST = 'RECEPTIONIST', 'Company Receptionist'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.RESIDENT)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f'{self.user.get_username()} ({self.get_role_display()})'

# Create your models here.
