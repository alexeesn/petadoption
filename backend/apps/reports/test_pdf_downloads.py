"""Real HTTP/PDF coverage for return records and authenticated download metadata."""
from datetime import date, datetime, timezone as dt_timezone
import re
from unittest.mock import patch

from apps.accounts.tests import BaseAPITestCase
from apps.adoptions.models import AdoptionRecord
from apps.adoptions.tests import _extract_pdf_text
from apps.applications.models import Application
from apps.audit.models import AuditLog
from apps.notifications.models import Notification
from apps.payments.models import Payment
from apps.pets.models import Pet


class PdfDownloadMetadataTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.recorder = self.create_staff(email="recorder@example.test", first_name="Original", last_name="Recorder")
        self.downloader = self.create_staff(email="downloader@example.test", first_name="Download", last_name="Operator")
        self.admin = self.create_admin(email="pdf-admin@example.test", first_name="Export", last_name="Administrator")
        self.adopter = self.create_user(email="pdf-adopter@example.test")
        self.pet = Pet.objects.create(name="PDF Buddy", species="dog", age_years=2, status="adopted")
        self.app = Application.objects.create(adopter=self.adopter, pet=self.pet, status="adoption_completed")
        self.record = AdoptionRecord.objects.create(
            application=self.app, pet=self.pet, adopter=self.adopter, staff_member=self.recorder,
            status="completed", transaction_id="TXN-PDF-HISTORY", completed_date=date(2026, 10, 1),
            completed_at=datetime(2026, 10, 1, 1, 0, tzinfo=dt_timezone.utc),
        )
        self.payment = Payment.objects.create(
            application=self.app, adoption=self.record, amount="500.00", status="completed", method="cash",
            processed_by=self.recorder, payment_date=date(2026, 10, 1),
        )
        self.now = datetime(2026, 10, 23, 16, 15, 30, tzinfo=dt_timezone.utc)
        self.urls = [
            f"/api/adoptions/{self.record.pk}/record-pdf/",
            "/api/adoptions/export-pdf/",
            f"/api/payments/{self.payment.pk}/receipt-pdf/",
            "/api/payments/export-pdf/",
            "/api/reports/monthly-payments-pdf/?year=2026&month=10",
            "/api/reports/monthly-adoptions-pdf/?year=2026&month=10",
        ]

    def snapshot(self):
        return {model.__name__: list(model.objects.order_by("pk").values()) for model in (
            AdoptionRecord, Payment, Application, Pet, AuditLog, Notification,
        )}

    def download(self, url):
        with patch("django.utils.timezone.now", return_value=self.now):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertTrue(response.content.startswith(b"%PDF"))
        return response, _extract_pdf_text(response.content)

    def test_all_six_pdf_downloads_identify_requesting_staff_and_current_philippine_time(self):
        self.downloader.first_name = "alexis"
        self.downloader.last_name = "teodosio"
        self.downloader.save(update_fields=["first_name", "last_name"])
        self.authenticate(self.downloader)
        before = self.snapshot()
        for url in self.urls:
            with self.subTest(url=url):
                response, content = self.download(url)
                for value in (b"Downloaded by:", b"Alexis Teodosio", b"downloader@example.test", b"Staff",
                              b"Generated on:", b"24 October 2026, 00:15:30", b"PHT", b"UTC+08:00"):
                    self.assertIn(value, content)
                self.assertEqual(self.snapshot(), before)
                if url in ("/api/adoptions/export-pdf/", "/api/payments/export-pdf/"):
                    self.assertIn("2026-10-24.pdf", response["Content-Disposition"])
        self.downloader.refresh_from_db()
        self.assertEqual(self.downloader.first_name, "alexis")
        self.assertEqual(self.downloader.last_name, "teodosio")

    def test_downloader_changes_per_request_without_replacing_original_recorder(self):
        for user in (self.downloader, self.admin):
            self.authenticate(user)
            for url in self.urls:
                with self.subTest(user=user.role, url=url):
                    _, content = self.download(url)
                    self.assertIn(user.full_name.encode(), content)
                    self.assertIn(user.email.encode(), content)
                    self.assertIn(b"Original Recorder" if "/record-pdf/" in url or "/receipt-pdf/" in url
                                  else self.recorder.email.encode(), content)
        self.record.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(self.record.staff_member, self.recorder)
        self.assertEqual(self.payment.processed_by, self.recorder)

    def test_query_parameters_cannot_spoof_downloader_or_generation_date(self):
        self.authenticate(self.downloader)
        _, content = self.download(self.urls[0] + "?downloaded_by=FakeDownloader&generated_at=2000-01-01")
        self.assertIn(b"Download Operator", content)
        self.assertIn(b"24 October 2026", content)
        self.assertNotIn(b"FakeDownloader", content)
        self.assertNotIn(b"2000-01-01", content)

    def make_returned(self):
        self.record.status = "returned"
        self.record.return_date = date(2026, 10, 20)
        self.record.returned_at = datetime(2026, 10, 20, 1, 0, tzinfo=dt_timezone.utc)
        self.record.return_reason = "Allergies & changed circumstances <confirmed>"
        self.record.save()
        self.pet.status = "available"
        self.pet.save(update_fields=["status"])

    def test_return_pdf_distinguishes_completion_return_and_download_dates_and_keeps_financial_history(self):
        self.make_returned()
        self.authenticate(self.downloader)
        before = self.snapshot()
        response, content = self.download(self.urls[0])
        self.assertIn("pawconnect-adoption-return-TXN-PDF-HISTORY.pdf", response["Content-Disposition"])
        for value in (b"Adoption Return Record", b"Current adoption status: Returned", b"20 October 2026",
                      b"01 October 2026", b"24 October 2026", b"Allergies & changed circumstances <confirmed>",
                      b"Original Recorder", b"Download Operator", b"TXN-PDF-HISTORY"):
            self.assertIn(value, content)
        self.assertIn(b"doesnotautomaticallyissuearefund", re.sub(rb"\s+", b"", content))
        self.assertNotIn(b"Certificate of Adoption", content)
        self.assertEqual(self.snapshot(), before)

    def test_return_pdf_keeps_unknown_historical_return_dates_unknown(self):
        self.make_returned()
        self.record.return_date = None
        self.record.returned_at = None
        self.record.save()
        self.authenticate(self.downloader)
        _, content = self.download(self.urls[0])
        self.assertIn(b"Return date:", content)
        self.assertIn(b"Return recorded:", content)
        self.assertGreaterEqual(content.count(b"Not recorded"), 2)

    def test_return_pdf_handles_long_saved_reason_and_names(self):
        self.make_returned()
        self.record.return_reason = ("Return details & follow-up <confirmed>.\n" * 40) + "END OF RETURN REASON"
        self.record.save()
        self.downloader.first_name = "Maria Isabel " * 10
        self.downloader.last_name = "Dela Cruz " * 14
        self.downloader.save()
        self.authenticate(self.downloader)
        _, content = self.download(self.urls[0])
        self.assertIn(b"END OF RETURN REASON", content)
        self.assertIn(self.downloader.email.encode(), content)

    def test_scheduled_and_cancelled_records_still_cannot_download_individual_pdf(self):
        self.authenticate(self.downloader)
        for record_status in ("scheduled", "cancelled"):
            self.record.status = record_status
            self.record.save()
            response = self.client.get(self.urls[0])
            self.assertEqual(response.status_code, 400)

    def test_return_pdf_remains_staff_only(self):
        self.make_returned()
        self.authenticate(self.adopter)
        self.assertEqual(self.client.get(self.urls[0]).status_code, 403)
        self.unauthenticate()
        self.assertIn(self.client.get(self.urls[0]).status_code, (401, 403))

    def test_returned_aggregate_keeps_original_completion_history(self):
        self.make_returned()
        self.authenticate(self.downloader)
        _, content = self.download("/api/adoptions/export-pdf/?status=returned")
        for value in (b"Returned", b"2026-10-01", b"09:00", self.recorder.email.encode()):
            self.assertIn(value, content)
