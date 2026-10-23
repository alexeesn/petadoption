# Appointment follow-ups

Implemented flow:

- The center accepts appointment dates Monday–Saturday, 8 AM–5 PM; Sunday is closed. The same schedule applies to new bookings and reschedules.
- An adopter can request a different open date for their own confirmed or no-show appointment, with a reason. One pending request per application is enforced by an application row lock and a database constraint.
- The original date stays unchanged while pending or if rejected. Active staff/admin receive an in-app notification linking to **Appointments → Reschedule Requests**.
- Staff/admin review requests with explicit confirmation. Rejection requires a reason. Approval revalidates the proposed date, retains the old appointment as rescheduled/no-show history, and creates one confirmed replacement. The existing Scheduled adoption record is updated, preserving its ID and every payment.
- No-show is a manual staff decision, with reason and confirmation, available after the visit day ends at 5 PM Philippine time. It does not cancel the application/adoption or release the pet. No automatic date-based cancellation runs.
- **Cancel Adoption** is available for Scheduled records only. Staff/admin must supply a reason and confirmation. The application, active appointments and pending reschedule requests close atomically. The pet becomes available only if it is pending/reserved and has no other approved application or scheduled/completed adoption. Medical/inactive states are retained.
- Cancellation keeps all history, payment statuses and receipt IDs. It does not issue a refund. Completed adoptions use the existing return workflow instead of cancellation.
- Adopters receive in-app notifications and email for review decisions, no-show and adoption cancellation. Email uses the existing Django transport and is dispatched after commit. SMTP delivery still depends on the deployment configuration.
- Existing handover/fee validation and individual receipt/adoption PDFs remain in force. Completion closes any pending reschedule request without deleting it. Generic cancellation routes cannot bypass the coordinated service.

## Local no-show demo

Set `NO_SHOW_DEMO_ENABLED=True` in the root `.env` and restart the Django
development server. Eligible confirmed appointments always offer **Mark as
No-show**, including future appointments. The switch has no expiry. Staff still
provide a reason and explicit confirmation; saving records the real no-show
decision and notifications. Existing records are not changed by enabling it.
Other payment/completion date rules and real timestamps are unchanged.

After the report, set `NO_SHOW_DEMO_ENABLED=False` and restart Django to restore
the normal 5 PM Philippine-time cutoff. Production (`DEBUG=False`) always uses
that normal cutoff, regardless of this setting.

## API

- `POST /api/appointments/{id}/request-reschedule/`: owner only; `requested_date`, `reason`.
- `GET /api/appointments/reschedule-requests/`: own rows for adopters, all rows for staff/admin; `application`, `status`, `page` filters.
- `POST /api/appointments/reschedule-requests/{id}/approve/`: staff/admin; `confirmed: true`.
- `POST /api/appointments/reschedule-requests/{id}/reject/`: staff/admin; `confirmed: true`, `reason`.
- `POST /api/appointments/{id}/mark-no-show/`: staff/admin; `confirmed: true`, `reason`.
- `POST /api/adoptions/{id}/cancel/`: staff/admin; `confirmed: true`, `reason`. Legacy PATCH with status `cancelled` uses this same validation/service.

Apply the additive migration with `python manage.py migrate`. No existing rows are backfilled, deleted, merged or automatically cancelled.

## Verification

From `backend`:

```powershell
../venv/Scripts/python.exe manage.py test --settings=config.settings.testing --noinput
```

To run PostgreSQL race tests and a browser walkthrough against a real, running Django server:

```powershell
$env:PAWCONNECT_BROWSER_TESTS='1'
$env:PLAYWRIGHT_CHANNEL='msedge'
../venv/Scripts/python.exe manage.py test apps.appointments --settings=config.settings.testing_postgresql --noinput
```

The PostgreSQL settings generate a unique test-database name for each run. Django creates and removes that database; existing application/test databases are not reset. The browser test starts both Vite portals on ports 5188/5189, overrides their API URLs to the isolated server, rejects development-backend requests, and uses fixture accounts. It exercises request persistence, notifications, approval/rejection, no-show, rescheduling, cancellation and payment preservation. It requires staff-portal npm dependencies and an installed Playwright-compatible browser (Edge by default).

Verified for this implementation:

- Full SQLite suite: 552 tests run, 545 passed and 7 PostgreSQL/browser-only cases skipped.
- All five PostgreSQL follow-up concurrency cases passed, including cancellation versus completion.
- The real browser walkthrough passed against an isolated PostgreSQL database, including clicking the staff notification into the reschedule queue, reload persistence and cancellation after no-show history.
- All four existing Payment Records browser regressions passed.
- Both portals passed TypeScript/production builds. The adopter portal retains its existing bundle-size warning.
- Django checks, migration checks and diff whitespace checks passed; the additive migration was applied.
- SHA-256 comparisons of existing appointment, adoption, application, pet, payment, audit and notification table contents were unchanged after verification. No test requests were saved in the regular database.
