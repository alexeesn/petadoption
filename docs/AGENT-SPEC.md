# AGENT SPECIFICATION — Pet Adoption Management System

Status: **Specification only. No code, migrations, or dependencies have been created or modified.**
This document is implementation-ready and intended to be handed to a coding agent for build-out.

---

## 1. Project Overview

The Pet Adoption Management System (PAMS) is a two-sided platform connecting **adopters** with a shelter/organization's **staff and administrators**, managing the full adoption lifecycle: browsing pets, applying, document submission, staff review, optional package/payment handling, and adoption record completion.

It is not a generic CRUD demo. It must read as a real product with two distinct experiences:
- **Adopter side** — public-facing, warm, pet-focused browsing and application experience.
- **Staff/Admin side** — operational dashboard for managing pets, applications, reviews, health records, packages, payments, and reports.

Payment is a **secondary, optional module** — many adoptions are free, and the system must never block a workflow on payment.

---

## 2. Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React + TypeScript + Vite | SPA, no Next.js |
| Styling | Tailwind CSS | Single consistent design system, no ad-hoc CSS frameworks |
| Routing | React Router | Route guards per role |
| Backend | Django + Django REST Framework | Primary API and business-logic layer |
| Database | PostgreSQL | Managed hosting (e.g. Supabase) allowed for hosting only — Django remains the API layer, Supabase is never used as a REST/Auth replacement unless explicitly requested later |
| Auth | Django-based (existing module extended) | See §8 |
| Email | Django email backend, SMTP via env vars | Console/test backend for dev |
| VCS | Git + GitHub | Environment variables for all secrets |

**Explicitly excluded:** Node/Express as primary backend, MongoDB, MySQL, PHP, Firebase as primary backend, Next.js in place of Vite+React, Supabase as API/auth replacement.

---

## 3. Architecture

```
React + TypeScript + Tailwind + Vite  (SPA client)
              │  REST (JSON, JWT/session auth)
              ▼
     Django + Django REST Framework   (API + business logic + RBAC + validation)
              │
              ▼
          PostgreSQL                  (system of record)
              │
     ┌────────┴────────┐
     ▼                 ▼
  SMTP Email      File storage (documents/images,
  (async where     protected access, not public URLs)
  practical)
```

- Frontend never talks to the database directly.
- All authorization is enforced server-side in DRF (permission classes/viewset checks), never only hidden in the UI.
- File uploads (pet images, application documents) are stored with access mediated by Django, not raw public static URLs for private documents.

---

## 4. User Roles

### 4.1 Adopter
Register, verify email, log in/out, reset password, manage own profile, browse/search/filter pets, view pet details, submit applications, upload documents, track application status, receive in-app + email notifications, view own payment/package info, view own adoption records.

### 4.2 Staff
Everything an operational team member needs: manage adopters, pets, applications (review/approve/reject/request info), documents, packages, health records, adoption records, payments, and reports.

### 4.3 Administrator
Everything Staff can do, plus manage staff/user accounts and system-level settings, and access all reports.

Role is a field on the user account (`adopter` / `staff` / `admin`), enforced via DRF permission classes on every viewset — never inferred from the frontend route alone.

---

## 5. FDD Mapping

The uploaded Functional Decomposition Diagram and the written functional breakdown are **consistent with no meaningful discrepancies**. The diagram's ten Level-1 modules map 1:1 to the written spec's modules, and Level-2/3 items match. The diagram's numbering (1.0–10.0) is adopted as the canonical module numbering throughout this spec.

| FDD # | Module | Written Spec Section |
|---|---|---|
| 1.0 | Adopter Management | §9 |
| 2.0 | Pet Management | §10 |
| 3.0 | Adoption Application Management | §11 |
| 4.0 | Document Management | §14 |
| 5.0 | Staff Review Management | §12 |
| 6.0 | Adoption Package Management | §13 (packages) |
| 7.0 | Pet Health Management | §15 |
| 8.0 | Adoption Record Management | §16 |
| 9.0 | Report Management | §17 |
| 10.0 | Payment Management | §13 (payments) |

