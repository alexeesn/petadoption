# PawConnect Manual QA & Defense Demo Checklist

This document provides an actionable, end-to-end manual QA and defense-demo walkthrough for the PawConnect Pet Adoption Management System. It reflects the existing routes, controls, and backend services.

---

## Part 1: Environment Readiness & Pre-Flight Checks

Before starting the demo, verify that all prerequisites, environment variables, and ports are correctly configured.

### 1.1 Python Dependencies & Environment

Ensure that all backend dependencies (including ReportLab for server-side PDF exports) are installed:

```bash
cd backend
python -m pip install -r requirements.txt
```

Verify that ReportLab is functional:
```bash
python -c "import reportlab; print('ReportLab version:', reportlab.Version)"
```

### 1.2 Database & Migrations

Verify that PostgreSQL is running and reachable with the credentials specified in `.env`:

```bash
cd backend
python manage.py check --settings=config.settings.development
python manage.py showmigrations --settings=config.settings.development
python manage.py migrate --settings=config.settings.development
```

*(Optional: populate sample pets and adoption packages if starting from a fresh database)*:
```bash
python manage.py seed_data --settings=config.settings.development
```

### 1.3 Service URLs & Port Allocation

Ensure no port conflicts exist before launching services:

| Component | Port | Local URL | Notes |
|---|---|---|---|
| **Backend API (Django)** | `8000` | `http://localhost:8000` | Exposes `/api/` endpoints |
| **Adopter Portal (Vite)** | `5173` | `http://localhost:5173` | Proxies `/api` to port 8000 |
| **Staff Portal (Vite)** | `5174` | `http://localhost:5174` | Proxies `/api` to port 8000 |

### 1.4 Manual Verification & Live Infrastructure Scenarios

> [!IMPORTANT]
> The following four areas cannot be verified through headless unit/integration test runners alone and require manual verification or live infrastructure:

1. **Gmail / SMTP Email Delivery** *(Requires Live SMTP Credentials)*:
   - If `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, and `SMTP_PASSWORD` are present in `.env`, Django dispatches actual emails via TLS on port 587.
   - If omitted or unset, Django defaults to `django.core.mail.backends.console.EmailBackend`, printing email bodies and OTPs to the backend terminal without error.
   - **Check without exposing secrets**:
     ```bash
     python -c "from django.conf import settings; print('Email Backend:', settings.EMAIL_BACKEND)"
     ```

2. **Google OAuth / "Continue with Google"** *(Requires Live Google Cloud Credentials)*:
   - Configured via `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`.
   - In Google Cloud Console (`APIs & Services > Credentials`), ensure the following **Authorized JavaScript origins** are added:
     - `http://localhost:5173`
     - `http://localhost:5174`
   - If unconfigured, the standard email/password authentication flow is used.

3. **PostgreSQL Concurrency & Row-Locking** *(Requires Live Multi-Client Environment)*:
   - Concurrency safety (`select_for_update()` on Application and AdoptionRecord rows in `complete_application_adoption`) must be verified manually under simultaneous competing requests against PostgreSQL.

4. **Interactive Browser Walkthrough & Downloads** *(Requires Running Portals in Browser)*:
   - Visual checks of the Philippine address cascading selector (Region > Province > City > Barangay).
   - Pet photo gallery lightbox.
   - File input and MIME validation in the browser.
   - PDF blob download triggers (`Content-Disposition: attachment`). Ensure the browser does not block automatic downloads from `localhost:5174`.

---

## Part 2: Accounts Preparation

Two distinct user roles are required for the demo:

### 1. Staff / Administrator Account
Create a staff account via Django management command:
```bash
cd backend
python manage.py createsuperuser --email=staff@pawconnect.local --first_name=Staff --last_name=Admin
```
*(When prompted, set a secure password, e.g., `StaffPass123!`)*.

### 2. Adopter Account
Adopters can be registered through the Adopter Portal UI at `http://localhost:5173/register` or pre-created via Django shell:
```bash
python manage.py shell -c "from apps.accounts.models import User; u, _ = User.objects.get_or_create(email='adopter@pawconnect.local', defaults={'first_name': 'Jane', 'last_name': 'Doe', 'role': 'adopter', 'is_email_verified': True}); u.set_password('AdopterPass123!'); u.is_email_verified=True; u.save()"
```

