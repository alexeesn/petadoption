from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from apps.accounts.tests import BaseAPITestCase
from apps.pets.models import Pet
from apps.applications.models import Application
from apps.documents.models import Document


class ApplicationTests(BaseAPITestCase):

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(name="Buddy", species="dog", age_months=12, status="available")
        self.adopter = self.create_user(email="adopter1@example.com")
        self.staff = self.create_staff(email="staff1@example.com")

    def create_application(self, user=None, status="submitted"):
        # Application.save() auto-advances draft → submitted on creation
        # (see models.py).  Tests that need a specific status (e.g. "draft")
        # must bypass save() via .update(), which is a standard test pattern.
        app = Application.objects.create(
            adopter=user or self.adopter,
            pet=self.pet,
            status=status,
        )
        if status == "draft":
            # save() already advanced to "submitted"; force back to draft
            # without re-triggering the auto-advance in save().
            Application.objects.filter(pk=app.pk).update(status="draft")
            app.refresh_from_db()
        return app

    def required_documents(self):
        """The documents an adopter must upload with the application itself."""
        return {
            "documents": [self.make_pdf("id.pdf"), self.make_pdf("address.pdf")],
            "document_types": ["identification", "proof_of_address"],
        }

    def submit_application(self, pet=None, **fields):
        """POST a complete application (fields + required documents)."""
        payload = {"pet": str((pet or self.pet).id), **fields}
        payload.update(self.required_documents())
        return self.client.post("/api/applications/", payload, format="multipart")

    def test_adopter_can_create_application(self):
        self.authenticate(self.adopter)
        resp = self.submit_application(why_adopt="I love dogs")
        self.assertEqual(resp.status_code, 201)

    def test_create_application_leaves_draft_and_becomes_submitted(self):
        # Regression for QA-REPORT-2026-09-09.md section 2: a normal
        # submission must not remain stuck in "draft" with no way for the
        # adopter to advance it. Hit the real endpoint, not the model layer.
        self.authenticate(self.adopter)
        resp = self.submit_application(why_adopt="I love dogs")
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
        resp = self.submit_application(why_adopt="I love dogs")
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
        resp = self.submit_application(why_adopt="again")
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

    def make_pdf(self, name="doc.pdf", content=b"%PDF-1.4 test"):
        return SimpleUploadedFile(name, content, content_type="application/pdf")

    def test_under_review_to_rejected_shows_reason_and_allows_reapply(self):
        # Regression from live walkthrough (QA report branch test):
        # under_review -> rejected with a rejection_reason, the adopter sees
        # the reason, and rejected is a terminal (non-active) state so the
        # adopter CAN re-apply for the same pet.
        app = self.create_application(status="submitted")
        self.authenticate(self.staff)
        resp = self.client.post(f"/api/applications/{app.id}/update-status/", {"status": "under_review"})
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(f"/api/applications/{app.id}/update-status/", {
            "status": "rejected",
            "rejection_reason": "Fencing requirement not met",
        })
        self.assertEqual(resp.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, "rejected")
        # Adopter can see the rejection reason via the real endpoint.
        self.authenticate(self.adopter)
        resp = self.client.get(f"/api/applications/{app.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "rejected")
        self.assertEqual(resp.data["rejection_reason"], "Fencing requirement not met")
        # Re-application for the same pet is allowed (rejected is not active).
        resp = self.submit_application(why_adopt="Fence fixed")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["status"], "submitted")

    def test_pending_documents_round_trip_with_upload(self):
        # under_review -> pending_documents -> (real upload) -> under_review
        app = self.create_application(status="submitted")
        self.authenticate(self.staff)
        self.client.post(f"/api/applications/{app.id}/update-status/", {"status": "under_review"})
        resp = self.client.post(f"/api/applications/{app.id}/update-status/", {"status": "pending_documents"})
        self.assertEqual(resp.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, "pending_documents")
        # Adopter uploads a real document through the documents endpoint.
        self.authenticate(self.adopter)
        resp = self.client.post("/api/documents/", {
            "application": str(app.id),
            "document_type": "vet_reference",
            "file": self.make_pdf(),
        }, format="multipart")
        self.assertEqual(resp.status_code, 201)
        doc_id = resp.data["id"]
        self.assertEqual(Document.objects.filter(application=app).count(), 1)
        # Staff can see the uploaded document.
        self.authenticate(self.staff)
        resp = self.client.get(f"/api/documents/?application_id={app.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        # Owning adopter can download it.
        self.authenticate(self.adopter)
        resp = self.client.get(f"/api/documents/{doc_id}/download/")
        self.assertEqual(resp.status_code, 200)
        # Staff moves the application back under review once documents arrived.
        self.authenticate(self.staff)
        resp = self.client.post(f"/api/applications/{app.id}/update-status/", {"status": "under_review"})
        self.assertEqual(resp.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, "under_review")

    def test_additional_info_round_trip(self):
        # under_review -> additional_info_requested -> under_review
        app = self.create_application(status="submitted")
        self.authenticate(self.staff)
        self.client.post(f"/api/applications/{app.id}/update-status/", {"status": "under_review"})
        resp = self.client.post(f"/api/applications/{app.id}/update-status/", {"status": "additional_info_requested"})
        self.assertEqual(resp.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, "additional_info_requested")
        resp = self.client.post(f"/api/applications/{app.id}/update-status/", {"status": "under_review"})
        self.assertEqual(resp.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, "under_review")

    def test_adopter_can_cancel_submitted_application(self):
        app = self.create_application(status="submitted")
        self.authenticate(self.adopter)
        resp = self.client.post(f"/api/applications/{app.id}/cancel/")
        self.assertEqual(resp.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, "cancelled")

    def test_adopter_can_cancel_draft_application(self):
        app = self.create_application(status="draft")
        self.authenticate(self.adopter)
        resp = self.client.post(f"/api/applications/{app.id}/cancel/")
        self.assertEqual(resp.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, "cancelled")

    # ------------------------------------------------------------------
    # Regression tests for docs/QA-REPORT-2026-09-09.md section 2 and
    # the staff-portal ApplicationDetailPage missing "draft" entry.
    # ------------------------------------------------------------------

    def test_staff_can_move_draft_to_submitted_via_api(self):
        """Staff must be able to manually advance a stuck draft application to
        'submitted' through the update-status API endpoint.  This is the
        backend counterpart to the UI fix in ApplicationDetailPage.tsx
        (adding 'draft' to VALID_STATUS_TRANSITIONS)."""
        app = self.create_application(status="draft")
        self.authenticate(self.staff)
        resp = self.client.post(
            f"/api/applications/{app.id}/update-status/",
            {"status": "submitted"},
        )
        self.assertEqual(resp.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, "submitted")

    def test_staff_can_cancel_draft_application(self):
        """Staff can also cancel a stuck draft application (draft -> cancelled)."""
        app = self.create_application(status="draft")
        self.authenticate(self.staff)
        resp = self.client.post(
            f"/api/applications/{app.id}/update-status/",
            {"status": "cancelled"},
        )
        self.assertEqual(resp.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, "cancelled")

    def test_model_save_auto_advances_draft_to_submitted(self):
        """Direct ORM creation (non-API path) must also auto-advance
        draft -> submitted and create an AuditLog entry, preventing new
        stuck drafts through shell, admin, or management commands."""
        app = Application.objects.create(
            adopter=self.adopter, pet=self.pet
        )
        self.assertEqual(app.status, "submitted")
        from apps.audit.models import AuditLog
        self.assertTrue(
            AuditLog.objects.filter(
                model_name="Application",
                object_id=str(app.id),
                previous_value="draft",
                new_value="submitted",
            ).exists()
        )

    # ------------------------------------------------------------------
    # Documents are part of the application submission itself: they must be
    # validated before submission and stored with the application.
    # ------------------------------------------------------------------

    def test_submitted_application_has_its_documents_attached(self):
        self.authenticate(self.adopter)
        resp = self.submit_application(why_adopt="I love dogs")
        self.assertEqual(resp.status_code, 201)
        app = Application.objects.get(pk=resp.data["id"])
        self.assertEqual(app.status, "submitted")
        self.assertEqual(Document.objects.filter(application=app).count(), 2)
        types = set(Document.objects.filter(application=app).values_list("document_type", flat=True))
        self.assertEqual(types, {"identification", "proof_of_address"})
        # The create response already carries the documents.
        self.assertEqual(len(resp.data["documents"]), 2)

    def test_application_rejected_when_required_documents_missing(self):
        self.authenticate(self.adopter)
        resp = self.client.post("/api/applications/", {
            "pet": str(self.pet.id),
            "why_adopt": "I love dogs",
        }, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("documents", resp.data)
        self.assertEqual(Application.objects.filter(adopter=self.adopter).count(), 0)

    def test_application_rejected_when_one_required_document_missing(self):
        self.authenticate(self.adopter)
        resp = self.client.post("/api/applications/", {
            "pet": str(self.pet.id),
            "why_adopt": "I love dogs",
            "documents": [self.make_pdf("id.pdf")],
            "document_types": ["identification"],
        }, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("proof_of_address", resp.data["documents"])
        self.assertEqual(Application.objects.filter(adopter=self.adopter).count(), 0)

    def test_invalid_document_blocks_submission_and_rolls_back(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.authenticate(self.adopter)
        resp = self.client.post("/api/applications/", {
            "pet": str(self.pet.id),
            "why_adopt": "I love dogs",
            "documents": [
                self.make_pdf("id.pdf"),
                SimpleUploadedFile("proof.exe", b"MZ", content_type="application/x-msdownload"),
            ],
            "document_types": ["identification", "proof_of_address"],
        }, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("proof_of_address", resp.data["documents"])
        self.assertEqual(Application.objects.filter(adopter=self.adopter).count(), 0)
        self.assertEqual(Document.objects.count(), 0)

    def test_optional_extra_document_is_accepted(self):
        self.authenticate(self.adopter)
        resp = self.client.post("/api/applications/", {
            "pet": str(self.pet.id),
            "why_adopt": "I love dogs",
            "documents": [
                self.make_pdf("id.pdf"),
                self.make_pdf("address.pdf"),
                self.make_pdf("vet.pdf"),
            ],
            "document_types": ["identification", "proof_of_address", "vet_reference"],
        }, format="multipart")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data["documents"]), 3)

    def test_staff_retrieves_application_with_documents(self):
        self.authenticate(self.adopter)
        created = self.submit_application(why_adopt="I love dogs")
        self.assertEqual(created.status_code, 201)
        self.authenticate(self.staff)
        resp = self.client.get(f"/api/applications/{created.data['id']}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["documents"]), 2)
        self.assertTrue(all(d["download_url"] for d in resp.data["documents"]))
