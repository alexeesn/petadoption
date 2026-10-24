from unittest.mock import patch

from apps.accounts.tests import BaseAPITestCase
from apps.adoptions.models import AdoptionRecord
from apps.applications.models import Application
from apps.pets.models import Pet


class RecordViewTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.staff = self.create_staff(email="record-views-staff@example.test")
        self.adopter = self.create_user(email="record-views-adopter@example.test")
        self.pets = {status: Pet.objects.create(name=f"Pet {status}", species="dog", status=status)
                     for status in Pet.Status.values}
        self.applications = {}
        for status in Application.Status.values:
            pet = Pet.objects.create(name=f"Applicant pet {status}", species="cat")
            application = Application.objects.create(pet=pet, adopter=self.adopter, status=status)
            if status == "draft":
                Application.objects.filter(pk=application.pk).update(status="draft")
            self.applications[status] = application
        self.records = {}
        for state, application_state, pet_state in (
            ("scheduled", "approved", "pending"),
            ("completed", "adoption_completed", "adopted"),
            ("cancelled", "cancelled", "available"),
            ("returned", "adoption_completed", "available"),
        ):
            pet = Pet.objects.create(name=f"Record pet {state}", species="dog", status=pet_state)
            application = Application.objects.create(pet=pet, adopter=self.adopter, status=application_state)
            self.records[state] = AdoptionRecord.objects.create(
                pet=pet, application=application, adopter=self.adopter, staff_member=self.staff,
                status=state,
            )
        self.authenticate(self.staff)

    def test_active_history_and_all_counts_are_partitioned_before_pagination(self):
        for resource, active, history, total in (("pets", 16, 3, 19), ("applications", 7, 6, 13), ("adoptions", 1, 3, 4)):
            with self.subTest(resource=resource):
                active_data = self.client.get(f"/api/{resource}/", {"scope": "active"}).data
                history_data = self.client.get(f"/api/{resource}/", {"scope": "history"}).data
                all_data = self.client.get(f"/api/{resource}/", {"scope": "all"}).data
                self.assertEqual(active_data["count"], active)
                self.assertEqual(history_data["count"], history)
                self.assertEqual(all_data["count"], total)
                self.assertFalse({r["id"] for r in active_data["results"]} & {r["id"] for r in history_data["results"]})
                self.assertEqual(self.client.get(f"/api/{resource}/").data["count"], total)

    def test_pet_pagination_counts_all_matching_pets_not_only_the_visible_page(self):
        for number in range(25):
            Pet.objects.create(name=f"Available {number}", species="dog")
        first = self.client.get("/api/pets/", {"scope": "active"})
        second = self.client.get("/api/pets/", {"scope": "active", "page": 2})
        self.assertEqual(first.data["count"], 41)
        self.assertEqual(len(first.data["results"]), 20)
        self.assertIsNotNone(first.data["next"])
        self.assertEqual(second.data["count"], 41)
        self.assertFalse({row["id"] for row in first.data["results"]} & {row["id"] for row in second.data["results"]})

    def test_status_and_scope_filters_are_applied_together(self):
        for resource, scope, status, count in (
            ("pets", "active", "available", 12), ("pets", "history", "adopted", 2),
            ("applications", "active", "approved", 2), ("applications", "history", "cancelled", 2),
            ("adoptions", "history", "returned", 1), ("adoptions", "active", "completed", 0),
        ):
            with self.subTest(resource=resource, status=status):
                response = self.client.get(f"/api/{resource}/", {"scope": scope, "status": status})
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data["count"], count)
                self.assertTrue(all(row["status"] == status for row in response.data["results"]))

    def test_invalid_scope_has_a_validation_error(self):
        for resource in ("pets", "applications", "adoptions"):
            response = self.client.get(f"/api/{resource}/", {"scope": "invalid"})
            self.assertEqual(response.status_code, 400)
            self.assertIn("scope", response.data)

    def test_dashboard_counts_are_real_and_recent_applications_are_active_only(self):
        response = self.client.get("/api/reports/dashboard/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["available_pets"], 12)
        self.assertEqual(response.data["active_applications"], 7)
        self.assertEqual(response.data["scheduled_adoptions"], 1)
        self.assertEqual(response.data["completed_adoptions"], 1)
        self.assertEqual(len(response.data["recent_applications"]), 5)
        self.assertTrue(all(row["status"] not in ("rejected", "cancelled", "adoption_completed") for row in response.data["recent_applications"]))
        self.assertEqual(self.client.get("/api/reports/pets/").data["stats"]["total"], 19)

    def test_dashboard_is_staff_only(self):
        self.authenticate(self.adopter)
        self.assertEqual(self.client.get("/api/reports/dashboard/").status_code, 403)
        self.unauthenticate()
        self.assertIn(self.client.get("/api/reports/dashboard/").status_code, (401, 403))

    def test_history_filters_preserve_adopter_ownership(self):
        other = self.create_user(email="other-record-views@example.test")
        pet = Pet.objects.create(name="Other adopter's pet", species="dog", status="adopted")
        application = Application.objects.create(pet=pet, adopter=other, status="adoption_completed")
        record = AdoptionRecord.objects.create(pet=pet, application=application, adopter=other, status="completed")
        self.authenticate(self.adopter)
        applications = self.client.get("/api/applications/", {"scope": "history"})
        records = self.client.get("/api/adoptions/", {"scope": "history"})
        self.assertNotIn(str(application.pk), [row["id"] for row in applications.data["results"]])
        self.assertNotIn(str(record.pk), [row["id"] for row in records.data["results"]])

    def test_history_pdf_uses_all_matching_records_without_changing_saved_data(self):
        before = list(AdoptionRecord.objects.order_by("pk").values())
        with patch("apps.adoptions.views.build_adoption_records_pdf", return_value=b"%PDF-1.4\n%%EOF") as builder:
            response = self.client.get("/api/adoptions/export-pdf/", {"scope": "history"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual({record.pk for record in builder.call_args.args[0]}, {self.records[state].pk for state in ("completed", "cancelled", "returned")})
        self.assertIn("View: History", builder.call_args.kwargs["filters"])
        self.assertEqual(list(AdoptionRecord.objects.order_by("pk").values()), before)
