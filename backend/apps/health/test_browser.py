"""Opt-in create/edit workflow against a disposable database and live API."""
import json
import os
from pathlib import Path
import subprocess
from unittest import skipUnless

from django.test import LiveServerTestCase
from rest_framework.authtoken.models import Token

from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from apps.pets.models import Pet
from .models import HealthRecord


@skipUnless(os.environ.get('PAWCONNECT_HEALTH_BROWSER_TESTS') == '1', 'Opt-in health record browser test')
class HealthRecordBrowserTests(LiveServerTestCase):
    def test_add_excludes_existing_pets_and_edit_persists(self):
        staff = User.objects.create_user(email='health-browser@example.test', role='staff', is_email_verified=True)
        for index in range(25):
            pet = Pet.objects.create(name=f'Recorded {index:02d}', species='dog')
            HealthRecord.objects.create(pet=pet, record_date='2026-01-01', diagnosis='Existing history', created_by=staff)
            eligible = Pet.objects.create(name=f'Eligible {index:02d}', species='cat')
        before = list(HealthRecord.objects.order_by('pk').values())
        fixture = {
            'api': self.live_server_url, 'eligible_pet': str(eligible.pk),
            'staff': {'token': Token.objects.create(user=staff).key, 'user': dict(UserSerializer(staff).data)},
        }
        root = Path(__file__).resolve().parents[3]
        result = subprocess.run(
            ['node', str(root / 'staff-portal/tests/health-records-live.mjs')], cwd=root / 'staff-portal',
            env={**os.environ, 'PAWCONNECT_HEALTH_FIXTURE': json.dumps(fixture)},
            capture_output=True, text=True, encoding='utf-8', timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        record = HealthRecord.objects.get(pet=eligible)
        self.assertEqual(record.diagnosis, 'Recovered after follow-up')
        self.assertEqual(record.notes, 'Updated care plan')
        self.assertIsNone(record.next_checkup_date)
        self.assertEqual(record.created_by_id, staff.pk)
        self.assertEqual(HealthRecord.objects.count(), 26)
        self.assertEqual(list(HealthRecord.objects.exclude(pk=record.pk).order_by('pk').values()), before)
