# PawConnect portal UI refresh

## Scope and design

- Adopter: off-white neutral background, teal actions, a quieter pet-focused
  home page, shared public/account header, and rounded pet cards.
- Staff: graphite/blue workspace with a theme-aware sidebar, compact operational
  pages, individual overview cards, and a drawer for small screens.
- Both portals display PawConnect branding, support light/dark themes, remember
  the selected theme separately, and default to the device preference.
- Theme colors are semantic Tailwind variables, including surfaces, text,
  inputs and status colors. Images are not inverted for dark mode.

## Adopter navigation and home

The header's primary links are Home and Find a Pet. The profile icon opens on
hover or click and exposes My Applications, My Profile, Notifications and
Logout. The bell is immediately beside the profile icon. Popovers support
outside clicks and Escape.

Latest Pets explicitly filters the returned data to Available and takes at most
three rows. The backend does not support the old `page_size=3` request, so the
client now enforces this display limit. Find a Pet retains the full backend
pagination, including forwarding the current page and resetting page selection
when filters change. Missing/unavailable card photos get a neutral placeholder.

## Notifications and application status

Both bells load the six most recent notifications from the existing API, with
links and a View all notifications action. The total unread count comes from
`/api/notifications/unread-count/`, independently of list pagination. Counts
above 99 use a visible 99+ badge; the button label retains the actual count.
Opening a linked notification marks that notification read through the existing
endpoint and refreshes counters. Earlier read notifications remain in history.
The full inbox supports pagination and the existing mark-read endpoints.

The adopter application view shows the saved status, pet, next step and visible
staff feedback. Previously submitted form answers and the old uploaded-file
list are hidden from this view. Required application inputs and document rules
are unchanged. Appointment requests, confirmed-visit instructions, reschedule
requests and requested-document upload controls remain available when their
existing status conditions allow them. Terminal statuses show a compact view.

Rejection feedback uses the existing visible rejection reason. For document
requests, the view uses a matching notification when available in the recent
API page; otherwise it links to the full inbox. It never reads internal staff
notes. Navigating between applications resets the old view while the current
application is fetched, preventing stale status/actions from being displayed.

No backend models, permissions, payment services, adoption lifecycle rules,
PDF generation, or database schema were changed. Existing saved application
answers and documents are preserved.

## Verification

Both portals:

```powershell
npx tsc --noEmit
npm run build
```

Existing payment browser regressions, from `staff-portal/`:

```powershell
$env:PLAYWRIGHT_CHANNEL = 'msedge'
npm run test:payments
```

New UI walkthrough, from `backend/`:

```powershell
$env:PAWCONNECT_UI_BROWSER_TESTS = '1'
# Optional: screenshot output directory
$env:PAWCONNECT_UI_SCREENSHOTS = Join-Path $env:TEMP 'pawconnect-ui-refresh'
../venv/Scripts/python.exe manage.py test apps.notifications.test_portal_ui --settings=config.settings.testing_postgresql --noinput
```

This creates an isolated PostgreSQL test database using the existing uniquely
named test settings. Two independently configured Vite processes use ports
5192/5193 and proxy exclusively to Django's test live server. Requests to a
development backend are rejected. Fixture data includes 26 available pets,
multiple application statuses, document requests, 28 adopter notifications and
131 staff notifications. Only notification read actions and logout are allowed
as browser writes. Domain-table snapshots and notification row counts are
compared afterward to verify that records were preserved.

The walkthrough covers both themes, preference persistence after refresh,
desktop/mobile bounds, the three-card home cap, full pet pagination, account
menu hover/click/Escape/logout, notification links/counts/pagination, compact
completed status, rejection feedback, requested uploads, and reschedule controls.
The existing follow-up browser test still exercises actual request, approve,
reject, no-show and cancellation endpoints in its own isolated database.

Final verification on 2026-10-23: 9 UI browser groups passed, 4 payment browser
tests passed, the existing follow-up browser walkthrough passed, and the full
backend run completed with 545 passing tests and 8 conditional tests skipped
(553 discovered). The two opt-in browser walkthroughs were run separately.
Physical-device keyboards and a screen-reader pass remain manual.

## Typography and theme refinement (2026-10-23)

Both apps now use Figtree consistently for headings, body copy, buttons, inputs,
selects and textareas, with the same system fallback. The separate heading-font
request was removed. Page canvas, cards, header, navigation and inputs have
explicit semantic backgrounds. Neutral, emerald and orange status styles follow
the selected theme; photo/modal backdrops remain black. PostCSS resolves each
portal's own Tailwind config by absolute module path for standalone tooling.
Vite imports the theme object directly for development and production.

