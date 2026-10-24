"""HTTP regression coverage for physical returns and retained financial history."""
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.core import mail
from django.utils import timezone

from apps.accounts.tests import BaseAPITestCase
from apps.applications.models import Application
from apps.audit.models import AuditLog
from apps.notifications.models import Notification
from apps.payments.models import Payment
from apps.pets.models import Pet
from .models import AdoptionRecord


class AdoptionReturnTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.staff = self.create_staff(email="returns-staff@example.test")
        self.admin = self.create_admin(email="returns-admin@example.test")
        self.adopter = self.create_user(email="returns-adopter@example.test")
        self.other = self.create_user(email="returns-other@example.test")
        self.pet = Pet.objects.create(name="Return Buddy", species="dog", age_years=2, status="adopted")
        self.app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="adoption_completed")
        self.record = AdoptionRecord.objects.create(
            application=self.app, pet=self.pet, adopter=self.adopter, staff_member=self.staff,
            status="completed", transaction_id="TXN-RETURN-TEST", completed_date=timezone.localdate(),
            completed_at=timezone.now(), notes="Original completion notes",
        )
        self.payment = Payment.objects.create(
            application=self.app, adoption=self.record, amount="500.00", method="cash", status="completed",
            payment_date=timezone.localdate(), processed_by=self.staff,
        )
        self.url = f"/api/adoptions/{self.record.pk}/mark-returned/"
        self.authenticate(self.staff)

    def mark_returned(self, **overrides):
        data = {"return_reason": "Adopter developed allergies", "confirmed": True}
        data.update(overrides)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url, data, format="json")

    def test_return_preserves_completion_payments_receipt_and_notifies_once(self):
        old_record = AdoptionRecord.objects.values().get(pk=self.record.pk)
        old_payment = Payment.objects.values().get(pk=self.payment.pk)
        response = self.mark_returned()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "returned")
        self.assertTrue(response.data["return_date"])
        self.assertTrue(response.data["returned_at"])
        self.record.refresh_from_db()
        self.pet.refresh_from_db()
        self.app.refresh_from_db()
        self.assertEqual(self.pet.status, "for_assessment")
        self.assertEqual(self.app.status, "adoption_completed")
        for field in ("transaction_id", "completed_date", "completed_at", "staff_member_id", "notes"):
            self.assertEqual(getattr(self.record, field), old_record[field])
        self.assertEqual(Payment.objects.values().get(pk=self.payment.pk), old_payment)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(AdoptionRecord.objects.count(), 1)
        log = AuditLog.objects.get(action="adoption_returned", object_id=str(self.record.pk))
        self.assertEqual(log.user, self.staff)
        self.assertEqual(log.previous_value, "completed")
        self.assertIn("allergies", log.new_value)
        self.assertTrue(AuditLog.objects.filter(
            model_name="Pet", object_id=str(self.pet.pk), previous_value="adopted", new_value="for_assessment",
        ).exists())
        notification = Notification.objects.get(user=self.adopter, title="Adoption Returned")
        self.assertIn("no automatic refund", notification.message)
        self.assertEqual(notification.link, f"/applications/{self.app.pk}")
        self.assertEqual([message.subject for message in mail.outbox], ["Adoption Returned"])

    def test_reason_and_strict_physical_return_confirmation_are_required(self):
        for reason in (None, "", "   ", 42, "x" * 2001):
            with self.subTest(reason=repr(reason)[:40]):
                self.assertEqual(self.mark_returned(return_reason=reason).status_code, 400)
        for confirmed in (None, False, "true", 1):
            with self.subTest(confirmed=confirmed):
                self.assertEqual(self.mark_returned(confirmed=confirmed).status_code, 400)
        self.assertEqual(self.client.post(self.url, {}, format="json").status_code, 400)
        self.record.refresh_from_db()
        self.pet.refresh_from_db()
        self.assertEqual(self.record.status, "completed")
        self.assertIsNone(self.record.returned_at)
        self.assertEqual(self.pet.status, "adopted")
        self.assertFalse(AuditLog.objects.exists())
        self.assertFalse(Notification.objects.exists())

    def test_only_completed_records_can_be_returned(self):
        for record_status in ("scheduled", "cancelled"):
            with self.subTest(status=record_status):
                self.record.status = record_status
                self.record.save(update_fields=["status"])
                response = self.mark_returned()
                self.assertEqual(response.status_code, 400)
                self.record.refresh_from_db()
                self.assertEqual(self.record.status, record_status)

    def test_anonymous_and_adopters_cannot_mark_returns(self):
        self.unauthenticate()
        self.assertEqual(self.mark_returned().status_code, 403)
        for user in (self.adopter, self.other):
            self.authenticate(user)
            self.assertEqual(self.mark_returned().status_code, 403)
            response = self.client.patch(f"/api/adoptions/{self.record.pk}/", {
                "status": "returned", "return_reason": "No access", "confirmed": True,
            }, format="json")
            self.assertEqual(response.status_code, 403)

    def test_admin_can_mark_return_and_owner_can_read_but_others_cannot(self):
        self.authenticate(self.admin)
        self.assertEqual(self.mark_returned().status_code, 200)
        self.authenticate(self.adopter)
        response = self.client.get(f"/api/adoptions/{self.record.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["return_reason"], "Adopter developed allergies")
        self.authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/adoptions/{self.record.pk}/").status_code, 404)

    def test_patch_uses_same_validation_and_does_not_change_other_fields(self):
        url = f"/api/adoptions/{self.record.pk}/"
        data = {"status": "returned", "return_reason": "Allergies"}
        self.assertEqual(self.client.patch(url, data, format="json").status_code, 400)
        response = self.client.patch(url, {**data, "confirmed": True, "notes": "Overwrite"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.record.refresh_from_db()
        self.assertEqual(self.record.notes, "Original completion notes")
        self.assertEqual(self.record.return_reason, "Allergies")

    def test_retry_keeps_original_return_details_and_does_not_release_rehomed_pet(self):
        self.assertEqual(self.mark_returned().status_code, 200)
        original_record = AdoptionRecord.objects.values().get(pk=self.record.pk)
        self.pet.status = "adopted"
        self.pet.save(update_fields=["status"])
        self.assertEqual(self.mark_returned(return_reason="Duplicate retry").status_code, 200)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "adopted")
        self.assertEqual(AdoptionRecord.objects.values().get(pk=self.record.pk), original_record)
        self.assertEqual(AuditLog.objects.filter(action="adoption_returned").count(), 1)
        self.assertEqual(Notification.objects.filter(title="Adoption Returned").count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_return_details_cannot_be_changed_through_generic_patch(self):
        self.assertEqual(self.mark_returned().status_code, 200)
        original_record = AdoptionRecord.objects.values().get(pk=self.record.pk)
        response = self.client.patch(f"/api/adoptions/{self.record.pk}/", {
            "return_reason": "Overwrite", "returned_at": "2020-01-01T00:00:00Z", "return_date": "2020-01-01",
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.record.refresh_from_db()
        for field in ("return_reason", "returned_at", "return_date"):
            self.assertEqual(getattr(self.record, field), original_record[field])

    def test_return_date_uses_philippine_date_even_when_server_is_in_utc(self):
        now = datetime(2026, 10, 23, 16, 30, tzinfo=dt_timezone.utc)
        with patch("django.utils.timezone.now", return_value=now):
            response = self.mark_returned()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["return_date"], "2026-10-24")

    def test_conflicting_adoption_cannot_be_released(self):
        app = Application.objects.create(adopter=self.other, pet=self.pet, status="approved")
        AdoptionRecord.objects.create(application=app, adopter=self.other, pet=self.pet)
        self.assertEqual(self.mark_returned().status_code, 400)
        self.pet.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(self.pet.status, "adopted")
        self.assertEqual(self.record.status, "completed")

    def test_return_rolls_back_all_changes_when_notification_fails(self):
        with patch("apps.appointments.services.notify_adopter", side_effect=RuntimeError("Notification failure")):
            with self.assertRaises(RuntimeError):
                self.mark_returned()
        self.pet.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(self.pet.status, "adopted")
        self.assertEqual(self.record.status, "completed")
        self.assertIsNone(self.record.returned_at)
        self.assertFalse(AuditLog.objects.exists())

    def test_return_does_not_require_or_create_a_payment(self):
        self.payment.delete()
        self.assertEqual(self.mark_returned().status_code, 200)
        self.assertFalse(Payment.objects.exists())

    def test_returned_filter_lists_the_persisted_record(self):
        self.assertEqual(self.mark_returned().status_code, 200)
        response = self.client.get("/api/adoptions/?status=returned")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(str(response.data["results"][0]["id"]), str(self.record.pk))
        self.assertEqual(self.client.get("/api/adoptions/?status=completed").data["count"], 0)

    def test_return_is_held_off_available_list_and_reapplication_until_cleared(self):
        from apps.health.models import HealthRecord
        health = HealthRecord.objects.create(pet=self.pet, record_date="2025-01-01", diagnosis="Limping")
        before = HealthRecord.objects.values().get(pk=health.pk)
        self.assertEqual(self.mark_returned().status_code, 200)
        self.assertEqual(self.client.get("/api/pets/", {"status": "available", "search": self.pet.name}).data["count"], 0)
        active_health = self.client.get("/api/health-records/", {"scope": "active", "pet": self.pet.pk})
        self.assertEqual(active_health.data["count"], 1)
        self.assertEqual(active_health.data["results"][0]["pet_status"], "for_assessment")
        self.authenticate(self.other)
        for pet_status in ("for_assessment", "under_medical_care"):
            Pet.objects.filter(pk=self.pet.pk).update(status=pet_status)
            response = self.client.post("/api/applications/", {
                "pet": str(self.pet.pk), "privacy_consent": True, "require_home_visit": True,
            }, format="json")
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn("pet", response.data)
        self.assertEqual(HealthRecord.objects.values().get(pk=health.pk), before)
        self.assertFalse(Application.objects.filter(adopter=self.other, pet=self.pet).exists())

    def test_staff_assesses_medical_care_and_clears_without_changing_return_or_payment(self):
        self.assertEqual(self.mark_returned().status_code, 200)
        returned = AdoptionRecord.objects.values().get(pk=self.record.pk)
        payment = Payment.objects.values().get(pk=self.payment.pk)
        url = f"/api/pets/{self.pet.pk}/"
        for blocked_status in ("pending", "reserved", "adopted"):
            self.assertEqual(self.client.patch(url, {"status": blocked_status}, format="json").status_code, 400)
        for pet_status, available_count in (("under_medical_care", 0), ("available", 1)):
            response = self.client.patch(url, {"status": pet_status}, format="json")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["status"], pet_status)
            self.assertEqual(self.client.get("/api/pets/", {"status": "available", "search": self.pet.name}).data["count"], available_count)
            self.assertTrue(AuditLog.objects.filter(action="pet_status_change", object_id=str(self.pet.pk), new_value=pet_status).exists())
        self.assertEqual(AdoptionRecord.objects.values().get(pk=self.record.pk), returned)
        self.assertEqual(Payment.objects.values().get(pk=self.payment.pk), payment)

    def test_adopter_cannot_clear_the_returned_pet(self):
        self.assertEqual(self.mark_returned().status_code, 200)
        self.authenticate(self.adopter)
        self.assertEqual(self.client.patch(f"/api/pets/{self.pet.pk}/", {"status": "available"}, format="json").status_code, 403)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "for_assessment")

    def test_stale_applications_cannot_bypass_assessment_through_approval(self):
        self.assertEqual(self.mark_returned().status_code, 200)
        application = Application.objects.create(pet=self.pet, adopter=self.other, status="submitted")
        for pet_status in ("for_assessment", "under_medical_care"):
            Pet.objects.filter(pk=self.pet.pk).update(status=pet_status)
            for url, data in (
                (f"/api/applications/{application.pk}/update-status/", {"status": "approved"}),
                ("/api/reviews/", {"application": str(application.pk), "decision": "approve"}),
            ):
                response = self.client.post(url, data, format="json")
                self.assertEqual(response.status_code, 400, response.data)
            response = self.client.patch(f"/api/applications/{application.pk}/", {"status": "approved"}, format="json")
            self.assertEqual(response.status_code, 400, response.data)
            application.refresh_from_db()
            self.pet.refresh_from_db()
            self.assertEqual(application.status, "submitted")
            self.assertEqual(self.pet.status, pet_status)

    def test_stale_approved_application_cannot_complete_a_pet_in_care(self):
        from apps.appointments.models import Appointment
        self.assertEqual(self.mark_returned().status_code, 200)
        application = Application.objects.create(pet=self.pet, adopter=self.other, status="approved")
        appointment = Appointment.objects.create(application=application, pet=self.pet, adopter=self.other,
                                                 status="confirmed", requested_date=timezone.localdate())
        record = AdoptionRecord.objects.create(application=application, pet=self.pet, adopter=self.other,
                                               appointment=appointment, status="scheduled")
        Payment.objects.create(application=application, amount="500.00", status="completed", method="cash")
        for pet_status in ("for_assessment", "under_medical_care"):
            Pet.objects.filter(pk=self.pet.pk).update(status=pet_status)
            response = self.client.post(f"/api/applications/{application.pk}/complete-adoption/", {"confirmed": True}, format="json")
            self.assertEqual(response.status_code, 400, response.data)
            record.refresh_from_db()
            self.assertEqual(record.status, "scheduled")
            self.assertIsNone(record.transaction_id)
