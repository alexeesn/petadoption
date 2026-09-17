from django.test import TestCase
from django.urls import reverse
from apps.accounts.tests import BaseAPITestCase
from apps.notifications.models import Notification, create_notification
from apps.pets.models import Pet
from apps.applications.models import Application
from apps.adoptions.models import AdoptionRecord


class NotificationTests(BaseAPITestCase):

    def setUp(self):
        super().setUp()
        self.adopter = self.create_user(email="adopter@example.com")
        self.staff = self.create_staff(email="staff1@example.com")
        self.pet = Pet.objects.create(name="Buddy", species="dog", age_months=12, status="available")

    def test_create_notification_helper(self):
        create_notification(
            user=self.adopter,
            title="Hello",
            message="World",
            notification_type="general",
            link="/dashboard",
        )
        notif = Notification.objects.get(user=self.adopter)
        self.assertEqual(notif.title, "Hello")
        self.assertEqual(notif.message, "World")
        self.assertEqual(notif.notification_type, "general")
        self.assertEqual(notif.link, "/dashboard")
        self.assertFalse(notif.is_read)

    def test_list_own_notifications_only(self):
        create_notification(user=self.adopter, title="A", message="1")
        create_notification(user=self.staff, title="B", message="2")
        self.authenticate(self.adopter)
        resp = self.client.get("/api/notifications/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["title"], "A")

    def test_unread_count(self):
        create_notification(user=self.adopter, title="A", message="1")
        create_notification(user=self.adopter, title="B", message="2", notification_type="x")
        Notification.objects.filter(user=self.adopter, title="B").update(is_read=True)
        self.authenticate(self.adopter)
        resp = self.client.get("/api/notifications/unread-count/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["unread_count"], 1)

    def test_mark_as_read(self):
        create_notification(user=self.adopter, title="A", message="1")
        notif = Notification.objects.get(user=self.adopter, title="A")
        self.authenticate(self.adopter)
        resp = self.client.patch(
            f"/api/notifications/{notif.id}/read/", {}, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_mark_all_as_read(self):
        create_notification(user=self.adopter, title="A", message="1")
        create_notification(user=self.adopter, title="B", message="2")
        self.authenticate(self.adopter)
        resp = self.client.post("/api/notifications/mark-all-read/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Notification.objects.filter(user=self.adopter, is_read=False).count(), 0)

    def test_unread_filter(self):
        create_notification(user=self.adopter, title="A", message="1")
        create_notification(user=self.adopter, title="B", message="2")
        Notification.objects.filter(user=self.adopter, title="B").update(is_read=True)
        self.authenticate(self.adopter)
        resp = self.client.get("/api/notifications/?unread=true")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["title"], "A")

    def test_cannot_read_other_user_notification(self):
        create_notification(user=self.staff, title="A", message="1")
        notif = Notification.objects.get(user=self.staff)
        self.authenticate(self.adopter)
        resp = self.client.get(f"/api/notifications/{notif.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_application_submission_creates_notifications(self):
        """Submitting an application should notify the adopter and staff."""
        self.authenticate(self.adopter)
        from django.core.files.uploadedfile import SimpleUploadedFile
        resp = self.client.post("/api/applications/", {
            "pet": str(self.pet.id),
            "why_adopt": "I love pets",
            "experience_with_pets": "Some",
            "living_situation": "House",
            "has_other_pets": False,
            # Required documents are part of the submission itself.
            "documents": [
                SimpleUploadedFile("id.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
                SimpleUploadedFile("address.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
            ],
            "document_types": ["identification", "proof_of_address"],
        }, format="multipart")
        self.assertEqual(resp.status_code, 201)
        # Adopter got an "Application Submitted" notification
        self.assertTrue(Notification.objects.filter(user=self.adopter, title="Application Submitted").exists())
        # Staff got a "New Application Received" notification
        self.assertTrue(Notification.objects.filter(user=self.staff, title="New Application Received").exists())

    def test_approval_creates_adopter_notification(self):
        # Approval of a submitted application goes through the review flow,
        # which moves the application submitted -> under_review -> approved.
        app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="submitted")
        self.authenticate(self.staff)
        resp = self.client.post("/api/reviews/", {
            "application": str(app.id),
            "decision": "approve",
            "internal_notes": "Great fit",
            "adopter_visible_notes": "Welcome!",
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(
            Notification.objects.filter(user=self.adopter, title="Application Approved").exists()
        )

    def test_adoption_completion_creates_notification(self):
        app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="approved")
        adoption = AdoptionRecord.objects.create(
            application=app, pet=self.pet, adopter=self.adopter,
            staff_member=self.staff, status="scheduled",
        )
        self.authenticate(self.staff)
        resp = self.client.patch(f"/api/adoptions/{adoption.id}/", {"status": "completed"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            Notification.objects.filter(user=self.adopter, title="Adoption Completed").exists()
        )