---

## Part 3: Step-by-Step Defense Demo Walkthrough

---

### Step 1: Start Backend and Frontend Portals

- **Actor**: System Operator / Terminal
- **Action**: Launch all three services in separate terminal windows.
- **Commands**:
  - **Terminal 1 (Backend)**:
    ```bash
    cd backend
    python manage.py runserver 8000
    ```
  - **Terminal 2 (Adopter Portal)**:
    ```bash
    cd adopter-portal
    npm run dev
    ```
  - **Terminal 3 (Staff Portal)**:
    ```bash
    cd staff-portal
    npm run dev
    ```
- **Expected Result**:
  - Backend listening on `http://127.0.0.1:8000/`
  - Adopter Portal available at `http://localhost:5173/`
  - Staff Portal available at `http://localhost:5174/`
- **What to Verify**:
  - Navigate to `http://localhost:8000/api/pets/` in browser → returns JSON list of pets (HTTP 200).
- **Recovery Step**:
  - If port 8000, 5173, or 5174 is in use, terminate conflicting processes using `netstat -ano | findstr :<port>` and taskkill, or check Vite console output.

---

### Step 2: Sign In as Staff and Adopter

- **Actor**: Both roles in separate browser windows (or one standard and one incognito window).
- **Action**:
  1. Open Incognito window at `http://localhost:5174/login` (Staff Portal).
  2. Enter staff credentials (`staff@pawconnect.local` / `StaffPass123!`). Click **Sign in**.
  3. Open Normal window at `http://localhost:5173/login` (Adopter Portal).
  4. Enter adopter credentials (`adopter@pawconnect.local` / `AdopterPass123!`). Click **Log In**.
- **Expected Result**:
  - Staff Portal redirects to `/` (Operations Dashboard). Navigation bar shows links: Applications, Pets, Adopters, Documents, Reviews, Health Records, Adoptions, Schedule, Packages, Payment Records, Reports, Notifications, Audit Logs.
  - Adopter Portal redirects to `/applications` (My Applications). Header shows Browse Pets, My Applications, My Profile, Notifications bell, and user avatar.
- **What to Verify**:
  - Adopter cannot navigate to `http://localhost:5174/` (API denies non-staff tokens with 403).
  - Staff token has staff privileges in DRF API calls.
- **Recovery Step**:
  - If login fails with "Please verify your email first", check terminal output for the 6-digit OTP and complete verification at `http://localhost:5173/verify-email`, or set `is_email_verified = True` in Django shell.

---

### Step 3: Browse Available Pets and Complete Adopter Profile *(Manual Browser Check)*

- **Actor**: Adopter (`http://localhost:5173`)
- **Action**:
  1. Click **Browse Pets** (`/pets`).
  2. Filter by species (e.g. "Dog") or search by name. Verify listed pets show status **Available**.
  3. Click on a pet card (e.g., "Max" or "Buddy") to view the Pet Detail page (`/pets/:id`).
  4. Click **My Profile** in the top navigation (`/profile`).
  5. Fill in all required profile fields:
     - Contact Number: `+63 917 123 4567`
     - Address Line 1: `123 Sampaguita St.`
     - Region / Province / City / Barangay: Select from the Philippine cascading dropdowns (e.g. NCR > Metro Manila > Quezon City > Central).
     - Zip Code: `1100`
     - Date of Birth: `1995-05-15`
     - Housing Type: Select "House"
     - Ownership: Select "Own"
     - Household Members: `2`
     - Other Pets: Select No (or Yes with description)
  6. Click **Save Profile**.
- **Expected Result**:
  - Alert banner displays: *"Profile updated successfully. You can now start an adoption application."*
- **What to Verify**:
  - Verify that leaving any required field blank shows an inline field error and disables application creation.
- **Recovery Step**:
  - If address dropdowns fail to load, ensure `philippine_addresses.json` is intact and refresh the page.

---

### Step 4: Submit Application with Required Documents and Consent

