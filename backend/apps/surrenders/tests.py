import io
import tempfile
from datetime import timedelta

from PIL import Image
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.notifications.models import Notification
from apps.pets.models import Pet
from .models import SurrenderEvent, SurrenderRequest
from .services import today


def photo(name="pet.png", content_type="image/png"):
    out = io.BytesIO()
    Image.new("RGB", (8, 8), "brown").save(out, format="PNG")
    return SimpleUploadedFile(name, out.getvalue(), content_type=content_type)


class SurrenderFlowTests(APITestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory()
        self.addCleanup(self.storage.cleanup)
        override = override_settings(PRIVATE_SURRENDER_ROOT=self.storage.name)
        override.enable()
        self.addCleanup(override.disable)
        self.owner = User.objects.create_user(email="owner@example.test", role="adopter", is_email_verified=True)
        self.other = User.objects.create_user(email="other@example.test", role="adopter", is_email_verified=True)
        self.staff = User.objects.create_user(email="staff@example.test", role="staff", is_email_verified=True)
        self.admin = User.objects.create_user(email="admin@example.test", role="admin", is_email_verified=True)
        self.client.force_authenticate(self.owner)

    def payload(self, **overrides):
        return {"pet_name": "Mochi", "species": "cat", "breed": "Puspin", "age_years": 2, "age_months": 3,
                "gender": "female", "reason": "Moving to a home that does not allow pets.",
                "health_information": "Vaccination history unknown.", "behavior_information": "Shy around dogs.",
                "contact_number": "09123456789", "ownership_confirmed": True, **overrides}

    def create_request(self):
        self.client.force_authenticate(self.owner)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post("/api/surrenders/", {**self.payload(), "photos": [photo()]}, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "submitted")
        self.assertIn("id", response.data)
        return response.data

    def post_action(self, obj, action, data=None):
        return self.client.post(f"/api/surrenders/{obj['id']}/{action}/", data or {}, format="json")

    def schedule(self, obj, date=None):
        self.client.force_authenticate(self.staff)
        return self.post_action(obj, "review", {"status": "intake_scheduled", "note": "Bring vaccination records if available.",
                                "intake_date": str(date or today()), "intake_instructions": "Front desk at the center, 9 AM.",
                                "internal_notes": "Private capacity assessment"})

    def test_full_flow_creates_pet_only_after_handover(self):
        obj = self.create_request()
        self.assertEqual(Pet.objects.count(), 0)
        self.assertTrue(Notification.objects.filter(user=self.owner, notification_type="surrender").exists())
        self.assertTrue(Notification.objects.filter(user=self.staff, notification_type="surrender").exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.schedule(obj).status_code, 200)
        self.assertEqual(Pet.objects.count(), 0)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post_action(obj, "confirm-intake", {"confirmed": True})
        self.assertEqual(response.status_code, 200, response.data)
        pet = Pet.objects.get(pk=response.data["pet"])
        self.assertEqual(pet.status, "for_assessment")
        self.assertEqual(pet.arrival_date, today())
        self.assertEqual(pet.description, "")
        self.assertEqual(pet.images.count(), 0)  # Owner photos stay private.
        self.assertEqual(SurrenderRequest.objects.get(pk=obj["id"]).received_by, self.staff)
        self.assertEqual(self.post_action(obj, "confirm-intake", {"confirmed": True}).status_code, 400)
        self.assertEqual(Pet.objects.count(), 1)
        self.assertTrue(AuditLog.objects.filter(action="pet_intake", object_id=str(pet.pk)).exists())
        self.assertEqual(self.client.delete(f"/api/pets/{pet.pk}/").status_code, 400)
        self.assertTrue(Pet.objects.filter(pk=pet.pk).exists())
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.post_action(obj, "cancel").status_code, 400)

    def test_information_waitlist_reschedule_and_history(self):
        obj = self.create_request()
        self.client.force_authenticate(self.staff)
        response = self.post_action(obj, "review", {"status": "needs_information", "note": "Describe vaccination history.", "internal_notes": "Staff only"})
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(self.owner)
        response = self.post_action(obj, "resubmit", self.payload(health_information="Vaccinated last year."))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "submitted")
        self.assertNotIn("Staff only", str(response.data))
        self.client.force_authenticate(self.staff)
        response = self.post_action(obj, "review", {"status": "waitlisted", "note": "Awaiting a space."})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.schedule(obj).status_code, 200)
        tomorrow = today() + timedelta(days=1)
        self.assertEqual(self.schedule(obj, tomorrow).status_code, 200)
        self.assertEqual(SurrenderEvent.objects.filter(request_id=obj["id"], new_status="intake_scheduled").count(), 2)
        self.assertEqual(self.post_action(obj, "confirm-intake", {"confirmed": True}).status_code, 400)
        self.assertEqual(Pet.objects.count(), 0)

    def test_ownership_staff_permissions_private_photos_and_internal_notes(self):
        obj = self.create_request()
        photo_id = obj["photos"][0]["id"]
        url = f"/api/surrenders/{obj['id']}/photos/{photo_id}/"
        self.assertNotIn("image", obj["photos"][0])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(f"/api/surrenders/{obj['id']}/photos/not-a-uuid/").status_code, 404)
        self.assertEqual(self.post_action(obj, "review", {"status": "declined", "note": "no"}).status_code, 403)
        self.assertEqual(self.post_action(obj, "confirm-intake", {"confirmed": True}).status_code, 403)
        self.assertEqual(self.schedule(obj).status_code, 200)
        self.client.force_authenticate(self.owner)
        for url_to_check in ("/api/surrenders/", f"/api/surrenders/{obj['id']}/"):
            response = self.client.get(url_to_check)
            self.assertNotIn("internal_notes", str(response.data))
            self.assertNotIn("Private capacity", str(response.data))
            self.assertNotIn("owner_email", str(response.data))
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get("/api/surrenders/").data["count"], 0)
        self.assertEqual(self.client.get(f"/api/surrenders/{obj['id']}/").status_code, 404)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.post_action(obj, "cancel").status_code, 404)
        self.assertEqual(self.post_action(obj, "resubmit", self.payload()).status_code, 404)
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(url).status_code, (401, 403))
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_invalid_inputs_do_not_create_requests_or_files(self):
        for invalid in ({"ownership_confirmed": False}, {"age_years": 41}, {"age_months": 12}, {"contact_number": "abc"}, {"reason": ""}):
            response = self.client.post("/api/surrenders/", {**self.payload(**invalid), "photos": [photo()]}, format="multipart")
            self.assertEqual(response.status_code, 400, response.data)
        for invalid_photo in (photo("pet.jpg"), photo(content_type="image/jpeg"), SimpleUploadedFile("pet.png", b"fake", content_type="image/png")):
            response = self.client.post("/api/surrenders/", {**self.payload(), "photos": [invalid_photo]}, format="multipart")
            self.assertEqual(response.status_code, 400, response.data)
        response = self.client.post("/api/surrenders/", self.payload(), format="multipart")
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/surrenders/", {**self.payload(), "photos": [photo() for _ in range(6)]}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(SurrenderRequest.objects.count(), 0)

    def test_closed_requests_and_explicit_confirmation(self):
        obj = self.create_request()
        self.assertEqual(self.post_action(obj, "resubmit", self.payload()).status_code, 400)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.post_action(obj, "confirm-intake", {"confirmed": True}).status_code, 400)
        self.assertEqual(self.schedule(obj).status_code, 200)
        for flag in (False, "true", 1, None):
            self.assertEqual(self.post_action(obj, "confirm-intake", {"confirmed": flag}).status_code, 400)
        self.assertEqual(self.post_action(obj, "confirm-intake", {"confirmed": True, "pet_status": "adopted"}).status_code, 400)
        response = self.post_action(obj, "review", {"status": "declined", "note": "Assessment did not meet intake requirements."})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.schedule(obj).status_code, 400)
        self.assertEqual(Pet.objects.count(), 0)

    def test_cancel_schedule_validation_and_no_generic_updates(self):
        obj = self.create_request()
        self.assertEqual(self.schedule(obj, today() - timedelta(days=1)).status_code, 400)
        self.assertEqual(self.post_action(obj, "review", {"status": "declined", "note": " "}).status_code, 400)
        self.assertEqual(self.post_action(obj, "review", {"status": "intake_scheduled", "note": "Visit us"}).status_code, 400)
        self.assertEqual(self.client.patch(f"/api/surrenders/{obj['id']}/", {"status": "received"}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(f"/api/surrenders/{obj['id']}/").status_code, 405)
        self.assertEqual(self.post_action(obj, "cancel").status_code, 403)  # Staff cannot impersonate owner.
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.post_action(obj, "cancel").status_code, 200)
        self.assertEqual(self.post_action(obj, "cancel").status_code, 400)
        self.assertEqual(Pet.objects.count(), 0)

    def test_verified_accounts_only_and_owner_cannot_supply_system_fields(self):
        self.owner.is_email_verified = False
        self.owner.save()
        self.assertEqual(self.client.get("/api/surrenders/").status_code, 403)
        self.owner.is_email_verified = True
        self.owner.save()
        response = self.client.post("/api/surrenders/", {**self.payload(), "owner": str(self.other.pk), "status": "received", "photos": [photo()]}, format="multipart")
        self.assertEqual(response.status_code, 201)
        obj = SurrenderRequest.objects.get()
        self.assertEqual(obj.owner, self.owner)
        self.assertEqual(obj.status, "submitted")
        self.assertIsNone(obj.pet_id)

    def test_missing_consent_and_oversize_photo_are_validation_errors(self):
        payload = self.payload()
        del payload["ownership_confirmed"]
        response = self.client.post("/api/surrenders/", {**payload, "photos": [photo()]}, format="multipart")
        self.assertEqual(response.status_code, 400)
        large = photo()
        padded = SimpleUploadedFile("pet.png", large.read() + b"0" * (5 * 1024 * 1024), content_type="image/png")
        response = self.client.post("/api/surrenders/", {**self.payload(), "photos": [padded]}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(SurrenderRequest.objects.count(), 0)

    def test_resubmission_can_add_validated_photos_and_keeps_originals(self):
        obj = self.create_request()
        self.client.force_authenticate(self.staff)
        self.post_action(obj, "review", {"status": "needs_information", "note": "Add a clearer photo."})
        self.client.force_authenticate(self.owner)
        response = self.client.post(f"/api/surrenders/{obj['id']}/resubmit/", {**self.payload(), "photos": [photo()]}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["photos"]), 2)
        self.assertIn(obj["photos"][0], response.data["photos"])

    def test_admin_can_review_but_staff_cannot_create_owner_requests(self):
        obj = self.create_request()
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post("/api/surrenders/", self.payload(), format="json").status_code, 403)
        self.client.force_authenticate(self.admin)
        response = self.post_action(obj, "review", {"status": "declined", "note": "The center is unable to accept this request."})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "declined")

    def test_html_emails_have_request_link_schedule_and_no_private_notes(self):
        obj = self.create_request()
        email = mail.outbox[-1]
        html, mime = email.alternatives[0]
        self.assertEqual(mime, 'text/html')
        self.assertIn('Your request is with our team.', html)
        self.assertIn('Surrender request reference', html)
        self.assertIn(f'/surrenders/{obj["id"]}', html)
        self.assertIn('Track your request:', email.body)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.schedule(obj)
        self.assertEqual(response.status_code, 200)
        html = mail.outbox[-1].alternatives[0][0]
        self.assertIn('Your intake visit is scheduled.', html)
        self.assertIn('Front desk at the center, 9 AM.', html)
        self.assertIn('Bring vaccination records if available.', html)
        self.assertNotIn('Private capacity assessment', html)
        self.assertNotIn('Private capacity assessment', mail.outbox[-1].body)

    def test_render_failure_keeps_plain_text_delivery(self):
        from unittest.mock import patch
        with patch('apps.surrenders.emails.render_to_string', side_effect=RuntimeError('Template unavailable')):
            with self.assertLogs('apps.surrenders.emails', level='ERROR'):
                self.create_request()
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(mail.outbox[0].alternatives)
        self.assertIn('Your request for Mochi is pending review.', mail.outbox[0].body)

    def test_html_escapes_user_supplied_pet_name(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/surrenders/', {
                **self.payload(pet_name='Mochi <script>unsafe()</script>'), 'photos': [photo()],
            }, format='multipart')
        self.assertEqual(response.status_code, 201)
        html = mail.outbox[-1].alternatives[0][0]
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)
