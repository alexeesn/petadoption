// Launched by Django's isolated LiveServerTestCase; never use the development DB.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdir } from 'node:fs/promises';
import { chromium, expect as baseExpect } from '@playwright/test';

const fixture = JSON.parse(process.env.PAWCONNECT_SURRENDER_FIXTURE || 'null');
if (!fixture || !/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(fixture.api) || fixture.api.endsWith(':8000')) throw Error('An isolated Django live-server fixture is required.');
const expect = baseExpect.configure({ timeout: 15000 });
const errors = [];
const servers = [];
let browser;

async function startPortal(root, port) {
  const source = `import { createServer } from 'vite'; const server = await createServer({root:${JSON.stringify(root)},configFile:${JSON.stringify(`${root}/vite.config.ts`)},envFile:false,logLevel:'error',server:{host:'127.0.0.1',port:${port},strictPort:true,proxy:{'/api':{target:${JSON.stringify(fixture.api)},changeOrigin:true}}}}); await server.listen(); console.log('SURRENDER_UI_READY');`;
  const processHandle = spawn(process.execPath, ['--input-type=module', '-e', source], {
    env: { ...process.env, VITE_API_URL: '/api', VITE_API_BASE_URL: '/api' }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
  });
  servers.push(processHandle);
  await new Promise((resolve, reject) => {
    let stderr = '';
    const timer = setTimeout(() => reject(Error(`Vite startup timed out: ${stderr}`)), 40000);
    processHandle.stderr.on('data', value => { stderr += value.toString(); });
    processHandle.stdout.on('data', value => { if (value.toString().includes('SURRENDER_UI_READY')) { clearTimeout(timer); resolve(); } });
    processHandle.on('error', error => { clearTimeout(timer); reject(error); });
    processHandle.on('exit', code => { clearTimeout(timer); reject(Error(`Vite exited (${code}): ${stderr}`)); });
  });
  return `http://127.0.0.1:${port}`;
}

async function api(path, user = fixture.staff) {
  const response = await fetch(`${fixture.api}/api${path}`, { headers: { Authorization: `Token ${user.token}` } });
  assert.equal(response.status, 200);
  return response.json();
}

async function noOverflow(page) {
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'Mobile layout must not overflow horizontally.');
}

async function confirmDecision(page) {
  await page.getByRole('button', { name: 'Review decision', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: 'Save surrender decision', exact: true }).click();
  await expect(dialog).toHaveCount(0);
}

