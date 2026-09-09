# AGENTS.md

# PET ADOPTION MANAGEMENT SYSTEM

## Coding Agent Instructions

> **IMPORTANT:** This is a brand-new project being built from scratch.
> There is no existing implementation to preserve.
>
> The authoritative functional specification is:
>
> `docs/AGENT-SPEC.md`
>
> Read that file completely before implementing any feature.

---

# 1. PROJECT OBJECTIVE

Build a complete **Pet Adoption Management System (PAMS)** based on the Functional Decomposition Diagram (FDD) and the detailed specification in:

```text
docs/AGENT-SPEC.md
```

The system must support three roles:

* Adopter
* Staff
* Administrator

The system must manage the complete adoption lifecycle:

```text
Registration
→ Email Verification
→ Login
→ Browse Pets
→ Application
→ Documents
→ Staff Review
→ Approval / Rejection / Additional Information
→ Optional Package
→ Optional Payment
→ Adoption Record
→ Adoption Completion
```

This must be treated as a real application, not a generic CRUD demonstration.

---

# 2. NON-NEGOTIABLE ARCHITECTURE

This project MUST have:

```text
ONE Django backend
+
TWO separate React frontends
+
ONE PostgreSQL database
```

The exact high-level structure is:

```text
pet-adoption/
│
├── backend/
│
├── adopter-portal/
│
├── staff-portal/
│
├── docs/
│
├── AGENTS.md
├── README.md
├── .gitignore
└── .env.example
```

## CRITICAL

There must be **NO generic `frontend/` directory**.

Do NOT combine the two frontend applications.

Do NOT create:

```text
frontend/
```

instead of:

```text
adopter-portal/
staff-portal/
```

The two frontend applications are intentional and must remain separate.

---

# 3. TECHNOLOGY STACK

## Adopter Portal

Use:

* React
* TypeScript
* Vite
* Tailwind CSS
* React Router

## Staff Portal

Use:

* React
* TypeScript
* Vite
* Tailwind CSS
* React Router

## Backend

Use:

* Python
* Django
* Django REST Framework

## Database

Use:

* PostgreSQL
* Django ORM
* Django migrations

## Communication

Both React applications communicate with the same Django REST API.

```text
adopter-portal
       │
       │ REST API
       ▼
    Django
       │
       ▼
 PostgreSQL
       ▲
       │
    Django
       ▲
       │ REST API
       │
 staff-portal
```

The frontend applications must NEVER connect directly to PostgreSQL.

---

# 4. TECHNOLOGIES THAT MUST NOT REPLACE THE STACK

Do NOT replace the required architecture with:

* Node.js / Express as backend
* PHP
* Laravel
* MongoDB
* MySQL
* Firebase as primary backend
* Supabase Auth
* Supabase REST API
* Next.js
* Another frontend framework
* Another backend framework

Supabase MAY be used as managed PostgreSQL hosting.

However, the architecture must remain:

```text
React
  ↓
Django REST Framework
  ↓
PostgreSQL
```

Supabase must NOT replace Django's API, authentication, permissions, or business logic.

---

# 5. DIRECTORY STRUCTURE

Use the following architecture as the default.

```text
pet-adoption/
│
├── AGENTS.md
├── README.md
├── .gitignore
├── .env.example
│
├── docs/
│   └── AGENT-SPEC.md
│
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   │
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── development.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   └── wsgi.py
│   │
│   ├── apps/
│   │   ├── accounts/
│   │   ├── adopters/
│   │   ├── pets/
│   │   ├── applications/
│   │   ├── documents/
│   │   ├── reviews/
│   │   ├── packages/
│   │   ├── health/
│   │   ├── adoptions/
│   │   ├── payments/
│   │   ├── reports/
│   │   ├── notifications/
│   │   └── audit/
│   │
│   ├── media/
│   └── tests/
│
├── adopter-portal/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── assets/
│       ├── components/
│       ├── layouts/
│       ├── pages/
│       ├── features/
│       │   ├── auth/
│       │   ├── pets/
│       │   ├── applications/
│       │   ├── documents/
│       │   ├── notifications/
│       │   ├── payments/
│       │   └── profile/
│       ├── hooks/
│       ├── services/
│       ├── routes/
│       ├── types/
│       ├── utils/
│       ├── lib/
│       ├── App.tsx
│       └── main.tsx
│
└── staff-portal/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── index.html
    └── src/
        ├── assets/
        ├── components/
        ├── layouts/
        ├── pages/
        ├── features/
        │   ├── dashboard/
        │   ├── applications/
        │   ├── pets/
        │   ├── adopters/
        │   ├── documents/
        │   ├── reviews/
        │   ├── health/
        │   ├── adoptions/
        │   ├── packages/
        │   ├── payments/
        │   ├── reports/
        │   └── notifications/
        ├── hooks/
        ├── services/
        ├── routes/
        ├── types/
        ├── utils/
        ├── lib/
        ├── App.tsx
        └── main.tsx
```

