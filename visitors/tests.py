from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from residents.models import CommunityUnit, Resident
from traffic_logs.models import TrafficLog
from .models import Visitor


class VisitorWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'password123')
        self.guard = User.objects.create_user('guard', 'guard@example.com', 'password123')
        self.resident_user = User.objects.create_user('resident', 'resident@example.com', 'password123')
        self.other_resident_user = User.objects.create_user('other', 'other@example.com', 'password123')

        UserProfile.objects.create(user=self.guard, role=UserProfile.Role.SECURITY)
        UserProfile.objects.create(user=self.resident_user, role=UserProfile.Role.RESIDENT)
        UserProfile.objects.create(user=self.other_resident_user, role=UserProfile.Role.RESIDENT)
        self.unit = CommunityUnit.objects.create(
            name='Maisha Makao',
            unit_type=CommunityUnit.UnitType.RESIDENTIAL,
        )

        self.resident = Resident.objects.create(
            user=self.resident_user,
            community_unit=self.unit,
            full_name='Demo Resident',
            house_number='A-101',
            phone='0700000000',
        )
        self.other_resident = Resident.objects.create(
            user=self.other_resident_user,
            full_name='Other Resident',
            house_number='B-202',
            phone='0711111111',
        )

    def test_resident_can_approve_only_own_visitor(self):
        own_visitor = Visitor.objects.create(
            full_name='Own Visitor',
            id_number='OWN-1',
            phone='0722222222',
            host=self.resident,
            purpose='Visit',
        )
        other_visitor = Visitor.objects.create(
            full_name='Other Visitor',
            id_number='OTH-1',
            phone='0733333333',
            host=self.other_resident,
            purpose='Visit',
        )

        self.client.force_login(self.resident_user)
        response = self.client.post(reverse('visitors:approve', args=[own_visitor.pk]))
        own_visitor.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(own_visitor.status, Visitor.Status.APPROVED)

        response = self.client.post(reverse('visitors:approve', args=[other_visitor.pk]))
        other_visitor.refresh_from_db()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(other_visitor.status, Visitor.Status.PENDING)

    def test_security_log_updates_approved_visitor_status(self):
        visitor = Visitor.objects.create(
            full_name='Approved Visitor',
            id_number='APP-1',
            phone='0744444444',
            host=self.resident,
            purpose='Visit',
            status=Visitor.Status.APPROVED,
        )

        self.client.force_login(self.guard)
        entry_response = self.client.post(reverse('traffic_logs:create'), {
            'checkpoint_type': TrafficLog.CheckpointType.MAIN_GATE,
            'subject_type': TrafficLog.SubjectType.VISITOR,
            'direction': TrafficLog.Direction.ENTRY,
            'visitor': visitor.pk,
            'gate': 'CHUNGA_MALI',
            'notes': 'Entry approved',
        })
        visitor.refresh_from_db()

        self.assertEqual(entry_response.status_code, 302)
        self.assertEqual(visitor.status, Visitor.Status.ARRIVED_MAIN_GATE)

        unit_entry_response = self.client.post(reverse('traffic_logs:create'), {
            'checkpoint_type': TrafficLog.CheckpointType.COMMUNITY_UNIT,
            'subject_type': TrafficLog.SubjectType.VISITOR,
            'direction': TrafficLog.Direction.ENTRY,
            'visitor': visitor.pk,
            'gate': 'CHUNGA_MALI',
            'community_unit': self.unit.pk,
            'notes': 'Unit check-in',
        })
        visitor.refresh_from_db()

        self.assertEqual(unit_entry_response.status_code, 302)
        self.assertEqual(visitor.status, Visitor.Status.UNIT_CONFIRMED)

        self.client.force_login(self.resident_user)
        confirm_response = self.client.post(reverse('visitors:confirm_checkin', args=[visitor.pk]))
        visitor.refresh_from_db()

        self.assertEqual(confirm_response.status_code, 302)
        self.assertEqual(visitor.status, Visitor.Status.CHECKED_IN)

        exit_response = self.client.post(reverse('visitors:request_checkout', args=[visitor.pk]))
        visitor.refresh_from_db()

        self.assertEqual(exit_response.status_code, 302)
        self.assertEqual(visitor.status, Visitor.Status.CHECKOUT_REQUESTED)

    def test_gate_action_workflow_updates_statuses_and_logs(self):
        visitor = Visitor.objects.create(
            full_name='Workflow Visitor',
            id_number='FLOW-1',
            phone='0755555555',
            host=self.resident,
            destination=self.unit,
            purpose='Visit',
        )

        self.client.force_login(self.guard)
        alert_response = self.client.post(reverse('visitors:alert_host', args=[visitor.pk]))
        visitor.refresh_from_db()
        self.assertEqual(alert_response.status_code, 302)
        self.assertTrue(visitor.alert_sent)

        self.client.force_login(self.resident_user)
        approve_response = self.client.post(reverse('visitors:approve', args=[visitor.pk]))
        visitor.refresh_from_db()
        self.assertEqual(approve_response.status_code, 302)
        self.assertEqual(visitor.status, Visitor.Status.APPROVED)

        self.client.force_login(self.guard)
        main_gate_response = self.client.post(reverse('visitors:main_gate_checkin', args=[visitor.pk]))
        visitor.refresh_from_db()
        self.assertEqual(main_gate_response.status_code, 302)
        self.assertEqual(visitor.status, Visitor.Status.ARRIVED_MAIN_GATE)

        unit_response = self.client.post(reverse('visitors:unit_checkin', args=[visitor.pk]))
        visitor.refresh_from_db()
        self.assertEqual(unit_response.status_code, 302)
        self.assertEqual(visitor.status, Visitor.Status.UNIT_CONFIRMED)

        self.client.force_login(self.resident_user)
        confirm_response = self.client.post(reverse('visitors:confirm_checkin', args=[visitor.pk]))
        visitor.refresh_from_db()
        self.assertEqual(confirm_response.status_code, 302)
        self.assertEqual(visitor.status, Visitor.Status.CHECKED_IN)

        checkout_response = self.client.post(reverse('visitors:request_checkout', args=[visitor.pk]))
        visitor.refresh_from_db()
        self.assertEqual(checkout_response.status_code, 302)
        self.assertEqual(visitor.status, Visitor.Status.CHECKOUT_REQUESTED)

        self.client.force_login(self.guard)
        release_response = self.client.post(reverse('visitors:unit_release_exit', args=[visitor.pk]))
        visitor.refresh_from_db()
        self.assertEqual(release_response.status_code, 302)
        self.assertEqual(visitor.status, Visitor.Status.UNIT_EXIT_CONFIRMED)

        final_checkout_response = self.client.post(reverse('visitors:main_gate_checkout', args=[visitor.pk]))
        visitor.refresh_from_db()
        self.assertEqual(final_checkout_response.status_code, 302)
        self.assertEqual(visitor.status, Visitor.Status.CHECKED_OUT)
        self.assertEqual(TrafficLog.objects.filter(visitor=visitor).count(), 5)

    def test_resident_created_booking_is_preapproved(self):
        self.client.force_login(self.resident_user)
        response = self.client.post(reverse('visitors:create'), {
            'guest_type': Visitor.GuestType.VISITOR,
            'full_name': 'Prebooked Visitor',
            'id_number': 'PRE-1',
            'phone': '0766666666',
            'purpose': 'Visit',
            'vehicle_class': Visitor.VehicleClass.CAR,
            'vehicle_plate': 'KAA 123A',
            'vehicle_make_model': 'Toyota',
            'vehicle_color': 'White',
            'recurrence': Visitor.Recurrence.NONE,
        })

        visitor = Visitor.objects.get(id_number='PRE-1')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(visitor.status, Visitor.Status.APPROVED)
        self.assertEqual(visitor.destination, self.unit)
