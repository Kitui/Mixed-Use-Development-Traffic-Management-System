from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from residents.models import CommunityUnit, Resident
from traffic_logs.models import TrafficLog
from vehicles.models import Vehicle
from visitors.models import Visitor


class ReportAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.guard = User.objects.create_user('guard', 'guard@example.com', 'password123')
        self.resident = User.objects.create_user('resident', 'resident@example.com', 'password123')
        UserProfile.objects.create(user=self.guard, role=UserProfile.Role.SECURITY)
        UserProfile.objects.create(user=self.resident, role=UserProfile.Role.RESIDENT)

    def test_security_can_view_reports_and_export_csv(self):
        self.client.force_login(self.guard)

        self.assertEqual(self.client.get(reverse('dashboard:reports')).status_code, 200)
        response = self.client.get(reverse('dashboard:export_logs_csv'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')

    def test_resident_cannot_view_reports(self):
        self.client.force_login(self.resident)

        response = self.client.get(reverse('dashboard:reports'))

        self.assertEqual(response.status_code, 403)

    def test_unit_guard_records_registered_vehicle_unit_movement(self):
        unit = CommunityUnit.objects.create(name='Maisha Makao', unit_type=CommunityUnit.UnitType.RESIDENTIAL)
        resident_record = Resident.objects.create(
            full_name='Demo Resident',
            house_number='A-101',
            phone='0700000000',
            community_unit=unit,
        )
        vehicle = Vehicle.objects.create(
            plate_number='KDA 001A',
            vehicle_type=Vehicle.VehicleType.RESIDENT,
            vehicle_class=Vehicle.VehicleClass.CAR,
            resident_owner=resident_record,
            make_model='Toyota Axio',
            color='White',
        )

        self.client.force_login(self.guard)
        response = self.client.post(reverse('dashboard:record_unit_movement'), {
            'vehicle': vehicle.pk,
            'direction': TrafficLog.Direction.EXIT,
        })

        log = TrafficLog.objects.get(vehicle=vehicle)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(log.resident, resident_record)
        self.assertEqual(log.community_unit, unit)
        self.assertEqual(log.direction, TrafficLog.Direction.EXIT)

    def test_main_gate_guard_records_registered_vehicle_gate_movement(self):
        unit = CommunityUnit.objects.create(name='Coast Cables', unit_type=CommunityUnit.UnitType.COMMERCIAL)
        resident_record = Resident.objects.create(
            full_name='Coast Employee',
            house_number='Reception',
            phone='0710000000',
            community_unit=unit,
        )
        vehicle = Vehicle.objects.create(
            plate_number='KDB 002B',
            vehicle_type=Vehicle.VehicleType.RESIDENT,
            vehicle_class=Vehicle.VehicleClass.MOTORCYCLE,
            resident_owner=resident_record,
            make_model='Bajaj Boxer',
            color='Black',
        )

        self.client.force_login(self.guard)
        response = self.client.post(reverse('dashboard:record_gate_movement'), {
            'vehicle': vehicle.pk,
            'direction': TrafficLog.Direction.EXIT,
            'gate': 'LIMURU_ROAD',
        })

        log = TrafficLog.objects.get(vehicle=vehicle)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(log.checkpoint_type, TrafficLog.CheckpointType.MAIN_GATE)
        self.assertEqual(log.gate, 'LIMURU_ROAD')
        self.assertEqual(log.direction, TrafficLog.Direction.EXIT)

    def test_main_gate_guard_creates_pending_visitor_request(self):
        unit = CommunityUnit.objects.create(name='Maisha Makao', unit_type=CommunityUnit.UnitType.RESIDENTIAL)
        resident_record = Resident.objects.create(
            full_name='Demo Resident',
            house_number='A-101',
            phone='0700000000',
            community_unit=unit,
        )

        self.client.force_login(self.guard)
        response = self.client.post(reverse('dashboard:create_gate_visitor_request'), {
            'guest_type': Visitor.GuestType.VISITOR,
            'full_name': 'Gate Visitor',
            'id_number': 'GV-001',
            'phone': '0722000000',
            'host': resident_record.pk,
            'destination': unit.pk,
            'purpose': 'Visit',
            'main_gate': 'CHUNGA_MALI',
            'vehicle_class': Visitor.VehicleClass.CAR,
            'vehicle_plate': 'KCA 001A',
            'vehicle_make_model': 'Toyota',
            'vehicle_color': 'Silver',
        })

        visitor = Visitor.objects.get(id_number='GV-001')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(visitor.status, Visitor.Status.PENDING)
        self.assertTrue(visitor.alert_sent)
