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
        pet = Pet.objects.create(name="Buddy", species="dog", age_years=1, status="available")
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


# ---------------------------------------------------------------------------
# DateOfBirth tests
# ---------------------------------------------------------------------------

class DateOfBirthTests(BaseAPITestCase):
    """
    Tests for the date_of_birth field on AdopterProfile.

    The field is already in the model and initial migration (blank=True,
    null=True).  These tests verify:
      - Saving and retrieving a valid DOB.
      - Clearing the DOB (null value is acceptable — it is not a required field).
      - Rejecting a future date.
      - Rejecting a date more than 120 years in the past.
      - Adopters cannot update another user's profile.
      - Authorized staff can read the adopter's DOB; unauthorized adopter cannot
        read another adopter's profile at all.
    """

    def setUp(self):
        super().setUp()
        self.adopter = self.create_user(email="dob_adopter@example.com")
        self.other_adopter = self.create_user(email="dob_other@example.com")
        self.staff = self.create_staff(email="dob_staff@example.com")

    def profile_id(self, user=None):
        user = user or self.adopter
        return str(user.adopter_profile.id)

    # -- save / retrieve -----------------------------------------------------

    def test_adopter_can_save_date_of_birth(self):
        self.authenticate(self.adopter)
        resp = self.client.patch(
            "/api/adopters/profile/",
            {"date_of_birth": "1990-06-15"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        profile = self.adopter.adopter_profile
        profile.refresh_from_db()
        self.assertIsNotNone(profile.date_of_birth)
        from datetime import date
        self.assertEqual(profile.date_of_birth, date(1990, 6, 15))

    def test_profile_response_includes_date_of_birth(self):
        """GET /api/adopters/profile/ must return the date_of_birth field."""
        self.adopter.adopter_profile.date_of_birth = "1990-06-15"
        self.adopter.adopter_profile.save()
        self.authenticate(self.adopter)
        resp = self.client.get("/api/adopters/profile/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("date_of_birth", resp.data)
        self.assertEqual(resp.data["date_of_birth"], "1990-06-15")

    def test_adopter_can_clear_date_of_birth(self):
        """Setting date_of_birth to null is accepted (it is optional)."""
        self.adopter.adopter_profile.date_of_birth = "1990-06-15"
        self.adopter.adopter_profile.save()
        self.authenticate(self.adopter)
        resp = self.client.patch(
            "/api/adopters/profile/",
            {"date_of_birth": None},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.adopter.adopter_profile.refresh_from_db()
        self.assertIsNone(self.adopter.adopter_profile.date_of_birth)

    # -- validation ----------------------------------------------------------

    def test_future_date_of_birth_is_rejected(self):
        self.authenticate(self.adopter)
        resp = self.client.patch(
            "/api/adopters/profile/",
            {"date_of_birth": "2099-01-01"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("date_of_birth", resp.data)

    def test_date_of_birth_too_old_is_rejected(self):
        """A date more than 120 years in the past is rejected."""
        self.authenticate(self.adopter)
        resp = self.client.patch(
            "/api/adopters/profile/",
            {"date_of_birth": "1800-01-01"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("date_of_birth", resp.data)

    # -- ownership -----------------------------------------------------------

    def test_adopter_cannot_update_another_adopters_profile(self):
        """
        The /api/adopters/profile/ endpoint always resolves to the request
        user's own profile (via get_object using request.user).  There is no
        route that allows an adopter to PATCH a different adopter's profile.
        The staff-facing detail route /api/adopters/<id>/ is GET-only and
        requires IsStaff — an adopter is blocked by the permission class.
        """
        self.authenticate(self.adopter)
        other_id = self.profile_id(self.other_adopter)
        resp = self.client.patch(
            f"/api/adopters/{other_id}/",
            {"date_of_birth": "1990-06-15"},
            format="json",
        )
        # Staff-only route returns 403 for an adopter.
        self.assertIn(resp.status_code, [403, 404, 405])

    # -- staff visibility ----------------------------------------------------

    def test_staff_can_read_adopter_date_of_birth(self):
        """Staff GET /api/adopters/<id>/ includes date_of_birth."""
        self.adopter.adopter_profile.date_of_birth = "1985-03-20"
        self.adopter.adopter_profile.save()
        self.authenticate(self.staff)
        resp = self.client.get(f"/api/adopters/{self.profile_id()}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["date_of_birth"], "1985-03-20")

    def test_adopter_cannot_access_staff_adopter_detail_endpoint(self):
        """An adopter cannot read another adopter's profile via the staff route."""
        self.adopter.adopter_profile.date_of_birth = "1985-03-20"
        self.adopter.adopter_profile.save()
        other_id = self.profile_id(self.other_adopter)
        self.authenticate(self.adopter)
        resp = self.client.get(f"/api/adopters/{other_id}/")
        self.assertEqual(resp.status_code, 403)

    def test_dob_in_application_adopter_profile_for_staff(self):
        """
        When staff retrieve an application, the nested adopter_profile
        includes date_of_birth.  This is provided via AdopterProfileSerializer
        which already includes the field — this test confirms end-to-end.
        """
        from apps.pets.models import Pet
        from apps.applications.models import Application
        self.adopter.adopter_profile.date_of_birth = "1990-06-15"
        self.adopter.adopter_profile.save()
        pet = Pet.objects.create(name="Fluffy", species="cat", age_years=2, status="available")
        application = Application.objects.create(
            adopter=self.adopter,
            pet=pet,
            status="submitted",
            why_adopt="love cats",
            experience_with_pets="owned cats before",
            living_situation="house",
            privacy_consent=True,
        )
        self.authenticate(self.staff)
        resp = self.client.get(f"/api/applications/{application.id}/")
        self.assertEqual(resp.status_code, 200)
        profile = resp.data.get("adopter_profile")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.get("date_of_birth"), "1990-06-15")


    def test_dob_not_exposed_to_unauthenticated_requests(self):
        """Profile endpoint requires authentication."""
        self.adopter.adopter_profile.date_of_birth = "1990-06-15"
        self.adopter.adopter_profile.save()
        # No credentials.
        resp = self.client.get("/api/adopters/profile/")
        self.assertEqual(resp.status_code, 403)

    def test_clearing_dob_does_not_break_profile_completeness(self):
        """
        date_of_birth is not in REQUIRED_PROFILE_FIELDS, so clearing it must
        not affect profile_is_complete.
        """
        self.adopter.adopter_profile.date_of_birth = "1990-06-15"
        self.adopter.adopter_profile.save()
        self.authenticate(self.adopter)
        resp = self.client.patch(
            "/api/adopters/profile/",
            {"date_of_birth": None},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["profile_is_complete"])


class PhilippineAddressTests(BaseAPITestCase):
    """
    Tests for Philippine-wide cascading address hierarchy and persistence.

    Hierarchy:
      Region -> Province (when applicable) -> City/Municipality -> Barangay
    """

    def setUp(self):
        super().setUp()
        self.adopter = self.create_user(email="ph_adopter@example.com")
        self.other_adopter = self.create_user(email="ph_other@example.com")
        self.staff = self.create_staff(email="ph_staff@example.com")

    def test_ncr_address_saves_and_persists_without_province(self):
        """NCR address does not require province and persists correctly."""
        self.authenticate(self.adopter)
        resp = self.client.patch(
            "/api/adopters/profile/",
            {
                "region": "National Capital Region (NCR)",
                "city": "City of Manila",
                "barangay": "Barangay 1",
                "address_line1": "123 Taft Ave",
                "zip_code": "1000",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        profile = self.adopter.adopter_profile
        profile.refresh_from_db()
        self.assertEqual(profile.region, "National Capital Region (NCR)")
        self.assertEqual(profile.city, "City of Manila")
        self.assertEqual(profile.barangay, "Barangay 1")
        self.assertEqual(profile.state, "")  # No province for NCR
        self.assertTrue(profile.is_complete())
        self.assertTrue(resp.data["profile_is_complete"])

    def test_province_based_address_saves_and_persists(self):
        """Address in CALABARZON with province persists correctly."""
        self.authenticate(self.adopter)
        resp = self.client.patch(
            "/api/adopters/profile/",
            {
                "region": "Region IV-A (CALABARZON)",
                "state": "Cavite",
                "city": "Bacoor City",
                "barangay": "Alima",
                "address_line1": "Block 4 Lot 5 Molino",
                "zip_code": "4102",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        profile = self.adopter.adopter_profile
        profile.refresh_from_db()
        self.assertEqual(profile.region, "Region IV-A (CALABARZON)")
        self.assertEqual(profile.state, "Cavite")
        self.assertEqual(profile.city, "Bacoor City")
        self.assertEqual(profile.barangay, "Alima")
        self.assertTrue(profile.is_complete())

    def test_invalid_region_is_rejected(self):
        """Unrecognized region is rejected by backend validation."""
        self.authenticate(self.adopter)
        resp = self.client.patch(
            "/api/adopters/profile/",
            {
                "region": "Invalid Region Land",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("region", resp.data)

    def test_mismatched_province_is_rejected(self):
        """Province that does not belong to region is rejected."""
        self.authenticate(self.adopter)
        resp = self.client.patch(
            "/api/adopters/profile/",
            {
                "region": "Region IV-A (CALABARZON)",
                "state": "Cebu",  # Cebu is Region VII
                "city": "Cebu City",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("state", resp.data)

    def test_mismatched_city_is_rejected(self):
        """City that does not belong to province is rejected."""
        self.authenticate(self.adopter)
        resp = self.client.patch(
            "/api/adopters/profile/",
            {
                "region": "Region IV-A (CALABARZON)",
                "state": "Cavite",
                "city": "Baguio City",  # Baguio is in Benguet/CAR
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("city", resp.data)

    def test_mismatched_barangay_is_rejected(self):
        """Barangay that does not belong to city is rejected."""
        self.authenticate(self.adopter)
        resp = self.client.patch(
            "/api/adopters/profile/",
            {
                "region": "National Capital Region (NCR)",
                "city": "City of Manila",
                "barangay": "Nonexistent Barangay 99999",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("barangay", resp.data)

    def test_legacy_profile_address_remains_intact_and_complete(self):
        """Profiles saved before structured address fields are complete and readable."""
        profile = self.adopter.adopter_profile
        self.assertTrue(profile.is_complete())
        self.authenticate(self.adopter)
        resp = self.client.get("/api/adopters/profile/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["city"], "Manila")
        self.assertEqual(resp.data["state"], "Metro Manila")
        self.assertTrue(resp.data["profile_is_complete"])

    def test_staff_review_retrieves_saved_philippine_address(self):
        """Staff review retrieves complete applicant address including region and barangay."""
        from apps.pets.models import Pet
        from apps.applications.models import Application
        self.authenticate(self.adopter)
        patch_resp = self.client.patch(
            "/api/adopters/profile/",
            {
                "region": "Region III (Central Luzon)",
                "state": "Bulacan",
                "city": "City of Malolos",
                "barangay": "Atlag",
                "address_line1": "789 Malolos Hwy",
                "zip_code": "3000",
            },
            format="json",
        )
        self.assertEqual(patch_resp.status_code, 200)
        pet = Pet.objects.create(name="Spot", species="dog", age_years=1, status="available")
        app = Application.objects.create(
            adopter=self.adopter,
            pet=pet,
            status="submitted",
            why_adopt="good home",
            experience_with_pets="yes",
            living_situation="own house",
            privacy_consent=True,
        )
        self.authenticate(self.staff)
        resp = self.client.get(f"/api/applications/{app.id}/")
        self.assertEqual(resp.status_code, 200)
        adopter_data = resp.data["adopter_profile"]
        self.assertEqual(adopter_data["region"], "Region III (Central Luzon)")
        self.assertEqual(adopter_data["state"], "Bulacan")
        self.assertEqual(adopter_data["city"], "City of Malolos")
        self.assertEqual(adopter_data["barangay"], "Atlag")

    def test_unauthorized_user_cannot_update_another_users_address(self):
        """An adopter cannot modify another adopter's address."""
        self.authenticate(self.adopter)
        other_profile_id = str(self.other_adopter.adopter_profile.id)
        resp = self.client.patch(
            f"/api/adopters/{other_profile_id}/",
            {"region": "National Capital Region (NCR)"},
            format="json",
        )
        self.assertIn(resp.status_code, [403, 404, 405])