"""Opt-in browser check; all records use Django's isolated live test database."""
import json
import os
from pathlib import Path
import subprocess
from unittest import skipUnless

from django.test import LiveServerTestCase
from rest_framework.authtoken.models import Token
from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from apps.applications.models import Application
from apps.appointments.eligibility import philippine_today
from apps.appointments.models import Appointment
from apps.adoptions.models import AdoptionRecord
from apps.payments.models import Payment
from .models import Pet, PetDeathRecord


@skipUnless(os.environ.get('PAWCONNECT_DEATH_BROWSER_TESTS') == '1', 'Opt-in pet death browser walkthrough')
class PetDeathBrowserTests(LiveServerTestCase):
    def test_death_reporting_correction_and_payment_review_in_both_portals(self):
        staff = User.objects.create_user(email='death-browser-staff@example.test', role='staff', is_email_verified=True)
        admin = User.objects.create_user(email='death-browser-admin@example.test', role='admin', is_email_verified=True)
        owner = User.objects.create_user(email='death-browser-owner@example.test', is_email_verified=True)
        pet = Pet.objects.create(name='Browser Mochi', species='cat', status='pending')
        app = Application.objects.create(pet=pet, adopter=owner, status='approved')
        visit = Appointment.objects.create(application=app, pet=pet, adopter=owner, requested_date=philippine_today(), status='confirmed')
        adoption = AdoptionRecord.objects.create(application=app, pet=pet, adopter=owner, appointment=visit)
        payment = Payment.objects.create(application=app, amount='500.00', status='completed', method='cash')
        receipt = payment.receipt_number
        fixture = {'api': self.live_server_url, 'pet': str(pet.pk), 'application': str(app.pk), 'today': str(philippine_today())}
        for key, user in (('staff', staff), ('admin', admin), ('owner', owner)):
            fixture[key] = {'token': Token.objects.create(user=user).key, 'user': dict(UserSerializer(user).data)}
        root = Path(__file__).resolve().parents[3]
        result = subprocess.run(['node', str(root / 'staff-portal/tests/pet-deaths-live.mjs')], cwd=root / 'staff-portal',
                                env={**os.environ, 'PAWCONNECT_DEATH_FIXTURE': json.dumps(fixture)}, capture_output=True, text=True, encoding='utf-8', timeout=240)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        pet.refresh_from_db(); app.refresh_from_db(); visit.refresh_from_db(); adoption.refresh_from_db(); payment.refresh_from_db()
        self.assertEqual(pet.status, 'for_assessment')
        self.assertEqual(app.status, 'cancelled')
        self.assertEqual(visit.status, 'cancelled')
        self.assertEqual(adoption.status, 'cancelled')
        self.assertEqual(payment.receipt_number, receipt)
        self.assertEqual(payment.status, 'completed')
        self.assertFalse(payment.death_review_required)
        self.assertTrue(PetDeathRecord.objects.get(pet=pet).corrected_at)
