"""Opt-in browser return workflow against a running isolated Django server."""
import json
import os
from pathlib import Path
import subprocess
from datetime import timedelta
from unittest import skipUnless

from django.core import mail
from django.test import LiveServerTestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token

from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from apps.adopters.models import AdopterProfile
from apps.applications.models import Application
from apps.appointments.models import Appointment
from apps.audit.models import AuditLog
from apps.health.models import HealthRecord
from apps.notifications.models import Notification
from apps.payments.models import Payment
from apps.pets.models import Pet
from .models import AdoptionRecord


@skipUnless(os.environ.get("PAWCONNECT_BROWSER_TESTS") == "1", "Opt-in: set PAWCONNECT_BROWSER_TESTS=1; requires Playwright browser")
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AdoptionReturnBrowserTests(LiveServerTestCase):
    def test_completion_and_return_in_both_portals(self):
        staff = User.objects.create_user(email="return-browser-staff@example.test", role="staff", is_email_verified=True)
        adopter = User.objects.create_user(email="return-browser-adopter@example.test", first_name="Alexis", last_name="Teodosio", role="adopter", is_email_verified=True)
        profile, _ = AdopterProfile.objects.get_or_create(user=adopter)
        for field, value in {
            "phone_number": "+63 900 000 0000", "address_line1": "123 Test Street", "city": "Manila",
            "state": "Metro Manila", "zip_code": "1000", "housing_type": "house", "owns_or_rents": "own",
            "has_other_pets": True, "other_pets": "One older cat",
            "date_of_birth": "1990-06-15",
        }.items():
            setattr(profile, field, value)
        profile.save()
        pet = Pet.objects.create(name="Return Browser Buddy", species="dog", age_years=2, status="pending")
        health_record = HealthRecord.objects.create(pet=pet, record_date="2025-01-01", diagnosis="Saved medical history", created_by=staff)
        medical_before = HealthRecord.objects.values().get(pk=health_record.pk)
        app = Application.objects.create(adopter=adopter, pet=pet, status="approved")
        appointment = Appointment.objects.create(
            application=app, adopter=adopter, pet=pet, status="confirmed",
            requested_date=timezone.localdate() - timedelta(days=7),
        )
        record = AdoptionRecord.objects.create(
            application=app, adopter=adopter, pet=pet, appointment=appointment,
            adoption_date=appointment.requested_date, staff_member=staff,
        )
        payment = Payment.objects.create(application=app, amount="500.00", status="completed", method="cash")
        future_pet = Pet.objects.create(name="Future Visit Buddy", species="cat", age_years=1, status="pending")
        future_app = Application.objects.create(adopter=adopter, pet=future_pet, status="approved")
        future_date = timezone.localdate() + timedelta(days=8)
        while future_date.weekday() >= 5:
            future_date += timedelta(days=1)
        future_appointment = Appointment.objects.create(
            application=future_app, adopter=adopter, pet=future_pet, status="confirmed", requested_date=future_date,
        )
        future_record = AdoptionRecord.objects.create(
            application=future_app, adopter=adopter, pet=future_pet, appointment=future_appointment,
            adoption_date=future_date, staff_member=staff,
        )
        receipt = payment.receipt_number
        fixture = {
            "api": self.live_server_url,
            "staff": {"token": Token.objects.create(user=staff).key, "user": dict(UserSerializer(staff).data)},
            "adopter": {"token": Token.objects.create(user=adopter).key, "user": dict(UserSerializer(adopter).data)},
            "application": str(app.pk), "record": str(record.pk), "pet": str(pet.pk), "receipt": receipt,
            "futureApplication": str(future_app.pk), "futureAppointment": str(future_appointment.pk),
            "futureRecord": str(future_record.pk),
        }
        root = Path(__file__).resolve().parents[3]
        environment = {**os.environ, "PAWCONNECT_FIXTURE": json.dumps(fixture),
                       "PLAYWRIGHT_CHANNEL": os.environ.get("PLAYWRIGHT_CHANNEL", "msedge")}
        result = subprocess.run(
            ["node", str(root / "staff-portal" / "tests" / "return-live.mjs")], cwd=root, env=environment,
            capture_output=True, text=True, encoding="utf-8", timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        record.refresh_from_db()
        payment.refresh_from_db()
        pet.refresh_from_db()
        self.assertEqual(record.status, "returned")
        self.assertIsNotNone(record.returned_at)
        self.assertEqual(record.return_reason, "Adopter developed allergies")
        self.assertEqual(pet.status, "available")  # Staff explicitly clears the pet after medical care.
        self.assertEqual(HealthRecord.objects.values().get(pk=health_record.pk), medical_before)
        self.assertEqual(payment.status, "completed")
        self.assertEqual(payment.receipt_number, receipt)
        self.assertEqual(payment.adoption_id, record.pk)
        self.assertEqual(AdoptionRecord.objects.count(), 2)
        future_record.refresh_from_db()
        self.assertEqual(future_record.status, "cancelled")
        self.assertFalse(Payment.objects.filter(application=future_app).exists())
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(AuditLog.objects.filter(action="adoption_returned").count(), 1)
        self.assertEqual(Notification.objects.filter(title="Adoption Returned", user=adopter).count(), 1)
        self.assertIn("Adoption Returned", [message.subject for message in mail.outbox])
