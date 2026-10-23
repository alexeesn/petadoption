"""Opt-in confirmation UI checks using real requests and a disposable database."""
import json
import os
from pathlib import Path
import subprocess
from tempfile import gettempdir, TemporaryDirectory
from unittest import skipUnless

from django.test import LiveServerTestCase, override_settings
from rest_framework.authtoken.models import Token

from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from apps.adopters.models import AdopterProfile
from apps.applications.models import Application
from apps.documents.models import Document
from apps.health.models import HealthRecord
from apps.pets.models import Pet


@skipUnless(os.environ.get('PAWCONNECT_FEEDBACK_BROWSER_TESTS') == '1', 'Opt-in action feedback browser test')
class ActionFeedbackBrowserTests(LiveServerTestCase):
    def test_success_feedback_follows_saved_actions_in_both_portals(self):
        adopter = User.objects.create_user(email='feedback-adopter@example.test', first_name='Jamie', role='adopter', is_email_verified=True)
        staff = User.objects.create_user(email='feedback-staff@example.test', first_name='Alex', role='staff', is_email_verified=True)
        profile, _ = AdopterProfile.objects.get_or_create(user=adopter)
        for field, value in {'phone_number': '09000000000', 'address_line1': 'Test Street', 'city': 'Manila', 'state': 'Metro Manila', 'zip_code': '1000', 'housing_type': 'house', 'owns_or_rents': 'own'}.items():
            setattr(profile, field, value)
        profile.save()
        pet = Pet.objects.create(name='Milo', species='cat', age_years=2)
        fixture = {
            'api': self.live_server_url, 'pet': str(pet.pk),
            'screenshots': str(Path(gettempdir()) / 'pawconnect-feedback-preview'),
            'adopter': {'token': Token.objects.create(user=adopter).key, 'user': dict(UserSerializer(adopter).data)},
            'staff': {'token': Token.objects.create(user=staff).key, 'user': dict(UserSerializer(staff).data)},
        }
        root = Path(__file__).resolve().parents[3]
        with TemporaryDirectory(prefix='pawconnect-feedback-files-') as media, override_settings(MEDIA_ROOT=media):
            result = subprocess.run(
                ['node', str(root / 'staff-portal/tests/action-feedback-live.mjs')], cwd=root / 'staff-portal',
                env={**os.environ, 'PAWCONNECT_FEEDBACK_FIXTURE': json.dumps(fixture)},
                capture_output=True, text=True, encoding='utf-8', timeout=240,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        self.assertEqual(Application.objects.get(pet=pet).status, 'approved')
        self.assertEqual(Document.objects.count(), 4)
        self.assertEqual(Pet.objects.count(), 2)
        saved_pet = Pet.objects.get(name='Feedback Buddy')
        self.assertEqual(saved_pet.breed, 'Friendly mix')
        self.assertEqual(HealthRecord.objects.get(pet=saved_pet).diagnosis, 'Healthy')
