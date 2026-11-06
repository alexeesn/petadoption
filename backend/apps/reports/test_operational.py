import csv
from datetime import date, datetime, timezone as dt_timezone
import io
from unittest.mock import patch

from django.utils import timezone
from apps.accounts.tests import BaseAPITestCase
from apps.adopters.models import AdopterProfile, IdentityVerification
from apps.adoptions.models import AdoptionRecord
from apps.applications.models import Application
from apps.appointments.models import Appointment, RescheduleRequest
from apps.payments.models import Payment
from apps.pets.models import Pet, PetDeathRecord
from apps.surrenders.models import SurrenderRequest


class OperationalReportTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.staff = self.create_staff(email='ops-staff@example.test')
        self.admin = self.create_admin(email='ops-admin@example.test')
        self.owner = self.create_user(email='ops-owner@example.test')
        self.pet = Pet.objects.create(name='Report Mochi', species='cat', status='deceased', arrival_date='2026-01-01')
        self.death = PetDeathRecord.objects.create(pet=self.pet, recorded_by=self.staff, death_date='2026-10-01', cause='Unknown')
        corrected_pet = Pet.objects.create(name='Corrected entry pet', species='dog', status='for_assessment')
        self.corrected = PetDeathRecord.objects.create(pet=corrected_pet, recorded_by=self.staff, death_date='2026-10-02', corrected_at=timezone.now(), corrected_by=self.admin, correction_reason='Wrong pet selected')
        self.app = Application.objects.create(pet=self.pet, adopter=self.owner, status='cancelled', death_record=self.death, cancellation_reason='Pet passed away', cancelled_at=timezone.now())
        self.adoption = AdoptionRecord.objects.create(application=self.app, pet=self.pet, adopter=self.owner, status='cancelled', adoption_date='2026-10-03', cancelled_at=timezone.now(), cancellation_reason='Pet passed away')
        self.visit = Appointment.objects.create(application=self.app, pet=self.pet, adopter=self.owner, requested_date='2026-10-03', status='cancelled')
        self.reschedule = RescheduleRequest.objects.create(application=self.app, appointment=self.visit, original_date='2026-10-03', requested_date='2026-10-04', reason='Move visit', status='cancelled')
        self.payment = Payment.objects.create(application=self.app, amount='500.00', status='completed', payment_date='2026-10-01', death_review_required=True, death_review_note='Review after death')
        self.refunded = Payment.objects.create(application=self.app, amount='200.00', status='refunded', payment_date='2026-10-02', death_review_note='Review resolved')
        self.surrender = SurrenderRequest.objects.create(owner=self.owner, pet_name='Incoming cat', species='cat', status='waitlisted', reason='Relocating', ownership_confirmed=True)
        self.verification = IdentityVerification.objects.get(profile__user=self.owner)
        self.authenticate(self.staff)
        self.keys = ['surrenders', 'pet-deaths', 'verifications', 'appointments', 'reschedules', 'adoptions', 'payments', 'pets', 'applications']

    def read(self, key, **params):
        return self.client.get(f'/api/reports/operations/{key}/', params)

    def stats(self, response):
        return {item['key']: item['value'] for item in response.data['stats']}

    def test_staff_catalog_and_every_report_are_real_and_admin_accessible(self):
        catalog = self.client.get('/api/reports/operations/')
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual({r['key'] for r in catalog.data['reports']}, set(self.keys))
        expected = {'surrenders': 1, 'pet-deaths': 1, 'verifications': 1, 'appointments': 1, 'reschedules': 1, 'adoptions': 1, 'payments': 2, 'pets': 2, 'applications': 1}
        for key, count in expected.items():
            with self.subTest(key=key):
                response = self.read(key)
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data['count'], count)
                self.assertEqual(self.stats(response)['total'], count)
                self.assertEqual(len(response.data['results']), count)
                self.assertIn('date_basis', response.data)
        self.authenticate(self.admin)
        self.assertEqual(self.read('pet-deaths', status='').data['count'], 2)

    def test_all_formats_and_catalog_are_staff_only(self):
        for user in (self.owner, None):
            self.authenticate(user) if user else self.unauthenticate()
            self.assertEqual(self.client.get('/api/reports/operations/').status_code, 403)
            for key in self.keys:
                for export in ('', 'csv', 'pdf'):
                    with self.subTest(key=key, export=export):
                        self.assertEqual(self.read(key, **({'export': export} if export else {})).status_code, 403)

    def test_death_corrections_are_not_counted_as_mortality(self):
        response = self.read('pet-deaths')
        self.assertEqual(self.stats(response)['deaths'], 1)
        self.assertEqual(self.stats(response)['corrected'], 0)
        all_entries = self.read('pet-deaths', status='')
        self.assertEqual(all_entries.data['count'], 2)
        self.assertEqual(self.stats(all_entries)['deaths'], 1)
        self.assertEqual(self.stats(all_entries)['corrected'], 1)
        corrected = self.read('pet-deaths', status='corrected')
        self.assertEqual(self.stats(corrected)['deaths'], 0)
        self.assertEqual(corrected.data['results'][0]['status'], 'corrected')

    def test_dates_use_selected_business_date_and_philippine_timezone(self):
        timestamp = datetime(2026, 9, 30, 16, 30, tzinfo=dt_timezone.utc)
        SurrenderRequest.objects.filter(pk=self.surrender.pk).update(created_at=timestamp, intake_date=date(2026, 10, 5))
        for params, expected in [
            ({'date_from': '2026-10-01', 'date_to': '2026-10-01'}, 1),
            ({'date_from': '2026-09-30', 'date_to': '2026-09-30'}, 0),
            ({'date_basis': 'intake', 'date_from': '2026-10-05', 'date_to': '2026-10-05'}, 1),
            ({'date_basis': 'received', 'date_from': '2026-10-01'}, 0),
        ]:
            response = self.read('surrenders', **params)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['count'], expected)
        death = self.read('pet-deaths', date_from='2026-10-01', date_to='2026-10-01')
        self.assertEqual(death.data['count'], 1)

    def test_filters_compose_before_stats_pagination_and_export(self):
        for number in range(25):
            SurrenderRequest.objects.create(owner=self.owner, pet_name=f'Waiting {number}', species='dog', status='waitlisted', reason='Relocating', ownership_confirmed=True)
        filters = {'status': 'waitlisted', 'species': 'dog', 'search': 'Waiting'}
        first, second = self.read('surrenders', **filters), self.read('surrenders', page=2, **filters)
        self.assertEqual(first.data['count'], 25)
        self.assertEqual(self.stats(first)['waitlisted'], 25)
        self.assertEqual(len(first.data['results']), 20)
        self.assertEqual(len(second.data['results']), 5)
        export = self.read('surrenders', export='csv', page=2, **filters)
        rows = list(csv.reader(io.StringIO(export.content.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 26)  # All matching records, not only page 2.
        with patch('apps.reports.operational_pdf.build_operational_pdf', return_value=b'%PDF-test') as build:
            response = self.read('surrenders', export='pdf', page=2, **filters)
            self.assertEqual(len(list(build.call_args.args[1])), 25)
            self.assertEqual(build.call_args.args[4], self.staff)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Date basis: Request submitted date', build.call_args.args[3])

    def test_payment_review_and_completed_amount_are_separate(self):
        response = self.read('payments')
        self.assertEqual(self.stats(response)['completed_amount'], '500.00')
        self.assertEqual(self.stats(response)['review_required'], 1)
        required = self.read('payments', review_status='required')
        resolved = self.read('payments', review_status='resolved')
        self.assertEqual(required.data['count'], 1)
        self.assertEqual(resolved.data['count'], 1)
        self.assertEqual(resolved.data['results'][0]['status'], 'refunded')
        self.assertEqual(self.stats(resolved)['completed_amount'], '0.00')

    def test_every_csv_and_pdf_works_without_mutating_records(self):
        before = list(Payment.objects.order_by('pk').values())
        for key in self.keys:
            with self.subTest(key=key):
                csv_response = self.read(key, export='csv')
                self.assertEqual(csv_response.status_code, 200)
                self.assertIn('attachment;', csv_response['Content-Disposition'])
                pdf = self.read(key, export='pdf')
                self.assertEqual(pdf.status_code, 200)
                self.assertTrue(pdf.content.startswith(b'%PDF'))
                self.assertEqual(pdf['Cache-Control'], 'private, no-store')
        self.assertEqual(list(Payment.objects.order_by('pk').values()), before)

    def test_invalid_filters_return_validation_errors(self):
        for params in ({'date_from': 'not-a-date'}, {'date_from': '2026-11-01', 'date_to': '2026-10-01'}, {'status': 'invalid'}, {'date_basis': 'invalid'}, {'species': 'bird'}, {'pet': 'bad-id'}, {'export': 'invalid'}, {'review_status': 'required'}):
            response = self.read('surrenders', **params)
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(self.read('missing').status_code, 404)
        self.assertEqual(self.read('verifications', species='cat').status_code, 400)

    def test_private_files_and_internal_notes_are_not_bulk_exported(self):
        self.death.internal_notes = 'SECRET-INTERNAL-DETAILS'; self.death.save()
        for key in self.keys:
            for params in ({}, {'export': 'csv'}):
                response = self.read(key, **params)
                content = response.content.decode('utf-8-sig')
                self.assertNotIn('SECRET-INTERNAL-DETAILS', content)
                self.assertNotIn('selfie_with_id', content)
                self.assertNotIn('combined_pdf', content)

    def test_csv_formula_cells_are_escaped(self):
        self.surrender.pet_name = '=HYPERLINK("https://example.test")'; self.surrender.save()
        response = self.read('surrenders', export='csv')
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertTrue(rows[1][0].startswith("'="))

    def test_pdf_handles_long_saved_text_and_escapes_markup(self):
        self.corrected.cause = '<not markup> ' * 75
        self.corrected.correction_reason = 'A detailed correction reason. ' * 60
        self.corrected.save()
        response = self.read('pet-deaths', status='', export='pdf')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))
