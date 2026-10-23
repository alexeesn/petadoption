from datetime import date, datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from .services import visit_has_ended


@override_settings(
    NO_SHOW_DEMO_NOW="2026-10-24T18:00:00+08:00",
    NO_SHOW_DEMO_EXPIRES_AT="2026-10-24T12:15:00+08:00",
)
class NoShowDemoClockTests(SimpleTestCase):
    def setUp(self):
        self.appointment = SimpleNamespace(requested_date=date(2026, 10, 24))
        clock = patch("django.utils.timezone.now", return_value=datetime(2026, 10, 24, 4, tzinfo=dt_timezone.utc))
        self.clock = clock.start()
        self.addCleanup(clock.stop)

    @override_settings(DEBUG=True)
    def test_local_preview_expires_automatically(self):
        self.assertTrue(visit_has_ended(self.appointment))
        self.clock.return_value = datetime(2026, 10, 24, 4, 15, tzinfo=dt_timezone.utc)
        self.assertFalse(visit_has_ended(self.appointment))

    @override_settings(DEBUG=False)
    def test_production_always_uses_real_time(self):
        self.assertFalse(visit_has_ended(self.appointment))

    @override_settings(DEBUG=True)
    def test_incomplete_or_invalid_preview_uses_real_time(self):
        for value in ("", "not-a-time", "2026-10-24T12:15:00", "2026-99-24T12:15:00+08:00"):
            with self.subTest(value=value), self.settings(NO_SHOW_DEMO_EXPIRES_AT=value):
                self.assertFalse(visit_has_ended(self.appointment))
