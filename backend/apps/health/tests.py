from datetime import date

from django.test import TestCase
from apps.accounts.tests import BaseAPITestCase
from apps.pets.models import Pet
from apps.health.models import HealthRecord, Vaccination


class HealthTests(BaseAPITestCase):

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(name="Buddy", species="dog", age_years=1, status="available")
        self.adopter = self.create_user(email="adopter@example.com")
        self.staff = self.create_staff(email="staff1@example.com")

    def test_health_record_staff_only(self):
        self.authenticate(self.staff)
        resp = self.client.post("/api/health-records/", {
            "pet": str(self.pet.id),
            "record_date": "2024-01-01",
            "diagnosis": "Healthy",
        })
        self.assertEqual(resp.status_code, 201)

    def test_adopter_cannot_access_health(self):
        self.authenticate(self.adopter)
        resp = self.client.get("/api/health-records/")
        self.assertEqual(resp.status_code, 403)

    def test_vaccination_status_computation(self):
        from datetime import date
        vax = Vaccination.objects.create(
            pet=self.pet, vaccine_name="Rabies",
            date_administered=date(2020, 1, 1),
            next_due_date=date(2020, 1, 15),
        )
        self.assertEqual(vax.vaccination_status, "overdue")

    def test_vaccination_computed_status_via_api(self):
        # The computed vaccination_status must come back from the real
        # endpoint (staff-created vaccination with a long-past due date is
        # always "overdue", so the assertion is stable regardless of when the
        # suite runs).
        self.authenticate(self.staff)
        resp = self.client.post("/api/health-records/vaccinations/", {
            "pet": str(self.pet.id),
            "vaccine_name": "Rabies",
            "date_administered": "2020-01-01",
            "next_due_date": "2020-06-01",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["vaccination_status"], "overdue")
        self.assertTrue(resp.data["is_due"])


class HealthRecordCreationTests(BaseAPITestCase):
    """Creating a health record through the staff API.

    Regression coverage for the staff-portal bug where the create form posted
    ``record_type`` / ``date`` / ``vet_name`` / ``vet_contact`` instead of the
    model's real field names, so ``record_date`` (required) was never sent and
    every submission failed with a 400 that the UI hid behind a generic
    "Failed to create health record." message.
    """

    # Exactly what the staff portal's "New Health Record" form submits.
    FORM_PAYLOAD = {
        "record_date": "2026-01-15",
        "diagnosis": "Ear infection (otitis externa)",
        "treatment": "Antibiotic ear drops twice daily for 10 days",
        "veterinarian_name": "Dr. Reyes",
        "veterinary_clinic": "PawCare Animal Clinic",
        "next_checkup_date": "2026-02-15",
        "notes": "Recheck in two weeks if scratching continues.",
    }

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(
            name="Buddy", species="dog", age_years=2, status="available"
        )
        self.staff = self.create_staff(email="health-staff@example.com")
        self.adopter = self.create_user(email="health-adopter@example.com")

    def create_record(self, **overrides):
        payload = {"pet": str(self.pet.id), **self.FORM_PAYLOAD, **overrides}
        return self.client.post("/api/health-records/", payload)

    def test_staff_can_create_health_record_for_a_pet(self):
        self.authenticate(self.staff)
        resp = self.create_record()
        self.assertEqual(resp.status_code, 201)

        # Saved to the database, attached to the selected pet, with the
        # submitted values and the creating staff member.
        record = HealthRecord.objects.get(id=resp.data["id"])
        self.assertEqual(record.pet, self.pet)
        self.assertEqual(str(record.record_date), self.FORM_PAYLOAD["record_date"])
        self.assertEqual(record.diagnosis, self.FORM_PAYLOAD["diagnosis"])
        self.assertEqual(record.treatment, self.FORM_PAYLOAD["treatment"])
        self.assertEqual(record.veterinarian_name, self.FORM_PAYLOAD["veterinarian_name"])
        self.assertEqual(record.veterinary_clinic, self.FORM_PAYLOAD["veterinary_clinic"])
        self.assertEqual(
            str(record.next_checkup_date), self.FORM_PAYLOAD["next_checkup_date"]
        )
        self.assertEqual(record.notes, self.FORM_PAYLOAD["notes"])
        self.assertEqual(record.created_by, self.staff)
        self.assertEqual(resp.data["pet_name"], "Buddy")

    def test_created_record_appears_in_the_list_and_detail(self):
        self.authenticate(self.staff)
        created_id = self.create_record().data["id"]

        listed = self.client.get("/api/health-records/")
        self.assertEqual(listed.status_code, 200)
        rows = {row["id"]: row for row in listed.data["results"]}
        self.assertIn(created_id, rows)
        self.assertEqual(rows[created_id]["pet_name"], "Buddy")

        # A follow-up request (what a page refresh does) still returns it.
        detail = self.client.get(f"/api/health-records/{created_id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["diagnosis"], self.FORM_PAYLOAD["diagnosis"])
        self.assertEqual(str(detail.data["pet"]), str(self.pet.id))

    def test_next_checkup_date_is_optional(self):
        # The form omits the field entirely when staff leave it blank.
        self.authenticate(self.staff)
        payload = {"pet": str(self.pet.id), **self.FORM_PAYLOAD}
        payload.pop("next_checkup_date")
        resp = self.client.post("/api/health-records/", payload)
        self.assertEqual(resp.status_code, 201)
        record = HealthRecord.objects.get(id=resp.data["id"])
        self.assertIsNone(record.next_checkup_date)

    def test_missing_record_date_returns_a_field_error(self):
        # The legacy (buggy) frontend payload: no `record_date`, and field names
        # the serializer does not know about. The API must reject it with an
        # actionable field error the UI can display.
        self.authenticate(self.staff)
        resp = self.client.post("/api/health-records/", {
            "pet": str(self.pet.id),
            "record_type": "checkup",
            "date": "2026-01-15",
            "vet_name": "Dr. Reyes",
            "vet_contact": "0917 000 0000",
            "notes": "note",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("record_date", resp.data)
        self.assertEqual(HealthRecord.objects.count(), 0)

    def test_unknown_pet_is_rejected(self):
        import uuid

        self.authenticate(self.staff)
        resp = self.create_record(pet=str(uuid.uuid4()))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("pet", resp.data)
        self.assertEqual(HealthRecord.objects.count(), 0)

    def test_adopter_cannot_create_health_record(self):
        self.authenticate(self.adopter)
        self.assertEqual(self.create_record().status_code, 403)
        self.assertEqual(HealthRecord.objects.count(), 0)


class AdopterPetHealthSummaryTests(BaseAPITestCase):
    """Adopter-facing health summary on the Pet Details endpoint.

    The adopter portal renders its "Health Information" section straight from
    GET /api/pets/<id>/, so the summary has to come from the real health records,
    must never leak staff-only fields, and must stay useful when a pet has no
    health record yet.
    """

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(
            name="Buddy", species="dog", age_years=2, status="available"
        )
        self.url = f"/api/pets/{self.pet.id}/"

    def test_pet_without_health_record_returns_empty_summary(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.data["health_summary"],
            {
                "has_health_record": False,
                "vaccination_status": None,
                "health_status": "",
                "last_checkup_date": None,
                "next_checkup_date": None,
            },
        )

    def test_summary_reflects_the_latest_health_record(self):
        HealthRecord.objects.create(
            pet=self.pet, record_date=date(2024, 1, 1), diagnosis="Healthy"
        )
        HealthRecord.objects.create(
            pet=self.pet,
            record_date=date(2024, 6, 1),
            diagnosis="Recovering from kennel cough",
            next_checkup_date=date(2024, 7, 1),
        )
        summary = self.client.get(self.url).data["health_summary"]
        self.assertTrue(summary["has_health_record"])
        self.assertEqual(summary["health_status"], "Recovering from kennel cough")
        self.assertEqual(summary["last_checkup_date"], "2024-06-01")
        self.assertEqual(summary["next_checkup_date"], "2024-07-01")

    def test_internal_health_fields_are_never_exposed(self):
        HealthRecord.objects.create(
            pet=self.pet,
            record_date=date(2024, 1, 1),
            diagnosis="Healthy",
            treatment="Internal treatment detail",
            notes="Staff-only note",
            veterinarian_name="Dr. Smith",
            veterinary_clinic="Clinic X",
        )
        summary = self.client.get(self.url).data["health_summary"]
        for internal_field in (
            "notes", "treatment", "veterinarian_name", "veterinary_clinic",
        ):
            self.assertNotIn(internal_field, summary)
        self.assertNotIn("Staff-only note", str(summary))

    def test_vaccination_status_reports_the_most_urgent_record(self):
        Vaccination.objects.create(
            pet=self.pet, vaccine_name="Anti-Rabies",
            date_administered=date(2020, 1, 1), next_due_date=date(2020, 6, 1),
        )
        Vaccination.objects.create(
            pet=self.pet, vaccine_name="DHPP",
            date_administered=date(2024, 1, 1), next_due_date=date(2099, 1, 1),
        )
        summary = self.client.get(self.url).data["health_summary"]
        self.assertEqual(summary["vaccination_status"], "overdue")

    def test_pet_without_vaccinations_has_no_vaccination_status(self):
        self.assertIsNone(
            self.client.get(self.url).data["health_summary"]["vaccination_status"]
        )

    def test_summary_is_available_without_auth_for_the_public_pet_page(self):
        # The adopter Pet Details page is also reachable while logged out.
        HealthRecord.objects.create(
            pet=self.pet, record_date=date(2024, 1, 1), diagnosis="Healthy"
        )
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["health_summary"]["health_status"], "Healthy")
