from django.test import TestCase
from apps.accounts.tests import BaseAPITestCase
from apps.adopters.models import AdopterProfile


class AdopterTests(BaseAPITestCase):

    def setUp(self):
        super().setUp()
        self.adopter = self.create_user(email="adopter@example.com")
        self.staff = self.create_staff(email="staff1@example.com")

    def profile_id(self):
        return str(AdopterProfile.objects.get(user=self.adopter).id)

    def test_adopter_gets_own_profile(self):
        self.authenticate(self.adopter)
        resp = self.client.get("/api/adopters/profile/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["user_email"], "adopter@example.com")

    def test_profile_requires_auth(self):
        resp = self.client.get("/api/adopters/profile/")
        self.assertEqual(resp.status_code, 403)

    def test_adopter_can_update_own_profile(self):
        self.authenticate(self.adopter)
        resp = self.client.patch("/api/adopters/profile/", {
            "phone_number": "09171234567",
            "city": "Manila",
        }, format="json")
        self.assertEqual(resp.status_code, 200)
        profile = AdopterProfile.objects.get(user=self.adopter)
        self.assertEqual(profile.city, "Manila")
        self.assertEqual(profile.phone_number, "09171234567")

    def test_staff_can_list_adopters(self):
        self.authenticate(self.staff)
        resp = self.client.get("/api/adopters/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)

    def test_adopter_cannot_list_all_adopters(self):
        self.authenticate(self.adopter)
        resp = self.client.get("/api/adopters/")
        self.assertEqual(resp.status_code, 403)

    def test_staff_can_view_adopter_detail(self):
        self.authenticate(self.staff)
        resp = self.client.get(f"/api/adopters/{self.profile_id()}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["user_email"], "adopter@example.com")

    def test_adopter_cannot_view_other_adopter_detail(self):
        self.authenticate(self.adopter)
        resp = self.client.get(f"/api/adopters/{self.profile_id()}/")
        self.assertEqual(resp.status_code, 403)