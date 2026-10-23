# Household pets and application entry

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
