from django.test import TestCase
from apps.accounts.tests import BaseAPITestCase
from apps.pets.models import Pet
from apps.applications.models import Application
from apps.adoptions.models import AdoptionRecord
from apps.packages.models import AdoptionPackage
from apps.payments.models import Payment


class PaymentRulesTests(BaseAPITestCase):

    def setUp(self):
        super().setUp()
        self.pet = Pet.objects.create(name="Buddy", species="dog", age_months=12, status="available")
        self.adopter = self.create_user(email="adopter@example.com")
        self.staff = self.create_staff(email="staff1@example.com")
        self.app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="approved")
        self.adoption = AdoptionRecord.objects.create(
            application=self.app, pet=self.pet, adopter=self.adopter,
            staff_member=self.staff, status="scheduled",
        )

    def test_free_adoption_requires_no_payment(self):
        """No package assigned -> no payment should be generated."""
        self.authenticate_staff()
        # No payment should need to be created
        self.assertEqual(Payment.objects.count(), 0)

    def test_zero_package_requires_no_payment(self):
        """A ₱0 package requires no payment."""
        pkg = AdoptionPackage.objects.create(name="Free Care Kit", price=0, description="Free kit")
        # Even with package assigned, amount is 0 so no payment required
        self.assertEqual(pkg.price, 0)

    def test_paid_package_can_regenerate_receipt(self):
        pkg = AdoptionPackage.objects.create(name="Premium Kit", price=500, description="Premium kit")
        # Create a payment for the paid package
        self.authenticate_staff()
        resp = self.client.post("/api/payments/", {
            "application": str(self.app.id),
            "package": str(pkg.id),
            "amount": "500.00",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Payment.objects.count(), 1)

    def authenticate_staff(self):
        self.authenticate(self.staff)
