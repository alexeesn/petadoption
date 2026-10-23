# Onsite appointment date validation

A confirmed visit must have reached its appointment date in **Asia/Manila**
before staff can record a payment or complete physical adoption handover.
For an October 28 visit, those actions are blocked before October 28 and become
available from Philippine midnight on October 28. An earlier `payment_date`
cannot bypass the server clock. A confirmed visit may still be recorded later;
the existing manual no-show and cancellation decisions remain authoritative.

Future appointments can still be confirmed and automatically create a
**Scheduled** adoption record. Scheduling is separate from recording money or
completing the adoption.

## Enforcement

- Both onsite payment routes and the generic payment-create endpoint use the
  same confirmed-appointment date guard under the application transaction lock.
- All completion routes use the shared completion service, including
  complete-adoption, confirm-turnover, update-status and adoption-record PATCH.
- An onsite payment's actual payment date must be on/after the confirmed visit
  and on/before the current Philippine date. Its default is the Philippine date.
- Completion uses the Philippine date for `completed_date`.
- A reschedule approved for a future date blocks further completion until the
  new date, while preserving any previously received payment and receipt.
- Existing payment/completion history is not rewritten. Retrying an already
  completed transaction preserves its historical record.

Application details, payment summaries and adoption-record responses include an
`onsite_visit` object:

```json
{
  "appointment_date": "2026-10-28",
  "date_reached": false,
  "message": "Onsite payment and adoption completion are available on or after 2026-10-28 (Philippine time). The appointment date has not arrived yet."
}
```

The existing `can_record_payment` and `turnover_eligible` flags also incorporate
the date guard. The staff Payment Records page hides early payment entry and
shows this message; Adoption Records disables completion until eligible.
Application Review contains application details and review actions; onsite
payments are recorded in Payment Records and completion in Adoption Records.
Date inputs use Philippine dates and appropriate min/max values.

No new models or migrations are required.

## Verification

From `backend`:

```powershell
../venv/Scripts/python.exe manage.py test apps.appointments.test_onsite_date --settings=config.settings.testing_postgresql --noinput
$env:PAWCONNECT_BROWSER_TESTS='1'
../venv/Scripts/python.exe manage.py test apps.adoptions.test_return_browser --settings=config.settings.testing_postgresql --noinput
```

The eight HTTP regressions cover all payment/completion routes, future paid
legacy data, unchanged records after rejection, Philippine midnight, missing or
unconfirmed visits, payment-date validation, later recording, and approved
rescheduling. The live browser walkthrough checks blocked future visits on all
three staff pages and successful completion for an elapsed confirmed visit.
Its records live only in a uniquely named PostgreSQL test database.

Existing onsite-flow tests now use a deterministic weekday and explicitly
advance to the visit day before receiving money or handing over a pet. Tests
that deliberately omit confirmation or use legacy paid records retain those
fixtures. The separate scheduling tests still exercise future appointments.

Verified for this change:

- Full PostgreSQL suite: 601 tests, 596 passed and 5 opt-in cases skipped.
- Full SQLite suite: 601 tests, 589 passed and 12 PostgreSQL/browser cases skipped.
- The real browser walkthrough passed separately, including future-date
  restrictions on all three staff pages and the existing adoption/return flow.
- All four Payment Records browser regressions passed.
- Staff portal TypeScript/production build, Django system checks, migration
  checks and diff whitespace checks passed. No migration is needed.
