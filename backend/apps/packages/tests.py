from django.test import TestCase
from apps.accounts.tests import BaseAPITestCase
from apps.packages.models import AdoptionPackage


class PackageTests(BaseAPITestCase):

    def setUp(self):
        super().setUp()
        self.adopter = self.create_user(email="adopter@example.com")
        self.staff = self.create_staff(email="staff1@example.com")

    def test_public_can_list_packages(self):
        AdoptionPackage.objects.create(name="Starter", price=0, is_active=True)
        resp = self.client.get("/api/packages/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)

    def test_public_can_view_package_detail(self):
        pkg = AdoptionPackage.objects.create(name="Premium", price=1500, is_active=True)
        resp = self.client.get(f"/api/packages/{pkg.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["name"], "Premium")

    def test_adopter_cannot_create_package(self):
        self.authenticate(self.adopter)
        resp = self.client.post("/api/packages/", {"name": "X", "price": 0})
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_cannot_create_package(self):
        resp = self.client.post("/api/packages/", {"name": "X", "price": 0})
        self.assertEqual(resp.status_code, 403)

    def test_staff_can_create_package(self):
        self.authenticate(self.staff)
        resp = self.client.post("/api/packages/", {
            "name": "Complete Care",
            "description": "Everything included",
            "price": "2500.00",
            "inclusions": ["Vet check", "Microchip", "Vaccines"],
            "is_active": True,
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(AdoptionPackage.objects.count(), 1)

    def test_staff_can_update_package(self):
        pkg = AdoptionPackage.objects.create(name="Old", price=500, is_active=True)
        self.authenticate(self.staff)
        resp = self.client.patch(f"/api/packages/{pkg.id}/", {"price": "750.00"})
        self.assertEqual(resp.status_code, 200)
        pkg.refresh_from_db()
        self.assertEqual(str(pkg.price), "750.00")

    def test_staff_can_delete_package(self):
        pkg = AdoptionPackage.objects.create(name="Old", price=500, is_active=True)
        self.authenticate(self.staff)
        resp = self.client.delete(f"/api/packages/{pkg.id}/")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(AdoptionPackage.objects.count(), 0)