The exact internal structure may be adjusted if there is a strong engineering reason, but the following MUST remain:

```text
adopter-portal/
staff-portal/
backend/
```

---

# 6. RESPONSIBILITY OF EACH APPLICATION

## adopter-portal

This is the adopter-facing application.

It handles:

* Public homepage
* Pet browsing
* Pet search
* Pet filtering
* Pet details
* Registration
* Login
* Email verification
* Password recovery
* Adopter profile
* Adoption applications
* Document uploads
* Application tracking
* Notifications
* Assigned package information
* Payment information
* Adoption records

The adopter portal must feel like a modern pet adoption website.

It must NOT look like an administrative dashboard.

---

# 7. staff-portal

This is the operational application for Staff and Administrators.

It handles:

* Dashboard
* Applications
* Application review
* Pet management
* Adopter management
* Documents
* Health records
* Adoption records
* Packages
* Payments
* Reports
* Notifications
* Staff management for administrators

The staff portal should have a professional operational dashboard.

---

# 8. SHARED BACKEND

Both portals use the same Django REST API.

Example:

```text
adopter-portal
      ↓
/api/auth/
/api/pets/
/api/applications/
/api/documents/
/api/notifications/
      ↓
Django REST Framework
```

and:

```text
staff-portal
      ↓
/api/pets/
/api/applications/
/api/reviews/
/api/adopters/
/api/health-records/
/api/reports/
/api/payments/
      ↓
Django REST Framework
```

Do not duplicate business logic between the two frontends.

Business rules belong primarily in Django.

---

# 9. FDD IS THE SOURCE OF TRUTH

Implement all ten FDD modules:

```text
1.0 Adopter Management
2.0 Pet Management
3.0 Adoption Application Management
4.0 Document Management
5.0 Staff Review Management
6.0 Adoption Package Management
7.0 Pet Health Management
8.0 Adoption Record Management
9.0 Report Management
10.0 Payment Management
```

Read:

```text
docs/AGENT-SPEC.md
```

for the complete functional requirements.

Do not omit modules simply because they are not part of the public adopter experience.

---

# 10. DEVELOPMENT STRATEGY

Do not attempt to build the entire system in one pass.

Implement incrementally.

Required order:

```text
Phase 1
Foundation
↓
Phase 2
Authentication + RBAC
↓
Phase 3
Adopter Management
↓
Phase 4
Pet Management
↓
Phase 5
Applications
↓
Phase 6
Documents + Reviews
↓
Phase 7
Health + Adoption
↓
Phase 8
Packages + Optional Payments
↓
Phase 9
Reports
↓
Phase 10
Notifications + UI/UX
↓
Phase 11
Testing + Final Audit
```

After every major phase:

1. Run the application.
2. Run tests/checks.
3. Fix errors.
4. Verify the feature.
5. Only then proceed.

---

# 11. PHASE 1 — FOUNDATION

Create:

### Backend

* Django project
* DRF
* PostgreSQL connection
* Environment configuration
* Base API routing
* Application structure
* Development configuration
* Production configuration

### Frontends

Create BOTH:

```text
adopter-portal
staff-portal
```

Each must be an independent:

```text
React + TypeScript + Vite + Tailwind
```

application.

Configure:

* TypeScript
* Vite
* Tailwind
* React Router
* API service foundation
* Environment variables

Verify:

```text
adopter-portal runs
staff-portal runs
backend runs
PostgreSQL connects
```

---

# 12. AUTHENTICATION

Implement authentication using Django.

Required:

* Registration
* Email uniqueness
* Password validation
* Email verification
* OTP
* OTP expiration
* OTP attempt limits
* Login
* Logout
* Forgot password
* Password reset
* Account status
* Login throttling
* Lockout/backoff

Roles:

```text
adopter
staff
admin
```

---

# 13. AUTH VALIDATION

Validate on BOTH:

```text
Frontend
+
Backend
```

Validate:

