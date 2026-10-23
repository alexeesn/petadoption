from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.core import mail
from django.utils import timezone

from apps.accounts.tests import BaseAPITestCase
from apps.adoptions.models import AdoptionRecord
from apps.applications.models import Application
from apps.audit.models import AuditLog
from apps.notifications.models import Notification
from apps.payments.models import Payment
from apps.pets.models import Pet
from .models import Appointment, RescheduleRequest
from .tests import next_weekday


class AppointmentFollowupTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.adopter = self.create_user(email="followup-adopter@example.com")
        self.other = self.create_user(email="other-followup@example.com")
        self.staff = self.create_staff(email="followup-staff@example.com")
        self.admin = self.create_admin(email="followup-admin@example.com")
        self.pet = Pet.objects.create(name="Reschedule Buddy", species="dog", age_years=2, status="pending")
        self.app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="approved")
        self.appointment = Appointment.objects.create(
            application=self.app, adopter=self.adopter, pet=self.pet,
            requested_date=next_weekday(), status="confirmed",
        )
        self.record = AdoptionRecord.objects.create(
            application=self.app, adopter=self.adopter, pet=self.pet, staff_member=self.staff,
            appointment=self.appointment, adoption_date=self.appointment.requested_date,
        )
        self.new_date = next_weekday(8)

    def request_change(self, **overrides):
        self.authenticate(self.adopter)
        data = {"requested_date": self.new_date.isoformat(), "reason": "Work schedule changed"}
        data.update(overrides)
        return self.client.post(f"/api/appointments/{self.appointment.pk}/request-reschedule/", data, format="json")

    def review(self, request_id, approve=True, **overrides):
        self.authenticate(self.staff)
        data = {"confirmed": True}
        data.update(overrides)
        decision = "approve" if approve else "reject"
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(f"/api/appointments/reschedule-requests/{request_id}/{decision}/", data, format="json")

    def cancel(self, **overrides):
        self.authenticate(self.staff)
        data = {"reason": "Adopter withdrew", "confirmed": True}
        data.update(overrides)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(f"/api/adoptions/{self.record.pk}/cancel/", data, format="json")

    def make_past_visit(self):
        day = timezone.localdate() - timedelta(days=2)
        while day.weekday() >= 5:
            day -= timedelta(days=1)
        self.appointment.requested_date = day
        self.appointment.save(update_fields=["requested_date"])
        self.record.adoption_date = day
        self.record.save(update_fields=["adoption_date"])

    def test_request_notifies_staff_without_changing_confirmed_date(self):
        original_date = self.appointment.requested_date
        response = self.request_change()
        self.assertEqual(response.status_code, 201, response.data)
        self.appointment.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(self.appointment.requested_date, original_date)
        self.assertEqual(self.appointment.status, "confirmed")
        self.assertEqual(self.record.adoption_date, original_date)
        self.assertEqual(self.record.status, "scheduled")
        self.assertEqual(Notification.objects.filter(title="Reschedule Requested").count(), 2)
        for user in (self.staff, self.admin):
            notification = Notification.objects.get(user=user, title="Reschedule Requested")
            self.assertIn("Work schedule changed", notification.message)
            self.assertIn(self.adopter.email, notification.message)
            self.assertEqual(notification.link, "/appointments?tab=reschedules")
        self.assertFalse(Payment.objects.exists())

    def test_only_owner_can_request_and_adopter_cannot_review(self):
        self.authenticate(self.other)
        url = f"/api/appointments/{self.appointment.pk}/request-reschedule/"
        response = self.client.post(url, {"requested_date": self.new_date.isoformat(), "reason": "Other"})
        self.assertEqual(response.status_code, 404)
        self.authenticate(self.staff)
        self.assertEqual(self.client.post(url, {}).status_code, 403)
        request = self.request_change().data
        self.authenticate(self.adopter)
        self.assertEqual(self.client.post(f"/api/appointments/reschedule-requests/{request['id']}/approve/", {"confirmed": True}).status_code, 403)
        self.authenticate(self.other)
        self.assertEqual(self.client.get("/api/appointments/reschedule-requests/").data["count"], 0)
        self.assertEqual(self.client.get(f"/api/appointments/reschedule-requests/{request['id']}/").status_code, 404)

    def test_invalid_dates_reasons_and_duplicate_requests_rejected(self):
        for changes in ({"reason": "  "}, {"reason": "x" * 2001},
                        {"requested_date": self.appointment.requested_date.isoformat()},
                        {"requested_date": "2020-01-01"}, {"requested_date": "not-a-date"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.request_change(**changes).status_code, 400)
        weekend = self.new_date
        while weekend.weekday() != 5:
            weekend += timedelta(days=1)
        self.assertEqual(self.request_change(requested_date=weekend.isoformat()).status_code, 400)
        self.assertEqual(self.request_change().status_code, 201)
        self.assertEqual(self.request_change().status_code, 400)
        self.assertEqual(RescheduleRequest.objects.count(), 1)

    def test_approval_preserves_history_and_reuses_adoption_and_payment(self):
        payment = Payment.objects.create(application=self.app, amount="500.00", status="completed")
        before = list(Payment.objects.values())
        request = self.request_change().data
        response = self.review(request["id"])
        self.assertEqual(response.status_code, 200, response.data)
        self.appointment.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(self.appointment.status, "rescheduled")
        self.assertEqual(self.appointment.requested_date.isoformat(), request["original_date"])
        replacement = Appointment.objects.get(pk=response.data["replacement_appointment"])
        self.assertEqual(replacement.status, "confirmed")
        self.assertEqual(replacement.requested_date, self.new_date)
        self.assertEqual(self.record.appointment_id, replacement.pk)
        self.assertEqual(self.record.adoption_date, self.new_date)
        self.assertEqual(self.record.status, "scheduled")
        self.assertIsNone(self.record.transaction_id)
        self.assertEqual(AdoptionRecord.objects.count(), 1)
        self.assertEqual(list(Payment.objects.values()), before)
        self.assertEqual(Payment.objects.get().pk, payment.pk)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Reschedule Approved", mail.outbox[0].subject)
        self.assertIn(str(self.new_date), mail.outbox[0].body)
        audit_count = AuditLog.objects.count()
        self.assertEqual(self.review(request["id"]).status_code, 400)
        self.assertEqual(AuditLog.objects.count(), audit_count)
        self.assertEqual(Appointment.objects.count(), 2)

    def test_rejection_keeps_schedule_and_allows_another_request(self):
        request = self.request_change().data
        self.assertEqual(self.review(request["id"], approve=False, reason=" ").status_code, 400)
        response = self.review(request["id"], approve=False, reason="Center fully booked")
        self.assertEqual(response.status_code, 200, response.data)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "confirmed")
        self.assertEqual(Appointment.objects.count(), 1)
        self.assertIn("Center fully booked", mail.outbox[0].body)
        self.assertEqual(self.request_change().status_code, 201)

    def test_no_show_requires_elapsed_date_reason_confirmation_and_staff(self):
        url = f"/api/appointments/{self.appointment.pk}/mark-no-show/"
        self.authenticate(self.adopter)
        self.assertEqual(self.client.post(url, {"reason": "Absent", "confirmed": True}).status_code, 403)
        self.authenticate(self.staff)
        self.assertEqual(self.client.post(url, {"reason": "Absent", "confirmed": True}, format="json").status_code, 400)
        self.make_past_visit()
        for data in ({}, {"reason": " "}, {"reason": "Absent", "confirmed": "true"}):
            self.assertEqual(self.client.post(url, data, format="json").status_code, 400)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, {"reason": "Adopter did not arrive", "confirmed": True}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "no_show")
        self.app.refresh_from_db()
        self.record.refresh_from_db()
        self.pet.refresh_from_db()
        self.assertEqual(self.app.status, "approved")
        self.assertEqual(self.record.status, "scheduled")
        self.assertEqual(self.pet.status, "pending")
        self.assertEqual(self.request_change().status_code, 201)
        request = RescheduleRequest.objects.get()
        self.assertEqual(self.review(request.pk).status_code, 200)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "no_show")
        self.assertEqual(self.appointment.no_show_reason, "Adopter did not arrive")

    def test_same_day_no_show_only_after_center_closes_in_philippines(self):
        self.appointment.requested_date = datetime(2026, 10, 23).date()
        self.appointment.save(update_fields=["requested_date"])
        self.authenticate(self.staff)
        url = f"/api/appointments/{self.appointment.pk}/mark-no-show/"
        data = {"reason": "No arrival", "confirmed": True}
        with patch("django.utils.timezone.now", return_value=datetime(2026, 10, 23, 8, 59, tzinfo=dt_timezone.utc)):
            self.assertEqual(self.client.post(url, data, format="json").status_code, 400)
        with patch("django.utils.timezone.now", return_value=datetime(2026, 10, 23, 9, 0, tzinfo=dt_timezone.utc)):
            self.assertEqual(self.client.post(url, data, format="json").status_code, 200)

    def test_new_booking_cannot_bypass_pending_reschedule(self):
        self.appointment.status = "no_show"
        self.appointment.save(update_fields=["status"])
        self.assertEqual(self.request_change().status_code, 201)
        response = self.client.post("/api/appointments/", {
            "application_id": str(self.app.pk), "requested_date": self.new_date.isoformat(),
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_cancel_closes_application_appointments_requests_and_keeps_payments(self):
        request = self.request_change().data
        Payment.objects.create(application=self.app, amount="500.00", status="completed")
        payments = list(Payment.objects.values())
        response = self.cancel()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "cancelled")
        self.assertEqual(response.data["cancellation_reason"], "Adopter withdrew")
        self.assertIsNotNone(response.data["cancelled_at"])
        self.app.refresh_from_db()
        self.appointment.refresh_from_db()
        self.pet.refresh_from_db()
        self.assertEqual(self.app.status, "cancelled")
        self.assertEqual(self.appointment.status, "cancelled")
        self.assertEqual(self.pet.status, "available")
        self.assertEqual(RescheduleRequest.objects.get(pk=request["id"]).status, "cancelled")
        self.assertEqual(list(Payment.objects.values()), payments)
        self.assertEqual(AdoptionRecord.objects.count(), 1)
        self.assertEqual(AuditLog.objects.get(action="adoption_cancelled").user, self.staff)
        self.assertEqual(len(mail.outbox), 1)
        before = (AuditLog.objects.count(), Notification.objects.count(), response.data["cancelled_at"])
        retried = self.cancel(reason="Retry must not overwrite the original reason")
        self.assertEqual(retried.status_code, 200)
        self.assertEqual(retried.data["cancellation_reason"], "Adopter withdrew")
        self.assertEqual((AuditLog.objects.count(), Notification.objects.count(), retried.data["cancelled_at"]), before)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.review(request["id"]).status_code, 400)
        self.authenticate(self.staff)
        self.assertEqual(self.client.post(f"/api/applications/{self.app.pk}/complete-adoption/", {"confirmed": True}, format="json").status_code, 400)

    def test_cancellation_requires_staff_reason_and_boolean_confirmation(self):
        self.authenticate(self.adopter)
        self.assertEqual(self.client.post(f"/api/adoptions/{self.record.pk}/cancel/", {"reason": "No", "confirmed": True}, format="json").status_code, 403)
        for value in (None, False, "true", 1):
            self.assertEqual(self.cancel(confirmed=value).status_code, 400)
        self.assertEqual(self.cancel(reason=" ").status_code, 400)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, "scheduled")

    def test_completed_or_returned_adoption_cannot_be_cancelled_or_rescheduled(self):
        for state in ("completed", "returned"):
            self.record.status = state
            self.record.save(update_fields=["status"])
            self.assertEqual(self.cancel().status_code, 400)
            self.assertEqual(self.request_change().status_code, 400)

    def test_generic_cancellation_cannot_skip_required_reason_or_synchronization(self):
        self.authenticate(self.staff)
        self.assertEqual(self.client.patch(f"/api/adoptions/{self.record.pk}/", {"status": "cancelled"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(f"/api/applications/{self.app.pk}/", {"status": "cancelled"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(f"/api/applications/{self.app.pk}/update-status/", {"status": "cancelled"}, format="json").status_code, 400)
        self.authenticate(self.adopter)
        self.assertEqual(self.client.post(f"/api/applications/{self.app.pk}/cancel/").status_code, 400)

    def test_generic_edit_cannot_bypass_handover_or_downgrade_approved_application(self):
        self.authenticate(self.staff)
        for value in ("adoption_completed", "submitted", "rejected"):
            with self.subTest(status=value):
                response = self.client.patch(f"/api/applications/{self.app.pk}/", {"status": value}, format="json")
                self.assertEqual(response.status_code, 400)
        self.app.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(self.app.status, "approved")
        self.assertEqual(self.record.status, "scheduled")

    def test_cancellation_keeps_medical_and_other_valid_reservations(self):
        self.pet.status = "under_medical_care"
        self.pet.save(update_fields=["status"])
        self.assertEqual(self.cancel().status_code, 200)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "under_medical_care")

    def test_pending_request_read_filters_and_approval_confirmation(self):
        request = self.request_change().data
        self.authenticate(self.admin)
        listing = self.client.get("/api/appointments/reschedule-requests/", {"application": str(self.app.pk), "status": "pending"})
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["count"], 1)
        self.assertEqual(self.client.get("/api/appointments/reschedule-requests/", {"status": "approved"}).data["count"], 0)
        self.assertEqual(self.review(request["id"], confirmed="true").status_code, 400)
        self.assertEqual(self.review(request["id"], confirmed=None).status_code, 400)

    def test_cancelled_application_cannot_be_reopened_with_generic_update(self):
        self.assertEqual(self.cancel().status_code, 200)
        self.authenticate(self.staff)
        response = self.client.patch(f"/api/applications/{self.app.pk}/", {"status": "approved"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, "cancelled")

    def test_completion_closes_a_pending_request_but_retains_history(self):
        self.make_past_visit()
        request = self.request_change().data
        Payment.objects.create(application=self.app, amount="500.00", status="completed")
        self.authenticate(self.staff)
        response = self.client.post(f"/api/applications/{self.app.pk}/complete-adoption/", {"confirmed": True}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(RescheduleRequest.objects.get(pk=request["id"]).status, "cancelled")
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, "completed")

    def test_pet_with_another_reservation_is_not_released(self):
        Application.objects.create(adopter=self.other, pet=self.pet, status="approved")
        self.assertEqual(self.cancel().status_code, 200)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "pending")

    def test_expired_proposed_date_cannot_be_approved(self):
        request = self.request_change().data
        RescheduleRequest.objects.filter(pk=request["id"]).update(requested_date=timezone.localdate() - timedelta(days=1))
        self.assertEqual(self.review(request["id"]).status_code, 400)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_date_validation_uses_philippine_day_when_utc_is_still_yesterday(self):
        with patch("django.utils.timezone.now", return_value=datetime(2026, 10, 22, 17, 0, tzinfo=dt_timezone.utc)):
            response = self.request_change(requested_date="2026-10-22")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(RescheduleRequest.objects.exists())
