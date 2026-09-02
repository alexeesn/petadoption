from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.tests import BaseAPITestCase
from apps.pets.models import Pet


class PetTests(BaseAPITestCase):

    def create_pet(self, **kwargs):
        return Pet.objects.create(
            name=kwargs.get("name", "Buddy"),
            species=kwargs.get("species", "dog"),
            breed=kwargs.get("breed", "Labrador"),
            age_months=kwargs.get("age_months", 12),
            gender=kwargs.get("gender", "male"),
            status=kwargs.get("status", "available"),
        )

    def test_public_can_list_pets(self):
        self.create_pet()
        resp = self.client.get("/api/pets/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)

    def test_public_can_view_pet_detail(self):
        pet = self.create_pet()
        resp = self.client.get(f"/api/pets/{pet.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["name"], "Buddy")

    def test_staff_can_create_pet(self):
        staff = self.create_staff()
        self.authenticate(staff)
        resp = self.client.post("/api/pets/", {
            "name": "Luna", "species": "cat", "age_months": 6,
            "gender": "female", "status": "available",
        })
        self.assertEqual(resp.status_code, 201)

    def test_adopter_cannot_create_pet(self):
        adopter = self.create_user()
        self.authenticate(adopter)
        resp = self.client.post("/api/pets/", {
            "name": "Luna", "species": "cat", "age_months": 6,
        })
        self.assertEqual(resp.status_code, 403)

    def test_search_pets(self):
        self.create_pet(name="Buddy")
        self.create_pet(name="Rex")
        resp = self.client.get("/api/pets/?search=Buddy")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)

    def test_filter_by_status(self):
        self.create_pet(name="AvailablePet")
        self.create_pet(name="AdoptedPet", status="adopted")
        resp = self.client.get("/api/pets/?status=available")
        self.assertEqual(resp.data["count"], 1)

    def test_staff_can_update_pet(self):
        pet = self.create_pet()
        staff = self.create_staff()
        self.authenticate(staff)
        resp = self.client.patch(f"/api/pets/{pet.id}/", {"status": "reserved"})
        self.assertEqual(resp.status_code, 200)
        pet.refresh_from_db()
        self.assertEqual(pet.status, "reserved")

    def test_pet_status_change_is_audited(self):
        from apps.audit.models import AuditLog
        pet = self.create_pet()
        staff = self.create_staff()
        self.authenticate(staff)
        resp = self.client.patch(f"/api/pets/{pet.id}/", {"status": "reserved"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            AuditLog.objects.filter(
                action="pet_status_change",
                model_name="Pet",
                object_id=str(pet.id),
                previous_value="available",
                new_value="reserved",
                user=staff,
            ).exists()
        )
