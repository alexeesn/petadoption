# Operational reports

The staff Reports page retains the existing monthly completed Payment and
Adoption PDFs and adds a filtered Operational Reports workspace.

Available reports:

| Report | Scope |
|---|---|
| Surrender and Intake | Current requests, waitlists, intake schedules, actual receipt and current linked pet status |
| Pet Deaths and Corrections | Private death entries, actual death dates, recording staff and retained corrections |
| Adopter Verification | Latest saved verification status and submission/review dates per adopter |
| Visit Appointments | Pending, confirmed, rejected, no-show, rescheduled and cancelled visits |
| Reschedule Requests | Original/proposed visit dates and staff decisions |
| Adoption Lifecycle | Scheduled, completed, cancelled and returned adoption records and permanent transaction references |
| Payments and Reviews | Payment status, actual amounts/receipts and separate death-related review flags |
| Pet Inventory | All current pet statuses, including deceased and other historical records |
| Applications | Application outcomes, cancellation/rejection reasons and corrected death notices |

## Filters and dates

Each report supports relevant status, date basis, inclusive date range and text
search filters. Pet-related reports support species. Payment reports also offer
required/resolved/not-required death-review filters. Date-time filters and
display use Asia/Manila, independent of server/browser timezone.

The date basis is explicit: a surrender can be filtered by request submission,
scheduled intake or actual receipt. A death entry can be filtered by actual
death date, recording date or correction date. Adoption reports can use schedule,
actual completion, actual return, cancellation or record-creation dates. Records
with no saved value for the selected date basis are excluded when a date bound
is applied; missing dates are never invented.

Verification reports describe the latest record per adopter, not a count of
every historical resubmission. The mortality report defaults to uncorrected
entries. Selecting All statuses includes retained corrections, with separate
Uncorrected deaths and Corrected entries counters. Corrected entries are never
counted as actual deaths.

Summary counts cover the whole filtered result, before pagination. Payment
completed-amount totals include completed transactions only. A resolved review
is independent of payment status; it is not evidence that a refund was issued.

## Tables and exports

Desktop tables and mobile cards display paginated records. Apply filters to
update results; downloads use those applied filters, including all matching
pages. Downloads and pagination wait until pending filter changes are applied.
CSV and server-rendered PDF use the same queryset/row definitions as the
table, without a 100/200-row export cap. CSV includes UTF-8 BOM and escapes
formula-like cells. PDFs include the date basis, applied filters, counts,
authenticated downloader and current Philippine generation timestamp.

Staff/admin API permissions protect metadata, results and both export formats.
Identity PDFs/selfies, surrender photos and internal narrative notes are not
bulk exported. Death cause and correction reason are available in this private
staff report. Reporting is read-only and does not change review state, money,
receipts, adoption status or other workflow records.

## API

- `GET /api/reports/operations/`: report options, columns and supported filters.
- `GET /api/reports/operations/{type}/`: paginated results, matching stats and
  report metadata. Types: surrenders, pet-deaths, verifications, appointments,
  reschedules, adoptions, payments, pets, applications.
- Parameters: `date_basis`, `date_from`, `date_to`, `status`, `search`, `species`,
  and (where supported) `pet` / `adopter` UUIDs and `review_status`.
- Explicit blank `status=` means all statuses. Omitted death-report status
  defaults to active (uncorrected) entries.
- Add `export=csv` or `export=pdf` to download all matching rows. Pagination
  parameters do not limit exports.

The existing six legacy report endpoints and monthly PDF endpoints remain
available. This extension adds no database models or migrations.

## Verification

From backend:

```powershell
..\venv\Scripts\python.exe manage.py test apps.reports --settings=config.settings.testing_postgresql --noinput
$env:PAWCONNECT_REPORT_BROWSER_TESTS='1'
..\venv\Scripts\python.exe manage.py test apps.reports.test_operational_browser --settings=config.settings.testing_postgresql --noinput
```

HTTP regressions cover real counts, corrections, Philippine date boundaries,
filter combinations, pagination, complete exports, money/review separation,
staff-only access, private-file exclusion, CSV formula escaping, long PDF text,
and unchanged source records. The opt-in live-browser walkthrough uses an
isolated PostgreSQL test server and a temporary Vite server; it verifies all
report choices, filtered CSV/PDF downloads beyond page one, date basis,
correction counts and mobile cards without touching development records.

Verified: full PostgreSQL suite, 720 tests (10 opt-in cases skipped); full SQLite
CI suite, 720 tests (21 database/browser cases skipped); the separate live
operational-report browser walkthrough; staff TypeScript/production build;
Django checks and migration checks. No new migration is required.
