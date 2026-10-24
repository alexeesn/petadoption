from datetime import date, datetime, timezone as dt_timezone
from unittest.mock import patch

from apps.accounts.tests import BaseAPITestCase
from apps.accounts.models import User
from apps.applications.models import Application
from apps.pets.models import Pet
from .models import AdopterProfile


class ProfileIdentityTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user(email="identity@example.test")
        self.other = self.create_user(email="identity-other@example.test")
        self.profile = self.user.adopter_profile
        self.authenticate(self.user)
        self.url = "/api/adopters/profile/"

    def test_names_are_saved_to_account_and_returned_in_both_profile_endpoints(self):
        response = self.client.patch(self.url, {"first_name": " Alexis ", "last_name": " Teodosio "}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["first_name"], "Alexis")
        self.assertEqual(response.data["last_name"], "Teodosio")
        self.assertEqual(response.data["user_name"], "Alexis Teodosio")
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Alexis Teodosio")
        self.assertEqual(self.client.get("/api/auth/profile/").data["first_name"], "Alexis")
        self.assertEqual(self.client.get(self.url).data["last_name"], "Teodosio")

    def test_blank_names_missing_birthday_and_underage_are_rejected_without_partial_saves(self):
        before = AdopterProfile.objects.values().get(pk=self.profile.pk)
        name_before = self.user.first_name
        for payload, field in (
            ({"first_name": "   "}, "first_name"), ({"last_name": ""}, "last_name"),
            ({"first_name": "Changed", "date_of_birth": None}, "date_of_birth"),
            ({"first_name": "Changed", "date_of_birth": "2020-01-01"}, "date_of_birth"),
        ):
            with self.subTest(payload=payload):
                response = self.client.patch(self.url, payload, format="json")
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(field, response.data)
                self.assertEqual(AdopterProfile.objects.values().get(pk=self.profile.pk), before)
                self.user.refresh_from_db()
                self.assertEqual(self.user.first_name, name_before)

    def test_philippine_midnight_controls_eighteenth_birthday(self):
        for hour, minute, expected in ((15, 59, 400), (16, 0, 200)):
            moment = datetime(2026, 10, 23, hour, minute, tzinfo=dt_timezone.utc)
            with patch("django.utils.timezone.now", return_value=moment):
                response = self.client.patch(self.url, {"date_of_birth": "2008-10-24"}, format="json")
                self.assertEqual(response.status_code, expected, response.data)

    def test_one_day_short_of_eighteen_and_leap_day(self):
        with patch("django.utils.timezone.now", return_value=datetime(2026, 10, 24, tzinfo=dt_timezone.utc)):
            response = self.client.patch(self.url, {"date_of_birth": "2008-10-25"}, format="json")
            self.assertEqual(response.status_code, 400)
        with patch("django.utils.timezone.now", return_value=datetime(2020, 2, 29, tzinfo=dt_timezone.utc)):
            response = self.client.patch(self.url, {"date_of_birth": "2002-02-28"}, format="json")
            self.assertEqual(response.status_code, 200, response.data)
            response = self.client.patch(self.url, {"date_of_birth": "2002-03-01"}, format="json")
            self.assertEqual(response.status_code, 400)

    def test_legacy_missing_or_underage_birthday_blocks_new_application_without_rewriting_history(self):
        pet = Pet.objects.create(name="Identity Buddy", species="dog")
        historical = Application.objects.create(pet=pet, adopter=self.user, status="cancelled")
        before = Application.objects.values().get(pk=historical.pk)
        for birthday in (None, date(2020, 1, 1)):
            AdopterProfile.objects.filter(pk=self.profile.pk).update(date_of_birth=birthday)
            self.assertFalse(self.client.get(self.url).data["profile_is_complete"])
            response = self.client.post("/api/applications/", {"pet": str(pet.pk), "privacy_consent": True}, format="json")
            self.assertEqual(response.status_code, 400)
            self.assertIn("date_of_birth", str(response.data["profile"]))
            self.assertEqual(Application.objects.values().get(pk=historical.pk), before)
            self.assertEqual(Application.objects.filter(adopter=self.user).count(), 1)

    def test_required_identity_cannot_be_omitted_for_an_incomplete_legacy_profile(self):
        User.objects.filter(pk=self.user.pk).update(first_name="", last_name="")
        AdopterProfile.objects.filter(pk=self.profile.pk).update(date_of_birth=None)
        response = self.client.patch(self.url, {"phone_number": "09170000000"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data), {"first_name", "last_name", "date_of_birth"})

    def test_name_and_profile_writes_roll_back_together(self):
        before = AdopterProfile.objects.values().get(pk=self.profile.pk)
        with patch.object(User, "save", side_effect=RuntimeError("Failed account update")):
            with self.assertRaises(RuntimeError):
                self.client.patch(self.url, {"first_name": "Changed", "phone_number": "09171234567"}, format="json")
        self.assertEqual(AdopterProfile.objects.values().get(pk=self.profile.pk), before)

    def test_identity_update_cannot_edit_other_account_or_role(self):
        response = self.client.patch(self.url, {"first_name": "Alexis", "user": str(self.other.pk), "role": "admin"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.other.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.other.first_name, "Test")
        self.assertEqual(self.user.role, "adopter")
