from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.tests import BaseAPITestCase
from apps.appointments.models import Appointment
from apps.audit.models import AuditLog
from apps.pets.models import Pet
from apps.applications.models import Application
from apps.adoptions.models import AdoptionRecord
from apps.notifications.models import Notification


class AdoptionBusinessRuleTests(BaseAPITestCase):

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(name="Buddy", species="dog", age_years=1, status="available")
        self.adopter = self.create_user(email="adopter@example.com")
        self.staff = self.create_staff(email="staff1@example.com")
        self.app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="approved")

    def authenticate_staff(self):
        self.authenticate(self.staff)

    def test_cannot_create_adoption_from_unapproved_application(self):
        # Use a different pet so this second application does not violate the
        # "one active application per adopter+pet" constraint.
        other_pet = Pet.objects.create(name="Rex", species="dog", age_years=2, status="available")
        unapproved_app = Application.objects.create(
            adopter=self.adopter, pet=other_pet, status="submitted"
        )
        self.authenticate_staff()
        resp = self.client.post("/api/adoptions/", {"application_id": str(unapproved_app.id)})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(AdoptionRecord.objects.count(), 0)

    def test_can_create_adoption_from_approved_application(self):
        self.authenticate_staff()
        resp = self.client.post("/api/adoptions/", {"application_id": str(self.app.id)})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(AdoptionRecord.objects.count(), 1)

    def test_completing_adoption_sets_pet_adopted(self):
        Appointment.objects.create(
            application=self.app, pet=self.pet, adopter=self.adopter,
            requested_date=timezone.localdate(), status="confirmed",
        )
        from apps.payments.models import Payment
        Payment.objects.create(
            application=self.app, amount="500.00", status="completed",
        )
        adoption = AdoptionRecord.objects.create(
            application=self.app, pet=self.pet, adopter=self.adopter,
            staff_member=self.staff, status="scheduled",
        )
        self.authenticate_staff()
        resp = self.client.patch(f"/api/adoptions/{adoption.id}/", {"status": "completed", "confirmed": True}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "adopted")

    def test_invalid_adoption_status_transition(self):
        adoption = AdoptionRecord.objects.create(
            application=self.app, pet=self.pet, adopter=self.adopter,
            staff_member=self.staff, status="completed",
        )
        self.authenticate_staff()
        # completed -> scheduled is invalid
        resp = self.client.patch(f"/api/adoptions/{adoption.id}/", {"status": "scheduled"})
        self.assertEqual(resp.status_code, 400)

    def test_adopter_cannot_create_adoption(self):
        # staff only
        self.authenticate(self.adopter)
        resp = self.client.post("/api/adoptions/", {"application_id": str(self.app.id)})
        self.assertEqual(resp.status_code, 403)

    def test_scheduled_to_cancelled_reverts_pet_to_available(self):
        # Pet is pending because the application was approved; cancellation
        # must put it back to available.
        self.pet.status = "pending"
        self.pet.save(update_fields=["status"])
        self.authenticate_staff()
        resp = self.client.post("/api/adoptions/", {"application_id": str(self.app.id)})
        self.assertEqual(resp.status_code, 201)
        adoption_id = resp.data["id"]
        resp = self.client.patch(f"/api/adoptions/{adoption_id}/", {"status": "cancelled"})
        self.assertEqual(resp.status_code, 200)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "available")

    def test_completed_to_returned_reverts_pet_and_allows_reapply(self):
        Appointment.objects.create(
            application=self.app, pet=self.pet, adopter=self.adopter,
            requested_date=timezone.localdate(), status="confirmed",
        )
        from apps.payments.models import Payment
        Payment.objects.create(
            application=self.app, amount="500.00", status="completed",
        )
        # scheduled -> completed (pet adopted) -> returned (pet available),
        # then a NEW adopter can apply for the returned pet.
        self.pet.status = "pending"
        self.pet.save(update_fields=["status"])
        self.authenticate_staff()
        resp = self.client.post("/api/adoptions/", {"application_id": str(self.app.id)})
        self.assertEqual(resp.status_code, 201)
        adoption_id = resp.data["id"]
        resp = self.client.patch(f"/api/adoptions/{adoption_id}/", {"status": "completed", "confirmed": True}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "adopted")
        resp = self.client.patch(f"/api/adoptions/{adoption_id}/", {
            "status": "returned", "return_reason": "Allergies",
        })
        self.assertEqual(resp.status_code, 200)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "available")
        # New adopter can submit an application for the returned pet.
        new_adopter = self.create_user(email="newadopter@example.com")
        self.authenticate(new_adopter)
        # Applications are submitted together with their required documents.
        from django.core.files.uploadedfile import SimpleUploadedFile
        resp = self.client.post("/api/applications/", {
            "pet": str(self.pet.id), "why_adopt": "New family",
            "privacy_consent": True,
            "require_home_visit": True,
            "documents": [
                SimpleUploadedFile("id.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
                SimpleUploadedFile("address.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
                SimpleUploadedFile("brgy.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
                SimpleUploadedFile("cage.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
            ],
            "document_types": [
                "identification", "proof_of_address",
                "barangay_certification", "cage_photo",
            ],
        }, format="multipart")
        self.assertEqual(resp.status_code, 201)



def next_weekday(days_ahead=1):
    """A future date that falls Monday-Friday (the center's open days)."""
    day = timezone.localdate() + timedelta(days=days_ahead)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


class AppointmentApprovalSchedulesAdoptionTests(BaseAPITestCase):
    """Approving the onsite visit date schedules the adoption record.

    Staff never create a Scheduled record by hand: the appointment approval
    endpoint does it server-side.  These tests drive the real HTTP endpoints
    (appointment create/approve, payments, complete-adoption) because this
    workflow has to be correct end to end, not only at the model layer.
    """

    PAYMENT_FEE = "500.00"

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
        self.visit_date = next_weekday()

    # ----- helpers ------------------------------------------------------

    def request_appointment(self, application=None, visit_date=None):
        self.authenticate(self.adopter)
        return self.client.post(
            "/api/appointments/",
            {
                "application_id": str((application or self.application).id),
                "requested_date": (visit_date or self.visit_date).isoformat(),
            },
        )

    def approve(self, appointment):
        self.authenticate(self.staff)
        return self.client.post(f"/api/appointments/{appointment['id']}/approve/")

    def reject(self, appointment, reason="Fully booked"):
        self.authenticate(self.staff)
        return self.client.post(
            f"/api/appointments/{appointment['id']}/reject/", {"reason": reason}
        )

    def record_payment(self, application=None):
        self.authenticate(self.staff)
        return self.client.post(
            "/api/payments/",
            {
                "application": str((application or self.application).id),
                "amount": self.PAYMENT_FEE,
                "method": "cash",
                "status": "completed",
                "payment_date": timezone.localdate().isoformat(),
                "reference_number": "OR-1",
            },
            format="json",
        )

    def complete(self, application=None, payload=None):
        self.authenticate(self.staff)
        if payload is None:
            payload = {"confirmed": True}
        return self.client.post(
            f"/api/applications/{(application or self.application).id}/complete-adoption/",
            payload,
            format="json",
        )

    # ----- Test 1: approved appointment schedules the adoption ----------

    def test_approving_appointment_creates_one_scheduled_adoption_record(self):
        appointment = self.request_appointment().data
        resp = self.approve(appointment)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "confirmed")

        # Staff did not create anything: the backend scheduled the record.
        self.assertEqual(AdoptionRecord.objects.count(), 1)
        record = AdoptionRecord.objects.get()
        self.assertEqual(record.status, "scheduled")
        self.assertEqual(record.application_id, self.application.id)
        self.assertEqual(record.pet, self.pet)
        self.assertEqual(record.adopter, self.adopter)
        self.assertEqual(str(record.appointment_id), appointment["id"])
        self.assertEqual(record.adoption_date, self.visit_date)
        self.assertEqual(record.staff_member, self.staff)

        # The record is visible to staff with its links and schedule date.
        self.authenticate(self.staff)
        listing = self.client.get("/api/adoptions/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["count"], 1)
        row = listing.data["results"][0]
        self.assertEqual(row["status"], "scheduled")
        self.assertEqual(str(row["application_id"]), str(self.application.id))
        self.assertEqual(str(row["appointment_id"]), appointment["id"])
        self.assertEqual(row["adoption_date"], self.visit_date.isoformat())
        self.assertEqual(row["appointment_date"], self.visit_date.isoformat())
        self.assertEqual(row["pet_name"], self.pet.name)
        self.assertEqual(row["adopter_email"], self.adopter.email)

        # Scheduling is not completion: nothing else changed.
        self.application.refresh_from_db()
        self.pet.refresh_from_db()
        self.assertEqual(self.application.status, "approved")
        self.assertEqual(self.pet.status, "pending")

        # Audit trail for the scheduling decision.
        self.assertTrue(
            AuditLog.objects.filter(
                action="adoption_scheduled",
                model_name="AdoptionRecord",
                object_id=str(record.id),
            ).exists()
        )

# ----- Test 2: duplicate approval never duplicates the record -------

    def test_repeated_approve_request_reuses_the_same_record(self):
        appointment = self.request_appointment().data
        self.assertEqual(self.approve(appointment).status_code, 200)
        record_id = AdoptionRecord.objects.get().id

        # Retry / double submit / page refresh of the same approval.
        resp = self.approve(appointment)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(AdoptionRecord.objects.count(), 1)
        self.assertEqual(AdoptionRecord.objects.get().id, record_id)

    def test_scheduling_the_same_appointment_again_reuses_the_record(self):
        from apps.adoptions.services import schedule_adoption_record_for_appointment

        appointment = self.request_appointment().data
        self.assertEqual(self.approve(appointment).status_code, 200)
        record_id = AdoptionRecord.objects.get().id

        stored = Appointment.objects.get(id=appointment["id"])
        again = schedule_adoption_record_for_appointment(stored, self.staff)
        self.assertEqual(again.id, record_id)
        self.assertEqual(again.status, "scheduled")
        self.assertEqual(AdoptionRecord.objects.count(), 1)

    def test_finished_record_is_never_reopened_or_duplicated(self):
        from apps.adoptions.services import schedule_adoption_record_for_appointment

        appointment = self.request_appointment().data
        self.assertEqual(self.approve(appointment).status_code, 200)
        record = AdoptionRecord.objects.get()

        # Existing staff action on the Adoption Records page.
        self.authenticate(self.staff)
        resp = self.client.patch(
            f"/api/adoptions/{record.id}/", {"status": "cancelled"}
        )
        self.assertEqual(resp.status_code, 200)

        # A later approval of the same confirmed visit must not create a second
        # record and must not reopen the cancelled one.
        again = schedule_adoption_record_for_appointment(
            Appointment.objects.get(id=appointment["id"]), self.staff
        )
        self.assertEqual(again.id, record.id)
        self.assertEqual(AdoptionRecord.objects.count(), 1)
        again.refresh_from_db()
        self.assertEqual(again.status, "cancelled")
# ----- Test 3: rejected appointment schedules nothing ---------------

    def test_rejected_appointment_does_not_create_a_scheduled_record(self):
        appointment = self.request_appointment().data
        resp = self.reject(appointment, "Fully booked")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(AdoptionRecord.objects.count(), 0)

        # Choosing another date starts unscheduled too.
        second = self.request_appointment(visit_date=next_weekday(8))
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.data["status"], "pending_confirmation")
        self.assertEqual(AdoptionRecord.objects.count(), 0)

    def test_cannot_approve_an_already_rejected_appointment(self):
        appointment = self.request_appointment().data
        self.assertEqual(self.reject(appointment).status_code, 200)
        resp = self.approve(appointment)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(AdoptionRecord.objects.count(), 0)

    # ----- Test 5: only the valid approval transition schedules ---------

    def test_unconfirmed_appointment_never_creates_a_record(self):
        from apps.adoptions.services import schedule_adoption_record_for_appointment

        pending = Appointment.objects.create(
            application=self.application,
            adopter=self.adopter,
            pet=self.pet,
            requested_date=next_weekday(),
            status=Appointment.Status.PENDING_CONFIRMATION,
        )
        self.assertIsNone(
            schedule_adoption_record_for_appointment(pending, self.staff)
        )
        self.assertEqual(AdoptionRecord.objects.count(), 0)

    def test_unapproved_application_never_gets_a_scheduled_record(self):
        from apps.adoptions.services import schedule_adoption_record_for_appointment

        other_pet = Pet.objects.create(
            name="Rex", species="dog", age_years=2, status="available"
        )
        submitted = Application.objects.create(
            adopter=self.adopter, pet=other_pet, status="submitted"
        )
        appointment = Appointment.objects.create(
            application=submitted,
            adopter=self.adopter,
            pet=other_pet,
            requested_date=next_weekday(),
            status=Appointment.Status.CONFIRMED,
        )
        self.assertIsNone(
            schedule_adoption_record_for_appointment(appointment, self.staff)
        )
        self.assertEqual(AdoptionRecord.objects.count(), 0)

    # ----- Test 4: Complete Adoption still works from the record --------

    def test_complete_adoption_uses_the_auto_scheduled_record(self):
        appointment = self.request_appointment().data
        self.assertEqual(self.approve(appointment).status_code, 200)
        record = AdoptionRecord.objects.get()
        self.assertEqual(record.status, "scheduled")

        # The guarded completion still refuses without an onsite payment.
        resp = self.complete()
        self.assertEqual(resp.status_code, 400)
        record.refresh_from_db()
        self.assertEqual(record.status, "scheduled")

        # Existing onsite payment workflow.
        self.assertEqual(self.record_payment().status_code, 201)

        resp = self.complete()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "adoption_completed")

        self.application.refresh_from_db()
        self.pet.refresh_from_db()
        self.assertEqual(self.application.status, "adoption_completed")
        self.assertEqual(self.pet.status, "adopted")

        # The completed record is the same one that was scheduled.
        self.assertEqual(AdoptionRecord.objects.count(), 1)
        record.refresh_from_db()
        self.assertEqual(record.status, "completed")
        self.assertEqual(record.completed_date, timezone.localdate())
        self.assertEqual(str(record.appointment_id), appointment["id"])
        self.assertEqual(record.adoption_date, self.visit_date)


class CompletedAdoptionTransactionTests(BaseAPITestCase):
    """Regression tests for completed adoption transactions (pet release).

    Verifies the business rule that a completed transaction is defined by a
    successful pet release/turnover, carrying a unique, immutable transaction ID,
    release date, completion timestamp, staff member, pet, and adopter.
    """

    PAYMENT_FEE = "500.00"

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(name="Luna", species="cat", age_years=2, status="pending")
        self.adopter = self.create_user(email="adopter_luna@example.com")
        self.staff = self.create_staff(email="staff_luna@example.com")
        self.application = Application.objects.create(
            adopter=self.adopter, pet=self.pet, status="approved"
        )
        self.visit_date = next_weekday()

    def _setup_scheduled_and_paid(self, app=None, pet=None, adopter=None):
        target_app = app or self.application
        target_adopter = adopter or self.adopter
        # Request appointment
        self.authenticate(target_adopter)
        apt_resp = self.client.post(
            "/api/appointments/",
            {
                "application_id": str(target_app.id),
                "requested_date": self.visit_date.isoformat(),
            },
        )
        self.assertEqual(apt_resp.status_code, 201)
        apt_id = apt_resp.data["id"]
        # Approve appointment
        self.authenticate(self.staff)
        appr_resp = self.client.post(f"/api/appointments/{apt_id}/approve/")
        self.assertEqual(appr_resp.status_code, 200)
        # Record payment
        pay_resp = self.client.post(
            "/api/payments/",
            {
                "application": str(target_app.id),
                "amount": self.PAYMENT_FEE,
                "method": "cash",
                "status": "completed",
                "payment_date": timezone.localdate().isoformat(),
                "reference_number": "OR-TEST-1",
            },
            format="json",
        )
        self.assertEqual(pay_resp.status_code, 201)

    def test_1_successful_release_creates_or_completes_exactly_one_transaction_record(self):
        self._setup_scheduled_and_paid()
        self.authenticate(self.staff)
        resp = self.client.post(f"/api/applications/{self.application.id}/complete-adoption/", {"confirmed": True}, format="json")
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(AdoptionRecord.objects.filter(application=self.application).count(), 1)
        record = AdoptionRecord.objects.get(application=self.application)
        self.assertEqual(record.status, AdoptionRecord.Status.COMPLETED)
        self.assertIsNotNone(record.transaction_id)
        self.assertTrue(record.transaction_id.startswith("TXN-"))

    def test_2_transaction_id_is_populated_and_unique(self):
        # First adoption
        self._setup_scheduled_and_paid()
        self.authenticate(self.staff)
        self.client.post(f"/api/applications/{self.application.id}/complete-adoption/", {"confirmed": True}, format="json")
        rec1 = AdoptionRecord.objects.get(application=self.application)
        self.assertTrue(rec1.transaction_id.startswith("TXN-"))

        # Second adoption with a different pet and adopter
        pet2 = Pet.objects.create(name="Milo", species="dog", age_years=1, status="pending")
        adopter2 = self.create_user(email="adopter_milo@example.com")
        app2 = Application.objects.create(adopter=adopter2, pet=pet2, status="approved")
        self._setup_scheduled_and_paid(app=app2, pet=pet2, adopter=adopter2)
        self.client.post(f"/api/applications/{app2.id}/complete-adoption/", {"confirmed": True}, format="json")
        rec2 = AdoptionRecord.objects.get(application=app2)
        self.assertTrue(rec2.transaction_id.startswith("TXN-"))

        # Unique across records
        self.assertNotEqual(rec1.transaction_id, rec2.transaction_id)

        # Database-level uniqueness enforcement
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            AdoptionRecord.objects.create(
                application=Application.objects.create(
                    adopter=self.adopter, pet=Pet.objects.create(name="Extra", species="dog"), status="approved"
                ),
                pet=self.pet,
                adopter=self.adopter,
                transaction_id=rec1.transaction_id,
                status=AdoptionRecord.Status.COMPLETED,
            )

    def test_3_completion_date_and_required_relationships_stored_correctly(self):
        self._setup_scheduled_and_paid()
        self.authenticate(self.staff)
        resp = self.client.post(f"/api/applications/{self.application.id}/complete-adoption/", {"confirmed": True}, format="json")
        self.assertEqual(resp.status_code, 200)

        record = AdoptionRecord.objects.get(application=self.application)
        self.assertEqual(record.pet, self.pet)
        self.assertEqual(record.adopter, self.adopter)
        self.assertEqual(record.staff_member, self.staff)
        self.assertEqual(record.adoption_date, self.visit_date)
        self.assertEqual(record.completed_date, timezone.localdate())
        self.assertIsNotNone(record.completed_at)
        self.assertEqual(record.completed_at.date(), timezone.localdate())

    def test_4_approval_without_successful_release_does_not_create_completed_transaction(self):
        # Application is approved, but release is not performed
        self.assertEqual(self.application.status, "approved")
        # No adoption records or any completed transaction records
        self.assertEqual(AdoptionRecord.objects.filter(status=AdoptionRecord.Status.COMPLETED).count(), 0)

        # Even with scheduled appointment, record is not completed
        self.authenticate(self.adopter)
        apt_resp = self.client.post(
            "/api/appointments/",
            {
                "application_id": str(self.application.id),
                "requested_date": self.visit_date.isoformat(),
            },
        )
        self.authenticate(self.staff)
        self.client.post(f"/api/appointments/{apt_resp.data['id']}/approve/")

        record = AdoptionRecord.objects.get(application=self.application)
        self.assertEqual(record.status, AdoptionRecord.Status.SCHEDULED)
        self.assertIsNone(record.transaction_id)
        self.assertIsNone(record.completed_date)
        self.assertIsNone(record.completed_at)

    def test_5_payment_recording_alone_does_not_mark_adoption_completed(self):
        self._setup_scheduled_and_paid()

        # Payment has been recorded, but release completion has not been triggered
        record = AdoptionRecord.objects.get(application=self.application)
        self.assertEqual(record.status, AdoptionRecord.Status.SCHEDULED)
        self.assertIsNone(record.transaction_id)
        self.assertIsNone(record.completed_date)
        self.assertIsNone(record.completed_at)

        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "approved")
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "pending")

    def test_6_retrying_or_repeating_completion_does_not_duplicate_or_change_id(self):
        self._setup_scheduled_and_paid()
        self.authenticate(self.staff)

        # First completion
        resp1 = self.client.post(f"/api/applications/{self.application.id}/complete-adoption/", {"confirmed": True}, format="json")
        self.assertEqual(resp1.status_code, 200)
        record1 = AdoptionRecord.objects.get(application=self.application)
        tx_id1 = record1.transaction_id
        completed_at1 = record1.completed_at

        # Repeat completion request (retry / duplicate click)
        resp2 = self.client.post(f"/api/applications/{self.application.id}/complete-adoption/", {"confirmed": True}, format="json")
        self.assertEqual(resp2.status_code, 200)

        # Must still be exactly one record with unchanged transaction ID
        self.assertEqual(AdoptionRecord.objects.filter(application=self.application).count(), 1)
        record2 = AdoptionRecord.objects.get(application=self.application)
        self.assertEqual(record2.transaction_id, tx_id1)
        self.assertEqual(record2.completed_at, completed_at1)

    def test_7_existing_completed_records_without_transaction_id_remain_readable(self):
        # Historical record created before transaction_id existed
        historical = AdoptionRecord.objects.create(
            application=self.application,
            pet=self.pet,
            adopter=self.adopter,
            staff_member=self.staff,
            status=AdoptionRecord.Status.COMPLETED,
            adoption_date=self.visit_date,
            completed_date=timezone.localdate(),
            transaction_id=None,
        )
        self.authenticate(self.staff)
        resp = self.client.get(f"/api/adoptions/{historical.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["transaction_id"])
        self.assertEqual(resp.data["status"], "completed")

        # Listing also works
        list_resp = self.client.get("/api/adoptions/")
        self.assertEqual(list_resp.status_code, 200)

    def test_8_unauthorized_users_cannot_create_or_alter_transaction_records(self):
        # Anonymous user cannot create
        self.unauthenticate()
        resp = self.client.post("/api/adoptions/", {"application_id": str(self.application.id)})
        self.assertEqual(resp.status_code, 403)

        # Adopter cannot create
        self.authenticate(self.adopter)
        resp = self.client.post("/api/adoptions/", {"application_id": str(self.application.id)})
        self.assertEqual(resp.status_code, 403)

        # Adopter cannot complete adoption
        resp = self.client.post(f"/api/applications/{self.application.id}/complete-adoption/", {"confirmed": True})
        self.assertEqual(resp.status_code, 403)

        # Staff cannot tamper with transaction_id through PATCH
        self._setup_scheduled_and_paid()
        self.authenticate(self.staff)
        self.client.post(f"/api/applications/{self.application.id}/complete-adoption/", {"confirmed": True}, format="json")
        rec = AdoptionRecord.objects.get(application=self.application)
        original_tx_id = rec.transaction_id

        patch_resp = self.client.patch(
            f"/api/adoptions/{rec.id}/",
            {"transaction_id": "TXN-TAMPERED-ID", "notes": "Updated note"},
            format="json",
        )
        self.assertEqual(patch_resp.status_code, 200)
        rec.refresh_from_db()
        self.assertEqual(rec.transaction_id, original_tx_id)  # unchanged
        self.assertEqual(rec.notes, "Updated note")

class Phase21HandoverHardeningTests(BaseAPITestCase):
    """Phase 2.1 - Require explicit physical handover boolean true.

    Every completion route (confirm-turnover, complete-adoption, PATCH /api/adoptions/{id}/)
    must reject missing, null, string, integer, and false confirmation values.
    Only an actual JSON boolean true succeeds.
    """

    PAYMENT_FEE = "500.00"

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(name="Panda", species="cat", age_years=1, status="pending")
        self.adopter = self.create_user(email="adopter_p21@example.com")
        self.staff = self.create_staff(email="staff_p21@example.com")
        self.application = Application.objects.create(
            adopter=self.adopter, pet=self.pet, status="approved"
        )
        self.visit_date = next_weekday()
        # Confirm appointment and record payment so only handover blocks completion
        self.authenticate(self.adopter)
        apt_resp = self.client.post(
            "/api/appointments/",
            {"application_id": str(self.application.id), "requested_date": self.visit_date.isoformat()},
        )
        self.authenticate(self.staff)
        self.client.post(f"/api/appointments/{apt_resp.data['id']}/approve/")
        self.client.post(
            "/api/payments/",
            {"application": str(self.application.id), "amount": self.PAYMENT_FEE,
             "method": "cash", "status": "completed",
             "payment_date": timezone.localdate().isoformat()},
            format="json",
        )
        self.record = AdoptionRecord.objects.get(application=self.application)

    def _complete_adoption(self, payload):
        self.authenticate(self.staff)
        return self.client.post(
            f"/api/applications/{self.application.id}/complete-adoption/",
            payload, format="json",
        )

    def _patch_adoption_record(self, payload):
        self.authenticate(self.staff)
        return self.client.patch(
            f"/api/adoptions/{self.record.id}/",
            payload, format="json",
        )

    # --- confirm-turnover / complete-adoption rejections ---

    def test_missing_confirmed_field_rejected(self):
        resp = self._complete_adoption({})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.data)

    def test_confirmed_false_rejected(self):
        resp = self._complete_adoption({"confirmed": False})
        self.assertEqual(resp.status_code, 400)

    def test_confirmed_null_rejected(self):
        resp = self._complete_adoption({"confirmed": None})
        self.assertEqual(resp.status_code, 400)

    def test_confirmed_string_true_rejected(self):
        resp = self._complete_adoption({"confirmed": "true"})
        self.assertEqual(resp.status_code, 400)

    def test_confirmed_integer_1_rejected(self):
        resp = self._complete_adoption({"confirmed": 1})
        self.assertEqual(resp.status_code, 400)

    def test_contradictory_confirmed_and_turnover_confirmed_rejected(self):
        resp = self._complete_adoption({"confirmed": True, "turnover_confirmed": False})
        self.assertEqual(resp.status_code, 400)

    def test_both_true_accepted(self):
        resp = self._complete_adoption({"confirmed": True, "turnover_confirmed": True})
        self.assertEqual(resp.status_code, 200)

    def test_turnover_confirmed_true_only_accepted(self):
        # Re-create application and setup since previous test consumed it
        pet2 = Pet.objects.create(name="Panda2", species="cat", age_years=1, status="pending")
        app2 = Application.objects.create(adopter=self.adopter, pet=pet2, status="approved")
        self.authenticate(self.adopter)
        apt_resp = self.client.post(
            "/api/appointments/",
            {"application_id": str(app2.id), "requested_date": next_weekday(3).isoformat()},
        )
        self.authenticate(self.staff)
        self.client.post(f"/api/appointments/{apt_resp.data['id']}/approve/")
        self.client.post(
            "/api/payments/",
            {"application": str(app2.id), "amount": self.PAYMENT_FEE,
             "method": "cash", "status": "completed",
             "payment_date": timezone.localdate().isoformat()},
            format="json",
        )
        resp = self.client.post(
            f"/api/applications/{app2.id}/complete-adoption/",
            {"turnover_confirmed": True}, format="json",
        )
        self.assertEqual(resp.status_code, 200)

    # --- PATCH /api/adoptions/{id}/ -> status=completed also requires confirmation ---

    def test_patch_adoption_record_completed_without_confirmation_rejected(self):
        resp = self._patch_adoption_record({"status": "completed"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.data)
        self.application.refresh_from_db()
        self.assertNotEqual(self.application.status, "adoption_completed")

    def test_patch_adoption_record_completed_with_false_rejected(self):
        resp = self._patch_adoption_record({"status": "completed", "confirmed": False})
        self.assertEqual(resp.status_code, 400)

    def test_patch_adoption_record_completed_with_boolean_true_succeeds(self):
        resp = self._patch_adoption_record({"status": "completed", "confirmed": True})
        self.assertEqual(resp.status_code, 200)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "adoption_completed")
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "adopted")

    def test_patch_adoption_record_non_completion_updates_do_not_require_confirmation(self):
        """Updating notes on an adoption record does not require a handover confirmation."""
        resp = self._patch_adoption_record({"notes": "Updated note by staff."})
        self.assertEqual(resp.status_code, 200)

    # --- confirm-turnover route requires the same explicit confirmation ---

    def test_confirm_turnover_without_confirmation_rejected(self):
        """POST /api/applications/{id}/confirm-turnover/ needs boolean true."""
        self.authenticate(self.staff)
        resp = self.client.post(
            f"/api/applications/{self.application.id}/confirm-turnover/",
            {"notes": "Handed over on site."},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "approved")
        self.assertEqual(self.record.status, AdoptionRecord.Status.SCHEDULED)

    def test_confirm_turnover_with_boolean_true_succeeds(self):
        self.authenticate(self.staff)
        resp = self.client.post(
            f"/api/applications/{self.application.id}/confirm-turnover/",
            {"confirmed": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "adoption_completed")
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "adopted")

    # --- update-status route to adoption_completed requires the same confirmation ---

    def test_update_status_completion_without_confirmation_rejected(self):
        """update-status -> adoption_completed is blocked without boolean true.

        All other prereqs (approved application, confirmed appointment, completed
        payment) are satisfied in setUp, so only the handover confirmation is
        missing and must be the reason for the 400.
        """
        self.authenticate(self.staff)
        resp = self.client.post(
            f"/api/applications/{self.application.id}/update-status/",
            {"status": "adoption_completed"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "approved")
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "pending")
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, AdoptionRecord.Status.SCHEDULED)

    def test_update_status_completion_with_boolean_true_succeeds(self):
        self.authenticate(self.staff)
        resp = self.client.post(
            f"/api/applications/{self.application.id}/update-status/",
            {"status": "adoption_completed", "confirmed": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "adoption_completed")
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "adopted")


    # --- idempotent retry under the row lock ---

    def test_service_retry_under_lock_returns_existing_completed_record(self):
        """A retry that loses the row lock returns the existing record untouched.

        This exercises the ``select_for_update`` reload path directly: the second
        call re-reads the application under the lock, sees ``adoption_completed``,
        and returns the already-completed record without re-running side effects.
        """
        from apps.adoptions.services import complete_application_adoption

        record1 = complete_application_adoption(
            self.application, self.staff, handover_confirmed=True
        )
        tx_id = record1.transaction_id
        completed_at = record1.completed_at
        self.assertEqual(record1.staff_member, self.staff)

        # A different staff member racing in after the first request committed.
        staff2 = self.create_staff(email="staff_p21c@example.com")
        record2 = complete_application_adoption(
            self.application, staff2, handover_confirmed=True
        )
        self.assertEqual(record2.id, record1.id)
        self.assertEqual(record2.transaction_id, tx_id)
        self.assertEqual(record2.completed_at, completed_at)
        # Staff attribution of the original completion is preserved.
        self.assertEqual(record2.staff_member, self.staff)

    def test_idempotent_retry_keeps_staff_and_does_not_duplicate_audit_or_notifications(self):
        """HTTP retry of an already-completed adoption is a no-op.

        The transaction_id, completed_at, and staff attribution of the original
        completion stay unchanged, and no duplicate audit logs or adoption
        notifications are written.
        """
        record_id = str(self.record.id)
        app_id = str(self.application.id)

        def completion_audit_count():
            return AuditLog.objects.filter(
                model_name="AdoptionRecord", action="adoption_completed",
                object_id=record_id,
            ).count() + AuditLog.objects.filter(
                model_name="Application", action="status_change",
                object_id=app_id, new_value="adoption_completed",
            ).count()

        def adoption_notification_count():
            return Notification.objects.filter(
                user=self.adopter, notification_type="adoption"
            ).count()

        # Complete with staff1 through the real HTTP endpoint.
        self.authenticate(self.staff)
        resp1 = self.client.post(
            f"/api/applications/{self.application.id}/complete-adoption/",
            {"confirmed": True}, format="json",
        )
        self.assertEqual(resp1.status_code, 200)
        self.record.refresh_from_db()
        tx_id = self.record.transaction_id
        completed_at = self.record.completed_at
        self.assertEqual(self.record.staff_member, self.staff)

        audit_after_first = completion_audit_count()
        notif_after_first = adoption_notification_count()
        self.assertEqual(audit_after_first, 2)  # record completion + application status change

        # Retry as a different staff member (simulates the concurrent loser).
        staff2 = self.create_staff(email="staff_p21d@example.com")
        self.authenticate(staff2)
        resp2 = self.client.post(
            f"/api/applications/{self.application.id}/complete-adoption/",
            {"confirmed": True}, format="json",
        )
        self.assertEqual(resp2.status_code, 200)

        self.record.refresh_from_db()
        self.assertEqual(self.record.transaction_id, tx_id)
        self.assertEqual(self.record.completed_at, completed_at)
        self.assertEqual(self.record.staff_member, self.staff)
        self.assertEqual(completion_audit_count(), audit_after_first)
        self.assertEqual(adoption_notification_count(), notif_after_first)


