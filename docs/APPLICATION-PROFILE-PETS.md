# Household pets and application entry

## Required identity and minimum age

My Profile displays and edits **First Name**, **Last Name** and **Date of Birth** as required fields. Names use the existing account fields and save atomically with the profile, so account displays, staff application reviews and emails use the same name. The adopter portal updates its cached account name immediately after a successful profile save.

Birthday must establish an age of at least **18** using the current **Asia/Manila** date; the eighteenth birthday itself is accepted. The browser supplies date bounds and inline errors, while Django independently validates profile writes and the profile-completeness gate for new applications. The existing 120-year sanity limit is retained. Missing or underage legacy birthdays make a profile incomplete without changing its saved data or existing adoption history. No schema migration or birthday backfill is required.

The real HTTP regressions cover required identity, failed-save rollback, ownership, Philippine midnight and leap-day boundaries. The opt-in browser test (`PAWCONNECT_PROFILE_BROWSER_TESTS=1`, `apps.adopters.test_browser`) checks required fields, underage rejection, an exact eighteenth birthday, save/reload, account-name synchronization, staff visibility, the application gate and mobile Cancel against an isolated database.

## Household pets

The adopter enters existing-pet information in **Profile** only. New Adoption
Application no longer asks "I currently have other pets" or repeats the related
description field and validation on its Application/Review steps.

When an application is submitted, Django copies the saved profile's
`has_other_pets` and `other_pets` into the application's existing
`has_other_pets` and `other_pets_description` fields. This keeps a submission-time
record available to staff. The description is empty when the profile says the
adopter has no other pets. Duplicate client-supplied form fields are ignored;
ordinary application edits cannot overwrite this information.

Updating the profile affects subsequent applications, while existing
applications retain the originally submitted information. Existing model fields
and records are preserved; no migration or backfill is needed.

The staff **Payment Records** filter and legend now offer only **All statuses**
and **Completed**, and no longer advertise Pending, Failed, Refunded or Cancelled
options. This is a UI change: historical payment rows and backend status values
are retained. The onsite recording flow continues to save received payments as
Completed, and adoption cancellation/return does not issue a refund.

Cancelled **adoption** records remain a separate lifecycle state and now have a
staff-only cancellation PDF; see `docs/ADOPTION-RETURNS.md`.

Validation passed: full backend suites on PostgreSQL (606 tests, 5 skipped) and
SQLite (606 tests, 12 skipped), both portal production builds, all four Payment
Records browser regressions, and a real two-portal browser walkthrough against
an isolated PostgreSQL server. The walkthrough checks the removed duplicate
question, payment filter choices and cancellation PDF download. HTTP regressions
verify profile-based application snapshots and cancellation PDF content/access.
