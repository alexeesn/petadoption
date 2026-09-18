import base64

from django.core.files.uploadedfile import SimpleUploadedFile
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


# A valid 1x1 PNG so DRF's ImageField (Pillow) accepts the upload.
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


class PetImageUploadTests(BaseAPITestCase):
    """Regression tests: a pet can be created with 1, 2, 3+ images via the
    real HTTP endpoint and ALL uploaded images must be saved for that pet."""

    def setUp(self):
        super().setUp()
        self.authenticate(self.create_staff())

    def upload(self, count):
        files = [
            SimpleUploadedFile(f"pet{i + 1}.png", PNG_1X1, content_type="image/png")
            for i in range(count)
        ]
        return self.client.post(
            "/api/pets/",
            {
                "name": "Luna", "species": "cat", "age_months": 6,
                "gender": "female", "images": files,
            },
            format="multipart",
        )

    def assert_image_count(self, count):
        resp = self.upload(count)
        self.assertEqual(resp.status_code, 201, resp.data)
        pet_id = resp.data["id"]
        self.assertEqual(resp.data["status"], "available")
        self.assertEqual(len(resp.data["images"]), count)
        pet = Pet.objects.get(pk=pet_id)
        self.assertEqual(pet.images.count(), count)
        # All images belong to the same pet and only the first is primary.
        for i, img in enumerate(pet.images.order_by("created_at")):
            self.assertEqual(str(img.pet_id), str(pet_id))
            self.assertEqual(img.is_primary, i == 0)
        return resp

    def test_create_pet_with_one_image(self):
        self.assert_image_count(1)

    def test_create_pet_with_two_images(self):
        resp = self.assert_image_count(2)
        names = {img["image"].split("/")[-1].split("_")[0] for img in resp.data["images"]}
        self.assertEqual(names, {"pet1", "pet2"})

    def test_create_pet_with_three_images(self):
        resp = self.assert_image_count(3)
        names = {img["image"].split("/")[-1].split("_")[0] for img in resp.data["images"]}
        self.assertEqual(names, {"pet1", "pet2", "pet3"})

    def test_public_pet_detail_returns_all_images(self):
        """Regression: the adopter-facing pet detail endpoint must return
        EVERY PetImage record for the pet, so the Adopter Portal can display
        all photos (not only the primary one)."""
        resp = self.upload(3)
        self.assertEqual(resp.status_code, 201, resp.data)
        pet_id = resp.data["id"]
        # Public (unauthenticated) request, exactly as the Adopter Portal calls it.
        self.unauthenticate()
        detail = self.client.get(f"/api/pets/{pet_id}/")
        self.assertEqual(detail.status_code, 200)
        images = detail.data["images"]
        self.assertEqual(len(images), 3)
        # All three uploaded files must be present, each with its own URL.
        urls = [img["image"] for img in images]
        self.assertEqual(len(set(urls)), 3)
        for i in range(1, 4):
            self.assertTrue(any(f"pet{i}" in url for url in urls), f"pet{i} image missing from {urls}")
        # Primary image comes first so the portal's initial gallery frame is the primary photo.
        self.assertTrue(images[0]["is_primary"])