* Required fields
* Email format
* Password strength
* Password confirmation
* Duplicate email
* Invalid credentials
* Unverified account
* Locked account
* Invalid OTP
* Expired OTP
* OTP attempts

Do not expose unnecessary account enumeration information.

---

# 14. ROLE-BASED ACCESS CONTROL

Backend authorization is mandatory.

Frontend route protection is only a UX mechanism.

Never trust frontend role values.

Django/DRF must enforce:

```text
Adopter
Staff
Admin
```

permissions.

An adopter must never be able to access staff functionality simply by manually navigating to a staff URL or directly calling the API.

---

# 15. ADOPTER OWNERSHIP

Adopters may only access their own:

* Profile
* Applications
* Documents
* Notifications
* Payments
* Adoption records

An adopter must not be able to access another adopter's resources by modifying IDs.

Use object-level permission checks.

---

# 16. PET MANAGEMENT

Pet statuses:

```text
available
pending
reserved
adopted
under_medical_care
inactive
```

Implement:

* Create
* Update
* View
* Search
* Filter
* Sort
* Images
* Status management

An adopted pet cannot remain available.

---

# 17. APPLICATION MANAGEMENT

Statuses:

```text
draft
submitted
under_review
pending_documents
approved
rejected
cancelled
adoption_completed
```

Implement explicit legal status transitions.

Do not allow arbitrary status changes.

Applications must support:

* Pet selection
* Application details
* Submission
* Validation
* Tracking
* Staff review
* Additional information requests
* Approval
* Rejection

---

# 18. DOCUMENT MANAGEMENT

Documents must be private.

Validate:

* File size
* Extension
* MIME type
* Actual content type

Use generated secure filenames.

Do not expose private documents through public static URLs.

Access must be authorized through Django.

---

# 19. STAFF REVIEWS

Staff must be able to:

* View applications
* Review applications
* Add notes
* Approve
* Reject
* Request additional information
* View review history

Maintain two separate fields:

```text
internal_notes
adopter_visible_notes
```

`internal_notes` must NEVER be serialized to adopter-facing API responses.

---

# 20. HEALTH RECORDS

Health records are:

```text
Staff/Admin only
```

Implement:

* Health records
* Medical history
* Veterinarian information
* Notes
* Vaccinations
* Vaccination dates
* Next due dates
* Computed vaccination status

Vaccination status must be calculated server-side.

---

# 21. ADOPTION RECORDS

An AdoptionRecord may only be created when:

```text
application.status == approved
```

Never rely only on frontend validation for this rule.

Status flow:

```text
approved
→ scheduled
→ completed
```

Possible terminal/re-entry states:

```text
cancelled
returned
```

When adoption becomes completed:

```text
Pet.status = adopted
```

must be synchronized appropriately.

---

# 22. OPTIONAL PAYMENT SYSTEM

Payment is OPTIONAL.

This is a critical business rule.

The system must support:

### Free adoption

```text
No package
→ No payment
```

or:

```text
₱0 package
→ No payment required
```

### Manual payment

Staff records:

* Amount
* Method
* Status
* Receipt

### Optional online payment

An online gateway may be added.

If it is not configured:

```text
The rest of the system must continue functioning.
```

Never make payment mandatory for all adoptions.

---

# 23. PAYMENT RULES

Never require payment when:

```text
package price == ₱0
```

or:

```text
no package assigned
```

Do not generate a receipt for a free adoption.

Receipt numbers are for actual paid transactions.

---

# 24. EMAIL SYSTEM

Use Django email.

Environment variables:

```text
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
DEFAULT_FROM_EMAIL
```

Never hard-code SMTP credentials.

Required emails:

### Account

* Registration
* Verification OTP
* Password reset OTP
* Password reset confirmation

### Application

* Submitted
* Status changes
* Approved
* Rejected
* Additional information requested

### Adoption

* Approved
* Completed
* Reminders when applicable

### Payment

Only when applicable:

* Payment request
* Payment confirmation
* Receipt

Development may use Django's console email backend.

---

# 25. NOTIFICATIONS

Implement in-app notifications.

Generate notifications for major events such as:

* Application submitted
* Status changed
* Documents required
* Approved
* Rejected
* Additional information requested
* Payment status changed
* Adoption completed

Adopter dashboard should show unread notifications.

---

# 26. API STRUCTURE

Use DRF.

Recommended namespaces:

```text
/api/auth/
/api/adopters/
/api/pets/
/api/applications/
/api/documents/
/api/reviews/
/api/packages/
/api/health-records/
/api/adoptions/
/api/payments/
/api/reports/
/api/notifications/
```

