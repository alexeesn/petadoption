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