class AdoptionRecordsFilterTests(BaseAPITestCase):
    """Phase 3.3 - the adoption records list endpoint filters by status
    server-side so the staff records page can paginate correctly."""

    def setUp(self):
        super().setUp()
        self.adopter = self.create_user(email="adopter_records_33@example.com")
        self.staff = self.create_staff(email="staff_records_33@example.com")
        self.pet1 = Pet.objects.create(name="P1", species="dog", age_years=1, status="adopted")
        self.pet2 = Pet.objects.create(name="P2", species="cat", age_years=2, status="pending")

    def _make_record(self, pet, status="scheduled"):
        app = Application.objects.create(adopter=self.adopter, pet=pet, status="approved")
        return AdoptionRecord.objects.create(
            application=app, pet=pet, adopter=self.adopter,
            staff_member=self.staff, status=status,
        )

    def test_list_filters_by_status(self):
        """?status= returns only records in that state (paginated response)."""
        self._make_record(self.pet1, status="completed")
        self._make_record(self.pet2, status="scheduled")
        self.authenticate(self.staff)

        resp = self.client.get("/api/adoptions/?status=completed")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["status"], "completed")
        self.assertEqual(resp.data["results"][0]["pet_name"], "P1")

    def test_list_unknown_status_returns_empty(self):
        """An unknown status matches nothing instead of erroring."""
        self._make_record(self.pet1, status="completed")
        self.authenticate(self.staff)
        resp = self.client.get("/api/adoptions/?status=does_not_exist")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 0)

    def test_list_unfiltered_returns_all_records_paginated(self):
        """Without a filter, the endpoint is the paginated list of all records."""
        self._make_record(self.pet1, status="completed")
        self._make_record(self.pet2, status="cancelled")
        self.authenticate(self.staff)
        resp = self.client.get("/api/adoptions/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 2)
        self.assertIsNone(resp.data["next"])
        self.assertIsNone(resp.data["previous"])

    def test_adopters_are_blocked_from_adoption_records(self):
        """The adoption records endpoint stays staff-only; the new status filter
        does not change access control."""
        self._make_record(self.pet1, status="completed")
        self.authenticate(self.adopter)
        all_resp = self.client.get("/api/adoptions/")
        self.assertEqual(all_resp.status_code, 403)
        filtered_resp = self.client.get("/api/adoptions/?status=completed")
        self.assertEqual(filtered_resp.status_code, 403)


def _extract_pdf_text(content):
    """Return the joined text of the PDF's content streams.

    ReportLab 5.x writes page content as ``/ASCII85Decode /FlateDecode`` by
    default, so the raw PDF bytes are not directly searchable. This helper
    decodes every content stream and joins the text strings (PDF breaks long
    lines into separate ``(text) Tj`` operators, so joining restores the full
    strings). Standard library only. Duplicated from ``apps.payments.tests``
    to keep the adoption test module self-contained.
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


class AdoptionPdfExportTests(BaseAPITestCase):
    """Phase 4.2 - staff-authorized A4 PDF export of adoption records.

    The report is generated server-side from persisted AdoptionRecord rows and
    reuses the list endpoint's queryset + ``?status=`` filter, so transaction
    IDs and statuses are read-only here (never generated or modified).
    """

    def setUp(self):
        super().setUp()
        self.adopter = self.create_user(email="adopter_pdf42@example.com")
        self.staff = self.create_staff(email="staff_pdf42@example.com")
        self.pet = Pet.objects.create(name="Max", species="dog", age_years=2, status="adopted")
        self.app = Application.objects.create(
            adopter=self.adopter, pet=self.pet, status="approved"
        )
        self.appointment = Appointment.objects.create(
            application=self.app, pet=self.pet, adopter=self.adopter,
            requested_date=timezone.localdate(), status=Appointment.Status.CONFIRMED,
        )
        self.completed = AdoptionRecord.objects.create(
            application=self.app, pet=self.pet, adopter=self.adopter,
            staff_member=self.staff, status=AdoptionRecord.Status.COMPLETED,
            appointment=self.appointment,
            completed_at=timezone.now(), completed_date=timezone.localdate(),
            transaction_id="TXN-ADOPT-42-COMPLETE",
        )
        self.scheduled_pet = Pet.objects.create(
            name="Bella", species="cat", age_years=1, status="pending"
        )
        self.scheduled_app = Application.objects.create(
            adopter=self.adopter, pet=self.scheduled_pet, status="approved"
        )
        self.scheduled = AdoptionRecord.objects.create(
            application=self.scheduled_app, pet=self.scheduled_pet, adopter=self.adopter,
            staff_member=self.staff, status=AdoptionRecord.Status.SCHEDULED,
            adoption_date=timezone.localdate(),
        )
    def test_export_pdf_requires_staff_permissions(self):
        self.unauthenticate()
        resp = self.client.get("/api/adoptions/export-pdf/")
        self.assertIn(resp.status_code, [401, 403])
        # Adopters are blocked by IsStaff (this is a staff-only endpoint).
        self.authenticate(self.adopter)
        resp = self.client.get("/api/adoptions/export-pdf/")
        self.assertEqual(resp.status_code, 403)

    def test_export_pdf_returns_pdf_attachment_with_fields(self):
        self.authenticate(self.staff)
        snapshot = (
            self.completed.transaction_id, self.completed.status, self.completed.completed_at,
        )
        resp = self.client.get("/api/adoptions/export-pdf/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp["Content-Type"].startswith("application/pdf"))
        self.assertTrue(
            resp["Content-Disposition"].startswith(
                'attachment; filename="pawconnect-adoption-records-'
            )
        )
        self.assertTrue(resp.content.startswith(b"%PDF-1."))
        text = _extract_pdf_text(resp.content)
        self.assertIn(b"PawConnect", text)
        self.assertIn(b"Adoption Records Report", text)
        self.assertIn(b"TXN-ADOPT-42-COMPLETE", text)
        self.assertIn(b"Max", text)
        self.assertIn(b"adopter_pdf42@example.com", text)
        self.assertIn(b"staff_pdf42@example.com", text)
        # The appointment date is included when a record has a stored visit.
        self.assertIn(timezone.localdate().isoformat().encode("ascii"), text)
        # Real statuses are displayed, and the summary reports both statuses.
        self.assertIn(b"Scheduled", text)
        self.assertIn(b"Completed", text)
        self.assertIn(b"Total adoption records: 2", text)
        # The export must never mutate records or invent transaction IDs.
        self.completed.refresh_from_db()
        self.assertEqual(
            (self.completed.transaction_id, self.completed.status, self.completed.completed_at),
            snapshot,
        )
        self.scheduled.refresh_from_db()
        self.assertIsNone(self.scheduled.transaction_id)
    def test_export_pdf_respects_status_filter(self):
        self.authenticate(self.staff)
        resp = self.client.get("/api/adoptions/export-pdf/?status=completed")
        self.assertEqual(resp.status_code, 200)
        text = _extract_pdf_text(resp.content)
        self.assertIn(b"TXN-ADOPT-42-COMPLETE", text)
        self.assertNotIn(b"Bella", text)  # scheduled pet excluded by the filter
        self.assertIn(b"Total adoption records: 1", text)

    def test_export_pdf_validates_status_filter(self):
        self.authenticate(self.staff)
        resp = self.client.get("/api/adoptions/export-pdf/?status=not-a-real-status")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("status", resp.data)

    def test_export_pdf_empty_match_still_returns_valid_pdf(self):
        self.authenticate(self.staff)
        resp = self.client.get("/api/adoptions/export-pdf/?status=returned")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b"%PDF-1."))
        text = _extract_pdf_text(resp.content)
        self.assertIn(b"No adoption records match the selected filters.", text)