Use:

* Pagination
* Filtering
* Search
* Sorting
* Proper HTTP status codes
* Consistent JSON responses
* Consistent validation errors

---

# 27. DATABASE

Use PostgreSQL through Django ORM.

Use:

* Foreign keys
* One-to-one relationships
* Constraints
* Transactions
* Validation
* Migrations

Prevent:

* Invalid relationships
* Duplicate conflicting assignments
* Invalid payment/package relationships
* Invalid adoption records
* Orphaned records where inappropriate

---

# 28. UI/UX REQUIREMENTS

The system must look:

* Modern
* Clean
* Friendly
* Professional
* Pet-focused
* Distinctive
* User-friendly

It must NOT look like a generic AI-generated template.

Avoid excessive:

* Blue dashboard templates
* Gradients
* Glassmorphism
* Huge rounded cards
* Unnecessary animations
* Decorative blobs
* Fake metrics
* Excessive paw-print decorations

Pet-inspired visual elements may be used subtly.

The result should look like a real product.

---

# 29. ADOPTER PORTAL DESIGN

The adopter portal should feel like a pet adoption website.

It should prioritize:

```text
Pets
Adoption
Trust
Clarity
Ease of use
```

Important pages:

```text
Home
Pets
Pet Details
Login
Register
Email Verification
Forgot Password
Reset Password
Dashboard
Applications
Application Details
Documents
Notifications
Profile
Adoption Record
Payment/Package information when applicable
```

Do not make the adopter dashboard visually resemble the staff dashboard.

---

# 30. STAFF PORTAL DESIGN

Staff portal should prioritize:

```text
Operations
Review
Data
Workflow
Efficiency
```

Navigation can include:

```text
Dashboard
Applications
Pets
Adopters
Documents
Reviews
Health Records
Adoption Records
Packages
Payments
Reports
Notifications
```

Dashboard statistics must use real database data.

Never fabricate metrics.

---

# 31. RESPONSIVENESS

Both portals must work on:

* Desktop
* Laptop
* Tablet
* Mobile

Do not simply shrink desktop layouts.

Tables must have an appropriate mobile representation.

Forms must remain usable on small screens.

Controls must be touch-friendly.

---

# 32. ACCESSIBILITY

Implement:

* Proper labels
* Keyboard navigation
* Visible focus states
* Good contrast
* Meaningful alt text
* Accessible buttons
* Accessible form errors
* `aria-describedby` where appropriate

Do not rely on color alone to communicate status.

Use:

```text
text + icon + color
```

when appropriate.

---

# 33. FRONTEND CODE QUALITY

Both frontends must use TypeScript correctly.

Avoid unnecessary:

```text
any
```

Do not use:

```text
@ts-ignore
```

as a shortcut.

Use reusable components and feature-based organization.

Avoid giant components.

Separate:

* UI
* API calls
* Types
* Business logic
* Routing
* State
* Utilities

where appropriate.

---

# 34. BACKEND CODE QUALITY

Keep Django applications modular.

Business logic must not be unnecessarily duplicated between views.

Use appropriate:

* Models
* Serializers
* ViewSets
* Permissions
* Services
* Validators
* Selectors/query utilities when useful

Do not over-engineer.

---

# 35. SECURITY

Implement:

* Secure password hashing
* RBAC
* Object-level permissions
* Input validation
* CSRF protection where applicable
* Explicit CORS
* Rate limiting
* OTP expiration
* OTP attempt limits
* Login protection
* Secure file uploads
* Environment-based secrets
* Safe production errors

Never trust frontend authorization.

---

# 36. ENVIRONMENT VARIABLES

Provide:

```text
.env.example
```

Never commit:

```text
.env
```

Never commit:

* Passwords
* API keys
* SMTP credentials
* Database credentials
* Django secret key
* Payment secret keys

---

# 37. AUDIT LOG

Implement audit logging for important actions.

At minimum:

* Application status changes
* Review decisions
* Pet status changes
* Payment status changes
* Adoption status changes

Store:

```text
acting user
action
model
object ID
previous value
new value
timestamp
```

---

# 38. REPORTS

Implement:

```text
Adoption Reports
Pet Inventory Reports
Adopter Reports
Application Reports
Health Record Reports
Payment Reports
```

Where relevant, support:

* Date ranges
* Status
* Pet
* Application
* Adopter
* Payment status
* Filters

Provide table views and CSV export.

