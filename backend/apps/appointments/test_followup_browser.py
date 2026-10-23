"""Opt-in real-browser walkthrough. All fixture records live in Django's isolated test DB."""
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
from apps.adoptions.models import AdoptionRecord
from apps.applications.models import Application
from apps.payments.models import Payment
from apps.pets.models import Pet
from .models import Appointment, RescheduleRequest
from .tests import next_weekday


@skipUnless(os.environ.get("PAWCONNECT_BROWSER_TESTS") == "1", "Opt-in: set PAWCONNECT_BROWSER_TESTS=1; requires Playwright browser")
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AppointmentFollowupBrowserTests(LiveServerTestCase):
    def test_two_portals_against_running_isolated_backend(self):
        staff = User.objects.create_user(email="browser-staff@example.test", role="staff", is_email_verified=True)
        adopter = User.objects.create_user(email="browser-adopter@example.test", role="adopter", is_email_verified=True)
        applications = []
        records = []
        for name in ("Reschedule Pet", "NoShow Pet"):
            pet = Pet.objects.create(name=name, species="dog", age_years=2, status="pending")
            app = Application.objects.create(adopter=adopter, pet=pet, status="approved")
            appointment = Appointment.objects.create(
                application=app, adopter=adopter, pet=pet, status="confirmed",
                requested_date=timezone.localdate() - timedelta(days=7),
            )
            record = AdoptionRecord.objects.create(
                application=app, adopter=adopter, pet=pet, appointment=appointment,
                adoption_date=appointment.requested_date, staff_member=staff,
            )
            applications.append(str(app.pk))
            records.append(str(record.pk))
        payment = Payment.objects.create(application_id=applications[0], amount="500.00", status="completed")
        receipt = payment.receipt_number
        fixture = {
            "api": self.live_server_url,
            "staff": {"token": Token.objects.create(user=staff).key, "user": dict(UserSerializer(staff).data)},
            "adopter": {"token": Token.objects.create(user=adopter).key, "user": dict(UserSerializer(adopter).data)},
            "applications": applications, "records": records,
            "newDate": next_weekday(8).isoformat(), "laterDate": next_weekday(15).isoformat(),
        }
        root = Path(__file__).resolve().parents[3]
        environment = {**os.environ, "PAWCONNECT_FIXTURE": json.dumps(fixture), "PLAYWRIGHT_CHANNEL": os.environ.get("PLAYWRIGHT_CHANNEL", "msedge")}
        result = subprocess.run(
            ["node", str(root / "staff-portal" / "tests" / "followup-live.mjs")],
            cwd=root, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        self.assertEqual(AdoptionRecord.objects.count(), 2)
        self.assertEqual(Payment.objects.count(), 1)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "completed")
        self.assertEqual(payment.receipt_number, receipt)
        self.assertEqual(AdoptionRecord.objects.get(pk=records[0]).status, "cancelled")
        self.assertEqual(AdoptionRecord.objects.get(pk=records[1]).status, "cancelled")
        self.assertFalse(RescheduleRequest.objects.filter(status="pending").exists())
        subjects = [message.subject for message in mail.outbox]
        for title in ("Reschedule Approved", "Reschedule Not Approved", "Visit Marked as No-show", "Adoption Cancelled"):
            self.assertIn(title, subjects)
