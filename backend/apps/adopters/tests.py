from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
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


class ProfileCompletenessTests(BaseAPITestCase):
    """AdopterProfile.is_complete drives the application profile gate."""

    def setUp(self):
        super().setUp()
        self.adopter = self.create_user(email="completeness@example.com")
        self.profile = self.adopter.adopter_profile

    def test_blank_profile_is_incomplete(self):
        profile = AdopterProfile(user=self.adopter)
        self.assertFalse(profile.is_complete())
        self.assertEqual(
            profile.missing_required_fields(),
            list(AdopterProfile.REQUIRED_PROFILE_FIELDS),
        )

    def test_whitespace_only_field_counts_as_missing(self):
        profile = AdopterProfile(user=self.adopter)
        for field in AdopterProfile.REQUIRED_PROFILE_FIELDS:
            setattr(profile, field, "x")
        profile.phone_number = "   "
        self.assertFalse(profile.is_complete())
        self.assertEqual(profile.missing_required_fields(), ["phone_number"])

    def test_complete_profile(self):
        self.assertTrue(self.profile.is_complete())
        self.assertEqual(self.profile.missing_required_fields(), [])

    def test_optional_fields_do_not_affect_completeness(self):
        self.profile.address_line2 = ""
        self.profile.date_of_birth = None
        self.profile.other_pets = ""
        self.profile.save()
        self.assertTrue(self.profile.is_complete())

    def test_profile_response_exposes_completeness_flag(self):
        self.authenticate(self.adopter)
        resp = self.client.get("/api/adopters/profile/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["profile_is_complete"])
        # Staff listing adopters sees the same flag.
        staff = self.create_staff(email="completeness-staff@example.com")
        self.authenticate(staff)
        resp = self.client.get("/api/adopters/")
        self.assertTrue(resp.data["results"][0]["profile_is_complete"])

    def test_staff_can_create_application_with_incomplete_own_profile(self):
        # Staff/admin act on applications through this endpoint and must not
        # be blocked by the adopter profile gate.
        from apps.pets.models import Pet
        pet = Pet.objects.create(name="Buddy", species="dog", age_months=12, status="available")
        staff = self.create_staff(email="completeness-staff2@example.com")
        self.authenticate(staff)
        resp = self.client.post("/api/applications/", {
            "pet": str(pet.id),
            "documents": [SimpleUploadedFile("id.pdf", b"%PDF-1.4", content_type="application/pdf")],
            "document_types": ["identification"],
        }, format="multipart")
        # Documents require both identification AND proof_of_address, so a
        # single-document submission is rejected on documents — but NOT with a
        # profile error. The profile gate applies to adopters only.
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn("profile", resp.data)