PDF export may be implemented if practical.

---

# 39. LOADING / EMPTY / ERROR STATES

Every major page must handle:

```text
Loading
Empty
Error
Success
```

Avoid relying on browser `alert()` for the primary user experience.

---

# 40. TESTING

Test backend and frontend behavior.

At minimum test:

### Authentication

* Registration
* Duplicate email
* Email verification
* OTP expiry
* OTP attempts
* Login
* Invalid credentials
* Logout
* Password reset
* Lockout

### Pets

* CRUD
* Search
* Filters
* Status
* Images

### Applications

* Submission
* Validation
* Status transitions
* Pet assignment
* Conflicting applications
* Ownership

### Documents

* Upload
* MIME validation
* Size validation
* Download permissions
* Delete permissions

### Reviews

* Approve
* Reject
* Request information
* Review history
* Internal notes protection

### Health

* Staff-only access
* Vaccination status

### Adoption

* Approved application
* Adoption record
* Status transitions
* Pet synchronization

### Payments

* Free adoption
* ₱0 package
* Manual payment
* Receipt
* Status changes

### Email

* Verification
* Password reset
* Application status
* Adoption status
* Payment

### Security

Attempt unauthorized access between:

```text
Adopter
Staff
Admin
```

---

# 41. TEST BOTH FRONTENDS

Verify independently:

```text
adopter-portal
```

and:

```text
staff-portal
```

Both must be able to communicate with the same backend.

Do not assume that because one portal works, the other is correct.

---

# 42. DATABASE MIGRATIONS

Use normal Django migrations.

When models change:

```bash
python manage.py makemigrations
python manage.py migrate
```

Do not delete migrations as a shortcut.

Do not reset the database unnecessarily.

---

# 43. GIT SAFETY

Before significant changes:

```bash
git status
```

Do not use destructive Git commands unnecessarily.

Never use:

```bash
git reset --hard
```

unless explicitly instructed.

Never commit secrets.

---

# 44. DEPENDENCY MANAGEMENT

Do not install unnecessary packages.

Before adding a package:

1. Determine whether it is actually required.
2. Check whether the existing stack already solves the problem.
3. Prefer stable maintained packages.
4. Avoid dependency bloat.

---

# 45. NO FAKE FUNCTIONALITY

Do not fake core functionality.

Do not use fake:

* Statistics
* Applications
* Payments
* Emails
* Approvals
* Database data

The final system must use real backend/database functionality.

---

# 46. DO NOT OVER-ENGINEER

Keep the architecture appropriate for a strong v1.

Do not introduce unnecessary:

* Microservices
* Message brokers
* Complex event buses
* Kubernetes
* Excessive infrastructure
* Unnecessary third-party services

Prefer:

```text
React SPA × 2
+
Django REST API
+
PostgreSQL
```

---

# 47. IMPORTANT BUSINESS RULES

Always preserve these rules:

1. An adopted pet cannot remain available.
2. An unapproved application cannot create a completed adoption record.
3. A pet cannot be assigned to conflicting active applications.
4. Payment is never mandatory for a free adoption.
5. A ₱0 package requires no payment.
6. Staff functionality must be protected at API level.
7. Adopters can access only their own records.
8. Internal staff notes must never be exposed to adopters.
9. Payments must reference valid application/package relationships.
10. Status transitions must be explicitly validated.
11. Audit history must remain intact.

---

# 48. AGENT WORKFLOW

Before starting a phase:

```text
Read specification
↓
Understand requirements
↓
Plan implementation
↓
Implement
↓
Run checks
↓
Run tests
↓
Fix errors
↓
Verify
↓
Continue
```

Do not blindly implement large amounts of code.

Do not move to the next major phase if the current phase is broken.

---

# 49. IF THE SPECIFICATION AND CODE CONFLICT

Because this is a fresh project, the specification takes priority.

Use this order:

```text
1. Explicit user instruction
2. docs/AGENT-SPEC.md
3. AGENTS.md
4. Normal engineering judgment
```

If a requirement appears ambiguous, choose the simplest implementation consistent with the specification and document the decision.

Do not silently remove required functionality.

---

# 50. FINAL ARCHITECTURE CHECK

Before considering the project structurally correct, verify:

```text
pet-adoption/
│
├── adopter-portal/    ← React + TypeScript + Vite + Tailwind
│
├── staff-portal/      ← React + TypeScript + Vite + Tailwind
│
├── backend/           ← Django + DRF
│
├── docs/
│   └── AGENT-SPEC.md
│
├── AGENTS.md
├── README.md
├── .gitignore
└── .env.example
```

