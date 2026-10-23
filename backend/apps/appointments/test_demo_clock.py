from datetime import date, datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from .services import visit_has_ended


@override_settings(NO_SHOW_DEMO_ENABLED=True)
class NoShowDemoModeTests(SimpleTestCase):
    def setUp(self):
        self.appointment = SimpleNamespace(requested_date=date(2026, 10, 24))
        clock = patch("django.utils.timezone.now", return_value=datetime(2026, 10, 24, 4, tzinfo=dt_timezone.utc))
        self.clock = clock.start()
        self.addCleanup(clock.stop)

    @override_settings(DEBUG=True)
    def test_demo_allows_future_visits_without_expiry(self):
        self.appointment.requested_date = date(2026, 10, 28)
        self.assertTrue(visit_has_ended(self.appointment))
        self.clock.return_value = datetime(2027, 10, 24, 4, tzinfo=dt_timezone.utc)
        self.appointment.requested_date = date(2027, 10, 28)
        self.assertTrue(visit_has_ended(self.appointment))

    @override_settings(DEBUG=False)
    def test_production_always_uses_real_time(self):
        self.assertFalse(visit_has_ended(self.appointment))

    @override_settings(DEBUG=True, NO_SHOW_DEMO_ENABLED=False)
    def test_disabling_demo_restores_five_pm_cutoff(self):
        self.assertFalse(visit_has_ended(self.appointment))
        self.clock.return_value = datetime(2026, 10, 24, 9, tzinfo=dt_timezone.utc)
        self.assertTrue(visit_has_ended(self.appointment))
