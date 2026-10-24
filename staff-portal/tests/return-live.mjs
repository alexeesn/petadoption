// Only Django's opt-in LiveServerTestCase supplies these isolated credentials.
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { expect } from '@playwright/test';
import { createServer } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from 'tailwindcss';
import autoprefixer from 'autoprefixer';

if (!process.env.PAWCONNECT_FIXTURE) throw Error('Isolated Django test fixture is required.');
const fixture = JSON.parse(process.env.PAWCONNECT_FIXTURE);
if (!/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(fixture.api) || fixture.api.endsWith(':8000')) {
  throw Error('Refusing to use a development backend.');
}
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
process.env.VITE_API_URL = '/api';
process.env.VITE_API_BASE_URL = '/api';
const adopterUrl = 'http://127.0.0.1:5190';
const staffUrl = 'http://127.0.0.1:5191';
const servers = [];
let browser;

async function read(url) {
  const response = await fetch(`${fixture.api}${url}`, { headers: { Authorization: `Token ${fixture.staff.token}` } });
  assert.equal(response.status, 200, url);
  return response.json();
}

try {
  for (const [folder, port] of [['adopter-portal', 5190], ['staff-portal', 5191]]) {
    const server = await createServer({
      configFile: false, plugins: [react()],
      root: path.join(root, folder), envFile: false, logLevel: 'error',
      css: { postcss: { plugins: [tailwindcss(path.join(root, folder, 'tailwind.config.js')), autoprefixer()] } },
      server: { host: '127.0.0.1', port, strictPort: true, proxy: { '/api': { target: fixture.api, changeOrigin: true } } },
    });
    await server.listen();
    servers.push(server);
  }
  browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
  const errors = [];
  const pages = {};
  for (const role of ['adopter', 'staff']) {
    const context = await browser.newContext();
    const prefix = role === 'adopter' ? 'pam' : 'staff_auth';
    await context.addInitScript(({ prefix, auth }) => {
      localStorage.setItem(`${prefix}_token`, auth.token);
      localStorage.setItem(prefix === 'pam' ? 'pam_user' : 'staff_auth_user', JSON.stringify(auth.user));
    }, { prefix, auth: fixture[role] });
    await context.route('**/*', async (route) => {
      const url = new URL(route.request().url());
      if (url.pathname.startsWith('/api/') && ![adopterUrl, staffUrl].includes(url.origin)) {
        errors.push(`Blocked API origin: ${url.origin}`);
        return route.abort();
      }
      return route.continue();
    });
    pages[role] = await context.newPage();
    pages[role].on('pageerror', (error) => errors.push(error.message));
  }
  const { adopter, staff } = pages;
  const healthBefore = await read(`/api/health-records/?scope=active&pet=${fixture.pet}`);
  assert.equal(healthBefore.count, 1);
  await staff.goto(`${staffUrl}/adoptions`);
  const row = staff.getByRole('row').filter({ hasText: 'Return Browser Buddy' });
  await expect(row.getByRole('button', { name: 'Complete Adoption', exact: true })).toBeVisible();
  await expect(staff.getByRole('button', { name: 'Mark as Returned', exact: true })).toHaveCount(0);
  await row.getByRole('button', { name: 'Complete Adoption', exact: true }).click();
  let dialog = staff.getByRole('dialog');
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: 'Complete Adoption', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(row).toHaveCount(0);
  await staff.getByRole('group', { name: 'Record views' }).getByRole('button', { name: 'History', exact: true }).click();
  await expect(row.getByRole('button', { name: 'Mark as Returned', exact: true })).toBeVisible();
  const completed = await read(`/api/adoptions/${fixture.record}/`);
  const paymentBefore = await read('/api/payments/');
  assert.equal(completed.status, 'completed');
  assert.equal((await read(`/api/health-records/?scope=active&pet=${fixture.pet}`)).count, 0);
  const healthHistory = await read(`/api/health-records/?scope=history&pet=${fixture.pet}`);
  assert.equal(healthHistory.count, 1);
  assert.equal(healthHistory.results[0].id, healthBefore.results[0].id);
  assert.ok(completed.transaction_id);
  console.log('Scheduled adoption completed through the real staff UI; return action appears only after completion.');

  await staff.setViewportSize({ width: 390, height: 844 });
  await row.getByRole('button', { name: 'Mark as Returned', exact: true }).click();
  dialog = staff.getByRole('dialog');
  const bounds = await dialog.boundingBox();
  assert.ok(bounds && bounds.x >= 0 && bounds.x + bounds.width <= 390, 'Return dialog must fit the mobile viewport.');
  const submit = dialog.getByRole('button', { name: 'Mark as Returned', exact: true });
  await expect(submit).toBeDisabled();
  await dialog.getByRole('textbox').fill('Adopter developed allergies');
  await expect(submit).toBeDisabled();
  await dialog.getByLabel('I confirm the pet has been physically returned to the shelter.').check();
  await expect(submit).toBeEnabled();

  // A failed save must keep the dialog open without a successful return.
  const returnUrl = `**/api/adoptions/${fixture.record}/mark-returned/`;
  await staff.route(returnUrl, (route) => route.fulfill({ status: 503, json: { error: 'Return was not saved. Try again.' } }));
  await submit.click();
  await expect(dialog.getByRole('alert')).toContainText('Return was not saved');
  assert.equal((await read(`/api/adoptions/${fixture.record}/`)).status, 'completed');
  await staff.unroute(returnUrl);
  await submit.click();
  await expect(dialog).toHaveCount(0);
  await expect(row.getByRole('cell').nth(4)).toHaveText(/^returned$/i);
  await expect(row).not.toContainText('Adopter developed allergies');
  await expect(row).not.toContainText('No automatic refund');
  await expect(row.getByRole('button', { name: 'Mark as Returned', exact: true })).toHaveCount(0);
  await staff.reload();
  await staff.getByLabel('Status').selectOption('returned');
  await expect(row.getByRole('cell').nth(4)).toHaveText(/^returned$/i);
  await expect(row).not.toContainText('Adopter developed allergies');
  const returned = await read(`/api/adoptions/${fixture.record}/`);
  assert.equal(returned.status, 'returned');
  assert.equal(returned.return_reason, 'Adopter developed allergies');
  assert.ok(returned.returned_at);
  assert.equal(returned.transaction_id, completed.transaction_id);
  assert.equal(returned.completed_at, completed.completed_at);
  assert.deepEqual(await read('/api/payments/'), paymentBefore);
  assert.equal((await read(`/api/pets/${fixture.pet}/`)).status, 'for_assessment');
  assert.equal((await read(`/api/pets/?status=available&search=Return%20Browser%20Buddy`)).count, 0);
  const healthReturned = await read(`/api/health-records/?scope=active&pet=${fixture.pet}`);
  assert.equal(healthReturned.count, 1);
  assert.equal(healthReturned.results[0].id, healthBefore.results[0].id);
  assert.equal(healthReturned.results[0].diagnosis, healthBefore.results[0].diagnosis);
  assert.equal((await read(`/api/health-records/?scope=history&pet=${fixture.pet}`)).count, 0);
  const pdfDownload = staff.waitForEvent('download');
  await row.getByRole('button', { name: 'Download Return PDF', exact: true }).click();
  const downloaded = await pdfDownload;
  assert.equal(downloaded.suggestedFilename(), `pawconnect-adoption-return-${returned.transaction_id}.pdf`);
  const stream = await downloaded.createReadStream();
  const chunks = [];
  for await (const chunk of stream) chunks.push(chunk);
  assert.equal(Buffer.concat(chunks).subarray(0, 4).toString(), '%PDF');
  assert.deepEqual(await read(`/api/adoptions/${fixture.record}/`), returned);
  console.log('Returned record PDF downloaded through the mobile staff UI without changing saved history.');
  console.log('Return holds the pet For Assessment, restores its active medical record and retains all payments.');

  await adopter.setViewportSize({ width: 390, height: 844 });
  await adopter.goto(`${adopterUrl}/adoptions/${fixture.record}`);
  await expect(adopter.getByText('Return Reason', { exact: true })).toBeVisible();
  await expect(adopter.getByText('Adopter developed allergies', { exact: true })).toBeVisible();
  await expect(adopter.getByText('Your adoption and payment history are retained. No automatic refund is issued.')).toBeVisible();
  await adopter.reload();
  await expect(adopter.getByText('The shelter has recorded the return', { exact: false })).toBeVisible();
  await adopter.goto(`${adopterUrl}/pets/${fixture.pet}`);
  await expect(adopter.getByRole('status').filter({ hasText: 'This pet is currently not available for adoption.' })).toBeVisible();
  await expect(adopter.getByRole('link', { name: 'Apply to Adopt Return Browser Buddy', exact: true })).toHaveCount(0);
  await adopter.goto(`${adopterUrl}/applications/new?pet=${fixture.pet}`);
  await expect(adopter.getByText('This pet is awaiting assessment or medical clearance and is not available for adoption.', { exact: true })).toBeVisible();
  await staff.setViewportSize({ width: 1280, height: 900 });
  await staff.goto(`${staffUrl}/pets?scope=active&status=for_assessment`);
  const petRow = staff.getByRole('row').filter({ hasText: 'Return Browser Buddy' });
  await petRow.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(staff.getByRole('combobox', { name: 'Care status', exact: true })).toHaveValue('for_assessment');
  await staff.getByRole('combobox', { name: 'Care status', exact: true }).selectOption('under_medical_care');
  await staff.getByRole('button', { name: 'Save Changes', exact: true }).click();
  await expect(staff.getByRole('heading', { name: 'Edit Pet', exact: true })).toHaveCount(0);
  assert.equal((await read(`/api/pets/${fixture.pet}/`)).status, 'under_medical_care');
  assert.equal((await read(`/api/pets/?status=available&search=Return%20Browser%20Buddy`)).count, 0);
  await adopter.reload();
  await expect(adopter.getByText('This pet is awaiting assessment or medical clearance and is not available for adoption.', { exact: true })).toBeVisible();
  await staff.getByRole('combobox', { name: 'Status', exact: true }).selectOption('under_medical_care');
  await petRow.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(staff.getByRole('combobox', { name: 'Care status', exact: true })).toHaveValue('under_medical_care');
  await staff.getByRole('combobox', { name: 'Care status', exact: true }).selectOption('available');
  await staff.getByRole('button', { name: 'Save Changes', exact: true }).click();
  await expect(staff.getByRole('heading', { name: 'Edit Pet', exact: true })).toHaveCount(0);
  assert.equal((await read(`/api/pets/${fixture.pet}/`)).status, 'available');
  assert.deepEqual(await read('/api/payments/'), paymentBefore);
  assert.deepEqual(await read(`/api/adoptions/${fixture.record}/`), returned);
  await adopter.goto(adopterUrl);
  await expect(adopter.getByTestId('latest-pets').getByRole('link').filter({ hasText: 'Return Browser Buddy' })).toBeVisible();
  console.log('Staff assessment -> medical care -> clearance restores the pet to the adopter homepage; historical adoption and payment stay unchanged.');
  await adopter.goto(`${adopterUrl}/applications/new?pet=${fixture.pet}`);
  await expect(adopter.getByLabel('Why do you want to adopt this pet?', { exact: false })).toBeVisible();
  await expect(adopter.getByLabel('I currently have other pets', { exact: true })).toHaveCount(0);
  await expect(adopter.getByLabel('Describe your other pets', { exact: false })).toHaveCount(0);
  console.log('Application form loads with a complete profile and no duplicate other-pets question.');
  await staff.setViewportSize({ width: 1280, height: 900 });
  await staff.goto(`${staffUrl}/payments`);
  const paymentRow = staff.getByRole('row').filter({ hasText: fixture.receipt });
  await expect(paymentRow).toContainText('completed');
  await expect(staff.getByLabel('Status').locator('option')).toHaveText(['All statuses', 'Completed']);
  await expect(paymentRow.getByRole('button', { name: 'Receipt PDF', exact: true })).toBeVisible();
  await staff.getByRole('button', { name: '+ Record Onsite Payment', exact: true }).click();
  await staff.getByLabel('Eligible Confirmed Appointment').selectOption(fixture.futureAppointment);
  await expect(staff.getByRole('status').filter({ hasText: 'The appointment date has not arrived yet' })).toBeVisible();
  await expect(staff.getByRole('form', { name: 'Record onsite payment' })).toHaveCount(0);
  await staff.goto(`${staffUrl}/applications/${fixture.futureApplication}`);
  await expect(staff.getByRole('heading', { name: 'Application Review', exact: true })).toBeVisible();
  await expect(staff.getByRole('heading', { name: 'Uploaded Documents', exact: true })).toBeVisible();
  await expect(staff.getByRole('heading', { name: 'Internal staff notes', exact: true })).toBeVisible();
  await expect(staff.getByRole('heading', { name: 'Onsite Adoption Transaction', exact: true })).toHaveCount(0);
  await expect(staff.getByRole('button', { name: 'Record Payment', exact: true })).toHaveCount(0);
  await expect(staff.getByRole('button', { name: 'Complete Adoption', exact: true })).toHaveCount(0);
  await staff.goto(`${staffUrl}/adoptions`);
  const futureRow = staff.getByRole('row').filter({ hasText: 'Future Visit Buddy' });
  await expect(futureRow.getByRole('button', { name: 'Complete Adoption', exact: true })).toBeDisabled();
  await expect(futureRow).toContainText('The appointment date has not arrived yet');
  await futureRow.getByRole('button', { name: 'Cancel Adoption', exact: true }).click();
  dialog = staff.getByRole('dialog');
  await dialog.getByRole('textbox').fill('Adopter cannot attend');
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: 'Cancel Adoption', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await staff.getByRole('group', { name: 'Record views' }).getByRole('button', { name: 'History', exact: true }).click();
  const cancellationDownload = staff.waitForEvent('download');
  await futureRow.getByRole('button', { name: 'Download Cancellation PDF', exact: true }).click();
  const cancellationFile = await cancellationDownload;
  assert.equal(cancellationFile.suggestedFilename(), `pawconnect-adoption-cancelled-${fixture.futureRecord.slice(0, 8)}.pdf`);
  const cancellationStream = await cancellationFile.createReadStream();
  const cancellationChunks = [];
  for await (const chunk of cancellationStream) cancellationChunks.push(chunk);
  assert.equal(Buffer.concat(cancellationChunks).subarray(0, 4).toString(), '%PDF');
  assert.equal((await read(`/api/adoptions/${fixture.futureRecord}/`)).status, 'cancelled');
  console.log('Cancelled adoption PDF downloaded; Payment Records exposes only the Completed filter.');
  console.log('Application Review shows application details without duplicate transaction controls; Payment Records and Adoption Records enforce appointment dates.');
  assert.deepEqual(errors, []);
  console.log('Adopter sees return details after reload; Payment Records retains the completed payment and receipt. No browser errors.');
} finally {
  if (browser) await browser.close();
  for (const server of servers.reverse()) await server.close();
}
