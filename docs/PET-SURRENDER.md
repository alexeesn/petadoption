# Pet surrender and center intake

User-approved scope extension, 2026-11-06. Online surrender requests use the
same accounts, two portals, Django API, and PostgreSQL database. This feature
does not enable owner-to-owner listings.

## Workflow

1. A verified adopter account submits authorization, contact number, pet details,
   surrender reason, owner-reported health/vaccination and behavior information,
   and 1–5 JPEG/PNG photos.
2. Staff/admin assess needs and center capacity. They request information,
   waitlist, decline with a reason, or schedule intake. Decisions require a
   message to the owner; internal notes use a separate staff-only field.
3. Owners can update and resubmit only when information is requested. They may
   add up to five photos per update, with ten retained photos maximum. They may
   cancel until the request is received, declined, or cancelled.
4. Scheduling includes a date and instructions: center location, time, and
   requirements. Staff can reschedule or decline after physical assessment.
   Scheduling does not transfer custody or guarantee acceptance. Owners keep
   their pets until the center physically receives them.
5. On or after the scheduled date, staff explicitly confirm physical receipt,
   authorization, and handover consent. One official pet record is created in
   the same transaction. Its default status is `for_assessment`; staff can
   choose `under_medical_care`, `inactive`, or `available` after assessment.
6. The staff request links to the exact pet editor for official photos,
   description, and care-status changes. Private request photos, surrender
   reasons, behavior, and reported medical information are not copied into
   public listings or official health records. Staff enter those separately.
7. Once the pet is cleared as available, the existing adoption process applies.
   Surrender intake does not create any payments or packages.

## Status transitions

| Current state | Allowed next states |
|---|---|
| submitted | needs_information, waitlisted, intake_scheduled, declined, cancelled |
| needs_information | submitted (owner resubmission), waitlisted, intake_scheduled, declined, cancelled |
| waitlisted | needs_information, intake_scheduled, declined, cancelled |
| intake_scheduled | rescheduled intake, needs_information, waitlisted, declined, cancelled, received |
| received, declined, cancelled | Closed |

Dates use the center's Asia/Manila calendar. Staff coordinate capacity and
intake dates manually. This feature does not calculate shelter capacity,
arrange pickups, or apply adoption-visit calendar rules to surrender intake.

## API

All endpoints require a verified, authenticated account.

| Endpoint | Access / behavior |
|---|---|
| `GET /api/surrenders/` | Owners: own only. Staff/admin: all. Pagination, status/species filters, pet-name/breed search, ordering. |
| `POST /api/surrenders/` | Adopter only. Multipart fields and repeated `photos` files. Returns full record with ID/status. |
| `GET /api/surrenders/{id}/` | Owner or staff/admin; includes history and private photo IDs. |
| `POST /api/surrenders/{id}/resubmit/` | Owner only, while needs_information. All request fields, optional additional photos. |
| `POST /api/surrenders/{id}/cancel/` | Owner only, while open. |
| `POST /api/surrenders/{id}/review/` | Staff/admin: status, note, optional internal_notes. Scheduling requires intake_date and intake_instructions. |
| `POST /api/surrenders/{id}/confirm-intake/` | Staff/admin: JSON boolean confirmed=true, optional pet_status. |
| `GET /api/surrenders/{id}/photos/{photo_id}/` | Owner or staff/admin; authenticated image stream, private/no-store caching. |

Generic PATCH/PUT/DELETE are disabled. Mutations lock the request row;
concurrent intake confirmations cannot create duplicate pets. Database
constraints enforce receipt metadata and the one-to-one request/pet link.
Events and audit records preserve decisions and scheduling history. Owner API
responses exclude internal notes and staff email addresses entirely.

Submission, resubmission, decisions, cancellation, and receipt create in-app
notifications. Owner emails run after commit. Mail failures are logged without
rolling back a committed request.

## Deployment and storage

Run `python manage.py migrate`. Private photos live outside MEDIA_ROOT, at
`backend/private/surrenders` by default. Optionally set an absolute
`PRIVATE_SURRENDER_ROOT`. Keep this directory outside public web-server aliases
and include it in private backups. Images are validated against their actual
contents, extension, MIME type, and 5 MB limit, then stored with UUID filenames.
The API returns no public storage paths.

Pet deletion is refused when an intake request references it. Staff retain the
history and use the pet's inactive status instead.

## Verification

From backend, run:

```sh
python manage.py test apps.surrenders --settings=config.settings.testing_postgresql --noinput
```

Set PAWCONNECT_SURRENDER_BROWSER_TESTS=1 and run apps.surrenders.test_browser
with those settings for the opt-in browser walkthrough. It launches both Vite
portals and headless Edge (or PLAYWRIGHT_CHANNEL), with Django's isolated live
test server. It checks submission, private photos, information requests,
resubmission, scheduling, intake, assessment clearance, public pet details,
and mobile layouts. Data never enters the development database. PostgreSQL
tests also verify simultaneous intake confirmations.
