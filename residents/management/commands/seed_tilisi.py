from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import UserProfile
from residents.models import CommunityUnit, Resident
from vehicles.models import Vehicle


class Command(BaseCommand):
    help = 'Create Tilisi prototype units and demo users.'

    def handle(self, *args, **options):
        maisha, _ = CommunityUnit.objects.update_or_create(
            name='Maisha Makao',
            defaults={'unit_type': CommunityUnit.UnitType.RESIDENTIAL, 'contact_phone': '0700000000'},
        )
        coast, _ = CommunityUnit.objects.update_or_create(
            name='Coast Cables',
            defaults={'unit_type': CommunityUnit.UnitType.COMMERCIAL, 'contact_phone': '0710000000'},
        )

        User = get_user_model()
        admin, _ = User.objects.get_or_create(username='admin', defaults={'email': 'admin@example.com'})
        if not admin.is_superuser:
            admin.is_staff = True
            admin.is_superuser = True
        admin.set_password('admin12345')
        admin.save()

        guard, _ = User.objects.get_or_create(username='guard', defaults={'email': 'guard@example.com'})
        guard.set_password('guard12345')
        guard.save()
        UserProfile.objects.update_or_create(user=guard, defaults={'role': UserProfile.Role.MAIN_GATE_GUARD})

        unit_guard, _ = User.objects.get_or_create(username='unitguard', defaults={'email': 'unitguard@example.com'})
        unit_guard.set_password('unitguard12345')
        unit_guard.save()
        UserProfile.objects.update_or_create(user=unit_guard, defaults={'role': UserProfile.Role.UNIT_GUARD})

        resident_user, _ = User.objects.get_or_create(username='resident', defaults={'email': 'resident@example.com'})
        resident_user.set_password('resident12345')
        resident_user.save()
        UserProfile.objects.update_or_create(user=resident_user, defaults={'role': UserProfile.Role.RESIDENT})
        Resident.objects.update_or_create(
            user=resident_user,
            defaults={
                'community_unit': maisha,
                'person_type': Resident.PersonType.RESIDENT,
                'full_name': 'Demo Resident',
                'house_number': 'A-101',
                'phone': '0700000000',
            },
        )
        demo_resident = Resident.objects.get(user=resident_user)
        Vehicle.objects.update_or_create(
            plate_number='KDA 001A',
            defaults={
                'vehicle_type': Vehicle.VehicleType.RESIDENT,
                'vehicle_class': Vehicle.VehicleClass.CAR,
                'resident_owner': demo_resident,
                'make_model': 'Toyota Axio',
                'color': 'White',
                'is_active': True,
            },
        )

        receptionist, _ = User.objects.get_or_create(username='reception', defaults={'email': 'reception@example.com'})
        receptionist.set_password('reception12345')
        receptionist.save()
        UserProfile.objects.update_or_create(user=receptionist, defaults={'role': UserProfile.Role.RECEPTIONIST})
        Resident.objects.update_or_create(
            user=receptionist,
            defaults={
                'community_unit': coast,
                'person_type': Resident.PersonType.EMPLOYEE,
                'full_name': 'Coast Cables Reception',
                'house_number': 'Reception',
                'phone': '0710000000',
            },
        )

        self.stdout.write(self.style.SUCCESS('Tilisi prototype data created.'))