- **Actor**: Adopter (`http://localhost:5173`)
- **Action**:
  1. Return to **Browse Pets** (`/pets`) and click **Apply to Adopt** on an available pet.
  2. The multi-step application form opens (`/applications/new?pet=<pet_id>`).
  3. **Step 1 (Application Details)**:
     - Why adopt: `Looking for a loyal family companion.`
     - Experience with pets: `Had dogs growing up for 10 years.`
     - Living situation: `Quiet residential neighborhood with a fenced yard.`
     - Home visit consent: Check "Yes, I agree to a home visit" (or provide reason if declined).
     - Click **Continue to Documents**.
  4. **Step 2 (Documents)**:
     - Upload files for all 4 required document types matching `REQUIRED_DOCUMENT_TYPES` in `backend/apps/documents/serializers.py` (PDF, PNG, or JPG, under 10MB each):
       1. `identification`: Valid ID
       2. `proof_of_address`: Proof of Address
       3. `barangay_certification`: Barangay Certification
       4. `cage_photo`: Cage / Kennel Photo
     - Click **Continue to Review**.
  5. **Step 3 (Review & Consent)**:
     - Review entered information.
     - Check the mandatory checkbox: *"I confirm that all information provided is accurate and I agree to the adoption terms and privacy policy."*
     - Click **Submit Application**.
- **Expected Result**:
  - Success redirect to `/applications` showing the newly created application with status pill **Submitted**.
- **What to Verify**:
  - In backend terminal, verify `POST /api/applications/` returned `201 Created`.
  - Application auto-advances from draft directly to `submitted`.
- **Recovery Step**:
  - If submission fails with HTTP 400 stating missing documents, ensure each of the 4 document slots has an attached file before submitting.

---

### Step 5: Staff Reviews and Approves Application

- **Actor**: Staff (`http://localhost:5174`)
- **Action**:
  1. Open Staff Portal and click **Applications** (`/applications`).
  2. Click on the submitted application for the pet from Step 4.
  3. Review Applicant Details, Profile, and the 4 uploaded documents (click to preview/download).
  4. Type an internal note in the Review panel: `Verified valid ID and address proof. Applicant meets all shelter requirements.`
  5. Click **Approve Application**.
- **Expected Result**:
  - Status badge changes from **Submitted** to **Approved** (green).
  - An email notification is triggered to the adopter (or logged in console).
  - The pet's status automatically transitions to **Pending**.
- **What to Verify**:
  - In Adopter Portal window (`/applications`), refresh: status displays **Approved**.
  - In Adopter Portal, verify internal staff notes are **not** visible anywhere in the UI or in the API network response.
- **Recovery Step**:
  - If approval fails, verify pet is currently in `available` or `pending` status. If already adopted, transition will be rejected.

---

### Step 6: Request and Confirm Onsite Appointment

- **Actor**: Adopter (`http://localhost:5173`) then Staff (`http://localhost:5174`)
- **Action**:
  1. **As Adopter**: On `ApplicationDetailPage` (`/applications/:id`), see the approved banner: *"Your application has been approved!"*
  2. Under "Choose appointment date", select an upcoming open date (Monday–Saturday) for the onsite visit.
  3. Click **Submit appointment request**.
  4. Status pill shows appointment **Pending confirmation**.
  5. **As Staff**: Navigate to **Schedule** (`/appointments`) or open the Application detail page in the Staff Portal.
  6. Locate the appointment request under "Pending confirmation".
  7. Click **Confirm Appointment**.