The pet editor has a responsive public-profile preview. Name, breed and color
labels share the same trim, whitespace and title-case presentation function in
both apps. Raw form values, API payloads and saved records are preserved;
descriptions remain plain text with their paragraph breaks. Existing primary
photos take precedence in the preview until explicitly removed by staff.

The browser regression now measures rendered canvas, card, sidebar, table,
header and input background brightness in both themes, verifies input contrast,
compares computed font families, exercises both theme directions and refresh,
and checks staff preview/public detail formatting against the same fixture text.
It also covers the mobile pet form at 320px and 390px. All domain records remain
unchanged in the isolated browser fixture. Vite tracks the imported Tailwind configuration as a dependency and restarts
on configuration changes. The normal dev/build/preview scripts explicitly select
vite.config.ts, avoiding ambiguity with emitted config JavaScript.

## Live-server correction and visual redesign

The user's screenshot was reproduced on the existing localhost:5173 and :5174
servers. The root had current dark variables, while compiled utility rules still
contained the former fixed colors: text-stone-900 used rgb(28 36 56), bg-white
used rgb(255 255 255), and font-display still used the removed heading font.
The earlier fresh-process tests did not catch that long-running development
servers retained the old Tailwind configuration. The Vite config now imports the
actual theme object and passes it directly to Tailwind, so Vite tracks changes
and Tailwind's file-config cache cannot retain the old palette. Staff's emitted
vite.config.js is kept in sync, and scripts select the TypeScript file explicitly.
Both existing dev servers reloaded the corrected config; no user process was
terminated or replaced.

The home page now uses two asymmetric panels, a compact inset header with
segmented navigation, clear mint actions in dark mode, and shared pet cards for
Home and Find a Pet. Missing/broken uploaded photos use a clearly labeled vector
illustration. It does not pretend to be a photograph of the pet or replace saved
media. Staff uses distinct graphite/periwinkle tones, layered surfaces, real
record totals, a compact navigation rail, and links to existing workspace pages.
Theme switches apply colors together to avoid brief unreadable color transitions.
Motion is limited to hover/focus feedback and respects reduced-motion preferences.

A fixed 340px Google provider button was also found overflowing the staff login
at 320px. Its width now follows its container via ResizeObserver in both portals;
credential processing and role checks are unchanged. The existing provider width
option is used rather than cropping its button. Live OAuth completion itself
remains a manual check.

Design references: [Material color roles](https://m3.material.io/m3/pages/color-roles?s=m3),
[Atlassian surface elevation](https://atlassian.design/foundations/elevation/), and
[Google button sizing](https://developers.google.com/identity/gsi/web/reference/js-reference#width).

The shared browser assertion now calculates foreground/background contrast of
headings, navigation, labels, input text and pet details (4.5:1 for normal text,
3:1 for large text and standalone icons), checks actual painted surfaces and
compares font families, including the brand wordmark. The live smoke test checks
the existing dev servers, not replacements, in isolated browser contexts and
blocks all API writes. It also inspects the served CSS for semantic variables.

From staff-portal, with both usual dev servers running:

```powershell
node tests/theme-live.mjs
```

Optional screenshot directory: PAWCONNECT_LIVE_SCREENSHOTS. The isolated Django
UI fixture uses the same contrast assertions and tests staff/adopter controls,
notifications, persisted themes, pet label formatting and mobile forms. Existing
physical-device, screen-reader and live OAuth checks remain manual.

Final correction verification on 2026-10-23: 8 live theme/refresh groups passed
against the existing localhost servers (Home, Find a Pet, and both sign-in
pages), 9 isolated UI browser groups passed, all 4 payment browser tests passed,
and the reschedule/no-show/cancellation live walkthrough passed. Both frontend
TypeScript checks and production builds passed. Django discovered 553 tests:
545 passed, 8 conditional skips; Django checks, migration drift and unapplied
migration checks passed. The adopter build retains its existing large-chunk
warning. No production backend code, schema or existing database rows were
changed. Test fixtures lived only in disposable test databases. The original
local dev-server processes remained running on their original ports.

## Softer light mode

Light mode uses a muted sage/stone canvas and warm off-white cards for adopters,
and a softer blue-gray canvas with pale slate cards for staff. Large pure-white
surfaces were reduced, including the header, sidebar, tables and inputs. Light
muted text was darkened enough to preserve its contrast against the softer
surfaces. Dark-theme tokens, component styles, layouts and workflows were kept.
The shared browser check now also rejects near-white large light-mode surfaces
above an average RGB value of 248, while retaining the existing text-contrast
checks.

Softer-light verification: 8 checks against the running dev servers and 9
isolated UI browser groups passed, including light/dark contrast and mobile
bounds. Both frontend production builds passed their TypeScript compilation;
the existing adopter chunk-size warning remains. This adjustment changes only
light-mode color tokens, the surface-brightness regression assertion, and these
notes. No database or workflow changes were made.
