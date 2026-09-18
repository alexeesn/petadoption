import base64

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from apps.accounts.tests import BaseAPITestCase
from apps.pets.models import Pet


class PetTests(BaseAPITestCase):

    def create_pet(self, **kwargs):
        return Pet.objects.create(
            name=kwargs.get("name", "Buddy"),
            species=kwargs.get("species", "dog"),
            breed=kwargs.get("breed", "Labrador"),
            age_years=kwargs.get("age_years", 1),
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
            "name": "Luna", "species": "cat", "age_years": 1,
            "gender": "female", "status": "available",
            "arrival_date": "2026-02-01",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["age_years"], 1)
        self.assertEqual(resp.data["arrival_date"], "2026-02-01")

    def test_age_years_is_validated(self):
        self.authenticate(self.create_staff())
        too_old = self.client.post("/api/pets/", {
            "name": "Luna", "species": "cat", "age_years": 41,
        })
        self.assertEqual(too_old.status_code, 400)
        self.assertIn("age_years", too_old.data)
        negative = self.client.post("/api/pets/", {
            "name": "Luna", "species": "cat", "age_years": -1,
        })
        self.assertEqual(negative.status_code, 400)
        self.assertIn("age_years", negative.data)

    def test_adopter_cannot_create_pet(self):
        adopter = self.create_user()
        self.authenticate(adopter)
        resp = self.client.post("/api/pets/", {
            "name": "Luna", "species": "cat", "age_years": 1,
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
                "name": "Luna", "species": "cat", "age_years": 1,
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


def png(name):
    return SimpleUploadedFile(name, PNG_1X1, content_type="image/png")


class PetEditPhotoTests(BaseAPITestCase):
    """Regression tests for the Staff Portal "Edit Pet" photo behavior.

    Every test uses the real HTTP endpoints the portal calls, not the model
    layer directly:
      * PATCH  /api/pets/{id}/                    -> pet information
      * POST   /api/pets/{id}/images/             -> add one new photo
      * DELETE /api/pets/{id}/images/{image_id}/  -> remove one existing photo
    """

    def setUp(self):
        super().setUp()
        self.staff = self.create_staff()
        self.authenticate(self.staff)

    def create_pet_with_photos(self, count):
        resp = self.client.post(
            "/api/pets/",
            {
                "name": "Buddy", "species": "dog", "breed": "Beagle",
                "age_years": 2, "gender": "male",
                "images": [png(f"photo{i}.png") for i in range(1, count + 1)],
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data["images"]), count)
        return resp.data

    def detail(self, pet_id):
        resp = self.client.get(f"/api/pets/{pet_id}/")
        self.assertEqual(resp.status_code, 200)
        return resp.data

    def image_urls(self, pet_id):
        return [img["image"] for img in self.detail(pet_id)["images"]]

    def add_photo(self, pet_id, name):
        return self.client.post(
            f"/api/pets/{pet_id}/images/", {"image": png(name)}, format="multipart"
        )

    def remove_photo(self, pet_id, image_id):
        return self.client.delete(f"/api/pets/{pet_id}/images/{image_id}/")

    def test_edit_pet_information_preserves_existing_photos(self):
        """Changing ordinary pet fields must never drop the pet's photos."""
        pet = self.create_pet_with_photos(3)
        before = self.image_urls(pet["id"])
        resp = self.client.patch(
            f"/api/pets/{pet['id']}/",
            {
                "name": "Buddy Renamed", "breed": "Labrador", "age_years": 3,
                "gender": "male", "size": "large", "color": "Golden",
                "is_vaccinated": True, "is_neutered": True,
                "description": "Friendly.", "arrival_date": "2026-01-15",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["name"], "Buddy Renamed")
        self.assertEqual(resp.data["age_years"], 3)
        self.assertEqual(resp.data["arrival_date"], "2026-01-15")
        # All three photos must still exist, unchanged.
        self.assertEqual(self.image_urls(pet["id"]), before)
        self.assertEqual(Pet.objects.get(pk=pet["id"]).images.count(), 3)

    def test_removing_arrival_date_is_allowed(self):
        pet = self.create_pet_with_photos(1)
        self.client.patch(
            f"/api/pets/{pet['id']}/", {"arrival_date": "2026-01-15"}, format="json"
        )
        resp = self.client.patch(
            f"/api/pets/{pet['id']}/", {"arrival_date": None}, format="json"
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data["arrival_date"])

    def test_edit_pet_adds_new_photos_additively(self):
        """Existing photo1+photo2 plus newly added photo3+photo4 = 4 photos."""
        pet = self.create_pet_with_photos(2)
        self.assertEqual(self.add_photo(pet["id"], "photo3.png").status_code, 201)
        self.assertEqual(self.add_photo(pet["id"], "photo4.png").status_code, 201)
        urls = self.image_urls(pet["id"])
        self.assertEqual(len(urls), 4)
        for name in ("photo1", "photo2", "photo3", "photo4"):
            self.assertTrue(any(name in url for url in urls), f"{name} missing from {urls}")
        pet_obj = Pet.objects.get(pk=pet["id"])
        self.assertEqual(pet_obj.images.count(), 4)
        self.assertTrue(all(str(img.pet_id) == str(pet["id"]) for img in pet_obj.images.all()))

    def test_edit_pet_removes_only_the_chosen_photo(self):
        pet = self.create_pet_with_photos(3)
        images = self.detail(pet["id"])["images"]
        target = next(img for img in images if "photo2" in img["image"])
        self.assertEqual(self.remove_photo(pet["id"], target["id"]).status_code, 204)
        urls = self.image_urls(pet["id"])
        self.assertEqual(len(urls), 2)
        self.assertFalse(any("photo2" in url for url in urls), urls)
        for name in ("photo1", "photo3"):
            self.assertTrue(any(name in url for url in urls), f"{name} missing from {urls}")

    def test_removing_primary_photo_promotes_the_next_remaining_photo(self):
        pet = self.create_pet_with_photos(3)
        images = self.detail(pet["id"])["images"]
        self.assertTrue(images[0]["is_primary"])
        self.assertEqual(self.remove_photo(pet["id"], images[0]["id"]).status_code, 204)
        remaining = self.detail(pet["id"])["images"]
        self.assertEqual(len(remaining), 2)
        self.assertTrue(remaining[0]["is_primary"])
        self.assertEqual(Pet.objects.filter(pk=pet["id"], images__is_primary=True).count(), 1)

    def test_first_photo_added_to_a_photo_less_pet_becomes_primary(self):
        pet = self.create_pet_with_photos(1)
        only_image = self.detail(pet["id"])["images"][0]
        self.assertEqual(self.remove_photo(pet["id"], only_image["id"]).status_code, 204)
        self.assertEqual(self.detail(pet["id"])["images"], [])
        self.assertEqual(self.add_photo(pet["id"], "replacement.png").status_code, 201)
        images = self.detail(pet["id"])["images"]
        self.assertEqual(len(images), 1)
        self.assertTrue(images[0]["is_primary"])

    def test_adopter_cannot_add_or_remove_pet_photos(self):
        pet = self.create_pet_with_photos(2)
        image_id = self.detail(pet["id"])["images"][0]["id"]
        self.authenticate(self.create_user(email="adopter-photos@example.com"))
        self.assertEqual(self.add_photo(pet["id"], "nope.png").status_code, 403)
        self.assertEqual(self.remove_photo(pet["id"], image_id).status_code, 403)
        self.assertEqual(Pet.objects.get(pk=pet["id"]).images.count(), 2)

    def test_cannot_remove_another_pets_photo_through_this_pet(self):
        pet_a = self.create_pet_with_photos(1)
        pet_b = self.create_pet_with_photos(1)
        image_a = self.detail(pet_a["id"])["images"][0]["id"]
        # image_a does not belong to pet_b, so the route must not expose it.
        self.assertEqual(self.remove_photo(pet_b["id"], image_a).status_code, 404)
        self.assertEqual(Pet.objects.get(pk=pet_a["id"]).images.count(), 1)

    def test_adding_photo_to_unknown_pet_returns_404(self):
        import uuid

        resp = self.add_photo(uuid.uuid4(), "ghost.png")
        self.assertEqual(resp.status_code, 404)


class PetAgeMigrationTests(TransactionTestCase):
    """Regression tests for the `age_months` -> `age_years` data migration.

    The migration only failed on databases that already contained pets (an
    empty table never enters the conversion loop), so these tests deliberately
    migrate to the old schema, insert a row, and migrate forward again through
    the real migration operations.
    """

    AGE_FIELD_MIGRATION = ("pets", "0002_pet_age_years_and_arrival_date")
    OLD_SCHEMA = ("pets", "0001_initial")

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([target])
        return executor.loader.project_state([target]).apps

    def test_existing_age_months_rows_are_converted_to_years(self):
        old_apps = self.migrate(self.OLD_SCHEMA)
        OldPet = old_apps.get_model("pets", "Pet")
        OldPet.objects.create(
            name="Buddy", species="dog", breed="Beagle", age_months=30,
            gender="male", size="medium", status="available",
        )
        OldPet.objects.create(
            name="Puppy", species="dog", breed="Aspin", age_months=5,
            gender="female", size="small", status="available",
        )

        new_apps = self.migrate(self.AGE_FIELD_MIGRATION)
        NewPet = new_apps.get_model("pets", "Pet")

        self.assertEqual(NewPet.objects.get(name="Buddy").age_years, 2)
        # Sub-year ages become 0, which the portals show as "Under 1 year".
        self.assertEqual(NewPet.objects.get(name="Puppy").age_years, 0)
        self.assertIsNone(NewPet.objects.get(name="Buddy").arrival_date)

    def test_migration_is_reversible_with_existing_rows(self):
        new_apps = self.migrate(self.AGE_FIELD_MIGRATION)
        NewPet = new_apps.get_model("pets", "Pet")
        NewPet.objects.create(
            name="Buddy", species="dog", breed="Beagle", age_years=3,
            gender="male", size="medium", status="available",
        )

        old_apps = self.migrate(self.OLD_SCHEMA)
        OldPet = old_apps.get_model("pets", "Pet")
        self.assertEqual(OldPet.objects.get(name="Buddy").age_months, 36)

        # Leave the database on the latest schema for any following test.
        self.migrate(self.AGE_FIELD_MIGRATION)

