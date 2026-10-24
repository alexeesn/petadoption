from apps.accounts.tests import BaseAPITestCase
from apps.pets.models import Pet
from .models import HealthRecord, Vaccination


class HealthRecordScopeTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.staff = self.create_staff(email="health-scope-staff@example.test")
        self.adopter = self.create_user(email="health-scope-adopter@example.test")
        self.records = {}
        for status in Pet.Status.values:
            pet = Pet.objects.create(name=f"Health {status}", species="dog", status=status)
            self.records[status] = HealthRecord.objects.create(
                pet=pet, record_date="2025-01-01", diagnosis=f"Saved diagnosis {status}",
                treatment="Existing care plan", notes="Keep medical history", created_by=self.staff,
            )
            Vaccination.objects.create(pet=pet, vaccine_name="Rabies", date_administered="2025-01-01")
        self.authenticate(self.staff)

    def test_health_views_use_pet_status_and_preserve_saved_medical_data(self):
        before = list(HealthRecord.objects.order_by("pk").values())
        vaccinations = list(Vaccination.objects.order_by("pk").values())
        for scope, statuses in (
            ("active", Pet.ACTIVE_STATUSES),
            ("history", ("adopted", "inactive")),
            ("all", Pet.Status.values),
        ):
            with self.subTest(scope=scope):
                response = self.client.get("/api/health-records/", {"scope": scope})
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data["count"], len(statuses))
                self.assertEqual({row["pet_status"] for row in response.data["results"]}, set(statuses))
                self.assertEqual({row["id"] for row in response.data["results"]},
                                 {str(self.records[status].pk) for status in statuses})
        self.assertEqual(self.client.get("/api/health-records/").data["count"], 6)
        self.assertEqual(list(HealthRecord.objects.order_by("pk").values()), before)
        self.assertEqual(list(Vaccination.objects.order_by("pk").values()), vaccinations)

    def test_health_scope_and_pet_filter_combine_before_pagination(self):
        record = self.records["adopted"]
        for scope, count in (("active", 0), ("history", 1), ("all", 1)):
            response = self.client.get("/api/health-records/", {"scope": scope, "pet": record.pet_id})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], count)
        for number in range(21):
            pet = Pet.objects.create(name=f"Historical {number}", species="cat", status="adopted")
            HealthRecord.objects.create(pet=pet, record_date="2025-01-01")
        first = self.client.get("/api/health-records/", {"scope": "history"})
        second = self.client.get("/api/health-records/", {"scope": "history", "page": 2})
        self.assertEqual(first.data["count"], 23)
        self.assertEqual(len(first.data["results"]), 20)
        self.assertIsNotNone(first.data["next"])
        self.assertEqual(second.data["count"], 23)
        self.assertEqual(len(second.data["results"]), 3)
        self.assertFalse({r["id"] for r in first.data["results"]} & {r["id"] for r in second.data["results"]})

    def test_existing_record_moves_between_views_as_pet_enters_and_leaves_care(self):
        record = self.records["available"]
        before = HealthRecord.objects.values().get(pk=record.pk)
        for status, visible_scope in (("adopted", "history"), ("available", "active")):
            Pet.objects.filter(pk=record.pet_id).update(status=status)
            for scope in ("active", "history"):
                response = self.client.get("/api/health-records/", {"scope": scope, "pet": record.pet_id})
                self.assertEqual(response.data["count"], 1 if scope == visible_scope else 0)
            self.assertEqual(HealthRecord.objects.values().get(pk=record.pk), before)
        self.assertEqual(HealthRecord.objects.filter(pet_id=record.pet_id).count(), 1)

    def test_history_can_be_retrieved_and_corrected_only_by_explicit_update(self):
        record = self.records["adopted"]
        response = self.client.get(f"/api/health-records/{record.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pet_status"], "adopted")
        response = self.client.patch(f"/api/health-records/{record.pk}/", {"notes": "Staff correction"})
        self.assertEqual(response.status_code, 200, response.data)
        record.refresh_from_db()
        self.assertEqual(record.notes, "Staff correction")
        self.assertEqual(record.diagnosis, "Saved diagnosis adopted")

    def test_invalid_scope_is_rejected(self):
        response = self.client.get("/api/health-records/", {"scope": "missing"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("scope", response.data)

    def test_every_health_scope_remains_staff_only(self):
        self.authenticate(self.adopter)
        for scope in ("active", "history", "all"):
            self.assertEqual(self.client.get("/api/health-records/", {"scope": scope}).status_code, 403)
        self.unauthenticate()
        self.assertIn(self.client.get("/api/health-records/", {"scope": "history"}).status_code, (401, 403))
