from django.test import TestCase
from apps.accounts.tests import BaseAPITestCase
from apps.pets.models import Pet
from apps.applications.models import Application
from apps.adoptions.models import AdoptionRecord


class AdoptionBusinessRuleTests(BaseAPITestCase):

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(name="Buddy", species="dog", age_months=12, status="available")
        self.adopter = self.create_user(email="adopter@example.com")
        self.staff = self.create_staff(email="staff1@example.com")
        self.app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="approved")

    def authenticate_staff(self):
        self.authenticate(self.staff)

    def test_cannot_create_adoption_from_unapproved_application(self):
        # Use a different pet so this second application does not violate the
        # "one active application per adopter+pet" constraint.
        other_pet = Pet.objects.create(name="Rex", species="dog", age_months=24, status="available")
        unapproved_app = Application.objects.create(
            adopter=self.adopter, pet=other_pet, status="submitted"
        )
        self.authenticate_staff()
        resp = self.client.post("/api/adoptions/", {"application_id": str(unapproved_app.id)})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(AdoptionRecord.objects.count(), 0)

    def test_can_create_adoption_from_approved_application(self):
        self.authenticate_staff()
        resp = self.client.post("/api/adoptions/", {"application_id": str(self.app.id)})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(AdoptionRecord.objects.count(), 1)

    def test_completing_adoption_sets_pet_adopted(self):
        adoption = AdoptionRecord.objects.create(
            application=self.app, pet=self.pet, adopter=self.adopter,
            staff_member=self.staff, status="scheduled",
        )
        self.authenticate_staff()
        resp = self.client.patch(f"/api/adoptions/{adoption.id}/", {"status": "completed"})
        self.assertEqual(resp.status_code, 200)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "adopted")

    def test_invalid_adoption_status_transition(self):
        adoption = AdoptionRecord.objects.create(
            application=self.app, pet=self.pet, adopter=self.adopter,
            staff_member=self.staff, status="completed",
        )
        self.authenticate_staff()
        # completed -> scheduled is invalid
        resp = self.client.patch(f"/api/adoptions/{adoption.id}/", {"status": "scheduled"})
        self.assertEqual(resp.status_code, 400)

    def test_adopter_cannot_create_adoption(self):
        # staff only
        self.authenticate(self.adopter)
        resp = self.client.post("/api/adoptions/", {"application_id": str(self.app.id)})
        self.assertEqual(resp.status_code, 403)

    def test_scheduled_to_cancelled_reverts_pet_to_available(self):
        # Pet is pending because the application was approved; cancellation
        # must put it back to available.
        self.pet.status = "pending"
        self.pet.save(update_fields=["status"])
        self.authenticate_staff()
        resp = self.client.post("/api/adoptions/", {"application_id": str(self.app.id)})
        self.assertEqual(resp.status_code, 201)
        adoption_id = resp.data["id"]
        resp = self.client.patch(f"/api/adoptions/{adoption_id}/", {"status": "cancelled"})
        self.assertEqual(resp.status_code, 200)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "available")

    def test_completed_to_returned_reverts_pet_and_allows_reapply(self):
        # scheduled -> completed (pet adopted) -> returned (pet available),
        # then a NEW adopter can apply for the returned pet.
        self.pet.status = "pending"
        self.pet.save(update_fields=["status"])
        self.authenticate_staff()
        resp = self.client.post("/api/adoptions/", {"application_id": str(self.app.id)})
        self.assertEqual(resp.status_code, 201)
        adoption_id = resp.data["id"]
        resp = self.client.patch(f"/api/adoptions/{adoption_id}/", {"status": "completed"})
        self.assertEqual(resp.status_code, 200)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "adopted")
        resp = self.client.patch(f"/api/adoptions/{adoption_id}/", {
            "status": "returned", "return_reason": "Allergies",
        })
        self.assertEqual(resp.status_code, 200)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, "available")
        # New adopter can submit an application for the returned pet.
        new_adopter = self.create_user(email="newadopter@example.com")
        self.authenticate(new_adopter)
        # Applications are submitted together with their required documents.
        from django.core.files.uploadedfile import SimpleUploadedFile
        resp = self.client.post("/api/applications/", {
            "pet": str(self.pet.id), "why_adopt": "New family",
            "documents": [
                SimpleUploadedFile("id.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
                SimpleUploadedFile("address.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
            ],
            "document_types": ["identification", "proof_of_address"],
        }, format="multipart")
        self.assertEqual(resp.status_code, 201)
