from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.utils import timezone

from apps.accounts.tests import BaseAPITestCase
from apps.pets.models import Pet
from .models import HealthRecord


class HealthRecordDateValidationTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        clock = patch("django.utils.timezone.now", return_value=datetime(2026, 10, 24, 4, tzinfo=dt_timezone.utc))
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        self.staff = self.create_staff(email="health-dates@example.test")
        self.pet = Pet.objects.create(name="Checkup patient", species="dog")
        self.authenticate(self.staff)
        self.payload = {
            "pet": str(self.pet.pk), "record_date": "2026-10-23",
            "next_checkup_date": "2026-10-25", "diagnosis": "Healthy",
        }

    def create_record(self, **overrides):
        return self.client.post("/api/health-records/", {**self.payload, **overrides}, format="json")

    def test_create_rejects_future_record_date(self):
        response = self.create_record(record_date="2026-10-25")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("record_date", response.data)
        self.assertFalse(HealthRecord.objects.exists())

    def test_create_rejects_past_next_checkup(self):
        response = self.create_record(next_checkup_date="2026-10-23")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("next_checkup_date", response.data)
        self.assertFalse(HealthRecord.objects.exists())

    def test_today_is_allowed_for_both_dates(self):
        response = self.create_record(record_date="2026-10-24", next_checkup_date="2026-10-24")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["record_date"], "2026-10-24")
        self.assertEqual(response.data["next_checkup_date"], "2026-10-24")

    def test_past_record_and_future_checkup_are_allowed(self):
        response = self.create_record()
        self.assertEqual(response.status_code, 201, response.data)

    def test_put_and_patch_reject_invalid_dates_without_changing_record(self):
        record_id = self.create_record().data["id"]
        before = HealthRecord.objects.values().get(pk=record_id)
        for method in (self.client.put, self.client.patch):
            for field, value in (("record_date", "2026-10-25"), ("next_checkup_date", "2026-10-23")):
                with self.subTest(method=method.__name__, field=field):
                    response = method(f"/api/health-records/{record_id}/", {
                        **self.payload, field: value, "diagnosis": "Must not save",
                    }, format="json")
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertIn(field, response.data)
                    self.assertEqual(HealthRecord.objects.values().get(pk=record_id), before)

    def test_notes_edit_preserves_historical_dates_and_checkup_can_be_cleared(self):
        record = HealthRecord.objects.create(
            pet=self.pet, record_date="2026-01-01", next_checkup_date="2026-02-01",
        )
        url = f"/api/health-records/{record.pk}/"
        response = self.client.patch(url, {"notes": "Existing history"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["next_checkup_date"], "2026-02-01")
        cleared = self.client.patch(url, {"next_checkup_date": None}, format="json")
        self.assertEqual(cleared.status_code, 200, cleared.data)
        self.assertIsNone(cleared.data["next_checkup_date"])

    def test_philippine_midnight_is_used_independent_of_server_timezone(self):
        with timezone.override("America/New_York"):
            self.clock.return_value = datetime(2026, 10, 23, 15, 59, tzinfo=dt_timezone.utc)
            before_midnight = self.create_record(record_date="2026-10-24")
            self.assertEqual(before_midnight.status_code, 400, before_midnight.data)
            self.assertIn("record_date", before_midnight.data)
            self.clock.return_value = datetime(2026, 10, 23, 16, tzinfo=dt_timezone.utc)
            yesterday_checkup = self.create_record(next_checkup_date="2026-10-23")
            self.assertEqual(yesterday_checkup.status_code, 400, yesterday_checkup.data)
            self.assertIn("next_checkup_date", yesterday_checkup.data)
            today = self.create_record(record_date="2026-10-24", next_checkup_date="2026-10-24")
            self.assertEqual(today.status_code, 201, today.data)
