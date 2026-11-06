from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.applications.models import Application
from apps.appointments.eligibility import philippine_today
from apps.appointments.models import Appointment
from apps.adoptions.models import AdoptionRecord
from apps.payments.models import Payment
from .models import Pet, PetDeathRecord


class PetDeathConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.staff = User.objects.create_user(email='death-race-staff@example.test', role='staff')
        owner = User.objects.create_user(email='death-race-owner@example.test')
        self.pet = Pet.objects.create(name='Race pet', species='dog', status='pending')
        self.app = Application.objects.create(pet=self.pet, adopter=owner, status='approved')
        self.visit = Appointment.objects.create(application=self.app, pet=self.pet, adopter=owner, status='confirmed', requested_date=philippine_today())
        self.adoption = AdoptionRecord.objects.create(application=self.app, pet=self.pet, adopter=owner, appointment=self.visit)
        Payment.objects.create(application=self.app, amount='500.00', status='completed')

    def race(self, operations):
        barrier = Barrier(2)
        def post(operation):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(self.staff)
                barrier.wait(timeout=10)
                return client.post(operation[0], operation[1], format='json').status_code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(post, operations))

    def death_operation(self):
        return (f'/api/pets/{self.pet.pk}/record-death/', {'death_date': str(philippine_today()), 'confirmed': True})

    @skipUnlessDBFeature('has_select_for_update')
    def test_death_and_handover_cannot_both_complete(self):
        results = self.race([self.death_operation(), (f'/api/applications/{self.app.pk}/confirm-turnover/', {'confirmed': True})])
        self.assertEqual(sorted(results), [200, 400])
        self.pet.refresh_from_db(); self.app.refresh_from_db(); self.adoption.refresh_from_db()
        if self.pet.status == 'deceased':
            self.assertEqual(self.app.status, 'cancelled')
            self.assertEqual(self.adoption.status, 'cancelled')
        else:
            self.assertEqual(self.pet.status, 'adopted')
            self.assertEqual(self.adoption.status, 'completed')
            self.assertFalse(PetDeathRecord.objects.exists())

    @skipUnlessDBFeature('has_select_for_update')
    def test_concurrent_repeated_death_creates_one_record(self):
        self.assertEqual(self.race([self.death_operation(), self.death_operation()]), [200, 200])
        self.assertEqual(PetDeathRecord.objects.count(), 1)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, 'deceased')

    @skipUnlessDBFeature('has_select_for_update')
    def test_concurrent_review_cannot_restore_pending_status(self):
        self.app.status = 'under_review'; self.app.save()
        results = self.race([self.death_operation(), ('/api/reviews/', {'application': str(self.app.pk), 'decision': 'approve'})])
        self.assertEqual(results[0], 200)
        self.assertIn(results[1], (201, 400))
        self.pet.refresh_from_db(); self.app.refresh_from_db()
        self.assertEqual(self.pet.status, 'deceased')
        self.assertEqual(self.app.status, 'cancelled')
