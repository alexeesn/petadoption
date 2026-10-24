from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.utils import timezone

from apps.accounts.tests import BaseAPITestCase
from .models import Pet


class PetArrivalDateTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        clock = patch("django.utils.timezone.now", return_value=datetime(2026, 10, 24, 4, tzinfo=dt_timezone.utc))
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        self.authenticate(self.create_staff(email="pet-arrival@example.test"))

    def test_future_arrival_rejected_for_json_and_multipart_create(self):
        for payload_format in ("json", "multipart"):
            with self.subTest(payload_format=payload_format):
                response = self.client.post("/api/pets/", {
                    "name": "Future arrival", "species": "dog", "arrival_date": "2026-10-25",
                }, format=payload_format)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn("arrival_date", response.data)
                self.assertFalse(Pet.objects.exists())

    def test_today_and_past_dates_are_allowed(self):
        for arrival_date in ("2026-10-24", "2026-10-23"):
            with self.subTest(arrival_date=arrival_date):
                response = self.client.post("/api/pets/", {
                    "name": "Arrived pet", "species": "cat", "arrival_date": arrival_date,
                }, format="json")
                self.assertEqual(response.status_code, 201, response.data)
                self.assertEqual(response.data["arrival_date"], arrival_date)

    def test_put_and_patch_reject_future_dates_without_changes(self):
        pet = Pet.objects.create(name="Existing pet", species="dog", arrival_date="2026-10-23")
        before = Pet.objects.values().get(pk=pet.pk)
        for method in (self.client.put, self.client.patch):
            with self.subTest(method=method.__name__):
                response = method(f"/api/pets/{pet.pk}/", {
                    "name": "Must not save", "species": "dog", "arrival_date": "2026-10-25",
                }, format="json")
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn("arrival_date", response.data)
                self.assertEqual(Pet.objects.values().get(pk=pet.pk), before)

    def test_optional_date_can_be_omitted_and_cleared(self):
        created = self.client.post("/api/pets/", {"name": "Undated pet", "species": "dog"}, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertIsNone(created.data["arrival_date"])
        url = f"/api/pets/{created.data['id']}/"
        dated = self.client.patch(url, {"arrival_date": "2026-10-24"}, format="json")
        self.assertEqual(dated.status_code, 200, dated.data)
        cleared = self.client.patch(url, {"arrival_date": None}, format="json")
        self.assertEqual(cleared.status_code, 200, cleared.data)
        self.assertIsNone(cleared.data["arrival_date"])

    def test_today_uses_philippine_midnight_even_with_another_server_timezone(self):
        payload = {"name": "Midnight arrival", "species": "dog", "arrival_date": "2026-10-24"}
        with timezone.override("America/New_York"):
            self.clock.return_value = datetime(2026, 10, 23, 15, 59, tzinfo=dt_timezone.utc)
            before = self.client.post("/api/pets/", payload, format="json")
            self.assertEqual(before.status_code, 400, before.data)
            self.clock.return_value = datetime(2026, 10, 23, 16, tzinfo=dt_timezone.utc)
            after = self.client.post("/api/pets/", payload, format="json")
            self.assertEqual(after.status_code, 201, after.data)
