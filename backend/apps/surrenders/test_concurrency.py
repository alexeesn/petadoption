from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.pets.models import Pet
from .models import SurrenderRequest
from .services import today


class IntakeConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_simultaneous_intake_creates_exactly_one_pet(self):
        owner = User.objects.create_user(email="intake-owner@example.test", is_email_verified=True)
        staff = User.objects.create_user(email="intake-staff@example.test", role="staff", is_email_verified=True)
        request = SurrenderRequest.objects.create(owner=owner, pet_name="One pet", species="dog", ownership_confirmed=True,
                                                   status="intake_scheduled", intake_date=today())
        barrier = Barrier(2)

        def confirm(_):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(staff)
                barrier.wait(timeout=10)
                return client.post(f"/api/surrenders/{request.pk}/confirm-intake/", {"confirmed": True}, format="json").status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(confirm, range(2)))
        self.assertEqual(sorted(results), [200, 400])
        self.assertEqual(Pet.objects.count(), 1)
        request.refresh_from_db()
        self.assertEqual(request.status, "received")
        self.assertEqual(request.history.filter(action="received").count(), 1)
