// Invoked only by Django's opt-in LiveServerTestCase with isolated fixture credentials.
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { expect } from '@playwright/test';
import { createServer } from 'vite';

if (!process.env.PAWCONNECT_FIXTURE) throw Error('Isolated Django test fixture is required.');
const fixture = JSON.parse(process.env.PAWCONNECT_FIXTURE);
if (!/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(fixture.api) || fixture.api.endsWith(':8000')) {
  throw Error('Refusing to use a development backend.');
}
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
process.env.VITE_API_URL = '/api';
process.env.VITE_API_BASE_URL = '/api';
const adopterUrl = 'http://127.0.0.1:5188';
const staffUrl = 'http://127.0.0.1:5189';
const servers = [];
let browser;

async function read(url) {
  const response = await fetch(`${fixture.api}${url}`, { headers: { Authorization: `Token ${fixture.staff.token}` } });
  assert.equal(response.status, 200, url);
  return response.json();
}

async function requestDate(page, application, date, reason) {
  await page.goto(`${adopterUrl}/applications/${application}`);
  await page.getByRole('button', { name: 'Request Reschedule', exact: true }).click();
  await page.getByLabel('New appointment date').fill(date);
  await page.getByLabel('Reason for rescheduling').fill(reason);
  await page.getByRole('button', { name: 'Submit Reschedule Request', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Waiting for staff review' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Request Reschedule', exact: true })).toHaveCount(0);
}

async function decide(page, approve, reason) {
  await page.goto(`${staffUrl}/appointments?tab=reschedules`);
  await page.getByRole('button', { name: approve ? 'Approve Reschedule' : 'Reject Request', exact: true }).click();
  const dialog = page.getByRole('dialog');
  if (!approve) await dialog.getByRole('textbox').fill(reason);
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: approve ? 'Approve Reschedule' : 'Reject Reschedule', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect.poll(async () => (await read('/api/appointments/reschedule-requests/?status=pending')).count).toBe(0);
}

try {
  for (const [folder, port] of [['adopter-portal', 5188], ['staff-portal', 5189]]) {
    const server = await createServer({
      root: path.join(root, folder), envFile: false, logLevel: 'error',
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
    // Defense in depth: never allow a local absolute .env URL to reach real data.
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
    pages[role].on('response', (response) => {
      if (response.url().includes('/api/') && response.status() >= 400) errors.push(`${response.status()} ${new URL(response.url()).pathname}`);
    });
  }
  const { adopter, staff } = pages;
  const [appA, appB] = fixture.applications;
  const original = await read(`/api/adoptions/${fixture.records[0]}/`);
  await requestDate(adopter, appA, fixture.newDate, 'Work schedule changed');
  assert.equal((await read(`/api/adoptions/${fixture.records[0]}/`)).adoption_date, original.adoption_date);
  const notifications = await read('/api/notifications/');
  assert.ok(notifications.results.some((n) => n.title === 'Reschedule Requested' && n.link === '/appointments?tab=reschedules'));
  await staff.goto(`${staffUrl}/notifications`);
  await staff.getByRole('link', { name: 'Reschedule Requested', exact: true }).click();
  await expect(staff).toHaveURL(`${staffUrl}/appointments?tab=reschedules`);
  await expect(staff.getByText('Reason: Work schedule changed', { exact: true })).toBeVisible();
  await adopter.reload();
  await expect(adopter.getByRole('status').filter({ hasText: 'Waiting for staff review' })).toBeVisible();
  console.log('Adopter request persisted; old date unchanged; staff notified.');

  await decide(staff, true);
  const approved = await read(`/api/adoptions/${fixture.records[0]}/`);
  assert.equal(approved.id, original.id);
  assert.equal(approved.status, 'scheduled');
  assert.equal(approved.adoption_date, fixture.newDate);
  assert.notEqual(approved.appointment_id, original.appointment_id);
  assert.equal(approved.transaction_id, null);
  await requestDate(adopter, appA, fixture.laterDate, 'Another date requested');
  await decide(staff, false, 'Center is fully booked');
  assert.equal((await read(`/api/adoptions/${fixture.records[0]}/`)).adoption_date, fixture.newDate);
  await adopter.reload();
  await expect(adopter.getByText('Center is fully booked', { exact: false })).toBeVisible();
  console.log('Staff approval/rejection works; same adoption record and original appointment history retained.');

  await staff.goto(`${staffUrl}/appointments`);
  await staff.getByRole('button', { name: 'Confirmed', exact: true }).click();
  const noShowCard = staff.locator('.panel').filter({ hasText: 'NoShow Pet' });
  await noShowCard.getByRole('button', { name: 'Mark as No-show' }).click();
  let dialog = staff.getByRole('dialog');
  await dialog.getByRole('textbox').fill('Adopter did not arrive');
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: 'Mark as No-show', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await requestDate(adopter, appB, fixture.newDate, 'Please give me another visit date');
  await decide(staff, true);
  const history = await read(`/api/appointments/?application=${appB}`);
  assert.ok(history.results.some((a) => a.status === 'no_show' && a.no_show_reason === 'Adopter did not arrive'));
  assert.equal((await read(`/api/adoptions/${fixture.records[1]}/`)).adoption_date, fixture.newDate);
  console.log('No-show recorded; adopter can request again; no-show history survives approval.');

  await requestDate(adopter, appA, fixture.laterDate, 'Pending request before withdrawal');
  await staff.goto(`${staffUrl}/adoptions`);
  await staff.getByRole('row').filter({ hasText: 'Reschedule Pet' }).getByRole('button', { name: 'Cancel Adoption', exact: true }).click();
  dialog = staff.getByRole('dialog');
  await dialog.getByRole('textbox').fill('Adopter withdrew from adoption');
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: 'Cancel Adoption', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(staff.getByRole('row').filter({ hasText: 'Reschedule Pet' })).toContainText('Adopter withdrew from adoption');
  const cancelled = await read(`/api/adoptions/${fixture.records[0]}/`);
  assert.equal(cancelled.status, 'cancelled');
  assert.equal((await read(`/api/applications/${appA}/`)).status, 'cancelled');
  const appointments = await read(`/api/appointments/?application=${appA}`);
  assert.ok(appointments.results.every((a) => !['confirmed', 'pending_confirmation'].includes(a.status)));
  const payments = await read('/api/payments/');
  assert.equal(payments.count, 1);
  assert.equal(payments.results[0].status, 'completed');
  await adopter.reload();
  await expect(adopter.getByRole('button', { name: 'Request Reschedule', exact: true })).toHaveCount(0);
  // Closing an adoption with old no-show history must not tell its adopter
  // that the adoption is still open or offer another request.
  await staff.getByRole('row').filter({ hasText: 'NoShow Pet' }).getByRole('button', { name: 'Cancel Adoption', exact: true }).click();
  dialog = staff.getByRole('dialog');
  await dialog.getByRole('textbox').fill('Adopter no longer proceeding');
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: 'Cancel Adoption', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await adopter.goto(`${adopterUrl}/applications/${appB}`);
  await expect(adopter.getByRole('heading', { name: 'Application for NoShow Pet' })).toBeVisible();
  await expect(adopter.getByRole('button', { name: 'Request Reschedule', exact: true })).toHaveCount(0);
  await expect(adopter.getByText('Your adoption has not been cancelled.', { exact: false })).toHaveCount(0);
  assert.deepEqual(errors, []);
  console.log('Cancellation closes application/appointments/pending request; payment retained; no browser/API errors.');
} finally {
  if (browser) await browser.close();
  for (const server of servers.reverse()) await server.close();
}
