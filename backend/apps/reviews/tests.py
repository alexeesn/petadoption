from django.test import TestCase
from apps.accounts.tests import BaseAPITestCase
from apps.pets.models import Pet
from apps.applications.models import Application
from apps.reviews.models import Review


class ReviewTests(BaseAPITestCase):

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(name="Buddy", species="dog", age_months=12, status="available")
        self.adopter = self.create_user(email="adopter@example.com")
        self.staff = self.create_staff(email="staff1@example.com")
        self.app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="submitted")

    def test_staff_can_approve_application(self):
        self.authenticate(self.staff)
        resp = self.client.post("/api/reviews/", {
            "application": str(self.app.id),
            "decision": "approve",
            "internal_notes": "Looks good",
            "adopter_visible_notes": "Congrats!",
        })
        self.assertEqual(resp.status_code, 201)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, "approved")

    def test_adopter_cannot_create_review(self):
        self.authenticate(self.adopter)
        resp = self.client.post("/api/reviews/", {
            "application": str(self.app.id),
            "decision": "approve",
        })
        self.assertEqual(resp.status_code, 403)

    def test_internal_notes_never_exposed_to_adopter(self):
        review = Review.objects.create(
            application=self.app, reviewer=self.staff, decision="reject",
            internal_notes="SECRET internal note",
            adopter_visible_notes="Application not approved",
        )
        # Adopter accesses their review -> internal_notes must be removed
        self.authenticate(self.adopter)
        resp = self.client.get(f"/api/reviews/{review.id}/")
        if resp.status_code == 403:
            # Staff-only endpoint; verify adopter cannot access at all
            self.assertTrue(True)
        else:
            self.assertNotIn("internal_notes", resp.data)

    def test_review_history_tracking(self):
        self.authenticate(self.staff)
        self.client.post("/api/reviews/", {
            "application": str(self.app.id), "decision": "request_info",
        })
        self.client.post("/api/reviews/", {
            "application": str(self.app.id), "decision": "approve",
        })
        self.assertEqual(Review.objects.filter(application=self.app).count(), 2)
