"""
Appointment (onsite visit date) tests.

These exercise the real HTTP endpoints — not the model layer — because the
adoption workflow bugs documented in docs/QA-REPORT-2026-09-09.md were only
visible through the full request/response flow.
"""
from datetime import timedelta

from django.utils import timezone

from apps.accounts.tests import BaseAPITestCase
from apps.applications.models import Application
from apps.appointments.models import Appointment
from apps.audit.models import AuditLog
from apps.pets.models import Pet


def next_weekday(days_ahead=1):
    """A future date that falls Monday-Friday."""
    day = timezone.localdate() + timedelta(days=days_ahead)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def next_weekend_day(weekday):
    """The next future Saturday (5) or Sunday (6)."""
    day = timezone.localdate() + timedelta(days=1)
    while day.weekday() != weekday:
        day += timedelta(days=1)
    return day


class AppointmentWorkflowTests(BaseAPITestCase):
    """Adopter picks a date; staff/admin confirm or reject that date."""

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(name="Buddy", species="dog", age_months=12, status="pending")
        self.adopter = self.create_user(email="adopter@example.com")
        self.staff = self.create_staff(email="staff@example.com")
        self.application = Application.objects.create(
            adopter=self.adopter, pet=self.pet, status="approved"
        )
        self.visit_date = next_weekday()

    def request_appointment(self, application=None, visit_date=None):
        self.authenticate(self.adopter)
        return self.client.post("/api/appointments/", {
            "application_id": str((application or self.application).id),
            "requested_date": (visit_date or self.visit_date).isoformat(),
        })

    # ----- adopter creates a request -------------------------------------

    def test_adopter_can_request_appointment_for_approved_application(self):
        resp = self.request_appointment()
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["status"], "pending_confirmation")
        self.assertEqual(resp.data["requested_date"], self.visit_date.isoformat())
        self.assertEqual(resp.data["pet_name"], self.pet.name)
        self.assertEqual(resp.data["adopter_email"], self.adopter.email)

        appointment = Appointment.objects.get()
        self.assertEqual(appointment.application, self.application)
        self.assertEqual(appointment.adopter, self.adopter)
        self.assertEqual(appointment.pet, self.pet)
        self.assertTrue(
            AuditLog.objects.filter(
                model_name="Appointment", action="appointment_requested"
            ).exists()
        )

    def test_unapproved_application_cannot_request_appointment(self):
        other_pet = Pet.objects.create(name="Rex", species="dog", age_months=24)
        submitted = Application.objects.create(
            adopter=self.adopter, pet=other_pet, status="submitted"
        )
        resp = self.request_appointment(application=submitted)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_adopter_cannot_request_for_another_adopters_application(self):
        other_adopter = self.create_user(email="other@example.com")
        other_pet = Pet.objects.create(name="Milo", species="cat", age_months=8)
        other_application = Application.objects.create(
            adopter=other_adopter, pet=other_pet, status="approved"
        )
        resp = self.request_appointment(application=other_application)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_saturday_cannot_be_requested(self):
        resp = self.request_appointment(visit_date=next_weekend_day(5))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("requested_date", resp.data)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_sunday_cannot_be_requested(self):
        resp = self.request_appointment(visit_date=next_weekend_day(6))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("requested_date", resp.data)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_past_date_cannot_be_requested(self):
        resp = self.request_appointment(
            visit_date=timezone.localdate() - timedelta(days=3)
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("requested_date", resp.data)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_duplicate_active_request_is_prevented(self):
        self.assertEqual(self.request_appointment().status_code, 201)
        second = self.request_appointment(visit_date=next_weekday(8))
        self.assertEqual(second.status_code, 400)
        self.assertIn("application_id", second.data)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_duplicate_after_confirmation_is_prevented(self):
        first = self.request_appointment()
        self.authenticate(self.staff)
        self.assertEqual(
            self.client.post(f"/api/appointments/{first.data['id']}/approve/").status_code,
            200,
        )
        second = self.request_appointment(visit_date=next_weekday(8))
        self.assertEqual(second.status_code, 400)
        self.assertEqual(Appointment.objects.count(), 1)

    # ----- staff/admin review --------------------------------------------

    def test_staff_sees_pending_request_with_full_context(self):
        appointment = self.request_appointment().data
        self.authenticate(self.staff)
        resp = self.client.get("/api/appointments/", {"status": "pending_confirmation"})
        self.assertEqual(resp.status_code, 200)
        results = resp.data["results"]
        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertEqual(row["id"], appointment["id"])
        self.assertEqual(row["adopter_email"], self.adopter.email)
        self.assertEqual(row["pet_name"], self.pet.name)
        self.assertEqual(row["application"], self.application.id)
        self.assertEqual(row["requested_date"], self.visit_date.isoformat())
        self.assertEqual(row["status"], "pending_confirmation")

    def test_staff_confirms_requested_date(self):
        appointment = self.request_appointment().data
        self.authenticate(self.staff)
        resp = self.client.post(f"/api/appointments/{appointment['id']}/approve/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "confirmed")

        # The adopter sees the confirmed appointment.
        self.authenticate(self.adopter)
        detail = self.client.get(f"/api/appointments/{appointment['id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["status"], "confirmed")

        # In-app notification reuses the existing notification mechanism.
        from apps.notifications.models import Notification
        self.assertTrue(
            Notification.objects.filter(
                user=self.adopter, notification_type="appointment"
            ).exists()
        )

    def test_confirming_twice_is_rejected(self):
        appointment = self.request_appointment().data
        self.authenticate(self.staff)
        self.client.post(f"/api/appointments/{appointment['id']}/approve/")
        resp = self.client.post(f"/api/appointments/{appointment['id']}/approve/")
        self.assertEqual(resp.status_code, 400)

    def test_adopter_cannot_confirm_or_reject(self):
        appointment = self.request_appointment().data
        self.authenticate(self.adopter)
        self.assertEqual(
            self.client.post(f"/api/appointments/{appointment['id']}/approve/").status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                f"/api/appointments/{appointment['id']}/reject/", {"reason": "No"}
            ).status_code,
            403,
        )
        self.assertEqual(Appointment.objects.get().status, "pending_confirmation")

    def test_reject_requires_a_reason(self):
        appointment = self.request_appointment().data
        self.authenticate(self.staff)
        blank = self.client.post(
            f"/api/appointments/{appointment['id']}/reject/", {"reason": "   "}
        )
        self.assertEqual(blank.status_code, 400)
        missing = self.client.post(f"/api/appointments/{appointment['id']}/reject/", {})
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(Appointment.objects.get().status, "pending_confirmation")

    def test_rejected_date_shows_reason_and_adopter_can_pick_another_date(self):
        appointment = self.request_appointment().data
        self.authenticate(self.staff)
        resp = self.client.post(
            f"/api/appointments/{appointment['id']}/reject/",
            {"reason": "Center is fully booked that day."},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "rejected")
        self.assertEqual(resp.data["rejection_reason"], "Center is fully booked that day.")

        # Adopter sees the rejection reason.
        self.authenticate(self.adopter)
        detail = self.client.get(f"/api/appointments/{appointment['id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["rejection_reason"], "Center is fully booked that day.")

        # ...and can submit another date without a new adoption application.
        again = self.request_appointment(visit_date=next_weekday(8))
        self.assertEqual(again.status_code, 201)
        self.assertEqual(again.data["status"], "pending_confirmation")
        self.assertEqual(Appointment.objects.count(), 2)

        # The adoption application is still approved.
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "approved")

    def test_rejected_appointment_cannot_be_confirmed_afterwards(self):
        appointment = self.request_appointment().data
        self.authenticate(self.staff)
        self.client.post(
            f"/api/appointments/{appointment['id']}/reject/", {"reason": "Closed"}
        )
        resp = self.client.post(f"/api/appointments/{appointment['id']}/approve/")
        self.assertEqual(resp.status_code, 400)

    # ----- ownership / isolation -----------------------------------------

    def test_adopter_only_sees_own_appointments(self):
        other_adopter = self.create_user(email="other@example.com")
        other_pet = Pet.objects.create(name="Milo", species="cat", age_months=8)
        other_application = Application.objects.create(
            adopter=other_adopter, pet=other_pet, status="approved"
        )
        self.authenticate(other_adopter)
        other_appointment = self.client.post("/api/appointments/", {
            "application_id": str(other_application.id),
            "requested_date": self.visit_date.isoformat(),
        })
        self.assertEqual(other_appointment.status_code, 201)

        self.request_appointment()
        self.authenticate(self.adopter)
        listing = self.client.get("/api/appointments/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.data["results"]), 1)
        self.assertEqual(listing.data["results"][0]["adopter_email"], self.adopter.email)

        # Direct access to another adopter's appointment is a 404, not a leak.
        detail = self.client.get(f"/api/appointments/{other_appointment.data['id']}/")
        self.assertEqual(detail.status_code, 404)

    def test_anonymous_user_cannot_access_appointments(self):
        self.unauthenticate()
        # DRF's SessionAuthentication is first in DEFAULT_AUTHENTICATION_CLASSES,
        # so an anonymous request is refused with 403 (matching the rest of the
        # project's endpoints, e.g. accounts/tests.py).
        resp = self.client.get("/api/appointments/")
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn("results", resp.data)

    def test_anonymous_user_cannot_create_appointment(self):
        self.unauthenticate()
        resp = self.client.post("/api/appointments/", {
            "application_id": str(self.application.id),
            "requested_date": self.visit_date.isoformat(),
        })
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Appointment.objects.count(), 0)

    # ----- application approval is a separate decision --------------------

    def test_approving_an_application_does_not_create_an_appointment(self):
        pet = Pet.objects.create(name="Luna", species="cat", age_months=18, status="available")
        application = Application.objects.create(
            adopter=self.adopter, pet=pet, status="submitted"
        )
        self.authenticate(self.staff)
        resp = self.client.post(
            f"/api/applications/{application.id}/update-status/", {"status": "approved"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "approved")
        self.assertEqual(Appointment.objects.count(), 0)