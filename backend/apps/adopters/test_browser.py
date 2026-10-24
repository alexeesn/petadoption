import json
import os
from pathlib import Path
import subprocess
from datetime import timedelta
from unittest import skipUnless
from zoneinfo import ZoneInfo

from django.test import LiveServerTestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token

from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from apps.pets.models import Pet
from .models import AdopterProfile


@skipUnless(os.environ.get("PAWCONNECT_PROFILE_BROWSER_TESTS") == "1", "Opt-in profile identity browser test")
class ProfileIdentityBrowserTests(LiveServerTestCase):
    def test_required_names_birthday_adult_boundary_and_persistence(self):
        adopter = User.objects.create_user(email="identity-browser@example.test", first_name="Alexis", last_name="Teodosio", role="adopter", is_email_verified=True)
        staff = User.objects.create_user(email="identity-browser-staff@example.test", role="staff", is_email_verified=True)
        profile = AdopterProfile.objects.create(user=adopter, phone_number="09171234567", address_line1="123 Taft Avenue",
            region="National Capital Region (NCR)", city="City of Manila", barangay="Barangay 1", zip_code="1000", housing_type="house", owns_or_rents="own")
        pet = Pet.objects.create(name="Profile Browser Buddy", species="dog")
        today = timezone.localtime(timezone.now(), ZoneInfo("Asia/Manila")).date()
        try:
            cutoff = today.replace(year=today.year - 18)
        except ValueError:
            cutoff = today.replace(year=today.year - 18, day=28)
        fixture = {"api": self.live_server_url, "profile": str(profile.pk), "pet": str(pet.pk),
            "cutoff": cutoff.isoformat(), "underage": (cutoff + timedelta(days=1)).isoformat(),
            "adopter": {"token": Token.objects.create(user=adopter).key, "user": dict(UserSerializer(adopter).data)},
            "staff_token": Token.objects.create(user=staff).key}
        root = Path(__file__).resolve().parents[3]
        result = subprocess.run(["node", str(root / "staff-portal/tests/profile-identity-live.mjs")], cwd=root / "staff-portal",
            env={**os.environ, "PAWCONNECT_PROFILE_FIXTURE": json.dumps(fixture)}, capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        adopter.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(adopter.first_name, "Alexis Updated")
        self.assertEqual(adopter.last_name, "Teodosio")
        self.assertEqual(profile.date_of_birth, cutoff)
        self.assertTrue(profile.is_complete())
