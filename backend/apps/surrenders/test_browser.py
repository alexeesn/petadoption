"""Two real portals and a live Django API, using only an isolated test DB."""
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest import skipUnless

from PIL import Image
from django.test import LiveServerTestCase, override_settings
from rest_framework.authtoken.models import Token

from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from apps.pets.models import Pet
from .models import SurrenderRequest
from .services import today


@skipUnless(os.environ.get("PAWCONNECT_SURRENDER_BROWSER_TESTS") == "1", "Opt-in surrender browser walkthrough")
class SurrenderBrowserTests(LiveServerTestCase):
    def test_owner_request_staff_review_and_intake_in_both_portals(self):
        staff = User.objects.create_user(email="surrender-browser-staff@example.test", role="staff", is_email_verified=True)
        owner = User.objects.create_user(email="surrender-browser-owner@example.test", role="adopter", is_email_verified=True)
        fixture = {"api": self.live_server_url, "today": today().isoformat()}
        for key, user in (("staff", staff), ("owner", owner)):
            fixture[key] = {"token": Token.objects.create(user=user).key, "user": dict(UserSerializer(user).data)}
        root = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as directory, override_settings(PRIVATE_SURRENDER_ROOT=directory):
            photo = Path(directory) / "mochi.png"
            Image.new("RGB", (200, 200), "brown").save(photo)
            fixture["photo"] = str(photo)
            result = subprocess.run(["node", str(root / "staff-portal/tests/surrenders-live.mjs")],
                                    cwd=root / "staff-portal", env={**os.environ, "PAWCONNECT_SURRENDER_FIXTURE": json.dumps(fixture)},
                                    capture_output=True, text=True, encoding="utf-8", timeout=240)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(result.stdout)
            request = SurrenderRequest.objects.get(owner=owner)
            self.assertEqual(request.status, "received")
            self.assertEqual(request.history.count(), 5)
            self.assertEqual(Pet.objects.count(), 1)
            self.assertEqual(request.pet.status, "available")
            self.assertEqual(request.pet.description, "Assessed and ready to find a home.")
