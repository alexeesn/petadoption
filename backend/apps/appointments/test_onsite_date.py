"""HTTP regressions: a future visit cannot record money or finalize handover."""
from datetime import date, datetime, timezone as dt_timezone
from unittest.mock import patch

from django.utils import timezone

from apps.accounts.tests import BaseAPITestCase
from apps.adoptions.models import AdoptionRecord
from apps.applications.models import Application
from apps.audit.models import AuditLog
from apps.notifications.models import Notification
from apps.payments.models import Payment
from apps.pets.models import Pet
from .models import Appointment


class OnsiteAppointmentDateTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.staff = self.create_staff(email="onsite-date-staff@example.test")
        self.adopter = self.create_user(email="onsite-date-adopter@example.test")
        self.pet = Pet.objects.create(name="Visit Date Buddy", species="dog", age_years=2, status="pending")
        self.app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="approved")
        self.appointment = Appointment.objects.create(
            application=self.app, pet=self.pet, adopter=self.adopter,
            requested_date=date(2026, 10, 28), status="confirmed",
        )
        self.record = AdoptionRecord.objects.create(
            application=self.app, pet=self.pet, adopter=self.adopter,
            appointment=self.appointment, adoption_date=self.appointment.requested_date,
        )
        self.authenticate(self.staff)
        clock_patch = patch("django.utils.timezone.now", return_value=datetime(2026, 10, 27, 4, tzinfo=dt_timezone.utc))
        self.clock = clock_patch.start()
        self.addCleanup(clock_patch.stop)

    def record_payment(self, application_route=False, **overrides):
        url = f"/api/applications/{self.app.pk}/record-payment/" if application_route else "/api/payments/record-onsite/"
        return self.client.post(url, {
            "application": str(self.app.pk), "payment_received": True, **overrides,
        }, format="json")

    def complete(self, action="complete-adoption"):
        return self.client.post(f"/api/applications/{self.app.pk}/{action}/", {
            "confirmed": True, "status": "adoption_completed",
        }, format="json")

    def snapshot(self):
        return {model.__name__: list(model.objects.order_by("pk").values()) for model in (
            Application, AdoptionRecord, Appointment, Pet, Payment, AuditLog, Notification,
        )}

    def test_future_visit_blocks_every_payment_create_route_without_side_effects(self):
        before = self.snapshot()
        for application_route in (False, True):
            response = self.record_payment(application_route, payment_date="2026-10-28")
            self.assertEqual(response.status_code, 400)
            self.assertIn("2026-10-28", response.data["error"])
        response = self.client.post("/api/payments/", {
            "application": str(self.app.pk), "amount": "500.00", "status": "pending",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.snapshot(), before)

    def test_future_visit_blocks_completion_even_when_legacy_payment_is_already_paid(self):
        Payment.objects.create(application=self.app, amount="500.00", status="completed")
        before = self.snapshot()
        for action in ("complete-adoption", "confirm-turnover", "update-status"):
            response = self.complete(action)
            self.assertEqual(response.status_code, 400, response.data)
        response = self.client.patch(f"/api/adoptions/{self.record.pk}/", {
            "status": "completed", "confirmed": True,
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.snapshot(), before)

    def test_summary_application_and_adoption_expose_the_same_future_date_gate(self):
        Payment.objects.create(application=self.app, amount="500.00", status="completed")
        urls = [
            f"/api/applications/{self.app.pk}/payment-summary/",
            f"/api/applications/{self.app.pk}/",
            f"/api/adoptions/{self.record.pk}/",
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.data["onsite_visit"]["date_reached"])
            self.assertEqual(response.data["onsite_visit"]["appointment_date"], "2026-10-28")
            self.assertIn("Philippine time", response.data["onsite_visit"]["message"])
            if "turnover_eligible" in response.data:
                self.assertFalse(response.data["turnover_eligible"])
        self.assertFalse(self.client.get(urls[0]).data["can_record_payment"])
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, "scheduled")

    def test_payment_and_completion_unlock_at_philippine_midnight(self):
        self.clock.return_value = datetime(2026, 10, 27, 15, 59, 59, tzinfo=dt_timezone.utc)
        self.assertEqual(self.record_payment().status_code, 400)
        self.clock.return_value = datetime(2026, 10, 27, 16, 0, tzinfo=dt_timezone.utc)
        with timezone.override("America/New_York"):
            response = self.record_payment()
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data["payment_date"], "2026-10-28")
            self.assertTrue(self.client.get(f"/api/applications/{self.app.pk}/payment-summary/").data["turnover_eligible"])
            self.assertEqual(self.complete().status_code, 200)
        self.record.refresh_from_db()
        self.pet.refresh_from_db()
        self.assertEqual(self.record.status, "completed")
        self.assertEqual(self.record.completed_date, date(2026, 10, 28))
        self.assertEqual(self.pet.status, "adopted")

    def test_payment_date_cannot_precede_visit_or_claim_future_receipt(self):
        self.clock.return_value = datetime(2026, 10, 28, 4, tzinfo=dt_timezone.utc)
        for payment_date in ("2026-10-27", "2026-10-29", "not-a-date"):
            with self.subTest(payment_date=payment_date):
                self.assertEqual(self.record_payment(payment_date=payment_date).status_code, 400)
        self.assertFalse(Payment.objects.exists())
        self.assertEqual(self.record_payment(True, payment_date="2026-10-28").status_code, 201)

    def test_later_recording_is_allowed_while_appointment_remains_confirmed(self):
        self.clock.return_value = datetime(2026, 10, 29, 4, tzinfo=dt_timezone.utc)
        self.assertEqual(self.record_payment(payment_date="2026-10-28").status_code, 201)
        self.assertEqual(self.complete().status_code, 200)

    def test_missing_or_nonconfirmed_appointment_blocks_onsite_actions(self):
        self.clock.return_value = datetime(2026, 10, 28, 4, tzinfo=dt_timezone.utc)
        for appointment_status in ("pending_confirmation", "rejected", "no_show", "rescheduled", "cancelled"):
            self.appointment.status = appointment_status
            self.appointment.save(update_fields=["status"])
            self.assertEqual(self.record_payment().status_code, 400)
            self.assertEqual(self.complete().status_code, 400)
        self.record.appointment = None
        self.record.save(update_fields=["appointment"])
        self.appointment.delete()
        self.assertEqual(self.record_payment().status_code, 400)
        self.assertFalse(Payment.objects.exists())

    def test_approved_reschedule_relocks_completion_until_the_new_date(self):
        self.clock.return_value = datetime(2026, 10, 28, 4, tzinfo=dt_timezone.utc)
        self.assertEqual(self.record_payment().status_code, 201)
        self.authenticate(self.adopter)
        response = self.client.post(f"/api/appointments/{self.appointment.pk}/request-reschedule/", {
            "requested_date": "2026-10-29", "reason": "Need a later visit",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.authenticate(self.staff)
        response = self.client.post(f"/api/appointments/reschedule-requests/{response.data['id']}/approve/", {
            "confirmed": True,
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.complete().status_code, 400)
        summary = self.client.get(f"/api/applications/{self.app.pk}/payment-summary/").data
        self.assertEqual(summary["onsite_visit"]["appointment_date"], "2026-10-29")
        self.assertFalse(summary["turnover_eligible"])
        self.assertTrue(summary["is_fee_paid"])
        self.assertEqual(Payment.objects.count(), 1)