One structural note the diagram makes explicit and the agent must preserve: the dashed line from `0.0` to `10.0` ("payment issued for staff service rendered") confirms payment is triggered **by staff, per service rendered**, not an automatic step every application passes through. This matches §13's "payment is optional" business rule and must not be re-interpreted as a mandatory checkout step.

---

## 6. Core User Workflows

### 6.1 Free adoption path
```
Application Submitted → Staff Review → Approved → Adoption Record → Completed
(no package, no payment)
```

### 6.2 Paid / package adoption path
```
Application Submitted → Staff Review → Approved → Package Assigned
   → Payment (if package price > 0) → Adoption Record → Completed
```

### 6.3 Rejection / info-request path
```
Application Submitted → Staff Review → Request Additional Info → Adopter Updates
   → Staff Review (again) → Approved | Rejected
```

Rule: an `AdoptionRecord` can only be created from an application in `approved` status, and only after any assigned package's payment is either `not_applicable`, `paid`, or the package price is 0.

---

## 7. Authentication (§17 requirement — preserve existing module)

**Before writing any auth code**, the coding agent must audit the existing authentication implementation in the repo (models, serializers, views, token handling, email verification flow) and:
1. Document current behavior.
2. Preserve what already works.
3. Extend rather than replace where the existing logic is sound.
4. Only refactor pieces that are broken, insecure, or block requirements below.

Required capability set:
- Registration with email uniqueness check
- Email verification via OTP/code (expiring, attempt-limited)
- Login / logout
- Forgot password → OTP/code → reset
- Session/token handling appropriate to the existing implementation (JWT or Django session — do not switch mechanisms without cause)
- Account status handling: unverified, active, locked
- Login attempt throttling (lock or backoff after repeated failures)

