from django.test import TestCase
from apps.accounts.tests import BaseAPITestCase
from apps.pets.models import Pet
from apps.applications.models import Application
from apps.adoptions.models import AdoptionRecord
from apps.payments.models import Payment


class ReportTests(BaseAPITestCase):

    def setUp(self):
        super().setUp()
        self.adopter = self.create_user(email="adopter@example.com")
        self.staff = self.create_staff(email="staff1@example.com")
        self.pet = Pet.objects.create(name="Buddy", species="dog", age_months=12, status="adopted")

    def test_staff_can_access_pet_inventory_report(self):
        self.authenticate(self.staff)
        resp = self.client.get("/api/reports/pets/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["stats"]["total"], 1)

    def test_adopter_cannot_access_reports(self):
        self.authenticate(self.adopter)
        resp = self.client.get("/api/reports/pets/")
        self.assertEqual(resp.status_code, 403)

    def test_adoption_report(self):
        app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="adoption_completed")
        AdoptionRecord.objects.create(
            application=app, pet=self.pet, adopter=self.adopter,
            staff_member=self.staff, status="completed", completed_date="2024-01-15",
        )
        self.authenticate(self.staff)
        resp = self.client.get("/api/reports/adoptions/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["stats"]["total"], 1)
        self.assertEqual(resp.data["stats"]["completed"], 1)

    def test_application_report(self):
        Application.objects.create(adopter=self.adopter, pet=self.pet, status="submitted")
        self.authenticate(self.staff)
        resp = self.client.get("/api/reports/applications/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["total"], 1)

    def test_adopter_report(self):
        self.authenticate(self.staff)
        resp = self.client.get("/api/reports/adopters/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["stats"]["total_adopters"], 1)

    def test_health_report(self):
        from apps.health.models import HealthRecord, Vaccination
        from datetime import date
        HealthRecord.objects.create(pet=self.pet, record_date=date(2024, 1, 1))
        Vaccination.objects.create(
            pet=self.pet, vaccine_name="Rabies",
            date_administered=date(2020, 1, 1), next_due_date=date(2020, 1, 15),
        )
        self.authenticate(self.staff)
        resp = self.client.get("/api/reports/health/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["stats"]["total_health_records"], 1)
        self.assertEqual(resp.data["stats"]["overdue_vaccinations"], 1)

    def test_pet_inventory_csv_export(self):
        self.authenticate(self.staff)
        resp = self.client.get("/api/reports/pets/?export=csv")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")