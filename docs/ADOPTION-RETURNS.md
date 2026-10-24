# Adoption returns

Staff/admin can open **Adoption Records**, find a **Completed** adoption and
select **Mark as Returned**. A reason (up to 2,000 characters, visible to the
adopter) and confirmation that the shelter physically received the pet are
required. Scheduled/cancelled records cannot be marked as returned.

The backend records the return atomically:

- Adoption status becomes `returned`; reason, Philippine return date and
  recording timestamp are persisted.
- Pet status becomes `for_assessment`, keeping the pet off the adopter homepage and available-pet catalog until staff clear it. A
  conflicting active adoption blocks the return rather than releasing its pet.
- Original completion dates, staff attribution and transaction ID are retained.
  The original application stays `adoption_completed` as historical evidence.
- Payment rows, amounts, statuses, adoption links and receipt numbers stay
  unchanged. Returning a pet does not issue a refund or create a payment.
- Adoption and pet status changes are audited. The adopter receives an in-app
  notification and an email dispatched after commit through Django's configured
  transport. The adopter's adoption record displays the reason and return date.

Retries preserve the first reason/timestamps and do not repeat notifications,
audits or release a pet that has since been adopted again. Return fields are
read-only through ordinary record edits. Existing historical return rows are
not backfilled. This feature uses existing model fields; no new migration is
needed.

## Assessment after return

Returned pets appear in **Pets > Active > Status: For Assessment**, and their existing medical records return to **Health Records > Active**. Record assessment findings through the normal explicit health-record Edit/Save flow. In **Pets > Edit > Care status**, choose **Under Medical Care** when treatment is needed, or **Available** after the pet is cleared. Medical care can later be changed to Available through the same control. Saving a care-status change creates a pet-status audit entry.

For Assessment and Under Medical Care pets cannot receive new adoption applications or approvals, and cannot complete a stale approved adoption. Direct adopter links show an unavailable message. Clearing the pet does not reopen the original application or alter the returned adoption, payment, receipt or medical history. A retry of the original return preserves any later care decision.

Migration `pets/0006_add_for_assessment_status` adds the status choice without rewriting existing pet or return records. Existing returned pets can be placed For Assessment manually through Pets > Edit > Care status when review is needed.

## PDF downloads

Returned records offer **Download Return PDF** in the staff Adoption Records
table. Their Status column shows only the Returned badge; the reason and return
messages are omitted from the table. The PDF is a return acknowledgment
containing the saved reason, actual
return date/timestamp, original completion date/staff and permanent transaction
reference. It retains the payment-history/no-automatic-refund statement.
Historical rows without a return date display **Not recorded**; downloading
never invents or changes their return dates.

Cancelled records also offer **Download Cancellation PDF**, containing the
saved cancellation reason/time, original schedule, adopter and pet information,
and a statement that cancellation does not issue a refund. Existing historical
rows without a cancellation timestamp display **Not recorded**.

All six generated PDF downloads (individual adoption/return/cancellation record, individual
payment receipt, adoption export, payment export and both monthly reports) show:

- **Downloaded by:** the authenticated staff/admin's current name, email and
  role. This is separate from the staff who originally completed/processed the
  transaction, and cannot be supplied through query parameters.
  Lowercase name parts are capitalized for display (for example, `alexis
  teodosio` becomes `Alexis Teodosio`) consistently across PDF attribution,
  signatures and transaction text. Existing mixed-case names and email addresses
  are preserved; account data is not changed.
- **Generated on:** the current date/time in Philippine time, explicitly
  labeled `PHT (UTC+08:00)`. Original transaction/return dates stay historical.

Each download is generated afresh with `Cache-Control: private, no-store`.
Only rendering changes; original record, payment, receipt and audit data are
not mutated by a download.

## API

`POST /api/adoptions/{id}/mark-returned/` (staff/admin):

```json
{
  "return_reason": "Adopter developed allergies",
  "confirmed": true
}
```

Legacy `PATCH /api/adoptions/{id}/` with `status: "returned"` uses the same
service and requires the same reason and strict boolean confirmation.
`GET /api/adoptions/?status=returned` filters persisted returned records.

`GET /api/adoptions/{id}/record-pdf/` (staff/admin) returns a certificate for
Completed records, a return acknowledgment for Returned records, or a
cancellation acknowledgment for Cancelled records. Scheduled records still
return HTTP 400. Return PDF filenames use
`pawconnect-adoption-return-{transaction-reference}.pdf`; cancellation filenames
use `pawconnect-adoption-cancelled-{transaction-reference-or-short-record-id}.pdf`.

## Verification

From `backend`, run HTTP regressions against an isolated PostgreSQL database:

```powershell
../venv/Scripts/python.exe manage.py test apps.adoptions.test_returns apps.adoptions.tests.AdoptionBusinessRuleTests --settings=config.settings.testing_postgresql --noinput
```

Run the browser walkthrough against a real isolated Django server:

```powershell
$env:PAWCONNECT_BROWSER_TESTS='1'
$env:PLAYWRIGHT_CHANNEL='msedge'
../venv/Scripts/python.exe manage.py test apps.adoptions.test_return_browser --settings=config.settings.testing_postgresql --noinput
```

The walkthrough starts both portals on ports 5190/5191 using isolated fixture
accounts. It completes an adoption, verifies mobile confirmation and failed-save
handling, records a return, reloads/filters it, checks pet availability and
unchanged payments, and verifies the adopter's return details and staff receipt.
It also downloads a Returned PDF through the mobile staff UI and checks that
the file is a PDF with the expected filename and that saved history is unchanged.
It requires the existing npm dependencies and a Playwright-compatible browser.
Existing development data is not modified.

Verified for this change:

- 20 return/lifecycle HTTP regressions passed on PostgreSQL.
- Full PostgreSQL suite after the cancellation PDF update: 606 tests, 601 passed and 5 opt-in cases skipped.
- Full SQLite suite (CI settings) after the cancellation PDF update: 606 tests, 594 passed and 12
  PostgreSQL/browser-only cases skipped.
- The opt-in return browser walkthrough passed separately against PostgreSQL,
  including both portals, a 390px viewport and a failed-save retry.
- Both portals passed TypeScript/production builds. The adopter portal retains
  its existing bundle-size warning.
- Django system checks, migration checks and diff whitespace checks passed.
- All 11 PDF metadata/return/cancellation-document regressions passed, and the staff portal
  passed its production build after adding Download Return PDF.

PDF HTTP/content regressions can be run separately:

```powershell
../venv/Scripts/python.exe manage.py test apps.reports.test_pdf_downloads --settings=config.settings.testing_postgresql --noinput
```

These verify each PDF endpoint's downloader identity and current Philippine
timestamp (including UTC midnight rollover), retained original staff attribution,
immutable transaction/payment history, return PDF permissions, missing historical
dates, and wrapping of long reasons/names.

The full suite also exposed an outdated staff RBAC test fixture that attempted
to create a second health record for a pet that already had one. That test now
uses an eligible pet; health-record production behavior was not changed.
