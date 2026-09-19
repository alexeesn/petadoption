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
            "documents": [
                SimpleUploadedFile("id.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
                SimpleUploadedFile("address.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
            ],
            "document_types": ["identification", "proof_of_address"],
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