Validation required on **both frontend and backend**:
- Required fields, email format, password strength
- Duplicate email → clear error, no account enumeration beyond necessity
- Invalid credentials → generic error (don't reveal whether email exists)
- Unverified account → block login, offer resend verification
- Locked account / too many attempts → explicit lockout message with retry guidance
- Invalid or expired OTP → distinct, clear errors
- Password mismatch on registration/reset

---

## 8. Email System

Environment-driven configuration only — never hard-code credentials:

```
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
DEFAULT_FROM_EMAIL
```

Dev environments use Django's console or file-based email backend; production uses SMTP.

Emails required:

| Category | Trigger |
|---|---|
| Account | Registration confirmation, email verification OTP, forgot-password OTP, password reset confirmation |
| Application | Submitted, status changed, approved, rejected, additional info requested |
| Adoption | Approved, completed, reminder (if scheduled) |
| Payment (only if applicable) | Payment request, payment confirmation, receipt |

---

## 9. Payment System

**Payment is optional and must never gate the adopter workflow when not applicable.**

Three supported modes, all of which the system must function without breaking if unavailable:

| Mode | Description |
|---|---|
| A — Free adoption | No payment record required, or a `Payment` row with status `not_applicable` |
| B — Manual payment | Staff records a payment against an application (amount, method, status) |
| C — Online payment | Optional gateway integration; system must degrade gracefully to Mode B if not configured |

Rules:
- A package price of ₱0 must not trigger any payment requirement.
- `AdoptionRecord` creation must not be blocked by an unresolved payment when the associated package is free or no package is assigned.
- Receipts (`receipt_number`, unique) are generated only for actual payments (status `paid`), not for free adoptions.

---

## 10. Data Model (PostgreSQL via Django ORM)

> Field lists below are the minimum required shape. The coding agent should reconcile with any existing models discovered in Phase 1 (§20) rather than blindly recreating tables that already exist in a different but compatible form.

**User** (extends existing auth model)
`id, email (unique), password_hash, role [adopter|staff|admin], is_active, is_verified, date_joined, last_login`

**AdopterProfile** (1:1 → User)
`full_name, contact_number, address, profile_photo, created_at, updated_at`

**Pet**
`id, name, species, breed, sex, age, size, color, description, personality, location, health_summary, status [available|pending|reserved|adopted|under_medical_care|inactive], created_by → User, created_at, updated_at`

**PetImage**
`id, pet → Pet (FK), image, is_primary, uploaded_at`

**AdoptionApplication**
`id, adopter → User (FK), pet → Pet (FK), status [draft|submitted|under_review|pending_documents|approved|rejected|cancelled|adoption_completed], household_info, living_situation, ownership_experience, reason_for_adoption, existing_pets, work_schedule_info, emergency_contact_name, emergency_contact_number, agreements_accepted (bool), submitted_at, updated_at`

**ApplicationDocument**
`id, application → AdoptionApplication (FK), document_type [valid_id|proof_of_residence|other], file, original_filename, file_size, mime_type, uploaded_by → User, uploaded_at`

**ApplicationReview**
`id, application → AdoptionApplication (FK), reviewer → User (FK, staff), decision [approve|reject|request_info|none], internal_notes (staff-only, never serialized to adopter-facing responses), adopter_visible_notes, previous_status, new_status, created_at`

**AdoptionPackage**
`id, name, description, included_items, price (decimal, ≥0), is_active, created_at, updated_at`

**ApplicationPackage**
`id, application → AdoptionApplication (1:1 or FK), package → AdoptionPackage (FK), assigned_by → User, assigned_at`

**PetHealthRecord**
`id, pet → Pet (FK), medical_history, veterinarian, notes, created_at, updated_at` — staff/admin visibility only

**Vaccination**
`id, health_record → PetHealthRecord (FK), vaccine_name, vaccination_date, next_due_date, administered_by, status [up_to_date|due_soon|overdue] (computed from next_due_date)`

**AdoptionRecord**
`id, application → AdoptionApplication (1:1), pet → Pet (FK), adopter → User (FK), adoption_date, status [approved|scheduled|completed|cancelled|returned], created_at, updated_at`

**Payment**
`id, application → AdoptionApplication (FK), package → AdoptionPackage (FK, nullable), amount, method [cash|gcash|bank_transfer|online|not_applicable], status [pending|paid|failed|cancelled|refunded|not_applicable], receipt_number (unique, nullable), processed_by → User (nullable), paid_at, created_at`

**Notification**
`id, user → User (FK), type, title, message, is_read, related_object_type, related_object_id, created_at`

**OTPVerification**
`id, user → User (FK), code_hash, purpose [email_verification|password_reset], expires_at, attempts, is_used, created_at`

**AuditLog**
`id, user → User (nullable), action, model_name, object_id, previous_value (JSON), new_value (JSON), timestamp`

**Integrity constraints:**
- Unique email on User.
- A pet cannot have two simultaneously "active" applications assigned to it in a conflicting state (enforce via status checks + DB constraint/partial unique index where practical).
- `AdoptionRecord` requires application.status == `approved` at creation time (enforced in serializer/view logic, not just UI).
- `Payment.package` if set must belong to the same application's assigned package.

---

## 11. API / Backend Structure

Base namespaces (DRF viewsets/routers), all versioned and paginated:

```
/api/auth/            register, login, logout, verify-email, forgot-password, reset-password
/api/adopters/         profile CRUD (self), staff list/detail
/api/pets/             list, retrieve, create, update, status
/api/applications/     submit, list (own/staff-all), retrieve, update-status, assign-pet
/api/documents/        upload, list, download, delete
/api/reviews/          create review, list history
/api/packages/         CRUD, assign-to-application
/api/health-records/   CRUD, vaccinations sub-resource
/api/adoptions/        create record, list, update-status
/api/payments/         create/record, receipt, history, update-status
/api/reports/          adoption, pet-inventory, adopter, application, health, payment
/api/notifications/    list (own), mark-read
```

Standards across all endpoints:
- Consistent JSON envelope for success/error responses.
- DRF pagination (page-number or cursor) on all list endpoints.
- Filtering/search/sorting via query params on pets, applications, and reports.
- Field-level and object-level permission checks (e.g., an adopter retrieving `/applications/{id}/` must own it; a 403/404 otherwise — prefer 404 to avoid leaking existence).
- Internal-only fields (e.g., `internal_notes`) excluded from adopter-facing serializers entirely, not just hidden client-side.

---

## 12. Staff Review Management

- `ApplicationReview` records reviewer, decision, timestamps, and both internal and adopter-visible notes as **separate fields** — the serializer used for adopter-facing endpoints must never include `internal_notes`.
- Decisions: approve, reject, request additional info — each writes a review record and updates `AdoptionApplication.status`.
- Approve/reject actions require a confirmation step in the UI (not a bare button click).
- Full review history is queryable per application: reviewer, timestamp, decision, notes, previous/new status.

---

## 13. Packages & Payments (see also §9)

- `AdoptionPackage` is independent of any application until assigned via `ApplicationPackage`.
- Packages can be priced at ₱0 — this is a first-class case, not an edge case.
- Payment records only make sense in the context of an assigned package or a standalone staff-service charge; a `Payment` without a valid `application` reference should be rejected.
- Payment status transitions (`pending → paid|failed|cancelled|refunded`) are staff/admin-only actions.

---

## 14. Document Management

- Upload validated on: file size limit, allowed extensions, and actual MIME/content-type sniffing (not just extension).
- Files stored with generated/secure filenames (not user-supplied names) and served through an authenticated Django view/endpoint — never a public static path for private documents.
- Access rules: adopter can view/download only their own documents; staff/admin can view/download documents tied to applications they're authorized to review.
- Delete is permission-controlled and should soft-delete or log via `AuditLog` rather than silently hard-deleting evidence of a decision trail, unless the org's policy requires hard delete.

---

## 15. Pet Health Management

- `PetHealthRecord` and `Vaccination` are staff/admin-only in both API and UI — never exposed to adopter-facing endpoints/serializers, even in a read-only reduced form, unless a product decision later says otherwise.
- Vaccination status (`up_to_date` / `due_soon` / `overdue`) is computed server-side from `next_due_date` against current date — do not store it as a manually-set field that can drift out of sync.

---

## 16. Adoption Records

- Created only from an `approved` application.
- Status flow: `approved → scheduled → completed`, with `cancelled` / `returned` as terminal or re-entry states depending on org policy (default: terminal, pet status reverts to `available` on `returned`).
- When an `AdoptionRecord` reaches `completed`, the linked `Pet.status` must be synchronized to `adopted`.

---

## 17. Reports

Types: adoption, pet inventory, adopter, application, health record, payment.

Each supports (where relevant): date range, pet, status, application status, adopter, payment status filters. Output as table view in UI plus CSV export; PDF export only where practical to maintain (do not over-engineer print layouts for a v1).

---

## 18. Notifications

In-app `Notification` rows generated alongside the email triggers in §8 (submitted, status changed, documents required, approved, rejected, payment status changed, adoption completed). Adopter dashboard surfaces unread notifications; staff dashboard is not required to duplicate this unless useful for review queue awareness.

---

## 19. Role-Based Access Control

| Resource | Adopter | Staff | Admin |
|---|---|---|---|
| Own profile | R/W | — | — |
| Other adopters' profiles | ✗ | R/W | R/W |
| Pets | R (public) | R/W | R/W |
| Own applications | R/W (create/track) | R (all) / W (status) | R/W |
| Documents | R/W (own) | R/W (authorized) | R/W |
| Reviews | R (visible notes only, own applications) | R/W | R/W |
| Packages | R (assigned to own application) | R/W | R/W |
| Health records | ✗ | R/W | R/W |
| Adoption records | R (own) | R/W | R/W |
| Payments | R (own) | R/W | R/W |
| Reports | ✗ | R | R |
| Staff/user accounts | ✗ | ✗ | R/W |

All of the above enforced in DRF permission classes / viewset `get_queryset` and `has_object_permission` — the frontend hiding a button is not sufficient anywhere in this table.

---

## 20. Security Requirements

- Password hashing (Django default hasher, do not weaken).
- Role-based authorization enforced backend-side (§19).
- Input validation/sanitization on every write endpoint, frontend and backend.
- Secure file upload handling (§14).
- CSRF protection where session auth is used; CORS configured explicitly for the frontend origin(s), not wildcard in production.
- Rate limiting on login, registration, OTP request/verify, and password reset endpoints.
- OTP: securely generated, expiring, attempt-limited.
- Login attempt protection (lockout/backoff).
- All secrets via environment variables: never commit `SECRET_KEY`, DB credentials, SMTP credentials, payment provider keys, or API keys.
- Error responses never leak stack traces, SQL, or internal paths in production mode.

---

## 21. Adopter-Facing UI/UX

- **Landing/Home:** what the org does, featured/available pets, adoption process explanation, CTA.
- **Pet listing:** card grid — image, name, breed, age, gender, availability, short description; search + filters + sort.
- **Pet details:** gallery, personality, health summary (public-safe subset only — no internal medical notes), availability, apply CTA.
- **Adopter dashboard:** active applications + statuses, required documents, notifications, adoption progress. No vanity/admin-style stats here.

Must not resemble an admin dashboard — separate visual treatment from staff side.

---

## 22. Staff/Admin UI/UX

Dashboard-oriented: Dashboard, Applications, Pets, Adopters, Documents, Reviews, Health Records, Adoption Records, Packages, Payments, Reports, Notifications.

Dashboard metrics limited to meaningful operational numbers: available pets, pending applications, under-review count, approved count, completed adoptions, documents awaiting review. No fabricated/placeholder stats.

---

## 23. Design System (Tailwind-based)

Single consistent system for: typography scale, spacing scale, border radius, buttons, inputs/selects, cards, tables, modals, badges (status pills), alerts, nav/sidebar, form layout, loading/empty/error states.

Visual direction: modern, clean, friendly, professional, pet-focused, distinctive — not a generic blue admin theme, not overloaded with gradients/glassmorphism/animation. Subtle organic motifs (paw prints, rounded shapes) are acceptable in moderation; keep it professional rather than childish.

---

## 24. Responsive Design

Desktop, laptop, tablet, and mobile must all be genuinely usable — not just a shrunk desktop layout. Requires: mobile nav pattern, responsive tables (e.g. card-collapse on small screens), responsive forms, touch-friendly controls, appropriate spacing at each breakpoint.

---

## 25. Accessibility

Proper form labels, full keyboard navigation, visible focus states, sufficient color contrast, accessible buttons/controls, meaningful alt text on pet images, status conveyed with more than color alone (icon/text + color), clear error messaging tied to fields via `aria-describedby` or equivalent.

---

## 26. Validation Summary

Applied on both frontend (immediate UX feedback) and backend (source of truth):
- Registration/auth fields (§7)
- Pet fields (required core attributes, sane numeric ranges for age)
- Application fields (required fields per org policy, consent checkbox required)
- Document upload (type, size, MIME)
- Package price ≥ 0
- Payment amount > 0 when status is `paid`
- Status transition legality (e.g., an application cannot jump from `draft` directly to `adoption_completed`)

---

## 27. Business Rules (authoritative list)

1. A pet marked `adopted` cannot remain `available`.
2. An application not in `approved` status cannot produce a completed `AdoptionRecord`.
3. A pet cannot be assigned to two conflicting active applications simultaneously.
4. Payment is never mandatory for a free adoption.
5. A ₱0 package requires no payment action.
6. Staff-only functionality is inaccessible to adopters at the API level, not just hidden in UI.
7. Adopters cannot access another adopter's records or documents.
8. Internal staff review notes are never exposed to adopters.
9. A `Payment` must reference a valid application/package combination.
10. Status transitions for applications, pets, and adoption records are validated against an explicit allowed-transitions map, not free-form.
11. Historical/audit records remain intact even after a related pet becomes `inactive`.

---

## 28. Audit / History

`AuditLog` captures: acting user, action, model + object id, previous value, new value, timestamp — for at minimum: application status changes, review decisions, pet status changes, payment status changes, adoption status changes.

---

## 29. Development Phases

1. **Codebase audit** — inspect existing structure, models, migrations, auth, API, React components, Tailwind config, routes, env config. Identify what to reuse vs. refactor. No rewrites without justification.
2. **Foundation** — DB base, auth, authorization, email verification, core layout, design system.
3. **Adopter management** — registration, login, verification, profile, dashboard shell.
4. **Pet management** — CRUD, images, search/filter, status, details page.
5. **Applications** — submission, tracking, documents, workflow states.
6. **Staff review** — review dashboard, notes, approve/reject, history, pet assignment.
7. **Health + adoption** — health records, vaccinations, packages, adoption records.
8. **Optional payments** — payment records, statuses, receipts, history, optional gateway hook.
9. **Reports** — all six report types with filtering and export.
10. **UI/UX polish** — responsiveness, states (loading/empty/error/success), accessibility, navigation/form consistency.
11. **Testing** — full workflow pass (§30).

---

## 30. Testing Requirements

- **Auth:** registration, duplicate email, verification, login (valid/invalid), logout, forgot/reset password, OTP expiry/attempt limits, lockout.
- **Pets:** create/update, search/filter, status changes, image upload.
- **Applications:** submit + validation, conflicting-assignment scenarios, status transitions, pet assignment, document upload.
- **Staff review:** review, notes, approve/reject, info-request, history.
- **Adoption:** approved → record → status tracking → pet status sync.
- **Payment:** free path, ₱0 package path, manual payment, status updates, receipt generation, history.
- **Email:** verification, reset, application-status, payment (when applicable).
- **Security:** unauthorized access attempts, role boundary checks, document access boundaries, API-level authorization, input validation edge cases.
- **UI:** desktop/tablet/mobile passes, loading/empty/error states.

---

## 31. Acceptance Criteria (end-to-end scenario)

1. Adopter registers → validated → email uniqueness checked → verification email sent.
2. Adopter verifies email → logs in.
3. Adopter browses pets → views a pet's details.
4. Adopter submits an application → uploads required documents.
5. Staff sees and reviews the application, adds notes, and approves/rejects/requests info.
6. On approval, a pet can be assigned/confirmed and a package optionally attached.
7. If free, no payment step occurs. If paid, payment is recorded and a receipt generated.
8. An `AdoptionRecord` is created post-approval and its status tracked to completion.
9. Relevant emails fire at each major transition.
10. Staff can generate reports across all six report types.
11. At every step, users only see/act on data their role and ownership permit.

---

## 32. Definition of Done

- All FDD modules (1.0–10.0) implemented and functionally verified.
- Auth, verification, password recovery, and RBAC all work end-to-end.
- Pet, application, document, review, health, package, adoption, and payment modules all work per this spec.
- Optional payment/package logic never becomes mandatory.
- Emails and in-app notifications fire correctly.
- Reports generate correctly with working filters/export.
- DB relationships and constraints hold (no orphaned/duplicate/invalid states).
- Frontend and backend validation both present and consistent.
- Security requirements (§20) implemented.
- Responsive across breakpoints; no major console or backend errors.
- Migrations run cleanly; main workflows (§31) manually or automatically tested.

---

*End of specification. Next natural step, if useful: a short `AGENTS.md`/`CLAUDE.md` at the repo root that points a coding agent at this document plus the concrete build/test commands once the codebase audit (Phase 1) is complete.*