try {
  const cwd = process.cwd().replace(/\\/g, '/');
  const [ownerOrigin, staffOrigin] = await Promise.all([startPortal(`${cwd}/../adopter-portal`, 5196), startPortal(cwd, 5197)]);
  browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
  const ownerContext = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const staffContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  for (const [context, user, prefix] of [[ownerContext, fixture.owner, 'pam'], [staffContext, fixture.staff, 'staff_auth']]) {
    await context.addInitScript(({ user, prefix }) => {
      localStorage.setItem(`${prefix}_token`, user.token);
      localStorage.setItem(`${prefix}_user`, JSON.stringify(user.user));
    }, { user, prefix });
    await context.route('**/*', route => {
      const hostname = new URL(route.request().url()).hostname;
      return ['localhost', '127.0.0.1', ''].includes(hostname) ? route.continue() : route.abort();
    });
  }
  const owner = await ownerContext.newPage();
  const staff = await staffContext.newPage();
  for (const page of [owner, staff]) page.on('pageerror', error => errors.push(error.message));
  await owner.goto(`${ownerOrigin}/surrenders`);
  await expect(owner.getByRole('heading', { name: 'My Surrender Requests', exact: true })).toBeVisible();
  await owner.getByRole('link', { name: 'Request to surrender a pet', exact: true }).click();
  await owner.getByLabel('Pet name', { exact: true }).fill('Browser Mochi');
  await owner.getByLabel('Species', { exact: true }).selectOption('cat');
  await owner.getByLabel('Estimated age — years', { exact: true }).fill('2');
  await owner.getByLabel('Reason for surrender', { exact: true }).fill('Moving to a home that does not allow pets.');
  await owner.getByLabel('Known health conditions and vaccination information', { exact: true }).fill('Unknown');
  await owner.getByLabel('Behavior and temperament', { exact: true }).fill('Shy but friendly.');
  await owner.getByLabel('Contact number', { exact: true }).fill('09123456789');
  await owner.getByLabel('Pet photos (1 to 5)', { exact: true }).setInputFiles(fixture.photo);
  await owner.getByRole('checkbox').check();
  await noOverflow(owner);
  await owner.getByRole('button', { name: 'Submit surrender request', exact: true }).click();
  await expect(owner.getByRole('heading', { name: 'Surrender request for Browser Mochi', exact: true })).toBeVisible();
  await expect(owner.getByAltText('Browser Mochi, submitted by the owner')).toBeVisible();
  const requestId = new URL(owner.url()).pathname.split('/').pop();
  assert.equal((await api('/pets/')).count, 0, 'No official pet before handover.');

  await staff.goto(`${staffOrigin}/surrenders`);
  await staff.getByRole('link', { name: 'Review request', exact: true }).click();
  await staff.getByLabel('Decision', { exact: true }).selectOption('needs_information');
  await staff.getByLabel('Message to owner / reason for decision', { exact: true }).fill('Please confirm the vaccination history.');
  await staff.getByLabel('Internal notes (staff only)', { exact: true }).fill('CONFIDENTIAL capacity assessment');
  await confirmDecision(staff);
  await expect(staff.getByRole('status')).toContainText('Decision saved');

  await owner.reload();
  await expect(owner.getByRole('heading', { name: 'Additional information requested', exact: true })).toBeVisible();
  assert(!(await owner.locator('body').innerText()).includes('CONFIDENTIAL'));
  assert(!JSON.stringify(await api(`/surrenders/${requestId}/`, fixture.owner)).includes('internal_notes'));
  await owner.getByLabel('Known health conditions and vaccination information', { exact: true }).fill('Vaccinated last year.');
  await owner.getByRole('checkbox').check();
  await owner.getByRole('button', { name: 'Send updated information', exact: true }).click();
  await expect(owner.getByRole('heading', { name: 'Additional information requested', exact: true })).toHaveCount(0);

  await staff.reload();
  await staff.getByLabel('Decision', { exact: true }).selectOption('intake_scheduled');
  await staff.getByLabel('Intake date', { exact: true }).fill(fixture.today);
  await staff.getByLabel('Center location, time, and intake requirements', { exact: true }).fill('Center front desk, 9 AM. Bring vaccination records.');
  await staff.getByLabel('Message to owner / reason for decision', { exact: true }).fill('A space is available for assessment.');
  await confirmDecision(staff);
  await expect(staff.getByRole('button', { name: 'Confirm intake', exact: true })).toBeVisible();
  assert.equal((await api('/pets/')).count, 0, 'Scheduling must not create a pet.');
  await owner.reload();
  await expect(owner.getByRole('region', { name: 'Intake schedule', exact: true })).toContainText('Center front desk');
  await expect(owner.getByAltText('Browser Mochi, submitted by the owner')).toBeVisible();
  await noOverflow(owner);
  await mkdir('../test-results', { recursive: true });
  await owner.screenshot({ path: '../test-results/surrender-owner-mobile.png', fullPage: true });
  await staff.screenshot({ path: '../test-results/surrender-staff-desktop.png', fullPage: true });

  await staff.getByRole('button', { name: 'Confirm intake', exact: true }).click();
  const intakeDialog = staff.getByRole('dialog');
  await intakeDialog.getByRole('checkbox').check();
  await intakeDialog.getByRole('button', { name: 'Confirm pet received', exact: true }).click();
  await expect(intakeDialog).toHaveCount(0);
  const received = await api(`/surrenders/${requestId}/`);
  assert.equal(received.status, 'received');
  assert.equal((await api(`/pets/${received.pet}/`)).status, 'for_assessment');
  await owner.reload();
  await expect(owner.getByRole('button', { name: 'Cancel request', exact: true })).toHaveCount(0);
  await expect(owner.getByText('The center has received your pet. Your request is complete.', { exact: true })).toBeVisible();
  await staff.getByRole('link', { name: 'Manage official pet record', exact: true }).click();
  await expect(staff.getByRole('heading', { name: 'Edit Pet', exact: true })).toBeVisible();
  await expect(staff.getByLabel('Name', { exact: true })).toHaveValue('Browser Mochi');
  await staff.getByLabel('Care status', { exact: true }).selectOption('available');
  await staff.getByLabel('Description', { exact: true }).fill('Assessed and ready to find a home.');
  await staff.getByRole('button', { name: 'Save Changes', exact: true }).click();
  await expect(staff.getByRole('heading', { name: 'Edit Pet', exact: true })).toHaveCount(0);
  await owner.goto(`${ownerOrigin}/pets/${received.pet}`);
  await expect(owner.getByRole('heading', { name: 'Browser Mochi', exact: true })).toBeVisible();
  await expect(owner.locator('body')).toContainText('Assessed and ready to find a home.');
  assert.equal((await api('/pets/')).count, 1);
  await staff.setViewportSize({ width: 390, height: 844 });
  await staff.goto(`${staffOrigin}/surrenders/${requestId}`);
  await expect(staff.getByRole('heading', { name: 'Browser Mochi — surrender request', exact: true })).toBeVisible();
  await noOverflow(staff);
  await staff.screenshot({ path: '../test-results/surrender-staff-mobile.png', fullPage: true });
  assert.deepEqual(errors, []);
  console.log('PASS: mobile owner submit, private photos, staff information request, owner resubmit, intake scheduling, confirmed handover, exact pet editor, assessment clearance, public pet details, and mobile staff layout.');
} finally {
  if (browser) await browser.close();
  for (const server of servers) server.kill();
}
