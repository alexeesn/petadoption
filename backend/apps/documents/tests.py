import io
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from apps.accounts.tests import BaseAPITestCase
from apps.pets.models import Pet
from apps.applications.models import Application
from apps.documents.models import Document


class DocumentTests(BaseAPITestCase):

    def setUp(self):
        super().setUp()
        self.adopter = self.create_user(email="adopter@example.com")
        self.other_adopter = self.create_user(email="other@example.com")
        self.staff = self.create_staff(email="staff1@example.com")
        self.pet = Pet.objects.create(name="Buddy", species="dog", age_months=12, status="available")
        self.app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="submitted")

    def make_pdf(self, name="doc.pdf", content=b"%PDF-1.4 test"):
        return SimpleUploadedFile(
            name, content, content_type="application/pdf"
        )

    def test_adopter_can_upload_document(self):
        self.authenticate(self.adopter)
        resp = self.client.post("/api/documents/", {
            "application": str(self.app.id),
            "document_type": "identification",
            "file": self.make_pdf(),
        }, format="multipart")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Document.objects.count(), 1)

    def test_adopter_cannot_upload_to_other_application(self):
        # Use a different pet for the other adopter's application to avoid the
        # one-active-application-per-pet constraint.
        other_pet = Pet.objects.create(name="Rex", species="dog", age_months=24, status="available")
        other_app = Application.objects.create(
            adopter=self.other_adopter, pet=other_pet, status="submitted"
        )
        self.authenticate(self.adopter)
        resp = self.client.post("/api/documents/", {
            "application": str(other_app.id),
            "document_type": "identification",
            "file": self.make_pdf(),
        }, format="multipart")
        self.assertEqual(resp.status_code, 403)

    def test_staff_can_upload_document_to_any_application(self):
        self.authenticate(self.staff)
        resp = self.client.post("/api/documents/", {
            "application": str(self.app.id),
            "document_type": "vet_reference",
            "file": self.make_pdf(),
        }, format="multipart")
        self.assertEqual(resp.status_code, 201)

    def test_rejects_invalid_extension(self):
        self.authenticate(self.adopter)
        resp = self.client.post("/api/documents/", {
            "application": str(self.app.id),
            "document_type": "other",
            "file": SimpleUploadedFile("malware.exe", b"MZ", content_type="application/x-msdownload"),
        }, format="multipart")
        self.assertEqual(resp.status_code, 400)

    def test_rejects_file_size_over_limit(self):
        self.authenticate(self.adopter)
        big = io.BytesIO(b"x" * (10 * 1024 * 1024 + 1))
        big_file = SimpleUploadedFile(
            "big.pdf", big.getvalue(), content_type="application/pdf"
        )
        resp = self.client.post("/api/documents/", {
            "application": str(self.app.id),
            "document_type": "other",
            "file": big_file,
        }, format="multipart")
        self.assertEqual(resp.status_code, 400)

    def test_adopter_can_download_own_document(self):
        self.authenticate(self.adopter)
        created = self.client.post("/api/documents/", {
            "application": str(self.app.id),
            "document_type": "identification",
            "file": self.make_pdf(),
        }, format="multipart")
        doc_id = created.data["id"]
        resp = self.client.get(f"/api/documents/{doc_id}/download/")
        self.assertEqual(resp.status_code, 200)

    def test_other_adopter_cannot_download_document(self):
        self.authenticate(self.adopter)
        created = self.client.post("/api/documents/", {
            "application": str(self.app.id),
            "document_type": "identification",
            "file": self.make_pdf(),
        }, format="multipart")
        doc_id = created.data["id"]
        self.authenticate(self.other_adopter)
        resp = self.client.get(f"/api/documents/{doc_id}/download/")
        self.assertEqual(resp.status_code, 403)

    def test_owning_adopter_can_delete_document(self):
        self.authenticate(self.adopter)
        created = self.client.post("/api/documents/", {
            "application": str(self.app.id),
            "document_type": "identification",
            "file": self.make_pdf(),
        }, format="multipart")
        doc_id = created.data["id"]
        resp = self.client.delete(f"/api/documents/{doc_id}/")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(Document.objects.count(), 0)

    def test_non_owning_adopter_cannot_delete_document(self):
        self.authenticate(self.adopter)
        created = self.client.post("/api/documents/", {
            "application": str(self.app.id),
            "document_type": "identification",
            "file": self.make_pdf(),
        }, format="multipart")
        doc_id = created.data["id"]
        self.authenticate(self.other_adopter)
        resp = self.client.delete(f"/api/documents/{doc_id}/")
        # The owning adopter's documents are not visible to others (filtered
        # queryset), so a non-owner gets a 404 rather than the object.
        self.assertEqual(resp.status_code, 404)