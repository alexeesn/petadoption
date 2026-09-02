from django.test import TestCase
from apps.accounts.tests import BaseAPITestCase
from apps.audit.models import AuditLog
from apps.pets.models import Pet
from apps.applications.models import Application


class AuditTests(BaseAPITestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email="admin@example.com")
        self.staff = self.create_staff(email="staff1@example.com")
        self.adopter = self.create_user(email="adopter@example.com")
        self.pet = Pet.objects.create(name="Buddy", species="dog", age_months=12, status="available")
        self.app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="submitted")

    def test_admin_can_list_audit_logs(self):
        AuditLog.objects.create(
            user=self.staff, action="test", model_name="Application",
            object_id=str(self.app.id), previous_value="a", new_value="b",
        )
        self.authenticate(self.admin)
        resp = self.client.get("/api/audit/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["action"], "test")
        self.assertEqual(resp.data["results"][0]["user_email"], "staff1@example.com")

    def test_staff_cannot_list_audit_logs(self):
        AuditLog.objects.create(
            user=self.staff, action="test", model_name="Application",
            object_id=str(self.app.id), previous_value="a", new_value="b",
        )
        self.authenticate(self.staff)
        resp = self.client.get("/api/audit/")
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_cannot_list_audit_logs(self):
        resp = self.client.get("/api/audit/")
        self.assertEqual(resp.status_code, 403)

    def test_filter_by_model_name(self):
        AuditLog.objects.create(user=self.admin, action="x", model_name="Application", object_id="1")
        AuditLog.objects.create(user=self.admin, action="y", model_name="Pet", object_id="2")
        self.authenticate(self.admin)
        resp = self.client.get("/api/audit/?model_name=Pet")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["model_name"], "Pet")

    def test_application_status_change_logged(self):
        """Changing an application status should write an audit log."""
        self.authenticate(self.staff)
        resp = self.client.post(
            f"/api/applications/{self.app.id}/update-status/",
            {"status": "under_review"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            AuditLog.objects.filter(
                action="status_change", model_name="Application",
                object_id=str(self.app.id), new_value="under_review",
            ).exists()
        )

    def test_review_decision_logged(self):
        """Creating a review should write an audit log."""
        self.authenticate(self.staff)
        resp = self.client.post("/api/reviews/", {
            "application": str(self.app.id),
            "decision": "approve",
            "internal_notes": "Looks good",
            "adopter_visible_notes": "Approved!",
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(
            AuditLog.objects.filter(
                action="review_decision", model_name="Review", new_value="approve"
            ).exists()
        )