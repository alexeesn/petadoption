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
        self.pet = Pet.objects.create(name="Buddy", species="dog", age_years=1, status="adopted")

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



class MonthlyReportPdfTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.adopter = self.create_user(email="adopter_monthly@example.com")
        self.staff = self.create_staff(email="staff_monthly@example.com")
        self.pet = Pet.objects.create(name="Max", species="dog", age_years=2, status="adopted")
        self.app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="adoption_completed")

        from datetime import date
        # Completed payment in October 2026
        self.pay_oct = Payment.objects.create(
            application=self.app,
            amount=500,
            method="cash",
            status="completed",
            payment_date=date(2026, 10, 15),
            processed_by=self.staff,
        )
        # Pending payment in October 2026 (should be excluded from completed report)
        self.pay_oct_pending = Payment.objects.create(
            application=self.app,
            amount=200,
            method="gcash",
            status="pending",
            payment_date=date(2026, 10, 16),
            processed_by=self.staff,
        )
        # Completed payment in September 2026 (different month)
        self.pay_sep = Payment.objects.create(
            application=self.app,
            amount=300,
            method="cash",
            status="completed",
            payment_date=date(2026, 9, 20),
            processed_by=self.staff,
        )

        from django.utils import timezone
        import datetime
        dt_oct = timezone.make_aware(datetime.datetime(2026, 10, 10, 14, 0))
        dt_sep = timezone.make_aware(datetime.datetime(2026, 9, 10, 14, 0))

        # Completed adoption in October 2026
        self.adopt_oct = AdoptionRecord.objects.create(
            application=self.app,
            pet=self.pet,
            adopter=self.adopter,
            staff_member=self.staff,
            status=AdoptionRecord.Status.COMPLETED,
            transaction_id="TXN-OCT123456789",
            completed_at=dt_oct,
            completed_date=date(2026, 10, 10),
        )
        # Completed adoption in September 2026
        other_pet = Pet.objects.create(name="Sam", species="dog", age_years=3, status="adopted")
        other_app = Application.objects.create(adopter=self.adopter, pet=other_pet, status="adoption_completed")
        self.adopt_sep = AdoptionRecord.objects.create(
            application=other_app,
            pet=other_pet,
            adopter=self.adopter,
            staff_member=self.staff,
            status=AdoptionRecord.Status.COMPLETED,
            transaction_id="TXN-SEP123456789",
            completed_at=dt_sep,
            completed_date=date(2026, 9, 10),
        )

    def test_monthly_payment_report_pdf(self):
        self.authenticate(self.staff)
        resp = self.client.get("/api/reports/monthly-payments-pdf/?year=2026&month=10")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF"))
        self.assertIn("attachment;", resp["Content-Disposition"])
        self.assertIn("pawconnect-payment-report-2026-10.pdf", resp["Content-Disposition"])

    def test_monthly_adoption_report_pdf(self):
        self.authenticate(self.staff)
        resp = self.client.get("/api/reports/monthly-adoptions-pdf/?year=2026&month=10")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF"))
        self.assertIn("attachment;", resp["Content-Disposition"])
        self.assertIn("pawconnect-adoption-report-2026-10.pdf", resp["Content-Disposition"])

    def test_monthly_reports_require_staff(self):
        self.authenticate(self.adopter)
        resp1 = self.client.get("/api/reports/monthly-payments-pdf/?year=2026&month=10")
        self.assertEqual(resp1.status_code, 403)
        resp2 = self.client.get("/api/reports/monthly-adoptions-pdf/?year=2026&month=10")
        self.assertEqual(resp2.status_code, 403)

    def test_invalid_parameters_return_400(self):
        self.authenticate(self.staff)
        resp1 = self.client.get("/api/reports/monthly-payments-pdf/?year=abc&month=10")
        self.assertEqual(resp1.status_code, 400)
        resp2 = self.client.get("/api/reports/monthly-payments-pdf/?year=2026&month=13")
        self.assertEqual(resp2.status_code, 400)
        resp3 = self.client.get("/api/reports/monthly-adoptions-pdf/")
        self.assertEqual(resp3.status_code, 400)
