from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.applications.models import Application
from apps.audit.models import AuditLog
from apps.notifications.models import Notification
from apps.pets.models import Pet
from .models import Payment


class ConcurrentFixedPaymentTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_concurrent_routes_collect_the_same_application_only_once(self):
        staff = User.objects.create_user(email="concurrent-staff@example.com", role="staff")
        adopter = User.objects.create_user(email="concurrent-adopter@example.com")
        pet = Pet.objects.create(name="Concurrency pet", species="cat", age_years=1)
        app = Application.objects.create(adopter=adopter, pet=pet, status="approved")
        barrier = Barrier(2)

        def record(url):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(user=staff)
                barrier.wait(timeout=10)
                return client.post(url, {
                    "application": str(app.id), "payment_received": True,
                }, format="json").status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(record, [
                "/api/payments/record-onsite/",
                f"/api/applications/{app.id}/record-payment/",
            ]))
        self.assertEqual(sorted(results), [201, 400])
        payment = Payment.objects.get(application=app)
        self.assertEqual(str(payment.amount), "500.00")
        self.assertEqual(payment.status, "completed")
        self.assertEqual(AuditLog.objects.filter(action="payment_created").count(), 1)
        self.assertEqual(Notification.objects.filter(title="Payment Confirmed").count(), 1)
