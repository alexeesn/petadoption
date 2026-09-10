from django.test import TestCase
from apps.accounts.tests import BaseAPITestCase
from apps.pets.models import Pet
from apps.health.models import HealthRecord, Vaccination


class HealthTests(BaseAPITestCase):

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(name="Buddy", species="dog", age_months=12, status="available")
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
