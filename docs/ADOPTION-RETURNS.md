# Adoption returns

Staff/admin can open **Adoption Records**, find a **Completed** adoption and
select **Mark as Returned**. A reason (up to 2,000 characters, visible to the
adopter) and confirmation that the shelter physically received the pet are
required. Scheduled/cancelled records cannot be marked as returned.

The backend records the return atomically:

- Adoption status becomes `returned`; reason, Philippine return date and
  recording timestamp are persisted.
- Pet status becomes `available`, allowing another adopter to apply. A
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
It requires the existing npm dependencies and a Playwright-compatible browser.
Existing development data is not modified.

Verified for this change:

- 20 return/lifecycle HTTP regressions passed on PostgreSQL.
- Full PostgreSQL suite: 584 tests, 579 passed and 5 opt-in cases skipped.
- Full SQLite suite (CI settings): 584 tests, 572 passed and 12
  PostgreSQL/browser-only cases skipped.
- The opt-in return browser walkthrough passed separately against PostgreSQL,
  including both portals, a 390px viewport and a failed-save retry.
- Both portals passed TypeScript/production builds. The adopter portal retains
  its existing bundle-size warning.
- Django system checks, migration checks and diff whitespace checks passed.

The full suite also exposed an outdated staff RBAC test fixture that attempted
to create a second health record for a pet that already had one. That test now
uses an eligible pet; health-record production behavior was not changed.
