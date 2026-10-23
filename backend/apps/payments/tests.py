from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.tests import BaseAPITestCase
from apps.appointments.models import Appointment
from apps.appointments.testing import OnsiteFlowTestCase, visit_on
from apps.notifications.models import Notification
from apps.pets.models import Pet
from apps.applications.models import Application
from apps.adoptions.models import AdoptionRecord
from apps.packages.models import AdoptionPackage
from apps.payments.models import Payment


class PaymentRulesTests(OnsiteFlowTestCase):

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(name="Buddy", species="dog", age_years=1, status="available")
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
        visit_on(self.app, timezone.localdate())
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


class OnsiteAdoptionCompletionTests(OnsiteFlowTestCase):
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
            name="Buddy", species="dog", age_years=1, status="pending"
        )
        self.adopter = self.create_user(email="adopter@example.com")
        self.staff = self.create_staff(email="staff@example.com")
        self.application = Application.objects.create(
            adopter=self.adopter, pet=self.pet, status="approved"
        )

    # ----- helpers ------------------------------------------------------

    def confirm_appointment(self, application=None):
        application = application or self.application
        return visit_on(application, timezone.localdate())

    def record_payment(self, application=None):
        """Record the onsite fee through the canonical staff-only endpoint."""
        application = application or self.application
        self.confirm_appointment(application)
        self.authenticate(self.staff)
        return self.client.post(
            "/api/payments/record-onsite/",
            {
                "application": str(application.id),
                "amount": self.ADOPTION_FEE,
                "method": "cash",
                "payment_received": True,
                "payment_date": timezone.localdate().isoformat(),
                "reference_number": "OR-1234",
            },
            format="json",
        )

    def complete(self, application=None, payload=None):
        application = application or self.application
        self.authenticate(self.staff)
        if payload is None:
            payload = {"confirmed": True}
        return self.client.post(
            f"/api/applications/{application.id}/complete-adoption/",
            payload,
            format="json",
        )

    # ----- recording the onsite payment ---------------------------------

    def test_recording_onsite_payment_persists_details_only(self):
        """The canonical onsite flow stores the payment without completing the
        adoption by itself; the backend forces status=completed and generates
        the receipt number server-side."""
        resp = self.record_payment()
        self.assertEqual(resp.status_code, 201)

        payment = Payment.objects.get()
        self.assertEqual(payment.amount, Decimal(self.ADOPTION_FEE))
        self.assertEqual(payment.method, "cash")
        # status is decided by the canonical flow (money received), never by
        # the client.
        self.assertEqual(payment.status, "completed")
        self.assertTrue(payment.receipt_number.startswith("REC-"))
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
        other_pet = Pet.objects.create(name="Rex", species="dog", age_years=2)
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
        # Historical paid data must not bypass a missing confirmed visit.
        Payment.objects.create(application=self.application, amount="500.00", status="completed")
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
        other_pet = Pet.objects.create(name="Nala", species="cat", age_years=1)
        submitted = Application.objects.create(
            adopter=self.adopter, pet=other_pet, status="submitted"
        )
        self.confirm_appointment(application=submitted)
        # Preserve the completion safeguard even for legacy invalid data;
        # new onsite payments now require an approved application themselves.
        Payment.objects.create(application=submitted, amount="500.00", status="completed")

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
            payload={"notes": "Verified ID and signed agreement onsite.", "confirmed": True}
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
            self.complete(payload={"notes": "Internal note", "confirmed": True}).status_code, 200
        )

        self.authenticate(self.adopter)
        resp = self.client.get(f"/api/applications/{self.application.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "adoption_completed")
        self.assertNotIn("staff_notes", resp.data)


class PaymentCreationRegressionTests(OnsiteFlowTestCase):
    """Regression tests for payment creation via POST /api/payments/.

    These verify the full HTTP endpoint, ensuring that the field values
    the Staff Portal sends (method, status, payment_date, etc.) are
    accepted by the backend serializer and model validation.
    """

    ADOPTION_FEE = "500.00"

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(
            name="Buddy", species="dog", age_years=1, status="pending"
        )
        self.adopter = self.create_user(email="adopter@example.com")
        self.staff = self.create_staff(email="staff@example.com")
        self.application = Application.objects.create(
            adopter=self.adopter, pet=self.pet, status="approved"
        )

    def _create_payment(self, **overrides):
        visit_on(self.application, timezone.localdate())
        payload = {
            "application": str(self.application.id),
            "amount": self.ADOPTION_FEE,
            "method": "cash",
            "payment_date": timezone.localdate().isoformat(),
            "reference_number": "OR-2026-0001",
            "notes": "Onsite cash payment",
        }
        payload.update(overrides)
        self.authenticate(self.staff)
        return self.client.post("/api/payments/", payload, format="json")

    def test_valid_cash_payment_creation(self):
        # Generic create without a status stores the model default ("pending");
        # completion is reserved for the canonical onsite flow.
        resp = self._create_payment(method="cash")
        self.assertEqual(resp.status_code, 201)
        payment = Payment.objects.get()
        self.assertEqual(payment.amount, Decimal("500.00"))
        self.assertEqual(payment.method, "cash")
        self.assertEqual(payment.status, "pending")
        self.assertEqual(payment.payment_date, timezone.localdate())
        self.assertEqual(payment.reference_number, "OR-2026-0001")
        self.assertEqual(payment.notes, "Onsite cash payment")
        self.assertEqual(payment.processed_by, self.staff)
        self.assertEqual(payment.application, self.application)

    def test_valid_pending_payment_creation(self):
        resp = self._create_payment(method="bank_transfer", status="pending")
        self.assertEqual(resp.status_code, 201)
        payment = Payment.objects.get()
        self.assertEqual(payment.method, "bank_transfer")
        self.assertEqual(payment.status, "pending")

    def test_all_valid_methods_accepted(self):
        for method in ["cash", "bank_transfer", "gcash", "paymaya", "credit_card", "online"]:
            Payment.objects.all().delete()
            resp = self._create_payment(method=method)
            self.assertEqual(resp.status_code, 201, f"method='{method}' rejected: {resp.data}")

    def test_completed_status_rejected_on_generic_create(self):
        """Generic create cannot mark a payment completed (that is reserved for
        the canonical onsite flow after the money is actually received)."""
        self.authenticate(self.staff)
        resp = self._create_payment(status="completed")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("status", resp.data)
        self.assertEqual(Payment.objects.count(), 0)

    def test_other_statuses_accepted_on_generic_create(self):
        """Non-completed statuses remain valid for generic create so staff can
        record pending/failed/refunded/cancelled records; none of them count as
        money received."""
        for status in ["pending", "failed", "refunded", "cancelled"]:
            Payment.objects.all().delete()
            resp = self._create_payment(status=status)
            self.assertEqual(resp.status_code, 201, f"status='{status}' rejected: {resp.data}")
            self.assertEqual(Payment.objects.get().status, status)
            self.assertEqual(Payment.objects.get().receipt_number, "")

    def test_payment_without_optional_fields(self):
        resp = self._create_payment(payment_date=None, reference_number="", notes="")
        self.assertEqual(resp.status_code, 201)

    def test_response_includes_id_and_key_fields(self):
        resp = self._create_payment()
        self.assertEqual(resp.status_code, 201)
        self.assertIn("id", resp.data)
        self.assertIn("status", resp.data)
        self.assertIn("amount", resp.data)
        self.assertIn("method", resp.data)


    def test_invalid_method_rejected(self):
        resp = self._create_payment(method="manual")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("method", resp.data)

    def test_invalid_status_rejected(self):
        resp = self._create_payment(status="paid")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("status", resp.data)

    def test_unpaid_status_rejected(self):
        resp = self._create_payment(status="unpaid")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("status", resp.data)

    def test_partial_status_rejected(self):
        resp = self._create_payment(status="partial")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("status", resp.data)

    def test_missing_application_rejected(self):
        resp = self._create_payment(application="")
        self.assertEqual(resp.status_code, 400)

    def test_missing_amount_rejected(self):
        resp = self._create_payment(amount="")
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_payment_creates_second_record(self):
        self._create_payment()
        self._create_payment()
        self.assertEqual(Payment.objects.count(), 2)

    def test_adopter_cannot_create_payment(self):
        self.authenticate(self.adopter)
        resp = self.client.post(
            "/api/payments/",
            {"application": str(self.application.id), "amount": self.ADOPTION_FEE, "method": "cash", "status": "completed"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Payment.objects.count(), 0)

    def test_created_payment_appears_in_list(self):
        self._create_payment()
        self.authenticate(self.staff)
        resp = self.client.get("/api/payments/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)

    def test_payment_filterable_by_application(self):
        self._create_payment()
        self.authenticate(self.staff)
        resp = self.client.get("/api/payments/", {"application": str(self.application.id)})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)



class Phase2OnsitePaymentAndTurnoverTests(OnsiteFlowTestCase):
    """Focused tests for Phase 2: backend business rules, on-site payment hardening,
    and safe pet turnover confirmation.
    """

    REFERENCE_FEE = "500.00"

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(
            name="Max", species="dog", age_years=2, status="pending"
        )
        self.adopter = self.create_user(email="adopter_phase2@example.com")
        self.staff = self.create_staff(email="staff_phase2@example.com")
        self.application = Application.objects.create(
            adopter=self.adopter, pet=self.pet, status="approved"
        )
        self.visit_date = timezone.localdate()
        self.confirm_appointment()

    def confirm_appointment(self, app=None):
        target = app or self.application
        return visit_on(target, self.visit_date)

    # -------------------------------------------------------------------------
    # Payment Tests
    # -------------------------------------------------------------------------

    def test_valid_onsite_payment_recorded_as_completed_with_permanent_unique_reference(self):
        """Staff records an on-site payment; it is completed with a permanent unique receipt_number."""
        self.authenticate(self.staff)
        resp = self.client.post(
            f"/api/applications/{self.application.id}/record-payment/",
            {
                "amount": "500.00",
                "method": "cash",
                "payment_received": True,
                "reference_number": "OR-2026-QC-001",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["status"], "completed")
        self.assertTrue(resp.data["receipt_number"].startswith("REC-"))

        # Verify database record
        payment = Payment.objects.get(application=self.application)
        self.assertEqual(payment.status, Payment.Status.COMPLETED)
        self.assertEqual(payment.amount, Decimal("500.00"))
        self.assertEqual(payment.receipt_number, resp.data["receipt_number"])
        self.assertEqual(payment.processed_by, self.staff)

        # Permanent reference stability on view / refresh
        resp2 = self.client.get(f"/api/payments/{payment.id}/")
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.data["receipt_number"], payment.receipt_number)

    def test_zero_and_negative_payment_amounts_rejected(self):
        """Zero and negative amounts for payment receipts are strictly rejected."""
        self.authenticate(self.staff)

        # Zero amount on record-payment
        resp_zero = self.client.post(
            f"/api/applications/{self.application.id}/record-payment/",
            {"amount": "0.00", "method": "cash"},
            format="json",
        )
        self.assertEqual(resp_zero.status_code, 400)

        # Negative amount on record-payment
        resp_neg = self.client.post(
            f"/api/applications/{self.application.id}/record-payment/",
            {"amount": "-100.00", "method": "cash"},
            format="json",
        )
        self.assertEqual(resp_neg.status_code, 400)

        # Zero amount on generic /api/payments/
        resp_gen_zero = self.client.post(
            "/api/payments/",
            {
                "application": str(self.application.id),
                "amount": "0.00",
                "method": "cash",
                "status": "completed",
            },
            format="json",
        )
        self.assertEqual(resp_gen_zero.status_code, 400)

        # Negative amount on generic /api/payments/
        resp_gen_neg = self.client.post(
            "/api/payments/",
            {
                "application": str(self.application.id),
                "amount": "-500.00",
                "method": "cash",
                "status": "completed",
            },
            format="json",
        )
        self.assertEqual(resp_gen_neg.status_code, 400)
        self.assertEqual(Payment.objects.count(), 0)

    def test_staff_cannot_record_payment_if_money_not_received(self):
        """Staff can record a payment only after actually receiving the money."""
        self.authenticate(self.staff)
        resp = self.client.post(
            f"/api/applications/{self.application.id}/record-payment/",
            {"amount": "500.00", "payment_received": False},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.data)
        self.assertEqual(Payment.objects.count(), 0)

    def test_client_supplied_status_and_reference_fields_cannot_forge_completed_receipt(self):
        """Receipt numbers stay server-controlled and client input cannot forge
        a completed payment through the generic endpoint.

        Generic create rejects the completion attempt entirely (Phase 5.2); the
        canonical onsite endpoint accepts the client's amount/method but always
        generates its own receipt and forces status=completed.
        """
        self.authenticate(self.staff)
        # Generic create: the forged-completed attempt is rejected outright.
        resp_gen = self.client.post(
            "/api/payments/",
            {
                "application": str(self.application.id),
                "amount": "500.00",
                "method": "cash",
                "status": "completed",
                "receipt_number": "FORGED-REC-FAKE123",
            },
            format="json",
        )
        self.assertEqual(resp_gen.status_code, 400)
        self.assertEqual(Payment.objects.count(), 0)

        # Canonical onsite flow: a client-supplied receipt_number is ignored and
        # the backend generates the permanent receipt.
        resp = self.client.post(
            "/api/payments/record-onsite/",
            {
                "application": str(self.application.id),
                "amount": "500.00",
                "method": "cash",
                "payment_received": True,
                "notes": "client tries to downgrade status",
                "status": "pending",  # ignored
                "receipt_number": "FORGED-REC-FAKE123",  # ignored
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        payment = Payment.objects.get()
        self.assertEqual(payment.status, "completed")
        self.assertNotEqual(payment.receipt_number, "FORGED-REC-FAKE123")
        self.assertTrue(payment.receipt_number.startswith("REC-"))

    def test_unauthorized_users_cannot_record_payments(self):
        """Adopters and anonymous users cannot record payments or mark payments completed."""
        # Anonymous
        self.unauthenticate()
        resp_anon = self.client.post(
            f"/api/applications/{self.application.id}/record-payment/",
            {"amount": "500.00"},
            format="json",
        )
        self.assertIn(resp_anon.status_code, [401, 403])

        # Adopter
        self.authenticate(self.adopter)
        resp_adopter = self.client.post(
            f"/api/applications/{self.application.id}/record-payment/",
            {"amount": "500.00"},
            format="json",
        )
        self.assertEqual(resp_adopter.status_code, 403)

        resp_adopter_gen = self.client.post(
            "/api/payments/",
            {
                "application": str(self.application.id),
                "amount": "500.00",
                "method": "cash",
                "status": "completed",
            },
            format="json",
        )
        self.assertEqual(resp_adopter_gen.status_code, 403)
        self.assertEqual(Payment.objects.count(), 0)

    def test_existing_payment_records_and_supported_workflows_remain_compatible(self):
        """Generic payment endpoint still supports other payment statuses like pending."""
        self.authenticate(self.staff)
        resp = self.client.post(
            "/api/payments/",
            {
                "application": str(self.application.id),
                "amount": "500.00",
                "method": "bank_transfer",
                "status": "pending",
                "reference_number": "BANK-TXN-777",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        payment = Payment.objects.get(id=resp.data["id"])
        self.assertEqual(payment.status, "pending")
        self.assertEqual(payment.receipt_number, "")

        # Central fee endpoint is accessible
        fee_resp = self.client.get("/api/payments/fee/")
        self.assertEqual(fee_resp.status_code, 200)
        self.assertEqual(fee_resp.data["adoption_fee"], "500.00")

    # -------------------------------------------------------------------------
    # Turnover Tests
    # -------------------------------------------------------------------------

    def test_turnover_rejected_when_no_payment(self):
        """No payment: turnover rejected."""
        self.confirm_appointment()
        self.authenticate(self.staff)
        resp = self.client.post(
            f"/api/applications/{self.application.id}/confirm-turnover/",
            {},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "approved")
        self.assertEqual(AdoptionRecord.objects.count(), 0)

    def test_turnover_rejected_when_only_pending_or_failed_payments(self):
        """Only pending or failed payments: turnover rejected."""
        self.confirm_appointment()
        self.authenticate(self.staff)
        Payment.objects.create(
            application=self.application,
            amount=Decimal("500.00"),
            method="bank_transfer",
            status="pending",
        )
        Payment.objects.create(
            application=self.application,
            amount=Decimal("500.00"),
            method="cash",
            status="failed",
        )
        resp = self.client.post(
            f"/api/applications/{self.application.id}/confirm-turnover/",
            {},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "approved")
        self.assertEqual(AdoptionRecord.objects.count(), 0)

    def test_turnover_rejected_when_partial_payment(self):
        """Partial payment (e.g. ₱200.00): turnover rejected."""
        self.confirm_appointment()
        self.authenticate(self.staff)
        Payment.objects.create(
            application=self.application,
            amount=Decimal("200.00"),
            method="cash",
            status="completed",
        )
        resp = self.client.post(
            f"/api/applications/{self.application.id}/confirm-turnover/",
            {},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "approved")
        self.assertEqual(AdoptionRecord.objects.count(), 0)

    def test_turnover_rejected_when_completed_payments_below_500(self):
        """Completed payments below ₱500 (e.g. ₱499.50): turnover rejected."""
        self.confirm_appointment()
        self.authenticate(self.staff)
        Payment.objects.create(
            application=self.application,
            amount=Decimal("499.50"),
            method="cash",
            status="completed",
        )
        resp = self.client.post(
            f"/api/applications/{self.application.id}/confirm-turnover/",
            {},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "approved")
        self.assertEqual(AdoptionRecord.objects.count(), 0)

    def test_turnover_succeeds_when_completed_payments_total_at_least_500_with_explicit_confirmation(self):
        """Completed payments totaling at least ₱500: turnover proceeds after explicit confirmation."""
        self.confirm_appointment()
        self.authenticate(self.staff)

        # Split payment: ₱250 + ₱250 = ₱500
        Payment.objects.create(
            application=self.application,
            amount=Decimal("250.00"),
            method="cash",
            status="completed",
        )
        Payment.objects.create(
            application=self.application,
            amount=Decimal("250.00"),
            method="gcash",
            status="completed",
        )

        # If staff explicitly denies handover, turnover rejected
        resp_denied = self.client.post(
            f"/api/applications/{self.application.id}/confirm-turnover/",
            {"confirmed": False},
            format="json",
        )
        self.assertEqual(resp_denied.status_code, 400)
        self.assertEqual(AdoptionRecord.objects.count(), 0)

        # Explicit confirmation
        resp = self.client.post(
            f"/api/applications/{self.application.id}/confirm-turnover/",
            {"confirmed": True, "notes": "Handed over leash and starter food."},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "adoption_completed")
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "adopted")

    def test_payment_recorded_but_turnover_does_not_occur_leaves_records_intact(self):
        """A paid adoption with an unsuccessful or postponed turnover remains incomplete,
        and its legitimate payment history remains intact."""
        self.confirm_appointment()
        self.authenticate(self.staff)
        pay = Payment.objects.create(
            application=self.application,
            amount=Decimal("500.00"),
            method="cash",
            status="completed",
        )
        receipt = pay.receipt_number

        # Turnover does not occur
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "approved")
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "pending")
        self.assertEqual(AdoptionRecord.objects.count(), 0)

        # Payment remains intact
        pay.refresh_from_db()
        self.assertEqual(pay.status, "completed")
        self.assertEqual(pay.receipt_number, receipt)
        self.assertIsNone(pay.adoption)

    def test_successful_turnover_finalizes_one_record_stable_txn_id_staff_pet_adopted(self):
        """Successful confirmation finalizes exactly one AdoptionRecord, persists its permanent
        transaction ID and completion timestamp, and records responsible staff."""
        appointment = self.confirm_appointment()
        self.authenticate(self.staff)
        pay = Payment.objects.create(
            application=self.application,
            amount=Decimal("500.00"),
            method="cash",
            status="completed",
        )

        resp = self.client.post(
            f"/api/applications/{self.application.id}/confirm-turnover/",
            {"confirmed": True, "notes": "Turnover complete."},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(AdoptionRecord.objects.filter(application=self.application).count(), 1)
        record = AdoptionRecord.objects.get(application=self.application)
        self.assertEqual(record.status, AdoptionRecord.Status.COMPLETED)
        self.assertTrue(record.transaction_id.startswith("TXN-"))
        self.assertEqual(record.completed_date, timezone.localdate())
        self.assertIsNotNone(record.completed_at)
        self.assertEqual(record.staff_member, self.staff)
        self.assertEqual(record.pet, self.pet)
        self.assertEqual(record.adopter, self.adopter)
        self.assertEqual(record.appointment, appointment)

        # Pet is adopted and unavailable
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "adopted")

        # Payment linked to record
        pay.refresh_from_db()
        self.assertEqual(pay.adoption, record)

    def test_turnover_rejected_when_appointment_not_confirmed(self):
        """Appointment not confirmed: turnover rejected."""
        self.application.appointments.all().delete()
        self.authenticate(self.staff)
        Payment.objects.create(
            application=self.application,
            amount=Decimal("500.00"),
            method="cash",
            status="completed",
        )
        # No appointment at all
        resp = self.client.post(
            f"/api/applications/{self.application.id}/confirm-turnover/",
            {"confirmed": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

        # Unconfirmed appointment (pending_confirmation)
        Appointment.objects.create(
            application=self.application,
            adopter=self.adopter,
            pet=self.pet,
            requested_date=self.visit_date,
            status=Appointment.Status.PENDING_CONFIRMATION,
        )
        resp2 = self.client.post(
            f"/api/applications/{self.application.id}/confirm-turnover/",
            {"confirmed": True},
            format="json",
        )
        self.assertEqual(resp2.status_code, 400)

    def test_adopter_or_unauthorized_user_cannot_confirm_turnover(self):
        """Adopter or unauthorized user cannot confirm turnover."""
        self.confirm_appointment()
        Payment.objects.create(
            application=self.application,
            amount=Decimal("500.00"),
            method="cash",
            status="completed",
        )

        # Adopter
        self.authenticate(self.adopter)
        resp_adopter = self.client.post(
            f"/api/applications/{self.application.id}/confirm-turnover/",
            {"confirmed": True},
            format="json",
        )
        self.assertEqual(resp_adopter.status_code, 403)

        # Anonymous
        self.unauthenticate()
        resp_anon = self.client.post(
            f"/api/applications/{self.application.id}/confirm-turnover/",
            {"confirmed": True},
            format="json",
        )
        self.assertIn(resp_anon.status_code, [401, 403])

    def test_repeated_completion_requests_idempotent_no_duplicate_or_regenerated_id(self):
        """Repeated completion requests do not create duplicate records or regenerate IDs."""
        self.confirm_appointment()
        self.authenticate(self.staff)
        Payment.objects.create(
            application=self.application,
            amount=Decimal("500.00"),
            method="cash",
            status="completed",
        )

        resp1 = self.client.post(
            f"/api/applications/{self.application.id}/confirm-turnover/",
            {"confirmed": True},
            format="json",
        )
        self.assertEqual(resp1.status_code, 200)
        record1 = AdoptionRecord.objects.get(application=self.application)
        original_txn_id = record1.transaction_id
        original_completed_at = record1.completed_at

        # Repeated request (idempotent retry)
        resp2 = self.client.post(
            f"/api/applications/{self.application.id}/confirm-turnover/",
            {"confirmed": True},
            format="json",
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(AdoptionRecord.objects.filter(application=self.application).count(), 1)
        record2 = AdoptionRecord.objects.get(application=self.application)
        self.assertEqual(record2.transaction_id, original_txn_id)
        self.assertEqual(record2.completed_at, original_completed_at)

    def test_failed_atomic_operation_leaves_related_records_in_consistent_state(self):
        """A failed atomic operation leaves related records in a consistent state."""
        self.confirm_appointment()
        self.authenticate(self.staff)
        Payment.objects.create(
            application=self.application,
            amount=Decimal("500.00"),
            method="cash",
            status="completed",
        )

        from unittest.mock import patch
        # Simulate a crash right when Pet.save() is called during turnover
        with patch.object(Pet, "save", side_effect=RuntimeError("Simulated database failure")):
            with self.assertRaises(RuntimeError):
                from apps.adoptions.services import complete_application_adoption
                complete_application_adoption(self.application, self.staff, handover_confirmed=True)

        # Atomic rollback check: application and pet remain unaffected
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "approved")
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "pending")
        self.assertFalse(AdoptionRecord.objects.filter(status=AdoptionRecord.Status.COMPLETED).exists())

    def test_fee_and_payment_totals_exposed_in_serializers_and_endpoints(self):
        """Central adoption fee, total_paid, is_fee_paid, and turnover_eligible are exposed."""
        self.confirm_appointment()
        self.authenticate(self.staff)

        # Before payment
        summary_resp1 = self.client.get(f"/api/applications/{self.application.id}/payment-summary/")
        self.assertEqual(summary_resp1.status_code, 200)
        self.assertEqual(summary_resp1.data["adoption_fee"], "500.00")
        self.assertEqual(summary_resp1.data["total_paid"], "0.00")
        self.assertFalse(summary_resp1.data["is_fee_paid"])
        self.assertFalse(summary_resp1.data["turnover_eligible"])

        # Record payment
        Payment.objects.create(
            application=self.application,
            amount=Decimal("500.00"),
            method="cash",
            status="completed",
        )

        # After payment
        summary_resp2 = self.client.get(f"/api/applications/{self.application.id}/payment-summary/")
        self.assertEqual(summary_resp2.status_code, 200)
        self.assertEqual(summary_resp2.data["total_paid"], "500.00")
        self.assertTrue(summary_resp2.data["is_fee_paid"])
        self.assertTrue(summary_resp2.data["turnover_eligible"])

        # Exposed in ApplicationSerializer
        app_resp = self.client.get(f"/api/applications/{self.application.id}/")
        self.assertEqual(app_resp.status_code, 200)
        self.assertEqual(app_resp.data["adoption_fee"], "500.00")
        self.assertEqual(app_resp.data["total_paid"], "500.00")
        self.assertTrue(app_resp.data["is_fee_paid"])
        self.assertTrue(app_resp.data["turnover_eligible"])


class Phase21PaymentReassignmentTests(BaseAPITestCase):
    """Phase 2.1 - Prevent reassignment of an existing payment to a different application."""

    ADOPTION_FEE = "500.00"

    def setUp(self):
        super().setUp()
        self.pet1 = Pet.objects.create(name="ReassignPet1", species="dog", age_years=1, status="pending")
        self.pet2 = Pet.objects.create(name="ReassignPet2", species="cat", age_years=2, status="pending")
        self.adopter = self.create_user(email="adopter_ra@example.com")
        self.staff = self.create_staff(email="staff_ra@example.com")
        self.app1 = Application.objects.create(adopter=self.adopter, pet=self.pet1, status="approved")
        self.app2 = Application.objects.create(adopter=self.adopter, pet=self.pet2, status="approved")
        self.payment = Payment.objects.create(
            application=self.app1,
            amount="500.00",
            method="cash",
            status="completed",
            processed_by=self.staff,
        )

    def test_patch_reassignment_to_different_application_rejected(self):
        """PATCH /api/payments/{id}/ cannot reassign payment to a different application."""
        self.authenticate(self.staff)
        resp = self.client.patch(
            f"/api/payments/{self.payment.id}/",
            {"application": str(self.app2.id)},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("application", resp.data)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.application, self.app1)

    def test_put_reassignment_to_different_application_rejected(self):
        """PUT /api/payments/{id}/ cannot reassign payment to a different application."""
        self.authenticate(self.staff)
        resp = self.client.put(
            f"/api/payments/{self.payment.id}/",
            {
                "application": str(self.app2.id),
                "amount": self.ADOPTION_FEE,
                "method": "cash",
                "status": "completed",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("application", resp.data)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.application, self.app1)

    def test_patch_same_application_does_not_trigger_reassignment_error(self):
        """PATCH with the same application FK is allowed."""
        self.authenticate(self.staff)
        resp = self.client.patch(
            f"/api/payments/{self.payment.id}/",
            {"application": str(self.app1.id), "notes": "Updated notes."},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.application, self.app1)

    def test_patch_without_application_field_is_allowed(self):
        """PATCH that does not include the application field is always allowed."""
        self.authenticate(self.staff)
        resp = self.client.patch(
            f"/api/payments/{self.payment.id}/",
            {"notes": "Staff note."},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_create_new_payment_for_different_application_is_allowed(self):
        """Creating a new payment for any application is always allowed
        (through the canonical onsite flow)."""
        from apps.appointments.eligibility import philippine_today
        visit_on(self.app2, philippine_today())
        self.authenticate(self.staff)
        resp = self.client.post(
            "/api/payments/record-onsite/",
            {
                "application": str(self.app2.id),
                "amount": self.ADOPTION_FEE,
                "method": "gcash",
                "payment_received": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        new_payment = Payment.objects.get(application=self.app2)
        self.assertEqual(new_payment.application, self.app2)
        self.assertEqual(new_payment.status, "completed")


class PaymentRecordsApiTests(BaseAPITestCase):
    """Phase 3.2 - server-side list filtering and serialized fields used by the
    staff Payment Records page."""

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(name="Rex", species="dog", age_years=2, status="available")
        self.adopter = self.create_user(email="adopter_records@example.com")
        self.staff = self.create_staff(email="staff_records@example.com")
        self.app = Application.objects.create(
            adopter=self.adopter, pet=self.pet, status="approved"
        )

    def _make_payment(self, status, amount="100.00", method="cash"):
        return Payment.objects.create(
            application=self.app,
            amount=amount,
            method=method,
            status=status,
            processed_by=self.staff,
        )

    def test_payment_response_includes_pet_name(self):
        """Payment records expose the associated pet name, not just the UUID."""
        pay = self._make_payment(status="completed")
        self.authenticate(self.staff)
        resp = self.client.get(f"/api/payments/{pay.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["pet_name"], "Rex")

    def test_payment_list_can_be_filtered_by_status(self):
        """?status= filters server-side so the records page never has to fetch
        and filter unbounded pages in the browser."""
        self._make_payment(status="completed")
        self._make_payment(status="completed")
        self._make_payment(status="pending")
        self._make_payment(status="failed")
        self.authenticate(self.staff)

        completed = self.client.get("/api/payments/?status=completed")
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.data["count"], 2)
        self.assertTrue(all(r["status"] == "completed" for r in completed.data["results"]))

        pending = self.client.get("/api/payments/?status=pending")
        self.assertEqual(pending.status_code, 200)
        self.assertEqual(pending.data["count"], 1)
        self.assertEqual(pending.data["results"][0]["status"], "pending")

        # An unknown status matches nothing instead of erroring.
        unknown = self.client.get("/api/payments/?status=does_not_exist")
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(unknown.data["count"], 0)

        # Without a filter, all records are returned (paginated).
        all_records = self.client.get("/api/payments/")
        self.assertEqual(all_records.status_code, 200)
        self.assertEqual(all_records.data["count"], 4)

    def test_payment_list_status_filter_is_combined_with_application_filter(self):
        """The status filter composes with the existing ?application= filter."""
        other_pet = Pet.objects.create(name="Bella", species="cat", age_years=1, status="available")
        other_app = Application.objects.create(
            adopter=self.adopter, pet=other_pet, status="approved"
        )
        Payment.objects.create(
            application=other_app, amount="500.00", method="gcash",
            status="completed", processed_by=self.staff,
        )
        self._make_payment(status="completed")
        self.authenticate(self.staff)

        resp = self.client.get(f"/api/payments/?status=completed&application={other_app.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(str(resp.data["results"][0]["application"]), str(other_app.id))
        self.assertEqual(resp.data["results"][0]["pet_name"], "Bella")


def _extract_pdf_text(content):
    """Return the joined text of the PDF's content streams.

    ReportLab 5.x writes page content as ``/ASCII85Decode /FlateDecode`` by
    default, so the raw PDF bytes are not directly searchable. This helper
    decodes every content stream and joins the text strings (PDF breaks long
    lines into separate ``(text) Tj`` operators, so joining restores the full
    strings). Standard library only.
    """
    import base64
    import re
    import zlib

    def _decode(payload):
        payload = payload.strip()
        if payload.endswith(b"~>"):
            payload = payload[:-2].rstrip()
        attempts = (
            lambda: zlib.decompress(base64.a85decode(payload)),
            lambda: zlib.decompress(payload),
            lambda: zlib.decompress(payload, -15),
        )
        for attempt in attempts:
            try:
                return attempt()
            except Exception:
                continue
        return payload

    def _strings(stream):
        tokens = []
        for m in re.finditer(rb"\((?:[^()\\]|\\.)*\)", stream):
            token = m.group(0)[1:-1]
            token = token.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
            tokens.append(token)
        return b"".join(tokens)

    pieces = []
    # Streams end with ``~>endstream`` (no separating newline) in reportlab 5.
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", content, re.DOTALL):
        pieces.append(_strings(_decode(match.group(1))))
    return b"".join(pieces)


class PaymentPdfExportTests(BaseAPITestCase):
    """Phase 4.1 - staff-authorized A4 PDF export of payment records.

    The report is generated server-side from persisted Payment rows and reuses
    the list endpoint's queryset + filters, so amounts/statuses/receipts are
    never supplied by the frontend.
    """

    def setUp(self):
        super().setUp()
        self.adopter = self.create_user(email="adopter_pdf41@example.com")
        self.staff = self.create_staff(email="staff_pdf41@example.com")
        self.pet = Pet.objects.create(name="Bruno", species="dog", age_years=2, status="available")
        self.app = Application.objects.create(
            adopter=self.adopter, pet=self.pet, status="approved"
        )

    def _make_payment(self, status="completed", reference="OR-UNIQUE", amount="500.00"):
        return Payment.objects.create(
            application=self.app,
            amount=amount,
            method="cash",
            status=status,
            reference_number=reference,
            processed_by=self.staff,
        )

    def test_export_pdf_requires_staff_permissions(self):
        self._make_payment()
        # Anonymous
        self.unauthenticate()
        resp = self.client.get("/api/payments/export-pdf/")
        self.assertIn(resp.status_code, [401, 403])
        # Adopter
        self.authenticate(self.adopter)
        resp = self.client.get("/api/payments/export-pdf/")
        self.assertEqual(resp.status_code, 403)

    def test_export_pdf_returns_pdf_attachment(self):
        payment = self._make_payment(status="completed", reference="REF-PRIMARY-1")
        self.authenticate(self.staff)
        resp = self.client.get("/api/payments/export-pdf/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp["Content-Type"].startswith("application/pdf"))
        self.assertTrue(
            resp["Content-Disposition"].startswith(
                'attachment; filename="pawconnect-payment-records-'
            )
        )
        self.assertTrue(resp.content.startswith(b"%PDF-1."))
        text = _extract_pdf_text(resp.content)
        self.assertIn(b"PawConnect", text)
        self.assertIn(b"Payment Records Report", text)
        # Completed payments carry a backend-generated receipt number, which is
        # what the report displays (preferred over the reference number).
        self.assertIn(payment.receipt_number.encode("ascii"), text)
        self.assertIn(b"Bruno", text)
        self.assertIn(b"adopter_pdf41@example.com", text)
        self.assertIn(b"staff_pdf41@example.com", text)

    def test_export_pdf_respects_status_filter(self):
        completed = self._make_payment(status="completed", reference="REF-COMPLETED-1")
        self._make_payment(status="pending", reference="REF-PENDING-1")
        self.authenticate(self.staff)

        resp = self.client.get("/api/payments/export-pdf/?status=completed")
        self.assertEqual(resp.status_code, 200)
        text = _extract_pdf_text(resp.content)
        self.assertIn(completed.receipt_number.encode("ascii"), text)
        # The pending payment has no receipt and was excluded by the filter, so
        # its reference must not appear anywhere in the report.
        self.assertNotIn(b"REF-PENDING-1", text)

        total_text = _extract_pdf_text(
            self.client.get("/api/payments/export-pdf/?status=completed").content
        )
        self.assertIn(b"Total completed payments:", total_text)

    def test_export_pdf_respects_application_filter(self):
        other_pet = Pet.objects.create(name="Luna", species="cat", age_years=1, status="available")
        other_app = Application.objects.create(
            adopter=self.adopter, pet=other_pet, status="approved"
        )
        p1 = Payment.objects.create(
            application=self.app, amount="500.00", method="cash",
            status="completed", reference_number="REF-APP-1", processed_by=self.staff,
        )
        p2 = Payment.objects.create(
            application=other_app, amount="250.00", method="gcash",
            status="completed", reference_number="REF-APP-2", processed_by=self.staff,
        )
        self.authenticate(self.staff)

        resp = self.client.get(f"/api/payments/export-pdf/?application={other_app.id}")
        self.assertEqual(resp.status_code, 200)
        text = _extract_pdf_text(resp.content)
        self.assertIn(b"Luna", text)
        self.assertNotIn(b"Bruno", text)
        self.assertIn(p2.receipt_number.encode("ascii"), text)
        self.assertNotIn(p1.receipt_number.encode("ascii"), text)

    def test_export_pdf_validates_filter_parameters(self):
        self.authenticate(self.staff)
        bad_status = self.client.get("/api/payments/export-pdf/?status=nonsense")
        self.assertEqual(bad_status.status_code, 400)
        self.assertIn("status", bad_status.data)

        bad_app = self.client.get("/api/payments/export-pdf/?application=not-a-uuid")
        self.assertEqual(bad_app.status_code, 400)
        self.assertIn("application", bad_app.data)

    def test_export_pdf_empty_match_still_returns_valid_pdf(self):
        self._make_payment(status="completed")
        self.authenticate(self.staff)
        resp = self.client.get("/api/payments/export-pdf/?status=refunded")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b"%PDF-1."))
        text = _extract_pdf_text(resp.content)
        self.assertIn(b"No payment records match the selected filters.", text)


class PaymentIntegrityGateTests(BaseAPITestCase):
    """Phase 5.2 - payment integrity.

    Only the canonical onsite flow (``record-onsite`` / ``record_onsite_payment``)
    may mark a payment completed, after staff confirm the money was actually
    received. Client input cannot complete a payment through the generic create
    or PATCH/PUT updates, receipts and totals stay server-controlled, and only
    completed payments count toward the fee and turnover eligibility.
    """

    ADOPTION_FEE = "500.00"

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(name="Pongo", species="dog", age_years=2, status="pending")
        self.adopter = self.create_user(email="adopter_pi52@example.com")
        self.staff = self.create_staff(email="staff_pi52@example.com")
        self.app = Application.objects.create(
            adopter=self.adopter, pet=self.pet, status="approved"
        )

    def _pending(self):
        return Payment.objects.create(
            application=self.app, amount="100.00", method="cash",
            status="pending", processed_by=self.staff,
        )

    def _completed(self):
        return Payment.objects.create(
            application=self.app, amount="500.00", method="cash",
            status="completed", processed_by=self.staff,
        )

    def test_generic_create_cannot_mark_payment_completed(self):
        self.authenticate(self.staff)
        resp = self.client.post(
            "/api/payments/",
            {"application": str(self.app.id), "amount": "500.00",
             "method": "cash", "status": "completed"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("status", resp.data)
        self.assertEqual(Payment.objects.count(), 0)

    def test_patch_cannot_mark_pending_payment_completed(self):
        payment = self._pending()
        self.authenticate(self.staff)
        resp = self.client.patch(
            f"/api/payments/{payment.id}/", {"status": "completed"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "pending")
        self.assertEqual(payment.receipt_number, "")

    def test_put_cannot_mark_pending_payment_completed(self):
        payment = self._pending()
        self.authenticate(self.staff)
        resp = self.client.put(
            f"/api/payments/{payment.id}/",
            {"application": str(self.app.id), "amount": "100.00",
             "method": "cash", "status": "completed"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "pending")

    def test_completed_to_refunded_remains_allowed(self):
        payment = self._completed()
        self.authenticate(self.staff)
        resp = self.client.patch(
            f"/api/payments/{payment.id}/", {"status": "refunded"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "refunded")

    def test_pending_to_failed_remains_allowed(self):
        payment = self._pending()
        self.authenticate(self.staff)
        resp = self.client.patch(
            f"/api/payments/{payment.id}/", {"status": "failed"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "failed")

    def test_only_completed_payments_count_toward_totals(self):
        self._pending()  # ₱100 pending - never counts
        Payment.objects.create(
            application=self.app, amount="50.00", method="cash",
            status="failed", processed_by=self.staff,
        )  # ₱50 failed - never counts
        self._completed()  # ₱500 completed - counts
        self.authenticate(self.staff)
        resp = self.client.get(f"/api/applications/{self.app.id}/payment-summary/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["total_paid"], "500.00")
        self.assertTrue(resp.data["is_fee_paid"])
        # No confirmed appointment yet, so turnover is not eligible.
        self.assertFalse(resp.data["turnover_eligible"])

    def test_pending_only_application_is_not_fee_paid(self):
        self._pending()
        self.authenticate(self.staff)
        resp = self.client.get(f"/api/applications/{self.app.id}/payment-summary/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["total_paid"], "0.00")
        self.assertFalse(resp.data["is_fee_paid"])

    def test_canonical_onsite_flow_still_records_completed_with_server_receipt(self):
        from apps.appointments.eligibility import philippine_today
        visit_on(self.app, philippine_today())
        self.authenticate(self.staff)
        resp = self.client.post(
            "/api/payments/record-onsite/",
            {"application": str(self.app.id), "amount": self.ADOPTION_FEE,
             "method": "cash", "payment_received": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        payment = Payment.objects.get()
        self.assertEqual(payment.status, "completed")
        self.assertTrue(payment.receipt_number.startswith("REC-"))

    def test_adopter_cannot_complete_or_create_payments(self):
        self._pending()
        self.authenticate(self.adopter)
        resp = self.client.post(
            "/api/payments/",
            {"application": str(self.app.id), "amount": "500.00",
             "method": "cash", "status": "completed"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
        resp2 = self.client.patch(
            f"/api/payments/{Payment.objects.get().id}/", {"status": "completed"}
        )
        self.assertEqual(resp2.status_code, 403)



class IndividualReceiptPdfTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(name="Rocky", species="dog", age_years=2, status="pending")
        self.adopter = self.create_user(email="adopter_receipt@example.com")
        self.staff = self.create_staff(email="staff_receipt@example.com")
        self.app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="approved")
        self.payment = Payment.objects.create(
            application=self.app,
            amount=Decimal("500.00"),
            method="cash",
            status="completed",
            payment_date=timezone.localdate(),
            reference_number="OR-112233",
            processed_by=self.staff,
        )

    def test_staff_can_download_individual_receipt_pdf(self):
        self.authenticate(self.staff)
        before = Payment.objects.values().get(pk=self.payment.pk)
        resp = self.client.get(f"/api/payments/{self.payment.id}/receipt-pdf/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertIn("attachment;", resp["Content-Disposition"])
        self.assertTrue(resp.content.startswith(b"%PDF"))
        text = _extract_pdf_text(resp.content)
        for value in ['Payment Receipt', '500.00', self.payment.receipt_number, self.adopter.email, self.staff.email, str(self.app.pk), str(self.payment.pk)]:
            self.assertIn(value.encode(), text)
        self.assertEqual(Payment.objects.values().get(pk=self.payment.pk), before)

    def test_non_completed_transaction_is_not_presented_as_money_received(self):
        payment = Payment.objects.create(application=self.app, amount='600.00', status='pending')
        self.authenticate(self.staff)
        response = self.client.get(f'/api/payments/{payment.pk}/receipt-pdf/')
        self.assertEqual(response.status_code, 200)
        text = _extract_pdf_text(response.content)
        self.assertIn(b'Payment Transaction Record', text)
        self.assertIn(b'It does not', text)
        self.assertIn(b'confirm receipt of funds.', text)
        self.assertNotIn(b'AMOUNT RECEIVED', text)
        payment.refresh_from_db()
        self.assertEqual(payment.receipt_number, '')
        self.assertEqual(payment.status, 'pending')

    def test_long_notes_and_names_wrap_without_losing_content(self):
        self.adopter.first_name = 'Maria Isabel ' * 10
        self.adopter.last_name = 'Dela Cruz ' * 14
        self.adopter.save(update_fields=['first_name', 'last_name'])
        self.payment.notes = ('Care note & follow-up <needs review>.\n' * 90) + 'END OF SAVED PAYMENT NOTES'
        self.payment.save(update_fields=['notes'])
        self.authenticate(self.staff)
        response = self.client.get(f'/api/payments/{self.payment.pk}/receipt-pdf/')
        self.assertEqual(response.status_code, 200)
        text = _extract_pdf_text(response.content)
        self.assertIn(b'END OF SAVED PAYMENT NOTES', text)
        self.assertIn(b'<needs review>', text)
        self.assertGreaterEqual(text.count(self.payment.receipt_number.encode()), 2)

    def test_adopter_cannot_download_receipt_pdf_via_staff_endpoint(self):
        self.authenticate(self.adopter)
        resp = self.client.get(f"/api/payments/{self.payment.id}/receipt-pdf/")
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_cannot_download_receipt_pdf(self):
        self.unauthenticate()
        resp = self.client.get(f"/api/payments/{self.payment.id}/receipt-pdf/")
        self.assertIn(resp.status_code, [401, 403])

    def test_receipt_pdf_contains_only_the_selected_transaction(self):
        other = Payment.objects.create(
            application=self.app, amount="750.00", method="gcash",
            status="completed", notes="OTHER-TRANSACTION-ONLY",
        )
        self.authenticate(self.staff)
        response = self.client.get(f"/api/payments/{self.payment.id}/receipt-pdf/")
        self.assertEqual(response.status_code, 200)
        text = _extract_pdf_text(response.content)
        self.assertIn(self.payment.receipt_number.encode(), text)
        self.assertNotIn(other.receipt_number.encode(), text)
        self.assertNotIn(b"OTHER-TRANSACTION-ONLY", text)


class FixedOnsitePaymentTests(OnsiteFlowTestCase):
    """The one-time obligation is application-scoped and enforced by both routes."""

    def setUp(self):
        super().setUp()
        self.staff = self.create_staff(email="fixed-staff@example.com")
        self.adopter = self.create_user(email="fixed-adopter@example.com")
        self.pet = Pet.objects.create(name="Fixed fee pet", species="dog", age_years=2, status="pending")
        self.app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="approved")
        visit_on(self.app, timezone.localdate())
        self.authenticate(self.staff)

    def record(self, route="canonical", **overrides):
        payload = {"application": str(self.app.id), "method": "cash", "payment_received": True}
        payload.update(overrides)
        url = "/api/payments/record-onsite/" if route == "canonical" else f"/api/applications/{self.app.id}/record-payment/"
        return self.client.post(url, payload, format="json")

    def summary(self):
        return self.client.get(f"/api/applications/{self.app.id}/payment-summary/")

    def test_fixed_fee_is_server_defined_and_does_not_complete_adoption(self):
        self.assertEqual(self.client.get("/api/payments/fee/").data["adoption_fee"], "500.00")
        self.assertTrue(self.summary().data["can_record_payment"])
        response = self.record(status="pending", receipt_number="FORGED")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["amount"], "500.00")
        self.assertEqual(response.data["status"], "completed")
        self.assertTrue(response.data["receipt_number"].startswith("REC-"))
        self.app.refresh_from_db()
        self.pet.refresh_from_db()
        self.assertEqual(self.app.status, "approved")
        self.assertEqual(self.pet.status, "pending")
        self.assertFalse(AdoptionRecord.objects.exists())
        summary = self.summary().data
        self.assertFalse(summary["can_record_payment"])
        self.assertTrue(summary["is_fee_paid"])
        self.assertEqual(summary["payments"][0]["receipt_number"], response.data["receipt_number"])
        # A fresh request re-derives eligibility from the saved transaction.
        self.assertFalse(self.summary().data["can_record_payment"])

    def test_non_fixed_and_invalid_amounts_rejected_on_both_routes(self):
        for route in ("canonical", "application"):
            for amount in ("0", "-500", "250", "499.99", "501", "1000", "NaN", "Infinity", "bad"):
                with self.subTest(route=route, amount=amount):
                    self.assertEqual(self.record(route, amount=amount).status_code, 400)
        self.assertFalse(Payment.objects.exists())

    def test_explicit_boolean_receipt_confirmation_required_on_both_routes(self):
        for route in ("canonical", "application"):
            for value in (None, False, 0, 1, "false", "true", "", [], {}):
                with self.subTest(route=route, value=value):
                    self.assertEqual(self.record(route, payment_received=value).status_code, 400)
            url = "/api/payments/record-onsite/" if route == "canonical" else f"/api/applications/{self.app.id}/record-payment/"
            response = self.client.post(url, {"application": str(self.app.id)}, format="json")
            self.assertEqual(response.status_code, 400)
        self.assertFalse(Payment.objects.exists())

    def test_duplicate_rejected_by_both_routes_without_new_side_effects(self):
        from apps.audit.models import AuditLog
        first = self.record()
        self.assertEqual(first.status_code, 201)
        before = (AuditLog.objects.count(), Notification.objects.count())
        for route in ("canonical", "application"):
            with self.subTest(route=route):
                response = self.record(route)
                self.assertEqual(response.status_code, 400)
                self.assertIn("already exists", response.data["error"])
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Payment.objects.get().receipt_number, first.data["receipt_number"])
        self.assertEqual((AuditLog.objects.count(), Notification.objects.count()), before)

    def test_legacy_completed_partial_or_duplicate_rows_block_another_collection(self):
        first = Payment.objects.create(application=self.app, amount="250.00", status="completed")
        self.assertFalse(self.summary().data["can_record_payment"])
        self.assertEqual(self.record().status_code, 400)
        second = Payment.objects.create(application=self.app, amount="500.00", status="completed")
        before = list(Payment.objects.order_by("id").values())
        self.assertEqual(self.record().status_code, 400)
        self.assertEqual(list(Payment.objects.order_by("id").values()), before)
        self.assertEqual({p["id"] for p in self.summary().data["payments"]}, {str(first.id), str(second.id)})

    def test_non_completed_transactions_do_not_block_or_count_as_collections(self):
        for status in ("pending", "failed", "cancelled", "refunded"):
            Payment.objects.create(application=self.app, amount="500.00", status=status)
        summary = self.summary().data
        self.assertTrue(summary["can_record_payment"])
        self.assertFalse(summary["is_fee_paid"])
        self.assertEqual(summary["total_paid"], "0.00")
        self.assertEqual(self.record().status_code, 201)
        self.assertEqual(self.summary().data["total_paid"], "500.00")

    def test_other_application_for_same_adopter_remains_payable(self):
        self.assertEqual(self.record().status_code, 201)
        pet = Pet.objects.create(name="Another pet", species="cat", age_years=1)
        self.app = Application.objects.create(adopter=self.adopter, pet=pet, status="approved")
        visit_on(self.app, timezone.localdate())
        self.assertTrue(self.summary().data["can_record_payment"])
        self.assertEqual(self.record("application").status_code, 201)
        self.assertEqual(Payment.objects.filter(status="completed").count(), 2)

    def test_unapproved_application_is_not_eligible(self):
        self.app.status = "submitted"
        self.app.save(update_fields=["status"])
        self.assertFalse(self.summary().data["can_record_payment"])
        self.assertEqual(self.record().status_code, 400)
        self.assertFalse(Payment.objects.exists())

    def test_invalid_application_or_method_rejected_without_saving(self):
        self.assertEqual(self.record(application="not-a-uuid").status_code, 400)
        self.assertEqual(self.record(method="invalid-method").status_code, 400)
        self.assertFalse(Payment.objects.exists())

    def test_service_itself_requires_confirmation_and_checks_duplicates(self):
        from django.core.exceptions import ValidationError
        from apps.payments.services import record_onsite_payment
        with self.assertRaises(ValidationError):
            record_onsite_payment(self.app, self.staff)
        record_onsite_payment(self.app, self.staff, payment_received=True)
        with self.assertRaises(ValidationError):
            record_onsite_payment(self.app, self.staff, payment_received=True)
        self.assertEqual(Payment.objects.count(), 1)
