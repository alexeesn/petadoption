from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.tests import BaseAPITestCase
from apps.pets.models import Pet
from apps.applications.models import Application


class ApplicationTests(BaseAPITestCase):

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(name="Buddy", species="dog", age_months=12, status="available")
        self.adopter = self.create_user(email="adopter1@example.com")
        self.staff = self.create_staff(email="staff1@example.com")

    def create_application(self, user=None, status="draft"):
        app = Application.objects.create(
            adopter=user or self.adopter,
            pet=self.pet,
            status=status,
        )
        return app

    def test_adopter_can_create_application(self):
        self.authenticate(self.adopter)
        resp = self.client.post("/api/applications/", {
            "pet": str(self.pet.id),
            "why_adopt": "I love dogs",
        })
        self.assertEqual(resp.status_code, 201)

    def test_create_application_leaves_draft_and_becomes_submitted(self):
        # Regression for QA-REPORT-2026-09-09.md section 2: a normal
        # submission must not remain stuck in "draft" with no way for the
        # adopter to advance it. Hit the real endpoint, not the model layer.
        self.authenticate(self.adopter)
        resp = self.client.post("/api/applications/", {
            "pet": str(self.pet.id),
            "why_adopt": "I love dogs",
        })
        self.assertEqual(resp.status_code, 201)
        app = Application.objects.get(adopter=self.adopter, pet=self.pet)
        self.assertEqual(app.status, "submitted")
        # Notifications and audit log must fire for the new flow.
        from apps.audit.models import AuditLog
        self.assertTrue(
            AuditLog.objects.filter(
                model_name="Application",
                object_id=str(app.id),
                previous_value="draft",
                new_value="submitted",
            ).exists()
        )

    def test_create_application_response_includes_id_and_status(self):
        # Regression for QA-REPORT-2026-09-09.md section 3: the create
        # response must use the read serializer so clients learn the new
        # application's id and status from the response body.
        self.authenticate(self.adopter)
        resp = self.client.post("/api/applications/", {
            "pet": str(self.pet.id),
            "why_adopt": "I love dogs",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertIn("id", resp.data)
        self.assertIn("status", resp.data)
        self.assertEqual(resp.data["status"], "submitted")
        app = Application.objects.get(pk=resp.data["id"])
        self.assertEqual(app.adopter, self.adopter)

    def test_adopter_sees_only_own_applications(self):
        other = self.create_user(email="other@example.com")
        Application.objects.create(adopter=other, pet=self.pet)
        self.authenticate(self.adopter)
        resp = self.client.get("/api/applications/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 0)

    def test_conflicting_active_applications_rejected(self):
        # Unique constraint on (adopter, pet) for active applications
        Application.objects.create(adopter=self.adopter, pet=self.pet, status="submitted")
        self.authenticate(self.adopter)
        resp = self.client.post("/api/applications/", {
            "pet": str(self.pet.id),
            "why_adopt": "again",
        })
        self.assertEqual(resp.status_code, 400)

    def test_staff_can_view_all_applications(self):
        Application.objects.create(adopter=self.adopter, pet=self.pet)
        self.authenticate(self.staff)
        resp = self.client.get("/api/applications/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)

    def test_valid_status_transition(self):
        app = self.create_application(status="submitted")
        self.authenticate(self.staff)
        resp = self.client.post(f"/api/applications/{app.id}/update-status/", {"status": "under_review"})
        self.assertEqual(resp.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, "under_review")

    def test_invalid_status_transition(self):
        app = self.create_application(status="draft")
        self.authenticate(self.staff)
        # draft -> approved is invalid
        resp = self.client.post(f"/api/applications/{app.id}/update-status/", {"status": "approved"})
        self.assertEqual(resp.status_code, 400)

    def test_adopter_cannot_update_status(self):
        app = self.create_application(status="submitted")
        self.authenticate(self.adopter)
        resp = self.client.post(f"/api/applications/{app.id}/update-status/", {"status": "under_review"})
        self.assertEqual(resp.status_code, 403)

    def test_adopter_cannot_access_other_app(self):
        other = self.create_user(email="other@example.com")
        app = Application.objects.create(adopter=other, pet=self.pet)
        self.authenticate(self.adopter)
        resp = self.client.get(f"/api/applications/{app.id}/")
        self.assertEqual(resp.status_code, 404)
