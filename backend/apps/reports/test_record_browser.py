"""Staff record views against an isolated PostgreSQL-backed live server."""
import json
import os
from pathlib import Path
import subprocess
from unittest import skipUnless

from django.test import LiveServerTestCase
from rest_framework.authtoken.models import Token

from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from apps.adoptions.models import AdoptionRecord
from apps.applications.models import Application
from apps.pets.models import Pet


@skipUnless(os.environ.get("PAWCONNECT_RECORD_BROWSER_TESTS") == "1", "Opt-in: set PAWCONNECT_RECORD_BROWSER_TESTS=1")
class RecordViewsBrowserTests(LiveServerTestCase):
    def test_history_pagination_dashboard_and_reports(self):
        staff = User.objects.create_user(email="views-staff@example.test", role="staff", is_email_verified=True)
        adopter = User.objects.create_user(email="views-adopter@example.test", role="adopter", is_email_verified=True)
        for number in range(22):
            pet = Pet.objects.create(name=f"Active pet {number:02}", species="dog")
            Application.objects.create(pet=pet, adopter=adopter, status="submitted")
        Pet.objects.create(name="Inactive pet", species="cat", status="inactive")
        for state, application_state, pet_state in (
            ("scheduled", "approved", "pending"),
            ("completed", "adoption_completed", "adopted"),
            ("cancelled", "cancelled", "available"),
            ("returned", "adoption_completed", "available"),
        ):
            pet = Pet.objects.create(name=f"History pet {state}", species="dog", status=pet_state)
            application = Application.objects.create(pet=pet, adopter=adopter, status=application_state)
            AdoptionRecord.objects.create(pet=pet, adopter=adopter, application=application, status=state)

        before = {model.__name__: list(model.objects.order_by("pk").values())
                  for model in (Pet, Application, AdoptionRecord)}
        fixture = {"api": self.live_server_url, "staff": {
            "token": Token.objects.create(user=staff).key, "user": dict(UserSerializer(staff).data),
        }}
        root = Path(__file__).resolve().parents[3]
        result = subprocess.run(
            ["node", str(root / "staff-portal/tests/record-views-live.mjs")], cwd=root,
            env={**os.environ, "PAWCONNECT_RECORD_FIXTURE": json.dumps(fixture)},
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        for model in (Pet, Application, AdoptionRecord):
            self.assertEqual(list(model.objects.order_by("pk").values()), before[model.__name__])