There must NOT be:

```text
frontend/
```

as a replacement for the two portals.

There must be exactly one shared Django backend.

There must be one PostgreSQL database.

---

# 51. DEFINITION OF DONE

The project is complete only when:

* Both React portals work.
* Django backend works.
* PostgreSQL works.
* Authentication works.
* Email verification works.
* Password recovery works.
* RBAC works.
* Adopter management works.
* Pet management works.
* Applications work.
* Documents work.
* Reviews work.
* Health records work.
* Adoption records work.
* Packages work.
* Optional payments work.
* Reports work.
* Notifications work.
* Emails work.
* Audit logging works.
* Business rules are enforced.
* API permissions are enforced.
* Frontend validation works.
* Backend validation works.
* Responsive UI works.
* Accessibility requirements are reasonably satisfied.
* Tests pass.
* Migrations run cleanly.
* No major frontend errors remain.
* No major backend errors remain.
* No secrets are committed.

---

# 52. FINAL PRINCIPLE

This project should feel like a real pet adoption platform.

The adopter experience should be:

```text
Warm
Simple
Trustworthy
Modern
Pet-focused
Easy to use
```

The staff experience should be:

```text
Professional
Organized
Efficient
Data-driven
Easy to operate
```

The backend should be:

```text
Secure
Validated
Maintainable
Well-structured
Role-aware
```

The final system should NOT feel like:

```text
Generic CRUD
Generic admin template
AI-generated demo
Mandatory ecommerce checkout
```

Build the system according to the FDD and specification while maintaining a clean, scalable architecture.

**Read `docs/AGENT-SPEC.md` before implementation.**

---

# 53. ACTIVE QA FINDINGS — READ BEFORE YOUR NEXT SESSION

> **IMPORTANT:** An independent audit was performed on 2026-09-09,
> including a live end-to-end API walkthrough against a running server
> (not just static code review and unit tests). It found the codebase
> to be genuinely strong — all 10 FDD modules implemented, 240 backend
> tests passing, both frontends build cleanly, no stub/TODO markers —
> but it also found one confirmed breaking bug and one confirmed API
> design defect in the core adoption lifecycle.
>
> Full details, evidence, and reproduction steps are in:
>
> `docs/QA-REPORT-2026-09-09.md`
>
> **Read that file completely before making further changes.** Do not
> re-derive these findings from scratch; the report already contains
> the root cause and the required fix for each.

## 53.1 Required fixes, in order

1. **Fix: applications never leave `"draft"` status.**
   Adopters have no way to move a newly created application from
   `draft` to `submitted` — only staff can call the status-update
   endpoint, and staff should not be performing the adopter's submit
   step for them. See `docs/QA-REPORT-2026-09-09.md` §2 for the two
   acceptable fix approaches. This blocks the rest of the adoption
   lifecycle from being testable end-to-end, so fix it first.

2. **Fix: `POST /api/applications/` response omits `id` and `status`.**
   The create action returns the write-only serializer instead of the
   read serializer. See `docs/QA-REPORT-2026-09-09.md` §3.

3. **Add regression tests for both fixes** that call the real HTTP
   endpoints (not just the model/serializer layer directly), so this
   class of bug — correct at the unit-test level, broken in the actual
   flow — is caught automatically going forward.

4. **Re-run the full live walkthrough** end to end: register → verify
   email → login → browse pets → submit application → confirm status
   is `submitted` → staff review → approve → attach package → record
   payment → adoption record created → adoption completed → pet status
   synced to `adopted`. Confirm each step against a running server, not
   only against passing unit tests.

5. **Do the same live-flow audit on payments, packages, and document
   upload** — see `docs/QA-REPORT-2026-09-09.md` §5 for what has and
   has not yet been verified live.

6. **Add a minimal CI workflow** (backend tests + both frontend
   builds) so future regressions are caught without a manual audit.

## 53.2 Do not

* Do not mark Finding §2 or §3 as resolved without adding the
  regression test described above.
* Do not silently change the `Application.Status` transition map in a
  way that removes the `draft` state — it may be needed for a future
  save-as-draft feature (see Option B in the report). Confirm with the
  user which fix option was intended if it isn't obvious from existing
  frontend code.
* Do not treat items listed in `docs/QA-REPORT-2026-09-09.md` §4
  ("verified as correct") as broken — they were checked and are fine.

# END OF AGENTS.md