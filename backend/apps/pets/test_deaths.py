from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from apps.accounts.tests import BaseAPITestCase
from apps.applications.models import Application
from apps.appointments.models import Appointment, RescheduleRequest
from apps.appointments.eligibility import philippine_today
from apps.adoptions.models import AdoptionRecord
from apps.audit.models import AuditLog
from apps.health.models import HealthRecord
from apps.notifications.models import Notification
from apps.payments.models import Payment
from .models import Pet, PetDeathRecord


class PetDeathTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.staff = self.create_staff(email="death-staff@example.test")
        self.admin = self.create_admin(email="death-admin@example.test")
        self.owner = self.create_user(email="death-owner@example.test")
        self.other = self.create_user(email="death-other@example.test")
        self.pet = Pet.objects.create(name="Mochi", species="cat", status="pending", arrival_date=philippine_today() - timedelta(days=10))
        self.app = Application.objects.create(adopter=self.owner, pet=self.pet, status="approved")
        self.other_app = Application.objects.create(adopter=self.other, pet=self.pet, status="under_review")
        self.visit = Appointment.objects.create(application=self.app, pet=self.pet, adopter=self.owner, requested_date=philippine_today(), status="confirmed")
        self.record = AdoptionRecord.objects.create(application=self.app, pet=self.pet, adopter=self.owner, appointment=self.visit, staff_member=self.staff)
        self.payment = Payment.objects.create(application=self.app, amount="500.00", status="completed", method="cash")
        self.health = HealthRecord.objects.create(pet=self.pet, record_date=philippine_today(), diagnosis="Existing medical history", created_by=self.staff)
        self.authenticate(self.staff)

    def report(self, **changes):
        payload = {"death_date": str(philippine_today()), "cause": "CONFIDENTIAL medical cause", "veterinarian": "Dr. Example", "internal_notes": "CONFIDENTIAL staff note", "confirmed": True, **changes}
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(f"/api/pets/{self.pet.pk}/record-death/", payload, format="json")

    def test_report_closes_active_work_retains_financial_and_health_history(self):
        old_payment = Payment.objects.values().get(pk=self.payment.pk)
        old_health = HealthRecord.objects.values().get(pk=self.health.pk)
        reschedule = RescheduleRequest.objects.create(application=self.app, appointment=self.visit, original_date=self.visit.requested_date, requested_date=philippine_today() + timedelta(days=1), reason="Move visit")
        response = self.report()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "deceased")
        self.assertEqual(response.data["death_records"][0]["recorded_by_email"], self.staff.email)
        for app in (self.app, self.other_app):
            app.refresh_from_db()
            self.assertEqual(app.status, "cancelled")
            self.assertTrue(app.cancelled_at)
            self.assertIn("passed away", app.cancellation_reason)
            self.assertEqual(app.rejection_reason, "")
        self.record.refresh_from_db(); self.visit.refresh_from_db(); reschedule.refresh_from_db(); self.payment.refresh_from_db()
        self.assertEqual(self.record.status, "cancelled")
        self.assertTrue(self.record.cancelled_at)
        self.assertEqual(self.visit.status, "cancelled")
        self.assertEqual(reschedule.status, "cancelled")
        self.assertTrue(self.payment.death_review_required)
        for field in ("amount", "status", "receipt_number", "application_id", "adoption_id", "payment_date"):
            self.assertEqual(getattr(self.payment, field), old_payment[field])
        self.assertEqual(HealthRecord.objects.values().get(pk=self.health.pk), old_health)
        self.assertEqual(len(mail.outbox), 2)
        self.assertNotIn("CONFIDENTIAL", str([email.body for email in mail.outbox]))
        for email in mail.outbox:
            html, mime = email.alternatives[0]
            self.assertEqual(mime, 'text/html')
            self.assertIn('A difficult update about Mochi.', html)
            self.assertIn('View your application details', html)
            self.assertNotIn('CONFIDENTIAL', html)
        self.assertTrue(AuditLog.objects.filter(action="pet_death_recorded", user=self.staff).exists())
        self.assertTrue(AuditLog.objects.filter(action="payment_death_review_required").exists())

    def test_public_listing_direct_link_private_details_and_history_scopes(self):
        self.assertEqual(self.report().status_code, 200)
        self.assertEqual(self.client.get('/api/pets/', {'scope': 'active'}).data['count'], 0)
        self.assertEqual(self.client.get('/api/pets/', {'scope': 'history', 'status': 'deceased'}).data['count'], 1)
        self.assertEqual(self.client.get('/api/health-records/', {'scope': 'history'}).data['count'], 1)
        self.unauthenticate()
        for params in ({}, {"status": "deceased"}, {"scope": "all"}):
            self.assertEqual(self.client.get('/api/pets/', params).data['count'], 0)
        response = self.client.get(f'/api/pets/{self.pet.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'deceased')
        self.assertNotIn('death_records', response.data)
        self.assertNotIn('CONFIDENTIAL', str(response.data))
        self.authenticate(self.owner)
        self.assertNotIn('death_records', self.client.get(f'/api/pets/{self.pet.pk}/').data)
        app = self.client.get(f'/api/applications/{self.app.pk}/').data
        self.assertIn('passed away', app['cancellation_reason'])

    def test_direct_writes_and_all_adoption_entry_points_cannot_revive_pet(self):
        self.assertEqual(self.client.patch(f'/api/pets/{self.pet.pk}/', {'status': 'deceased'}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/pets/', {'name': 'Invalid', 'species': 'cat', 'status': 'deceased'}, format='json').status_code, 400)
        self.assertEqual(self.report().status_code, 200)
        for status in ('available', 'pending', 'adopted', 'inactive'):
            self.assertEqual(self.client.patch(f'/api/pets/{self.pet.pk}/', {'status': status}, format='json').status_code, 400)
        self.assertEqual(self.client.post(f'/api/applications/{self.app.pk}/update-status/', {'status': 'approved'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/applications/{self.app.pk}/', {'status': 'approved'}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/reviews/', {'application': str(self.app.pk), 'decision': 'approve'}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/adoptions/', {'application_id': str(self.app.pk)}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/adoptions/{self.record.pk}/', {'status': 'completed', 'confirmed': True}, format='json').status_code, 400)
        self.assertEqual(self.client.post(f'/api/appointments/{self.visit.pk}/approve/', {}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/payments/record-onsite/', {'application': str(self.app.pk), 'payment_received': True}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(f'/api/pets/{self.pet.pk}/').status_code, 400)
        self.authenticate(self.owner)
        response = self.client.post('/api/applications/', {'pet': str(self.pet.pk), 'privacy_consent': True}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('pet', response.data)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, 'deceased')

    def test_confirmation_dates_roles_and_center_custody(self):
        for value in (None, False, 'true', 1):
            self.assertEqual(self.report(confirmed=value).status_code, 400)
        for date in (philippine_today() + timedelta(days=1), self.pet.arrival_date - timedelta(days=1)):
            self.assertEqual(self.report(death_date=str(date)).status_code, 400)
        for user in (self.owner, self.other):
            self.authenticate(user)
            self.assertEqual(self.report().status_code, 403)
        self.unauthenticate()
        self.assertEqual(self.report().status_code, 403)
        self.authenticate(self.staff)
        self.pet.status = 'adopted'; self.pet.save()
        self.assertEqual(self.report().status_code, 400)
        self.assertFalse(PetDeathRecord.objects.exists())

    def test_completed_adoption_and_returned_financial_history_are_preserved(self):
        self.record.status = 'completed'; self.record.transaction_id = 'TXN-HISTORY'; self.record.save()
        self.assertEqual(self.report().status_code, 400)  # Even an inconsistent pet status cannot bypass custody.
        self.record.status = 'returned'; self.record.return_date = philippine_today(); self.record.save()
        self.app.status = 'adoption_completed'; self.app.save()
        self.other_app.status = 'rejected'; self.other_app.save()
        old_record = AdoptionRecord.objects.values().get(pk=self.record.pk)
        old_payment = Payment.objects.values().get(pk=self.payment.pk)
        self.assertEqual(self.report(death_date=str(philippine_today() - timedelta(days=1))).status_code, 400)
        self.assertEqual(self.report().status_code, 200)
        self.assertEqual(AdoptionRecord.objects.values().get(pk=self.record.pk), old_record)
        self.assertEqual(Payment.objects.values().get(pk=self.payment.pk), old_payment)

    def test_retry_and_admin_correction_keep_original_record_and_closed_work(self):
        self.assertEqual(self.report().status_code, 200)
        death = PetDeathRecord.objects.get()
        original = PetDeathRecord.objects.values().get(pk=death.pk)
        notice_count = Notification.objects.count()
        self.assertEqual(self.report(cause='Changed on retry').status_code, 200)
        self.assertEqual(Notification.objects.count(), notice_count)
        self.assertEqual(PetDeathRecord.objects.values().get(pk=death.pk), original)
        url = f'/api/pets/{self.pet.pk}/correct-death/'
        self.assertEqual(self.client.post(url, {'reason': 'Incorrect pet selected.', 'confirmed': True}, format='json').status_code, 403)
        self.authenticate(self.admin)
        self.assertEqual(self.client.post(url, {'reason': ' ', 'confirmed': True}, format='json').status_code, 400)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, {'reason': 'Incorrect pet selected.', 'confirmed': True}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'for_assessment')
        death.refresh_from_db(); self.app.refresh_from_db(); self.payment.refresh_from_db()
        self.assertEqual(death.cause, original['cause'])
        self.assertEqual(death.corrected_by, self.admin)
        self.assertTrue(death.corrected_at)
        self.assertEqual(self.app.status, 'cancelled')
        self.assertTrue(self.payment.death_review_required)
        correction_html = mail.outbox[-1].alternatives[0][0]
        self.assertIn('A correction about Mochi.', correction_html)
        self.assertIn('Your previous application remains closed.', correction_html)
        self.assertNotIn('Incorrect pet selected.', correction_html)
        self.assertNotIn('CONFIDENTIAL', correction_html)
        self.authenticate(self.owner)
        self.assertTrue(self.client.get(f'/api/applications/{self.app.pk}/').data['death_notice_corrected'])

    def test_payment_review_resolution_preserves_actual_transaction(self):
        self.report()
        url = f'/api/payments/{self.payment.pk}/resolve-death-review/'
        self.assertEqual(self.client.get('/api/payments/', {'death_review': 'required'}).data['count'], 1)
        self.assertEqual(self.client.post(url, {'note': '', 'confirmed': True}, format='json').status_code, 400)
        response = self.client.post(url, {'note': 'Contacted adopter; refund will be handled onsite.', 'confirmed': True}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['death_review_required'])
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'completed')
        self.assertTrue(self.payment.receipt_number)
        self.authenticate(self.owner)
        self.assertEqual(self.client.post(url, {'note': 'No access', 'confirmed': True}, format='json').status_code, 403)
        self.assertNotIn('death_review_note', self.client.get(f'/api/payments/{self.payment.pk}/').data)

    def test_failure_rolls_back_every_lifecycle_change(self):
        with patch('apps.pets.lifecycle.notify_adopter', side_effect=RuntimeError('Notification storage failure')):
            with self.assertRaises(RuntimeError):
                self.report()
        self.pet.refresh_from_db(); self.app.refresh_from_db(); self.payment.refresh_from_db()
        self.assertEqual(self.pet.status, 'pending')
        self.assertEqual(self.app.status, 'approved')
        self.assertFalse(self.payment.death_review_required)
        self.assertFalse(PetDeathRecord.objects.exists())
