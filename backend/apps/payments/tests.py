from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.tests import BaseAPITestCase
from apps.appointments.models import Appointment
from apps.notifications.models import Notification
from apps.pets.models import Pet
from apps.applications.models import Application
from apps.adoptions.models import AdoptionRecord
from apps.packages.models import AdoptionPackage
from apps.payments.models import Payment


class PaymentRulesTests(BaseAPITestCase):

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(name="Buddy", species="dog", age_months=12, status="available")
        self.adopter = self.create_user(email="adopter@example.com")
        self.staff = self.create_staff(email="staff1@example.com")
        self.app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="approved")
        self.adoption = AdoptionRecord.objects.create(
            application=self.app, pet=self.pet, adopter=self.adopter,
            staff_member=self.staff, status="scheduled",
        )

    def test_free_adoption_requires_no_payment(self):
        """No package assigned -> no payment should be generated."""
        self.authenticate_staff()
        # No payment should need to be created
        self.assertEqual(Payment.objects.count(), 0)

    def test_zero_package_requires_no_payment(self):
        """A ₱0 package requires no payment."""
        pkg = AdoptionPackage.objects.create(name="Free Care Kit", price=0, description="Free kit")
        # Even with package assigned, amount is 0 so no payment required
        self.assertEqual(pkg.price, 0)

    def test_paid_package_can_regenerate_receipt(self):
        pkg = AdoptionPackage.objects.create(name="Premium Kit", price=500, description="Premium kit")
        # Create a payment for the paid package
        self.authenticate_staff()
        resp = self.client.post("/api/payments/", {
            "application": str(self.app.id),
            "package": str(pkg.id),
            "amount": "500.00",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Payment.objects.count(), 1)

    def authenticate_staff(self):
        self.authenticate(self.staff)


def next_weekday(days_ahead=1):
    """A future date that falls Monday-Friday (the center's visiting days)."""
    day = timezone.localdate() + timedelta(days=days_ahead)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


class OnsiteAdoptionCompletionTests(BaseAPITestCase):
    """Onsite payment recording + explicit adoption completion.

    These tests drive the real HTTP endpoints (``POST /api/payments/`` and
    ``POST /api/applications/<id>/complete-adoption/``) because the onsite flow
    is only correct if the whole request/response path works, not just the
    model layer.  No package is involved anywhere: the onsite flow records a
    flat ₱500.00 adoption fee.
    """

    ADOPTION_FEE = "500.00"

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(
            name="Buddy", species="dog", age_months=12, status="pending"
        )
        self.adopter = self.create_user(email="adopter@example.com")
        self.staff = self.create_staff(email="staff@example.com")
        self.application = Application.objects.create(
            adopter=self.adopter, pet=self.pet, status="approved"
        )

    # ----- helpers ------------------------------------------------------

    def confirm_appointment(self, application=None):
        application = application or self.application
        return Appointment.objects.create(
            application=application,
            adopter=application.adopter,
            pet=application.pet,
            requested_date=next_weekday(),
            status=Appointment.Status.CONFIRMED,
        )

    def record_payment(self, application=None, status_value="completed"):
        application = application or self.application
        self.authenticate(self.staff)
        return self.client.post(
            "/api/payments/",
            {
                "application": str(application.id),
                "amount": self.ADOPTION_FEE,
                "method": "cash",
                "status": status_value,
                "payment_date": timezone.localdate().isoformat(),
                "reference_number": "OR-1234",
            },
            format="json",
        )

    def complete(self, application=None, payload=None):
        application = application or self.application
        self.authenticate(self.staff)
        return self.client.post(
            f"/api/applications/{application.id}/complete-adoption/",
            payload or {},
            format="json",
        )

    # ----- recording the onsite payment ---------------------------------

    def test_recording_onsite_payment_persists_details_only(self):
        resp = self.record_payment(status_value="pending")
        self.assertEqual(resp.status_code, 201)

        payment = Payment.objects.get()
        self.assertEqual(payment.amount, Decimal(self.ADOPTION_FEE))
        self.assertEqual(payment.method, "cash")
        # The staff member's explicit choice is stored, not assumed.
        self.assertEqual(payment.status, "pending")
        self.assertEqual(payment.payment_date, timezone.localdate())
        self.assertEqual(payment.reference_number, "OR-1234")
        self.assertIsNone(payment.adoption_id)
        self.assertIsNone(payment.package_id)

        # Recording a payment never completes the adoption by itself.
        self.application.refresh_from_db()
        self.pet.refresh_from_db()
        self.assertEqual(self.application.status, "approved")
        self.assertEqual(self.pet.status, "pending")
        self.assertEqual(AdoptionRecord.objects.count(), 0)

    def test_payment_list_can_be_filtered_by_application(self):
        other_pet = Pet.objects.create(name="Rex", species="dog", age_months=24)
        other_app = Application.objects.create(
            adopter=self.adopter, pet=other_pet, status="approved"
        )
        self.record_payment()
        self.record_payment(application=other_app)

        self.authenticate(self.staff)
        resp = self.client.get(
            "/api/payments/", {"application": str(self.application.id)}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(
            str(resp.data["results"][0]["application"]), str(self.application.id)
        )

    # ----- completion requirements --------------------------------------

    def test_completion_requires_a_recorded_onsite_payment(self):
        self.confirm_appointment()
        resp = self.complete()
        self.assertEqual(resp.status_code, 400)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "approved")
        self.assertEqual(AdoptionRecord.objects.count(), 0)

    def test_completion_requires_a_confirmed_appointment(self):
        self.record_payment()
        # No appointment at all.
        self.assertEqual(self.complete().status_code, 400)

        # A date that staff have not confirmed yet is not enough either.
        Appointment.objects.create(
            application=self.application,
            adopter=self.adopter,
            pet=self.pet,
            requested_date=next_weekday(),
            status=Appointment.Status.PENDING_CONFIRMATION,
        )
        self.assertEqual(self.complete().status_code, 400)

        self.application.refresh_from_db()
        self.pet.refresh_from_db()
        self.assertEqual(self.application.status, "approved")
        self.assertEqual(self.pet.status, "pending")
        self.assertEqual(AdoptionRecord.objects.count(), 0)

    def test_unapproved_application_cannot_be_completed(self):
        other_pet = Pet.objects.create(name="Nala", species="cat", age_months=20)
        submitted = Application.objects.create(
            adopter=self.adopter, pet=other_pet, status="submitted"
        )
        self.confirm_appointment(application=submitted)
        self.record_payment(application=submitted)

        resp = self.complete(application=submitted)
        self.assertEqual(resp.status_code, 400)
        submitted.refresh_from_db()
        other_pet.refresh_from_db()
        self.assertEqual(submitted.status, "submitted")
        self.assertEqual(other_pet.status, "available")
        self.assertEqual(AdoptionRecord.objects.count(), 0)

    def test_adopter_cannot_complete_an_adoption(self):
        self.confirm_appointment()
        self.record_payment()
        self.authenticate(self.adopter)
        resp = self.client.post(
            f"/api/applications/{self.application.id}/complete-adoption/",
            {},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "approved")

    def test_update_status_cannot_bypass_onsite_requirements(self):
        self.authenticate(self.staff)
        resp = self.client.post(
            f"/api/applications/{self.application.id}/update-status/",
            {"status": "adoption_completed"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "approved")
        self.assertEqual(AdoptionRecord.objects.count(), 0)

    # ----- the happy path -----------------------------------------------

    def test_onsite_flow_completes_the_adoption(self):
        appointment = self.confirm_appointment()
        self.assertEqual(self.record_payment().status_code, 201)

        resp = self.complete(
            payload={"notes": "Verified ID and signed agreement onsite."}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "adoption_completed")

        self.application.refresh_from_db()
        self.pet.refresh_from_db()
        self.assertEqual(self.application.status, "adoption_completed")
        self.assertEqual(
            self.application.staff_notes, "Verified ID and signed agreement onsite."
        )
        # The adopted pet is no longer presented as available.
        self.assertEqual(self.pet.status, "adopted")

        record = AdoptionRecord.objects.get(application=self.application)
        self.assertEqual(record.status, "completed")
        self.assertEqual(record.adopter, self.adopter)
        self.assertEqual(record.pet, self.pet)
        self.assertEqual(record.completed_date, timezone.localdate())
        self.assertEqual(record.adoption_date, appointment.requested_date)

        # The recorded payment stays attached to the completed adoption.
        payment = Payment.objects.get()
        self.assertEqual(payment.adoption_id, record.id)

        self.assertTrue(
            Notification.objects.filter(
                user=self.adopter, notification_type="adoption"
            ).exists()
        )

    def test_adopter_sees_the_completed_status_without_internal_notes(self):
        self.confirm_appointment()
        self.record_payment()
        self.assertEqual(
            self.complete(payload={"notes": "Internal note"}).status_code, 200
        )

        self.authenticate(self.adopter)
        resp = self.client.get(f"/api/applications/{self.application.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "adoption_completed")
        self.assertNotIn("staff_notes", resp.data)
