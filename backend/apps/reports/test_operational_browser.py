"""Opt-in operational reporting walkthrough against a disposable live database."""
import json
import os
from pathlib import Path
import subprocess
from unittest import skipUnless

from django.test import LiveServerTestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from apps.adopters.models import AdopterProfile, IdentityVerification
from apps.applications.models import Application
from apps.payments.models import Payment
from apps.pets.models import Pet, PetDeathRecord
from apps.surrenders.models import SurrenderRequest


@skipUnless(os.environ.get('PAWCONNECT_REPORT_BROWSER_TESTS') == '1', 'Opt-in operational reports browser test')
class OperationalReportsBrowserTests(LiveServerTestCase):
    def test_reports_filters_pagination_downloads_and_mobile(self):
        staff = User.objects.create_user(email='reports-browser-staff@example.test', role='staff', is_email_verified=True)
        owner = User.objects.create_user(email='reports-browser-owner@example.test', is_email_verified=True)
        profile, _ = AdopterProfile.objects.get_or_create(user=owner)
        IdentityVerification.objects.create(profile=profile, status='pending_review', submitted_at=timezone.now())
        for index in range(25):
            SurrenderRequest.objects.create(owner=owner, pet_name=f'Waiting dog {index:02d}', species='dog', status='waitlisted', ownership_confirmed=True)
        received_pet = Pet.objects.create(name='Received cat', species='cat', status='for_assessment')
        SurrenderRequest.objects.create(owner=owner, pet_name='Received cat', species='cat', status='received', ownership_confirmed=True, pet=received_pet, received_by=staff, received_at='2026-10-01T10:00:00+08:00', intake_date='2026-10-01')
        dead_pet = Pet.objects.create(name='Death report cat', species='cat', status='deceased')
        corrected_pet = Pet.objects.create(name='Corrected dog', species='dog', status='for_assessment')
        PetDeathRecord.objects.create(pet=dead_pet, recorded_by=staff, death_date='2026-10-01', cause='Unknown')
        PetDeathRecord.objects.create(pet=corrected_pet, recorded_by=staff, death_date='2026-10-02', corrected_at=timezone.now(), corrected_by=staff, correction_reason='Wrong pet selected')
        application = Application.objects.create(pet=dead_pet, adopter=owner, status='cancelled')
        Payment.objects.create(application=application, amount='500.00', status='completed', death_review_required=True, death_review_note='Review after pet death', payment_date='2026-10-01')
        Payment.objects.create(application=application, amount='250.00', status='refunded', death_review_note='Review resolved', payment_date='2026-10-01')
        before_payments = list(Payment.objects.order_by('pk').values())
        before_surrenders = list(SurrenderRequest.objects.order_by('pk').values())
        fixture = {'api': self.live_server_url, 'staff': {'token': Token.objects.create(user=staff).key, 'user': dict(UserSerializer(staff).data)}}
        root = Path(__file__).resolve().parents[3]
        result = subprocess.run(['node', str(root / 'staff-portal/tests/operational-reports-live.mjs')], cwd=root / 'staff-portal', env={**os.environ, 'PAWCONNECT_REPORT_FIXTURE': json.dumps(fixture)}, capture_output=True, text=True, encoding='utf-8', timeout=240)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        self.assertEqual(list(Payment.objects.order_by('pk').values()), before_payments)
        self.assertEqual(list(SurrenderRequest.objects.order_by('pk').values()), before_surrenders)
