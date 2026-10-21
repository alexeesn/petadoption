from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.tests import BaseAPITestCase
from apps.appointments.models import Appointment
from apps.audit.models import AuditLog
from apps.pets.models import Pet
from apps.applications.models import Application
from apps.adoptions.models import AdoptionRecord


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
        resp = self.client.patch(f"/api/adoptions/{adoption.id}/", {"status": "completed"})
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
        resp = self.client.patch(f"/api/adoptions/{adoption_id}/", {"status": "completed"})
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

    def complete(self, application=None):
        self.authenticate(self.staff)
        return self.client.post(
            f"/api/applications/{(application or self.application).id}/complete-adoption/",
            {},
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
        resp = self.client.post(f"/api/applications/{self.application.id}/complete-adoption/", {}, format="json")
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
        self.client.post(f"/api/applications/{self.application.id}/complete-adoption/", {}, format="json")
        rec1 = AdoptionRecord.objects.get(application=self.application)
        self.assertTrue(rec1.transaction_id.startswith("TXN-"))

        # Second adoption with a different pet and adopter
        pet2 = Pet.objects.create(name="Milo", species="dog", age_years=1, status="pending")
        adopter2 = self.create_user(email="adopter_milo@example.com")
        app2 = Application.objects.create(adopter=adopter2, pet=pet2, status="approved")
        self._setup_scheduled_and_paid(app=app2, pet=pet2, adopter=adopter2)
        self.client.post(f"/api/applications/{app2.id}/complete-adoption/", {}, format="json")
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
        resp = self.client.post(f"/api/applications/{self.application.id}/complete-adoption/", {}, format="json")
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
        resp1 = self.client.post(f"/api/applications/{self.application.id}/complete-adoption/", {}, format="json")
        self.assertEqual(resp1.status_code, 200)
        record1 = AdoptionRecord.objects.get(application=self.application)
        tx_id1 = record1.transaction_id
        completed_at1 = record1.completed_at

        # Repeat completion request (retry / duplicate click)
        resp2 = self.client.post(f"/api/applications/{self.application.id}/complete-adoption/", {}, format="json")
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
        resp = self.client.post(f"/api/applications/{self.application.id}/complete-adoption/", {})
        self.assertEqual(resp.status_code, 403)

        # Staff cannot tamper with transaction_id through PATCH
        self._setup_scheduled_and_paid()
        self.authenticate(self.staff)
        self.client.post(f"/api/applications/{self.application.id}/complete-adoption/", {}, format="json")
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