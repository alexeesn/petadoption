from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.adoptions.models import AdoptionRecord
from apps.applications.models import Application
from apps.payments.models import Payment
from apps.pets.models import Pet
from .models import Appointment, RescheduleRequest
from .tests import next_weekday


class FollowupConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.staff = User.objects.create_user(email="race-staff@example.test", role="staff")
        self.adopter = User.objects.create_user(email="race-adopter@example.test")
        self.pet = Pet.objects.create(name="Race pet", species="cat", age_years=1, status="pending")
        self.app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="approved")
        self.appointment = Appointment.objects.create(
            application=self.app, adopter=self.adopter, pet=self.pet, status="confirmed",
            requested_date=timezone.localdate() - timedelta(days=7),
        )
        self.record = AdoptionRecord.objects.create(
            application=self.app, adopter=self.adopter, pet=self.pet, appointment=self.appointment,
            adoption_date=self.appointment.requested_date,
        )

    def request(self):
        return RescheduleRequest.objects.create(
            application=self.app, appointment=self.appointment, original_date=self.appointment.requested_date,
            requested_date=next_weekday(8), reason="Please reschedule",
        )

    def race(self, actions):
        barrier = Barrier(2)

        def post(action):
            user, url, data = action
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(user=user)
                barrier.wait(timeout=10)
                return client.post(url, data, format="json").status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(post, actions, timeout=45))

    @skipUnlessDBFeature("has_select_for_update")
    def test_simultaneous_requests_create_only_one_pending_row(self):
        url = f"/api/appointments/{self.appointment.pk}/request-reschedule/"
        results = self.race([
            (self.adopter, url, {"requested_date": next_weekday(days).isoformat(), "reason": "Date change"})
            for days in (8, 15)
        ])
        self.assertEqual(sorted(results), [201, 400])
        self.assertEqual(RescheduleRequest.objects.count(), 1)

    @skipUnlessDBFeature("has_select_for_update")
    def test_approve_and_reject_cannot_both_win(self):
        request = self.request()
        prefix = f"/api/appointments/reschedule-requests/{request.pk}"
        results = self.race([
            (self.staff, f"{prefix}/approve/", {"confirmed": True}),
            (self.staff, f"{prefix}/reject/", {"confirmed": True, "reason": "Full"}),
        ])
        self.assertEqual(sorted(results), [200, 400])
        request.refresh_from_db()
        self.assertIn(request.status, ["approved", "rejected"])
        self.assertEqual(Appointment.objects.filter(status="confirmed").count(), 1)
        self.assertEqual(AdoptionRecord.objects.count(), 1)

    @skipUnlessDBFeature("has_select_for_update")
    def test_cancellation_and_approval_leave_no_active_booking_for_closed_application(self):
        request = self.request()
        payment = Payment.objects.create(application=self.app, amount="500.00", status="completed")
        results = self.race([
            (self.staff, f"/api/adoptions/{self.record.pk}/cancel/", {"confirmed": True, "reason": "Withdrew"}),
            (self.staff, f"/api/appointments/reschedule-requests/{request.pk}/approve/", {"confirmed": True}),
        ])
        self.assertEqual(results[0], 200)
        self.assertIn(results[1], [200, 400])
        self.app.refresh_from_db()
        self.record.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(self.app.status, "cancelled")
        self.assertEqual(self.record.status, "cancelled")
        self.assertEqual(payment.status, "completed")
        self.assertFalse(Appointment.objects.filter(status__in=Appointment.ACTIVE_STATUSES).exists())
        self.assertFalse(RescheduleRequest.objects.filter(status="pending").exists())
        self.assertEqual(AdoptionRecord.objects.count(), 1)

    @skipUnlessDBFeature("has_select_for_update")
    def test_no_show_and_handover_cannot_leave_completed_adoption_with_no_show(self):
        Payment.objects.create(application=self.app, amount="500.00", status="completed")
        results = self.race([
            (self.staff, f"/api/appointments/{self.appointment.pk}/mark-no-show/", {"confirmed": True, "reason": "Absent"}),
            (self.staff, f"/api/applications/{self.app.pk}/complete-adoption/", {"confirmed": True}),
        ])
        self.assertEqual(sorted(results), [200, 400])
        self.app.refresh_from_db()
        self.record.refresh_from_db()
        self.appointment.refresh_from_db()
        if self.record.status == "completed":
            self.assertEqual(self.appointment.status, "confirmed")
            self.assertEqual(self.app.status, "adoption_completed")
        else:
            self.assertEqual(self.appointment.status, "no_show")
            self.assertEqual(self.app.status, "approved")
            self.assertEqual(self.record.status, "scheduled")

    @skipUnlessDBFeature("has_select_for_update")
    def test_cancellation_and_completion_are_mutually_exclusive(self):
        Payment.objects.create(application=self.app, amount="500.00", status="completed")
        results = self.race([
            (self.staff, f"/api/adoptions/{self.record.pk}/cancel/", {"confirmed": True, "reason": "Withdrew"}),
            (self.staff, f"/api/applications/{self.app.pk}/complete-adoption/", {"confirmed": True}),
        ])
        self.assertEqual(sorted(results), [200, 400])
        self.app.refresh_from_db()
        self.record.refresh_from_db()
        self.pet.refresh_from_db()
        if self.record.status == "completed":
            self.assertEqual(self.app.status, "adoption_completed")
            self.assertEqual(self.pet.status, "adopted")
        else:
            self.assertEqual(self.record.status, "cancelled")
            self.assertEqual(self.app.status, "cancelled")
            self.assertEqual(self.pet.status, "available")
