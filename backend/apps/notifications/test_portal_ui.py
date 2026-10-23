"""Opt-in portal UI verification against a disposable, isolated PostgreSQL DB."""
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
from apps.adopters.models import AdopterProfile
from apps.adoptions.models import AdoptionRecord
from apps.applications.models import Application
from apps.appointments.models import Appointment
from apps.documents.models import Document
from apps.payments.models import Payment
from apps.pets.models import Pet
from .models import Notification


@skipUnless(os.environ.get("PAWCONNECT_UI_BROWSER_TESTS") == "1", "Opt-in portal UI browser test")
class PortalUIBrowserTests(LiveServerTestCase):
    def test_both_portals_light_dark_and_navigation(self):
        adopter = User.objects.create_user(email="ui-adopter@example.test", first_name="Jamie", role="adopter", is_email_verified=True)
        staff = User.objects.create_user(email="ui-staff@example.test", first_name="Alex", role="staff", is_email_verified=True)
        profile, _ = AdopterProfile.objects.get_or_create(user=adopter)
        for field, value in {"phone_number": "09000000000", "address_line1": "Test Street", "city": "Manila", "state": "Metro Manila", "zip_code": "1000", "housing_type": "house", "owns_or_rents": "own"}.items():
            setattr(profile, field, value)
        profile.save()
        public_pet = None
        for index in range(26):
            pet = Pet.objects.create(name="  bRUNo  " if index == 0 else f"Available Friend {index + 1:02d}", species="dog" if index % 2 else "cat", breed="sHIH   tZU" if index == 0 else "Aspin" if index % 2 else "Puspin", color="tAN  AND  wHITE" if index == 0 else "", age_years=2, gender="female", description="Friendly and gentle.\nEnjoys a quiet home." if index == 0 else "A saved public pet description.")
            if index == 0:
                public_pet = str(pet.pk)
        apps = {}
        for status, name in [("approved", "Milo"), ("adoption_completed", "Luna"), ("pending_documents", "Coco"), ("rejected", "Zoro")]:
            pet = Pet.objects.create(name=name, species="dog", status="adopted" if status == "adoption_completed" else "pending")
            app = Application.objects.create(adopter=adopter, pet=pet, status=status, why_adopt="SAVED_FORM_ANSWER", experience_with_pets="SAVED_EXPERIENCE", living_situation="SAVED_LIVING_SITUATION", references="SAVED_REFERENCES", staff_notes="PRIVATE_STAFF_NOTES", rejection_reason="Please discuss the housing requirement with staff." if status == "rejected" else "")
            apps[status] = str(app.pk)
            Document.objects.create(application=app, document_type="identification", file="private/ui-placeholder.txt", original_filename="SAVED_DOCUMENT_FILENAME.txt", file_size=1, content_type="text/plain", uploaded_by=adopter)
        approved = Application.objects.get(pk=apps["approved"])
        appointment = Appointment.objects.create(application=approved, adopter=adopter, pet=approved.pet, status="confirmed", requested_date=timezone.localdate())
        AdoptionRecord.objects.create(application=approved, adopter=adopter, pet=approved.pet, appointment=appointment, status="scheduled")
        for index in range(24):
            Notification.objects.create(user=adopter, title=f"Earlier update {index + 1}", message="An existing notification remains in history.", link="/applications", notification_type="application")
        for status, title, message in [
            ("rejected", "Application Rejected", "Your application was not approved."),
            ("adoption_completed", "Adoption Completed", "Your adoption has been completed."),
            ("pending_documents", "Documents Required", "Please attach a clearer copy of your valid ID."),
            ("approved", "Application Approved", "Your application has been approved. Choose or check your appointment."),
        ]:
            Notification.objects.create(user=adopter, title=title, message=message, link=f"/applications/{apps[status]}", notification_type="application")
        for index in range(131):
            Notification.objects.create(user=staff, title=f"Staff update {index + 1}", message="A real persisted workspace notification.", link="/applications", notification_type="general")
        models = (Application, Appointment, AdoptionRecord, Document, Pet, Payment)
        before = {model._meta.label: list(model.objects.order_by("pk").values()) for model in models}
        fixture = {
            "api": self.live_server_url, "applications": apps, "public_pet": public_pet,
            "adopter": {"token": Token.objects.create(user=adopter).key, "user": dict(UserSerializer(adopter).data)},
            "staff": {"token": Token.objects.create(user=staff).key, "user": dict(UserSerializer(staff).data)},
        }
        root = Path(__file__).resolve().parents[3]
        result = subprocess.run(
            ["node", str(root / "staff-portal/tests/ui-refresh-live.mjs")], cwd=root / "staff-portal",
            env={**os.environ, "PAWCONNECT_UI_FIXTURE": json.dumps(fixture), "PLAYWRIGHT_CHANNEL": os.environ.get("PLAYWRIGHT_CHANNEL", "msedge")},
            capture_output=True, text=True, encoding="utf-8", timeout=240,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        self.assertEqual(before, {model._meta.label: list(model.objects.order_by("pk").values()) for model in models})
        self.assertEqual(Notification.objects.filter(user=adopter).count(), 28)
        self.assertEqual(Notification.objects.filter(user=staff).count(), 131)