- **Expected Result**:
  - Appointment status changes to **Confirmed**.
  - The backend automatically schedules an [`AdoptionRecord`](file:///C:/Users/teodo/OneDrive/Documents/test-gemini-petadopt/backend/apps/adoptions/models.py) with status `scheduled`.
  - Note: At this stage, the AdoptionRecord is **not finalized** (`transaction_id` is null, `completed_date` is null, pet is `pending`).
  - Adopter Portal shows: *"What to Prepare for Your Visit"* checklist and center operating hours.
- **What to Verify**:
  - In Staff Portal, navigate to **Adoptions** (`/adoptions`): the newly scheduled adoption record appears in the list with status `scheduled`.
- **Recovery Step**:
  - If date selection fails in Adopter Portal, ensure the selected date is today or a future Monday–Saturday date (Sundays and past dates are rejected).

---

### Step 7: Record Onsite Payment with Explicit Confirmation

> [!NOTE]
> **Business Rule Context**: The current prototype code enforces a prototype adoption fee of ₱500.00 (`PROTOTYPE_ADOPTION_FEE`). See Part 5 for discussion of the policy relationship to optional packages.

- **Actor**: Staff (`http://localhost:5174`)
- **Action**:
  1. Navigate to **Schedule** (`/appointments`) or the Application Detail page.
  2. Locate the "On-site Adoption Fee" transaction panel for the confirmed appointment.
  3. Notice the standard prototype adoption fee displays **₱500.00**.
  4. Leave the confirmation checkbox unchecked and click **Record payment**.
  5. Observe the validation error: *"Confirm that the payment has actually been received onsite before recording it."*
  6. Check the required box: `[x] I confirm the payment has actually been received onsite`.
  7. Enter:
     - Amount: `500.00`
     - Payment Method: `Cash`
     - Reference / OR Number: `OR-2026-MANUAL-01`
     - Notes: `Received cash payment onsite from adopter.`
  8. Click **Record payment**.
- **Expected Result**:
  - Success banner appears: *"Payment of ₱500.00 recorded · Receipt REC-XXXXXXXXXXXX."*
  - The payment status is marked **Completed** with a permanent unique receipt identifier.
- **What to Verify**:
  - In Staff Portal, open **Payment Records** (`/payments`): the completed payment row is listed with receipt number and date.
- **Recovery Step**:
  - If recording fails with an amount error, ensure amount is greater than zero and does not contain non-numeric characters.

---

### Step 8: Verify Payment Totals and Remaining Balance

- **Actor**: Staff (`http://localhost:5174`)
- **Action**:
  1. Look at the Payment Summary card on the Application Detail or Schedule page.
  2. Observe the breakdown:
     - Adoption Fee: `₱500.00`
     - Total Completed Payment: `₱500.00`
     - Remaining Balance: `₱0.00`
     - Fee Status: `Paid in Full`
     - Turnover Eligibility: `Eligible`
- **Expected Result**:
  - Payment is fully satisfied. The Turnover panel enables the completion controls.
- **What to Verify**:
  - Check network tab for `GET /api/applications/<id>/payment-summary/`:
    `"is_fee_paid": true`, `"turnover_eligible": true`.
- **Recovery Step**:
  - If total paid shows ₱0.00, check if payment was recorded with status other than completed (only `completed` status counts towards the adoption fee).

---

### Step 9: Demonstrate Insufficient Payment Cannot Complete Turnover

- **Actor**: Staff (`http://localhost:5174`) (Demonstration test)
- **Action**:
  1. Explain to the defense panel that PawConnect enforces financial integrity at the backend service layer.
  2. If an application has only partial payment (e.g. ₱200.00 of ₱500.00) or pending payment, the turnover endpoint strictly rejects completion with HTTP 400:
     *"The required adoption fee of ₱500.00 has not been fully paid."*
  3. Confirm that the UI "Confirm turnover and complete adoption" button remains locked or will be rejected by DRF if the fee is not met.
- **Expected Result**:
  - System prevents pet turnover whenever the completed amount is below ₱500.00.
- **What to Verify**:
  - Handover cannot be completed prematurely.

---

### Step 10: Confirm Physical Handover and Complete Adoption

- **Actor**: Staff (`http://localhost:5174`)
- **Action**:
  1. In the Staff Portal (on Schedule `/appointments` or Application Detail `/applications/:id`), scroll to the **Pet Turnover & Finalization** section.
  2. Notice the handover button is disabled until the explicit checkbox is ticked.
  3. Check the confirmation checkbox:
     `[x] I confirm the pet has been physically handed over to the adopter.`
  4. (Optional) Enter turnover notes: `Pet handed over in good health with vaccination booklet and collar.`
  5. Click **Confirm turnover and complete adoption**.
- **Expected Result**:
  - Success message: *"Adoption completed. The pet is now marked as adopted and is no longer available."*
  - Application status updates to **Adoption Completed**.
  - A permanent transaction ID (e.g., `TXN-4A2F8B1C9D0E`) is generated and locked into the `AdoptionRecord`.
  - The `AdoptionRecord` status transitions from `scheduled` to `completed`.
- **What to Verify**:
  - Network response shows `POST /api/applications/<id>/complete-adoption/` returns HTTP 200 with `status: "adoption_completed"`.
- **Recovery Step**:
  - If completion fails, verify all 3 mandatory prerequisites: (1) Application approved, (2) Appointment confirmed, (3) ₱500 fee paid in full.

---

### Step 11: Verify Pet Status and Listing Removal

- **Actor**: Adopter (`http://localhost:5173`) and Staff (`http://localhost:5174`)
- **Action**:
  1. In Staff Portal, navigate to **Pets** (`/pets`): find the adopted pet. Status is now **Adopted** (blue pill).
  2. In Adopter Portal, navigate to **Browse Pets** (`/pets`).
  3. Look for the pet or search for its name.
- **Expected Result**:
  - The adopted pet **no longer appears** in the public available pets catalog.
- **What to Verify**:
  - In browser network tab: `GET /api/pets/?status=available` does not contain the adopted pet.
  - Direct GET to `/api/pets/<pet_id>/` returns status `"adopted"`.
- **Recovery Step**:
  - If the pet still appears, check browser cache or verify that `status=available` query parameter is active on `/pets`.

---

### Step 12: Adopter Reads Own Adoption Record & Isolation Check

- **Actor**: Adopter (`http://localhost:5173`)
- **Action**:
  1. In Adopter Portal, check **Notifications** (`/notifications`).
  2. Notice the notification: *"Adoption Completed"* (links to `/applications/<app_id>`).
  3. Navigate to the Adoption Record URL: `http://localhost:5173/adoption/<adoption_record_id>` (or `http://localhost:5173/adoptions/<adoption_record_id>`).
  4. View the Adoption Record page:
     - Pet Name
     - Adoption Date & Completed Date
     - Status: **Completed**
     - Banner: *"Congratulations on your new family member! 🎉"*
  5. **Isolation Check**:
     - Attempt to access another adopter's record ID directly in the URL: `http://localhost:5173/adoption/<other_uuid>`.
- **Expected Result**:
  - The adopter successfully views their own completed adoption record.
  - Attempting to load another adopter's record returns **HTTP 404 Not Found** (*EmptyState: Adoption record not found*), never leaking another user's data.
- **What to Verify**:
  - Network tab returns HTTP 404 for foreign UUIDs, enforcing object-level permission in [`AdoptionRecordViewSet.get_queryset()`](file:///C:/Users/teodo/OneDrive/Documents/test-gemini-petadopt/backend/apps/adoptions/views.py#L34-L45).
  - Both `/adoption/:id` and `/adoptions/:id` routes in `adopter-portal/src/App.tsx` render `AdoptionRecordPage`.
- **Recovery Step**:
  - If page shows blank on notification click, verify that both `/adoption/:id` and `/adoptions/:id` routes are configured in `App.tsx`.

---

### Step 13: Export Payment Records and Adoption Records PDFs *(Manual Browser Check)*

- **Actor**: Staff (`http://localhost:5174`)
- **Action**:
  1. Navigate to **Payment Records** (`/payments`):
     - Click **Export PDF** (without filters) → Browser downloads `pawconnect-payment-records-YYYY-MM-DD.pdf`.
     - Filter status by **Completed**, then click **Export PDF** → Downloads filtered PDF.
  2. Navigate to **Adoptions** (`/adoptions`):
     - Click **Export PDF** (without filters) → Browser downloads `pawconnect-adoption-records-YYYY-MM-DD.pdf`.
     - Filter status by **Completed**, then click **Export PDF** → Downloads filtered PDF containing only completed adoptions.
  3. Open the downloaded PDF files in any PDF viewer.
- **Expected Result**:
  - A4 cleanly styled reports rendered via ReportLab with PawConnect branding, header metadata, timestamp, and table rows matching the applied filters.
  - Export does not mutate any records or invent fake data.
- **What to Verify**:
  - HTTP response header is `Content-Type: application/pdf`.
  - Content stream starts with `%PDF-1.`.
  - An unauthorized adopter attempting to call `/api/adoptions/export-pdf/` directly receives **HTTP 403 Forbidden**.
- **Recovery Step**:
  - If PDF export produces HTTP 500, verify `reportlab` is installed in the active Python environment (`pip install "reportlab>=4.0"`).

---

### Step 14: Verify In-App and Email Notifications *(Manual Verification)*

- **Actor**: Adopter and Staff
- **Action**:
  1. In Adopter Portal, click the **Bell Icon** (`/notifications`).
  2. Verify notification log contains event records:
     - *Application Submitted*
     - *Application Approved*
     - *Adoption Record Created*
     - *Payment Confirmed*
     - *Adoption Completed*
  3. Click **Mark as read** on unread notifications.
  4. Check email delivery:
     - **Console Mode (Default Dev)**: Check the running backend terminal output for formatted email text with subject lines, verification OTPs, and confirmation details.
     - **Live SMTP Mode (If Configured)**: Check the adopter's external email inbox for received PawConnect notification emails.
- **Expected Result**:
  - Every major workflow transition creates an audit trail entry and a matching notification.
- **What to Verify**:
  - In Staff Portal, navigate to **Audit Logs** (`/audit`): inspect recorded actions (`application_created`, `status_change`, `adoption_scheduled`, `payment_created`, `adoption_completed`).
- **Recovery Step**:
  - If notifications do not appear, verify `apps.notifications` is present in `INSTALLED_APPS` and migrations are applied.

---

## Part 4: Quick Defense Demo Cheatsheet

| Step | Action | Actor | Expected UI / API Result |
|---|---|---|---|
| **1** | Start 3 servers | Operator | Backend :8000, Adopter :5173, Staff :5174 |
| **2** | Login | Staff & Adopter | Role-based portal dashboards load |
| **3** | Profile Save | Adopter | Profile complete, cascading address saved *(Manual)* |
| **4** | Submit Application | Adopter | Status becomes `submitted`; 4 docs uploaded |
| **5** | Review & Approve | Staff | Application `approved`; Pet becomes `pending` |
| **6** | Schedule Visit | Adopter & Staff | Appointment `confirmed`; Adoption `scheduled` |
| **7** | Record Onsite Fee | Staff | ₱500 cash payment `completed`; Receipt generated |
| **8** | Verify Balance | Staff | Balance ₱0.00; Turnover eligibility `true` |
| **9** | Insufficient Gate | Staff | Turnover blocked if payment < ₱500 |
| **10** | Confirm Turnover | Staff | Adoption `completed`; Pet status `adopted` |
| **11** | Pet Disappears | Public/Adopter | Pet removed from `/pets` available listing |
| **12** | View Record | Adopter | Adopter views record; other records return 404 |
| **13** | Export PDFs | Staff | Server-side PDF reports download cleanly *(Manual)* |
| **14** | Notifications/Audit | Both | In-app alerts, console/SMTP emails, audit logs verified *(Manual)* |

---

## Part 5: Payment Policy Analysis & Architectural Decision

### The Conflict

There is a documented divergence between the high-level specification and the current runtime implementation:

1. **Original Specification (`docs/AGENT-SPEC.md` §9, §13 and `AGENTS.md` §22, §23)**:
   - "Payment is OPTIONAL and must never gate the adopter workflow when not applicable."
   - Supports 3 modes: Free adoption (no package or ₱0 package → no payment required), Manual payment, and Online payment.
   - Mandate: "Never make payment mandatory for all adoptions."

2. **Current Implemented Runtime (`backend/apps/payments/constants.py`, `services.py`, `views.py`)**:
   - `PROTOTYPE_ADOPTION_FEE = Decimal("500.00")`
   - Pet turnover (`complete_application_adoption` and `_confirm_turnover`) requires `total_completed >= ₱500.00`.
   - Free adoptions or ₱0 packages cannot complete turnover without staff recording an onsite payment of at least ₱500.00.

### Recommended Decision for Defense

For defense and QA demonstration purposes:
- **Demonstrate as implemented**: Explain that the prototype model implements the **Quezon City Animal Care and Adoption Center Onsite Workflow**, which charges a standardized ₱500.00 adoption fee covering shelter microchipping and rabies registration.
- **Future production toggle**: To reconcile with the original spec, the backend service would check if a package is assigned or if the center operates a free adoption policy (`is_fee_exempt = True` or `package.price == 0`) before enforcing `total_completed >= PROTOTYPE_ADOPTION_FEE`.
