"""
RBAC Security Tests — spec §14/§15

Verify that role-based access control is enforced at the API level:
  - Adopters cannot access staff/admin endpoints.
  - Staff cannot access admin-only endpoints.
  - Unauthenticated users are blocked from protected endpoints.
  - Adopters can only access their own resources.
  - Staff/admin cannot act as adopter when inappropriate.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.adopters.models import AdopterProfile
from apps.pets.models import Pet
from apps.applications.models import Application
from apps.health.models import HealthRecord, Vaccination
from apps.adoptions.models import AdoptionRecord
from apps.packages.models import AdoptionPackage
from apps.payments.models import Payment
from apps.reviews.models import Review
from apps.documents.models import Document
from apps.notifications.models import Notification

User = get_user_model()


class RBACTestCaseBase(TestCase):
    """Shared setUp for all RBAC tests."""

    def setUp(self):
        self.client = APIClient()

        # --- Users ---
        self.adopter = self._make_user("adopter1@example.com", role="adopter")
        self.other_adopter = self._make_user(
            "adopter2@example.com", role="adopter",
            first_name="Other", last_name="Adopter",
        )
        self.staff = self._make_user(
            "staff@example.com", role="staff",
            first_name="Staff", last_name="User",
        )
        self.admin = self._make_user(
            "admin@example.com", role="admin",
            first_name="Admin", last_name="User",
        )

        # --- Shared test objects ---
        self.pet = Pet.objects.create(
            name="Rex", species="dog", age_months=24,
            status="available", adoption_fee=0,
        )
        self.package = AdoptionPackage.objects.create(
            name="Basic", description="Basic package", price=0,
        )
        self.app = Application.objects.create(
            adopter=self.adopter, pet=self.pet,
            status="submitted", why_adopt="I love dogs",
        )
        self.other_app = Application.objects.create(
            adopter=self.other_adopter, pet=self.pet,
            status="submitted", why_adopt="I also love dogs",
        )
        self.health_record = HealthRecord.objects.create(
            pet=self.pet, record_date=date.today(),
            veterinarian_name="Dr. Smith",
        )
        self.vaccination = Vaccination.objects.create(
            pet=self.pet, vaccine_name="Rabies",
            date_administered=date.today(),
        )
        self.adoption = AdoptionRecord.objects.create(
            application=self.app, pet=self.pet,
            adopter=self.adopter, staff_member=self.staff,
            status="scheduled",
        )
        self.payment = Payment.objects.create(
            application=self.app, amount=100,
            status="pending", method="cash",
        )
        self.review = Review.objects.create(
            application=self.app, reviewer=self.staff,
            decision="request_info",
        )

        # Store profile references for adopter detail tests
        self.adopter_profile = self.adopter.adopter_profile
        self.other_adopter_profile = self.other_adopter.adopter_profile

    # ------------------------------------------------------------------
    def _make_user(self, email, role="adopter", **kwargs):
        user = User.objects.create_user(
            email=email, password="TestPass123!",
            first_name=kwargs.get("first_name", "Test"),
            last_name=kwargs.get("last_name", "User"),
            role=role,
        )
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        if role == "adopter":
            AdopterProfile.objects.get_or_create(user=user)
        return user

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def _unauth(self):
        self.client.credentials()


# ====================================================================
# 1. Unauthenticated users blocked from protected endpoints
# ====================================================================
class UnauthenticatedAccessTests(RBACTestCaseBase):
    """401 Unauthorized for every non-public endpoint."""

    def test_list_endpoints_return_401(self):
        """All non-public list endpoints must reject unauthenticated requests."""
        urls = [
            "/api/adopters/profile/",
            "/api/adopters/",
            "/api/applications/",
            "/api/documents/",
            "/api/reviews/",
            "/api/health-records/",
            "/api/health-records/vaccinations/",
            "/api/adoptions/",
            "/api/payments/",
            "/api/notifications/",
            "/api/notifications/unread-count/",
            "/api/audit/",
            "/api/reports/adoptions/",
            "/api/reports/pets/",
            "/api/reports/applications/",
            "/api/reports/payments/",
            "/api/reports/adopters/",
            "/api/reports/health/",
        ]
        self._unauth()
        for url in urls:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertIn(
                    resp.status_code, (401, 403),
                    f"Expected 401/403 for {url}, got {resp.status_code}",
                )

    def test_detail_endpoints_return_401(self):
        """Detail endpoints must reject unauthenticated requests."""
        detail_urls = [
            f"/api/adopters/{self.adopter_profile.id}/",
            f"/api/applications/{self.app.id}/",
            f"/api/reviews/{self.review.id}/",
            f"/api/health-records/{self.health_record.id}/",
            f"/api/health-records/vaccinations/{self.vaccination.id}/",
            f"/api/adoptions/{self.adoption.id}/",
            f"/api/payments/{self.payment.id}/",
        ]
        self._unauth()
        for url in detail_urls:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertIn(
                    resp.status_code, (401, 403),
                    f"Expected 401/403 for {url}, got {resp.status_code}",
                )

    def test_write_endpoints_return_401(self):
        """Write endpoints must reject unauthenticated requests."""
        write_endpoints = [
            ("POST", "/api/applications/",
             {"pet": str(self.pet.id), "why_adopt": "test"}),
            ("POST", "/api/pets/",
             {"name": "New", "species": "dog", "age_months": 12}),
        ]
        self._unauth()
        for method, url, data in write_endpoints:
            with self.subTest(method=method, url=url):
                resp = self.client.post(url, data, format="json")
                self.assertIn(
                    resp.status_code, (401, 403),
                    f"Expected 401/403 for {method} {url}, got {resp.status_code}",
                )

    def test_public_endpoints_work_without_auth(self):
        """Pet and package list/retrieve are public (AllowAny)."""
        resp = self.client.get("/api/pets/")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(f"/api/pets/{self.pet.id}/")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get("/api/packages/")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(f"/api/packages/{self.package.id}/")
        self.assertEqual(resp.status_code, 200)


# ====================================================================
# 2. Adopter blocked from staff/admin-only endpoints
# ====================================================================
class AdopterBlockedFromStaffEndpointsTests(RBACTestCaseBase):
    """Adopters must receive 403 for every staff-only endpoint."""

    def setUp(self):
        super().setUp()
        self._auth(self.adopter)

    # --- Adopter management (staff-only) ---
    def test_adopter_list_denied(self):
        resp = self.client.get("/api/adopters/")
        self.assertEqual(resp.status_code, 403)

    def test_adopter_detail_denied(self):
        resp = self.client.get(f"/api/adopters/{self.adopter_profile.id}/")
        self.assertEqual(resp.status_code, 403)

    # --- Reviews ---
    def test_review_list_denied(self):
        resp = self.client.get("/api/reviews/")
        self.assertEqual(resp.status_code, 403)

    def test_review_detail_denied(self):
        resp = self.client.get(f"/api/reviews/{self.review.id}/")
        self.assertEqual(resp.status_code, 403)

    def test_review_create_denied(self):
        resp = self.client.post("/api/reviews/", {
            "application": str(self.app.id),
            "decision": "approve",
        }, format="json")
        self.assertEqual(resp.status_code, 403)

    # --- Health records ---
    def test_health_record_list_denied(self):
        resp = self.client.get("/api/health-records/")
        self.assertEqual(resp.status_code, 403)

    def test_health_record_create_denied(self):
        resp = self.client.post("/api/health-records/", {
            "pet": str(self.pet.id),
            "record_date": str(date.today()),
        }, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_health_record_detail_denied(self):
        resp = self.client.get(
            f"/api/health-records/{self.health_record.id}/",
        )
        self.assertEqual(resp.status_code, 403)

    # --- Vaccinations ---
    def test_vaccination_list_denied(self):
        resp = self.client.get("/api/health-records/vaccinations/")
        self.assertEqual(resp.status_code, 403)

    def test_vaccination_create_denied(self):
        resp = self.client.post("/api/health-records/vaccinations/", {
            "pet": str(self.pet.id),
            "vaccine_name": "Parvo",
            "date_administered": str(date.today()),
        }, format="json")
        self.assertEqual(resp.status_code, 403)

    # --- Adoptions ---
    def test_adoption_list_denied(self):
        resp = self.client.get("/api/adoptions/")
        self.assertEqual(resp.status_code, 403)

    def test_adoption_create_denied(self):
        resp = self.client.post("/api/adoptions/", {
            "application": str(self.app.id),
            "pet": str(self.pet.id),
        }, format="json")
        self.assertEqual(resp.status_code, 403)

    # --- Pet write operations ---
    def test_pet_create_denied(self):
        resp = self.client.post("/api/pets/", {
            "name": "Buddy", "species": "dog", "age_months": 12,
        }, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_pet_update_denied(self):
        resp = self.client.patch(f"/api/pets/{self.pet.id}/", {
            "name": "Hacked",
        }, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_pet_delete_denied(self):
        resp = self.client.delete(f"/api/pets/{self.pet.id}/")
        self.assertEqual(resp.status_code, 403)

    def test_pet_image_create_denied(self):
        resp = self.client.post(
            f"/api/pets/{self.pet.id}/images/", {"caption": "Test"},
        )
        self.assertEqual(resp.status_code, 403)

    # --- Package write operations ---
    def test_package_create_denied(self):
        resp = self.client.post("/api/packages/", {
            "name": "Premium", "description": "Premium pkg", "price": 500,
        }, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_package_update_denied(self):
        resp = self.client.patch(
            f"/api/packages/{self.package.id}/", {"price": 999},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_package_delete_denied(self):
        resp = self.client.delete(f"/api/packages/{self.package.id}/")
        self.assertEqual(resp.status_code, 403)

    # --- Payment write operations ---
    def test_payment_create_denied(self):
        resp = self.client.post("/api/payments/", {
            "application": str(self.app.id), "amount": 100,
        }, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_payment_update_denied(self):
        resp = self.client.patch(
            f"/api/payments/{self.payment.id}/",
            {"status": "completed"}, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_payment_delete_denied(self):
        resp = self.client.delete(f"/api/payments/{self.payment.id}/")
        self.assertEqual(resp.status_code, 403)

    # --- Application update-status action ---
    def test_application_update_status_denied(self):
        resp = self.client.post(
            f"/api/applications/{self.app.id}/update-status/",
            {"status": "approved"}, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    # --- Reports ---
    def test_reports_adoptions_denied(self):
        resp = self.client.get("/api/reports/adoptions/")
        self.assertEqual(resp.status_code, 403)

    def test_reports_pets_denied(self):
        resp = self.client.get("/api/reports/pets/")
        self.assertEqual(resp.status_code, 403)

    def test_reports_applications_denied(self):
        resp = self.client.get("/api/reports/applications/")
        self.assertEqual(resp.status_code, 403)

    def test_reports_payments_denied(self):
        resp = self.client.get("/api/reports/payments/")
        self.assertEqual(resp.status_code, 403)

    def test_reports_adopters_denied(self):
        resp = self.client.get("/api/reports/adopters/")
        self.assertEqual(resp.status_code, 403)

    def test_reports_health_denied(self):
        resp = self.client.get("/api/reports/health/")
        self.assertEqual(resp.status_code, 403)

    # --- Audit ---
    def test_audit_log_denied(self):
        resp = self.client.get("/api/audit/")
        self.assertEqual(resp.status_code, 403)


# ====================================================================
# 3. Staff blocked from admin-only endpoints
# ====================================================================
class StaffBlockedFromAdminEndpointsTests(RBACTestCaseBase):
    """Staff role cannot access admin-only resources."""

    def setUp(self):
        super().setUp()
        self._auth(self.staff)

    def test_audit_log_denied_for_staff(self):
        resp = self.client.get("/api/audit/")
        self.assertEqual(resp.status_code, 403)


# ====================================================================
# 4. Admin can access all endpoints
# ====================================================================
class AdminAccessTests(RBACTestCaseBase):
    """Admin role can access every endpoint."""

    def setUp(self):
        super().setUp()
        self._auth(self.admin)

    def test_adopter_list(self):
        resp = self.client.get("/api/adopters/")
        self.assertEqual(resp.status_code, 200)

    def test_adopter_detail(self):
        resp = self.client.get(f"/api/adopters/{self.adopter_profile.id}/")
        self.assertEqual(resp.status_code, 200)

    def test_review_list(self):
        resp = self.client.get("/api/reviews/")
        self.assertEqual(resp.status_code, 200)

    def test_review_detail(self):
        resp = self.client.get(f"/api/reviews/{self.review.id}/")
        self.assertEqual(resp.status_code, 200)

    def test_health_record_list(self):
        resp = self.client.get("/api/health-records/")
        self.assertEqual(resp.status_code, 200)

    def test_health_record_detail(self):
        resp = self.client.get(
            f"/api/health-records/{self.health_record.id}/",
        )
        self.assertEqual(resp.status_code, 200)

    def test_vaccination_list(self):
        resp = self.client.get("/api/health-records/vaccinations/")
        self.assertEqual(resp.status_code, 200)

    def test_adoption_list(self):
        resp = self.client.get("/api/adoptions/")
        self.assertEqual(resp.status_code, 200)

    def test_pet_create(self):
        resp = self.client.post("/api/pets/", {
            "name": "AdminPet", "species": "cat", "age_months": 6,
        }, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_pet_update(self):
        resp = self.client.patch(f"/api/pets/{self.pet.id}/", {
            "name": "AdminRenamed",
        }, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_package_create(self):
        resp = self.client.post("/api/packages/", {
            "name": "AdminPkg", "description": "pkg", "price": 0,
        }, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_reports_adoptions(self):
        resp = self.client.get("/api/reports/adoptions/")
        self.assertEqual(resp.status_code, 200)

    def test_reports_pets(self):
        resp = self.client.get("/api/reports/pets/")
        self.assertEqual(resp.status_code, 200)

    def test_reports_applications(self):
        resp = self.client.get("/api/reports/applications/")
        self.assertEqual(resp.status_code, 200)

    def test_reports_payments(self):
        resp = self.client.get("/api/reports/payments/")
        self.assertEqual(resp.status_code, 200)

    def test_reports_adopters(self):
        resp = self.client.get("/api/reports/adopters/")
        self.assertEqual(resp.status_code, 200)

    def test_reports_health(self):
        resp = self.client.get("/api/reports/health/")
        self.assertEqual(resp.status_code, 200)

    def test_audit_log(self):
        """Admin CAN access the audit log."""
        resp = self.client.get("/api/audit/")
        self.assertEqual(resp.status_code, 200)


# ====================================================================
# 5. Staff can access staff endpoints
# ====================================================================
class StaffAccessTests(RBACTestCaseBase):
    """Staff role can access staff-protected endpoints."""

    def setUp(self):
        super().setUp()
        self._auth(self.staff)

    def test_adopter_list(self):
        resp = self.client.get("/api/adopters/")
        self.assertEqual(resp.status_code, 200)

    def test_adopter_detail(self):
        resp = self.client.get(f"/api/adopters/{self.adopter_profile.id}/")
        self.assertEqual(resp.status_code, 200)

    def test_review_list(self):
        resp = self.client.get("/api/reviews/")
        self.assertEqual(resp.status_code, 200)

    def test_health_record_list(self):
        resp = self.client.get("/api/health-records/")
        self.assertEqual(resp.status_code, 200)

    def test_health_record_create(self):
        resp = self.client.post("/api/health-records/", {
            "pet": str(self.pet.id),
            "record_date": str(date.today()),
            "veterinarian_name": "Dr. Staff",
        }, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_vaccination_list(self):
        resp = self.client.get("/api/health-records/vaccinations/")
        self.assertEqual(resp.status_code, 200)

    def test_vaccination_create(self):
        resp = self.client.post("/api/health-records/vaccinations/", {
            "pet": str(self.pet.id),
            "vaccine_name": "Parvo",
            "date_administered": str(date.today()),
        }, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_adoption_list(self):
        resp = self.client.get("/api/adoptions/")
        self.assertEqual(resp.status_code, 200)

    def test_adoption_create(self):
        # Adoption requires an approved application. Use a fresh pet/application
        # because the base setUp already created an AdoptionRecord for self.app.
        fresh_pet = Pet.objects.create(name="Lucky", species="dog", age_months=12, status="available")
        approved_app = Application.objects.create(
            adopter=self.adopter, pet=fresh_pet, status="approved",
            why_adopt="I love dogs",
        )
        resp = self.client.post("/api/adoptions/", {
            "application_id": str(approved_app.id),
        }, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_pet_create(self):
        resp = self.client.post("/api/pets/", {
            "name": "StaffPet", "species": "bird", "age_months": 3,
        }, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_pet_update(self):
        resp = self.client.patch(f"/api/pets/{self.pet.id}/", {
            "name": "StaffRenamed",
        }, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_pet_delete(self):
        pet2 = Pet.objects.create(name="TempPet", species="cat", age_months=1)
        resp = self.client.delete(f"/api/pets/{pet2.id}/")
        self.assertEqual(resp.status_code, 204)

    def test_package_create(self):
        resp = self.client.post("/api/packages/", {
            "name": "StaffPkg", "description": "pkg", "price": 0,
        }, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_payment_create(self):
        resp = self.client.post("/api/payments/", {
            "application": str(self.app.id),
            "amount": 50, "method": "cash",
        }, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_reports_adoptions(self):
        resp = self.client.get("/api/reports/adoptions/")
        self.assertEqual(resp.status_code, 200)

    def test_application_update_status(self):
        """Staff can use the update-status action."""
        self.app.status = "under_review"
        self.app.save(update_fields=["status"])
        resp = self.client.post(
            f"/api/applications/{self.app.id}/update-status/",
            {"status": "approved"}, format="json",
        )
        self.assertEqual(resp.status_code, 200)


# ====================================================================
# 6. Cross-adopter isolation
# ====================================================================
class AdopterOwnershipTests(RBACTestCaseBase):
    """Adopters can only access their own resources."""

    def setUp(self):
        super().setUp()
        self._auth(self.adopter)

    def test_adopter_sees_own_applications_only(self):
        resp = self.client.get("/api/applications/")
        self.assertEqual(resp.status_code, 200)
        app_ids = [a["id"] for a in resp.data.get("results", resp.data)]
        self.assertIn(str(self.app.id), app_ids)
        self.assertNotIn(str(self.other_app.id), app_ids)

    def test_adopter_cannot_access_other_app_detail(self):
        resp = self.client.get(f"/api/applications/{self.other_app.id}/")
        self.assertIn(resp.status_code, (403, 404))

    def test_adopter_cannot_cancel_other_app(self):
        resp = self.client.post(
            f"/api/applications/{self.other_app.id}/cancel/",
            format="json",
        )
        self.assertIn(resp.status_code, (403, 404))

    def test_adopter_cannot_update_status_on_other_app(self):
        resp = self.client.post(
            f"/api/applications/{self.other_app.id}/update-status/",
            {"status": "approved"}, format="json",
        )
        self.assertIn(resp.status_code, (403, 404))


# ====================================================================
# 7. Adopter profile access
# ====================================================================
class AdopterProfileAccessTests(RBACTestCaseBase):
    """Profile endpoint: any authenticated user can read, only adopter can write."""

    def test_adopter_can_read_own_profile(self):
        self._auth(self.adopter)
        resp = self.client.get("/api/adopters/profile/")
        self.assertEqual(resp.status_code, 200)

    def test_staff_cannot_update_profile(self):
        """Staff should be denied updating via adopter-profile PATCH."""
        self._auth(self.staff)
        resp = self.client.patch("/api/adopters/profile/", {
            "city": "Hacked",
        }, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_adopter_can_update_own_profile(self):
        self._auth(self.adopter)
        resp = self.client.patch("/api/adopters/profile/", {
            "city": "Manila",
        }, format="json")
        self.assertEqual(resp.status_code, 200)


# ====================================================================
# 8. Application cancellation ownership check
# ====================================================================
class ApplicationCancellationOwnershipTests(RBACTestCaseBase):
    """Cancel action is owner-only (view-level check)."""

    def test_adopter_can_cancel_own_application(self):
        self._auth(self.adopter)
        resp = self.client.post(
            f"/api/applications/{self.app.id}/cancel/",
            format="json",
        )
        self.assertIn(resp.status_code, (200, 400))

    def test_adopter_cannot_cancel_other_application(self):
        self._auth(self.adopter)
        resp = self.client.post(
            f"/api/applications/{self.other_app.id}/cancel/",
            format="json",
        )
        self.assertIn(resp.status_code, (403, 404))

    def test_staff_cannot_cancel_adopter_application(self):
        """Staff are not the owner — cancel action checks owner."""
        self._auth(self.staff)
        resp = self.client.post(
            f"/api/applications/{self.app.id}/cancel/",
            format="json",
        )
        self.assertIn(resp.status_code, (403, 404))



# ====================================================================
# 9. Pet public vs. write access
# ====================================================================
class PetAccessTests(RBACTestCaseBase):
    """Pet list/retrieve is public; create/update/delete is staff-only."""

    def test_anyone_can_list_pets(self):
        self._unauth()
        resp = self.client.get("/api/pets/")
        self.assertEqual(resp.status_code, 200)

    def test_anyone_can_retrieve_pet(self):
        self._unauth()
        resp = self.client.get(f"/api/pets/{self.pet.id}/")
        self.assertEqual(resp.status_code, 200)

    def test_adopter_cannot_create_pet(self):
        self._auth(self.adopter)
        resp = self.client.post("/api/pets/", {
            "name": "Nope", "species": "cat", "age_months": 1,
        }, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_adopter_cannot_update_pet(self):
        self._auth(self.adopter)
        resp = self.client.patch(f"/api/pets/{self.pet.id}/", {
            "name": "Hijacked",
        }, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_adopter_cannot_delete_pet(self):
        self._auth(self.adopter)
        resp = self.client.delete(f"/api/pets/{self.pet.id}/")
        self.assertEqual(resp.status_code, 403)


# ====================================================================
# 10. Package public vs. write access
# ====================================================================
class PackageAccessTests(RBACTestCaseBase):
    """Package list/retrieve is public; write operations are staff-only."""

    def test_anyone_can_list_packages(self):
        self._unauth()
        resp = self.client.get("/api/packages/")
        self.assertEqual(resp.status_code, 200)

    def test_adopter_cannot_create_package(self):
        self._auth(self.adopter)
        resp = self.client.post("/api/packages/", {
            "name": "Nope", "description": "x", "price": 0,
        }, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_adopter_cannot_update_package(self):
        self._auth(self.adopter)
        resp = self.client.patch(f"/api/packages/{self.package.id}/", {
            "price": 999,
        }, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_adopter_cannot_delete_package(self):
        self._auth(self.adopter)
        resp = self.client.delete(f"/api/packages/{self.package.id}/")
        self.assertEqual(resp.status_code, 403)


# ====================================================================
# 11. Payment scoping
# ====================================================================
class PaymentAccessTests(RBACTestCaseBase):
    """Adopters see only their own payments; staff see all."""

    def test_adopter_sees_own_payments(self):
        self._auth(self.adopter)
        resp = self.client.get("/api/payments/")
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get("results", resp.data)
        payment_ids = [p["id"] for p in results]
        self.assertIn(str(self.payment.id), payment_ids)

    def test_adopter_cannot_create_payment(self):
        self._auth(self.adopter)
        resp = self.client.post("/api/payments/", {
            "application": str(self.app.id),
            "amount": 50,
        }, format="json")
        self.assertEqual(resp.status_code, 403)



# ====================================================================
# 12. Notification scoping
# ====================================================================
class NotificationAccessTests(RBACTestCaseBase):
    """Notifications are user-scoped."""

    def setUp(self):
        super().setUp()
        self.notif_adopter = Notification.objects.create(
            user=self.adopter, title="Test 1", message="msg",
            notification_type="application",
        )
        self.notif_other = Notification.objects.create(
            user=self.other_adopter, title="Test 2", message="msg",
            notification_type="application",
        )

    def test_adopter_sees_own_notifications(self):
        self._auth(self.adopter)
        resp = self.client.get("/api/notifications/")
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get("results", resp.data)
        notif_ids = [n["id"] for n in results]
        self.assertIn(str(self.notif_adopter.id), notif_ids)
        self.assertNotIn(str(self.notif_other.id), notif_ids)

    def test_adopter_unread_count(self):
        self._auth(self.adopter)
        resp = self.client.get("/api/notifications/unread-count/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["unread_count"], 1)

    def test_adopter_cannot_read_other_notification(self):
        self._auth(self.adopter)
        resp = self.client.get(f"/api/notifications/{self.notif_other.id}/")
        self.assertIn(resp.status_code, (403, 404))

    def test_adopter_mark_read_own(self):
        self._auth(self.adopter)
        resp = self.client.patch(
            f"/api/notifications/{self.notif_adopter.id}/read/",
            {"is_read": True}, format="json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_adopter_mark_read_other_denied(self):
        self._auth(self.adopter)
        resp = self.client.patch(
            f"/api/notifications/{self.notif_other.id}/read/",
            {"is_read": True}, format="json",
        )
        self.assertIn(resp.status_code, (403, 404))


# ====================================================================
# 13. Review internal_notes protection
# ====================================================================
class ReviewInternalNotesProtectionTests(RBACTestCaseBase):
    """internal_notes must NEVER be in adopter-facing API responses."""

    def setUp(self):
        super().setUp()
        self.review_with_notes = Review.objects.create(
            application=self.other_app, reviewer=self.staff,
            decision="request_info",
            internal_notes="SECRET STAFF NOTE",
            adopter_visible_notes="Please provide proof of address.",
        )

    def test_staff_review_serializer_includes_notes(self):
        """Staff can read internal_notes from the reviews endpoint."""
        self._auth(self.staff)
        resp = self.client.get(f"/api/reviews/{self.review_with_notes.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("internal_notes", resp.data)

    def test_adopter_cannot_access_review_endpoint(self):
        """Adopters are blocked from the reviews endpoint entirely (IsStaff)."""
        self._auth(self.adopter)
        resp = self.client.get(f"/api/reviews/{self.review_with_notes.id}/")
        self.assertEqual(resp.status_code, 403)


# ====================================================================
# 14. Application scoping for staff vs adopter
# ====================================================================
class ApplicationQuerysetScopingTests(RBACTestCaseBase):
    """Staff/admin see all applications; adopters see only their own."""

    def test_adopter_sees_own_apps_only(self):
        self._auth(self.adopter)
        resp = self.client.get("/api/applications/")
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get("results", resp.data)
        for a in results:
            self.assertEqual(
                str(a.get("adopter")), str(self.adopter.id),
                "Adopter should only see their own applications",
            )

    def test_staff_sees_all_apps(self):
        self._auth(self.staff)
        resp = self.client.get("/api/applications/")
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get("results", resp.data)
        app_ids = [a["id"] for a in results]
        self.assertIn(str(self.app.id), app_ids)
        self.assertIn(str(self.other_app.id), app_ids)

    def test_staff_can_filter_by_adopter(self):
        self._auth(self.staff)
        resp = self.client.get(f"/api/applications/?adopter_id={self.adopter.id}")
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get("results", resp.data)
        for a in results:
            self.assertEqual(
                str(a.get("adopter")), str(self.adopter.id),
                "Staff adopter_id filter should work",
            )



# ====================================================================
# 15. Document access control
# ====================================================================
class DocumentAccessTests(RBACTestCaseBase):
    """Documents are scoped: adopters see own, staff see all."""

    def setUp(self):
        super().setUp()
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.test_content = b"fake pdf content"
        self.doc = Document.objects.create(
            application=self.app,
            document_type="identification",
            file=SimpleUploadedFile(
                "test.pdf", self.test_content,
                content_type="application/pdf",
            ),
            original_filename="test.pdf",
            content_type="application/pdf",
            file_size=len(self.test_content),
            uploaded_by=self.adopter,
        )
        self.other_doc = Document.objects.create(
            application=self.other_app,
            document_type="identification",
            file=SimpleUploadedFile(
                "other.pdf", self.test_content,
                content_type="application/pdf",
            ),
            original_filename="other.pdf",
            content_type="application/pdf",
            file_size=len(self.test_content),
            uploaded_by=self.other_adopter,
        )

    def test_adopter_sees_own_documents(self):
        self._auth(self.adopter)
        resp = self.client.get("/api/documents/")
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get("results", resp.data)
        doc_ids = [d["id"] for d in results]
        self.assertIn(str(self.doc.id), doc_ids)
        self.assertNotIn(str(self.other_doc.id), doc_ids)

    def test_adopter_cannot_delete_other_document(self):
        self._auth(self.adopter)
        resp = self.client.delete(f"/api/documents/{self.other_doc.id}/")
        self.assertIn(resp.status_code, (403, 404))

    def test_adopter_can_delete_own_document(self):
        self._auth(self.adopter)
        resp = self.client.delete(f"/api/documents/{self.doc.id}/")
        self.assertEqual(resp.status_code, 204)

