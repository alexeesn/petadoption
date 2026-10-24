from apps.accounts.tests import BaseAPITestCase
from .models import Pet


class SupportedPetSpeciesTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.authenticate(self.create_staff(email="pet-species@example.test"))

    def test_removed_species_cannot_be_created_in_json_or_multipart(self):
        for species in ("bird", "rabbit"):
            for payload_format in ("json", "multipart"):
                with self.subTest(species=species, payload_format=payload_format):
                    response = self.client.post("/api/pets/", {
                        "name": "Unsupported pet", "species": species,
                    }, format=payload_format)
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertIn("species", response.data)
                    self.assertFalse(Pet.objects.exists())

    def test_removed_species_cannot_be_assigned_by_put_or_patch(self):
        pet = Pet.objects.create(name="Existing dog", species="dog")
        before = Pet.objects.values().get(pk=pet.pk)
        for method in (self.client.put, self.client.patch):
            for species in ("bird", "rabbit"):
                with self.subTest(method=method.__name__, species=species):
                    response = method(f"/api/pets/{pet.pk}/", {
                        "name": "Must not save", "species": species,
                    }, format="json")
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertIn("species", response.data)
                    self.assertEqual(Pet.objects.values().get(pk=pet.pk), before)

    def test_dog_cat_and_other_remain_available(self):
        for species in ("dog", "cat", "other"):
            with self.subTest(species=species):
                response = self.client.post("/api/pets/", {
                    "name": "Supported pet", "species": species,
                }, format="json")
                self.assertEqual(response.status_code, 201, response.data)
                self.assertEqual(response.data["species"], species)
