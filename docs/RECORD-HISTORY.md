# Active records and history

The staff Pets, Applications and Adoption Records pages open in **Active**. Choose **History** to find finished records, or **All records** to browse both groups. These are filtered views of the same saved records; viewing history does not delete, copy or change them.

| Page | Active | History |
| --- | --- | --- |
| Pets | Available, pending, reserved, under medical care | Adopted, inactive |
| Applications | Draft, submitted, under review, pending documents, additional information requested, approved | Adoption completed, rejected, cancelled |
| Adoption Records | Scheduled | Completed, cancelled, returned |

Completing an adoption moves its application, pet and adoption record into their respective History views. Cancelling or returning an adoption retains its record in History. A returned pet becomes available again and appears in Active Pets. Existing payment receipts, certificates, return/cancellation PDFs and application details remain accessible.

Status filters apply within the selected view. Changing views clears the status filter and returns to page 1. Pets and Applications now have Previous/Next controls and display the total matching count across all pages. View, status and page are stored in the URL so reload and browser Back preserve the selection.

The dashboard shows Available Pets, Active Applications, Scheduled Adoptions and Completed Adoptions. Each card links to its matching filtered list. Recent applications include only active applications. **Reports > Pet Inventory · All-time** displays the total number of pets recorded, including adopted and inactive pets.

The list APIs accept `scope=active`, `scope=history` or `scope=all` before pagination. Omitting `scope` keeps the existing all-record API behavior. Ownership checks still apply. The aggregate adoption PDF uses the same scope and status as the current view, across all matching pages, and labels its selected view.

Verification:

```powershell
cd backend
..\venv\Scripts\python.exe manage.py test apps.reports.test_record_views --settings=config.settings.testing_postgresql --noinput
$env:PAWCONNECT_RECORD_BROWSER_TESTS='1'
..\venv\Scripts\python.exe manage.py test apps.reports.test_record_browser --settings=config.settings.testing_postgresql --noinput
```

The opt-in browser check uses a temporary test database and a separate Vite server. It checks dashboard totals, both pages of pet/application lists, status/view resets, History PDFs, Reports totals and mobile layout, then verifies the original saved records are unchanged. It requires the staff portal dependencies and the Microsoft Edge Playwright channel.
