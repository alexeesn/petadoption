# Death of a pet in center custody

User-approved scope extension, 2026-11-06. This records a pet's death while
in the center's custody; it is not a post-adoption mortality reporting feature.

## Staff workflow

Open Pets, choose **Record pet death**, enter the actual death date, confirmed
cause or Unknown, optional veterinarian and internal notes, then confirm custody
and the effects of the action. Dates follow the Philippine calendar and cannot
be in the future or before arrival / the latest recorded return to the center.

One transaction:

- Saves a private death entry with recording staff and timestamp.
- Sets the pet to `deceased`, excluding it from public list/search results.
- Cancels active applications with an adopter-visible, pet-related reason;
  these are cancellations, not adopter rejections.
- Cancels scheduled adoption records, active visits and pending reschedule
  requests, retaining their original dates, notes and history.
- Flags pending/completed payments associated with the affected adoption
  activities for staff review. Amounts, payment statuses, receipts, links, and
  original payment notes are retained; no automatic refund is issued.
- Preserves medical, vaccination, document, review and completed/returned
  adoption history. Earlier payments for a completed/returned adoption are not
  flagged as if they belonged to a newly cancelled adoption.
- Creates audit events and in-app notifications. Affected adopters receive a
  sensitive email after commit; private cause/veterinarian/notes are omitted.

Pets and Health Records show deceased pets in History. Pet inventory statistics
and CSV exports include the deceased status. A direct public pet URL remains
readable with an unavailable message and no Apply action. No death metadata is
serialized to the public/adopter API. New applications, reviews/approvals,
appointments and handover cannot advance a deceased pet's adoption.

Repeated death submissions while the pet is deceased return the saved entry
without repeating cancellations, notices or financial-review flags. Pet and
application row locks serialize death reporting against adoption activity.
Foreign-key inserts remain possible under PostgreSQL's non-key pet lock so an
already-running appointment action can finish before coordinated cancellation.

## Financial review

Payment Records has a **Payments requiring review after pet death** queue,
with pagination and mobile cards. Staff contact the adopter, determine any
applicable refund under center policy, and record a staff-only review outcome.
Resolving the flag does not change financial status or issue a refund. Actual
payment adjustments remain separate transactions/actions under existing policy.
The resolution and acting staff are audited.

## Correcting an incorrect entry

Administrators can open the saved **Death record**, choose **Correct mistaken
entry**, provide a reason and explicitly confirm. Staff/adopters cannot use
this action. The original death entry is retained with correction actor,
timestamp and reason. The pet returns to `for_assessment`, requiring staff
clearance before it can be offered again. Applications/visits remain cancelled,
and payment-review flags remain available for reconciliation. Affected adopters
receive a correction notice; their application page explains the correction.

Ordinary pet create/update cannot assign or remove deceased status. The Django
admin model validation also directs staff to the dedicated actions. Pet
deletion is protected by retained death records, including corrected entries.
Pets already adopted or associated with a current completed adoption cannot
use center-custody death reporting; completed adoptions stay historical.

## API and migrations

- `POST /api/pets/{id}/record-death/` (staff/admin): `death_date`, optional
  `cause` (default Unknown), `veterinarian`, `internal_notes`, and strict JSON
  boolean `confirmed: true`.
- `POST /api/pets/{id}/correct-death/` (admin): `reason`, `confirmed: true`.
- Staff `GET /api/pets/{id}/` includes private `death_records` and correction
  history. Public/adopter serializers omit that field entirely.
- `GET /api/payments/?death_review=required` lists flagged records (staff see
  all; normal adopter ownership restrictions still apply).
- `POST /api/payments/{id}/resolve-death-review/` (staff/admin): staff-only
  `note` and strict JSON boolean `confirmed: true`.

Run normal `python manage.py migrate`. New migrations add the pet status/death
record, application cancellation metadata, and payment-review fields. Existing
rows and financial references are not rewritten or backfilled.

## Verification

From backend:

```powershell
..\venv\Scripts\python.exe manage.py test apps.pets.test_deaths apps.pets.test_death_concurrency --settings=config.settings.testing_postgresql --noinput
$env:PAWCONNECT_DEATH_BROWSER_TESTS='1'
..\venv\Scripts\python.exe manage.py test apps.pets.test_death_browser --settings=config.settings.testing_postgresql --noinput
```

The opt-in browser check launches both Vite portals with headless Edge (or
PLAYWRIGHT_CHANNEL) against an isolated live Django test server. It checks mobile
confirmation, saved private details, History reload, public availability,
adopter cancellation messaging, payment-review resolution and administrator
correction, then verifies unchanged receipts and closed adoption records.
Development records are not used or modified by the walkthrough.

Verified: PostgreSQL full suite, 708 tests (9 opt-in cases skipped); SQLite CI
suite, 708 tests (20 database/browser cases skipped); a separate 73-test
lifecycle/payment regression run; the opt-in two-portal browser walkthrough;
both TypeScript/production builds; Django system and migration checks. The
adopter build retains its existing bundle-size warning.
