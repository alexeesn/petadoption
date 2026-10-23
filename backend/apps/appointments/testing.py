"""Deterministic clock for tests that perform an onsite visit on a weekday."""
from datetime import datetime, time, timezone as dt_timezone
from unittest.mock import patch

from apps.accounts.tests import BaseAPITestCase
from .models import Appointment


def visit_on(application, visit_date):
    return Appointment.objects.get_or_create(
        application=application, status="confirmed",
        defaults={"adopter": application.adopter, "pet": application.pet, "requested_date": visit_date},
    )[0]


class OnsiteFlowTestCase(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        clock_patch = patch("django.utils.timezone.now", return_value=datetime(2026, 10, 28, 4, tzinfo=dt_timezone.utc))
        self.onsite_clock = clock_patch.start()
        self.addCleanup(clock_patch.stop)

    def arrive_on(self, visit_date):
        self.onsite_clock.return_value = datetime.combine(visit_date, time(4), tzinfo=dt_timezone.utc)
