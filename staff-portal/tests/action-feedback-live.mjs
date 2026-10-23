// Real saves run only against ActionFeedbackBrowserTests' isolated database.
import assert from 'node:assert/strict';
import path from 'node:path';
import { mkdir } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { chromium, expect as baseExpect } from '@playwright/test';

const fixture = JSON.parse(process.env.PAWCONNECT_FEEDBACK_FIXTURE || 'null');
if (!fixture || !/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(fixture.api) || fixture.api.endsWith(':8000')) throw Error('Isolated live-server fixture required.');
const expect = baseExpect.configure({ timeout: 15000 });
const origins = { adopter: 'http://127.0.0.1:5196', staff: 'http://127.0.0.1:5197' };
const servers = [], pages = {}, errors = [];
let browser;
process.env.VITE_API_URL = '/api';
process.env.VITE_API_BASE_URL = '/api';

async function screenshot(page, label) {
  await mkdir(fixture.screenshots, { recursive: true });
  await page.screenshot({ path: path.join(fixture.screenshots, `${label}.png`) });
}
async function insideViewport(page) {
  const box = await page.locator('.toast-region').boundingBox();
  const viewport = page.viewportSize();
  assert.ok(box && box.x >= 0 && box.x + box.width <= viewport.width + 1 && box.y >= 0 && box.y + box.height <= viewport.height + 1);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
}
async function toastMatchesTheme(page) {
  const colors = await page.locator('.toast-notice').last().evaluate(element => {
    const root = getComputedStyle(document.documentElement);
    const background = getComputedStyle(element).backgroundColor.match(/\d+/g).slice(0, 3).map(Number);
    const surface = root.getPropertyValue('--surface').trim().split(/\s+/).map(Number);
    return { background, surface };
  });
  assert.deepEqual(colors.background, colors.surface);
}

try {
  for (const [folder, port] of [['adopter-portal', 5196], ['staff-portal', 5197]]) {
    const source = `import { createServer } from 'vite'; const server = await createServer({ configFile:'vite.config.ts', envFile:false, logLevel:'error', server:{host:'127.0.0.1',port:${port},strictPort:true,proxy:{'/api':{target:${JSON.stringify(fixture.api)},changeOrigin:true}}} }); await server.listen(); console.log('FEEDBACK_READY');`;
    const child = spawn(process.execPath, ['--input-type=module', '-e', source], { cwd: path.resolve('../', folder), env: process.env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    servers.push(child);
    await new Promise((resolve, reject) => {
      let stderr = '';
      const timer = setTimeout(() => reject(Error(`Vite startup timed out: ${stderr}`)), 30000);
      child.stderr.on('data', data => { stderr += data.toString(); });
      child.stdout.on('data', data => { if (data.toString().includes('FEEDBACK_READY')) { clearTimeout(timer); resolve(); } });
      child.on('error', error => { clearTimeout(timer); reject(error); });
      child.on('exit', code => { clearTimeout(timer); reject(Error(`Vite exited (${code}): ${stderr}`)); });
    });
  }
  browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
  for (const role of ['adopter', 'staff']) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: 'light' });
    await context.addInitScript(({ role, auth }) => {
      localStorage.setItem(role === 'adopter' ? 'pam_token' : 'staff_auth_token', auth.token);
      localStorage.setItem(role === 'adopter' ? 'pam_user' : 'staff_auth_user', JSON.stringify(auth.user));
      localStorage.setItem('pawconnect-theme', 'light');
    }, { role, auth: fixture[role] });
    pages[role] = await context.newPage();
    pages[role].on('pageerror', error => errors.push(error.message));
  }
  const { adopter, staff } = pages;
  const adopterNotices = adopter.getByRole('region', { name: 'Action confirmations' });
  const staffNotices = staff.getByRole('region', { name: 'Action confirmations' });
  await adopter.goto(`${origins.adopter}/applications/new?pet=${fixture.pet}`);
  for (const [id, value] of [['why_adopt', 'A caring and permanent home.'], ['experience_with_pets', 'I have cared for cats before.'], ['living_situation', 'A safe home with room for a pet.'], ['references', 'A reference is available for review.']]) await adopter.locator(`#${id}`).fill(value);
  await adopter.getByRole('radio', { name: 'Yes', exact: true }).check();
  await adopter.locator('#privacy_consent').check();
  await adopter.getByRole('button', { name: 'Continue', exact: true }).click();
  for (const type of ['identification', 'proof_of_address', 'barangay_certification', 'cage_photo']) {
    await adopter.locator(`#file-${type}`).setInputFiles({ name: `${type}.txt`, mimeType: 'text/plain', buffer: Buffer.from('Isolated workflow test document.') });
  }
  await adopter.getByRole('button', { name: 'Continue', exact: true }).click();
  let releaseApplication;
  const applicationGate = new Promise(resolve => { releaseApplication = resolve; });
  await adopter.route('**/api/applications/', async route => { if (route.request().method() === 'POST') await applicationGate; await route.continue(); });
  const submitted = adopter.waitForResponse(response => response.url().endsWith('/api/applications/') && response.request().method() === 'POST');
  await adopter.getByRole('button', { name: 'Submit Application', exact: true }).click();
  await expect(adopter.getByRole('button', { name: 'Submitting...', exact: true })).toBeDisabled();
  await expect(adopterNotices.locator('.toast-notice')).toHaveCount(0);
  releaseApplication();
  const applicationResponse = await submitted;
  assert.equal(applicationResponse.status(), 201);
  const application = await applicationResponse.json();
  await expect(adopterNotices.getByText('Application submitted', { exact: true })).toBeVisible();
  await toastMatchesTheme(adopter);
  await screenshot(adopter, 'adopter-success-light');
  await adopter.getByRole('link', { name: 'View application', exact: true }).click();
  await expect(adopterNotices.getByText('Application submitted', { exact: true })).toBeVisible();
  await adopterNotices.getByRole('button', { name: 'Dismiss: Application submitted', exact: true }).click();
  await expect(adopterNotices.locator('.toast-notice')).toHaveCount(0);

  await staff.goto(`${origins.staff}/applications/${application.id}`);
  await staff.getByRole('button', { name: 'Approve Application', exact: true }).click();
  await expect(staffNotices.getByText('Application approved', { exact: true })).toBeVisible();
  await staffNotices.getByRole('button', { name: 'Dismiss: Application approved' }).click();
  await staff.getByRole('navigation', { name: 'Staff portal sections' }).getByRole('link', { name: 'Pets', exact: true }).click();
  await staff.getByRole('button', { name: 'Add New Pet', exact: true }).click();
  await staff.getByLabel('Name', { exact: true }).fill('   ');
  await staff.getByLabel('Age (Years)', { exact: true }).fill('1');
  await staff.getByLabel('Weight (kg)', { exact: true }).fill('4.5');
  const invalid = staff.waitForResponse(response => response.url().endsWith('/api/pets/') && response.request().method() === 'POST');
  await staff.getByRole('button', { name: 'Create Pet', exact: true }).click();
  assert.equal((await invalid).status(), 400);
  await expect(staff.getByText('This field may not be blank.', { exact: true })).toBeVisible();
  await expect(staffNotices.locator('.toast-notice')).toHaveCount(0);
  await staff.getByLabel('Name', { exact: true }).fill('Feedback Buddy');
  const created = staff.waitForResponse(response => response.url().endsWith('/api/pets/') && response.request().method() === 'POST');
  await staff.getByRole('button', { name: 'Create Pet', exact: true }).click();
  const createdResponse = await created;
  assert.equal(createdResponse.status(), 201);
  const pet = await createdResponse.json();
  await expect(staffNotices.getByText('Pet added', { exact: true })).toBeVisible();
  await screenshot(staff, 'staff-success-light');
  await staff.getByRole('row').filter({ hasText: 'Feedback Buddy' }).getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(staff.getByText('Existing photos (0)', { exact: true })).toBeVisible();
  await staff.getByLabel('Breed', { exact: true }).fill('Friendly mix');
  await staff.getByRole('button', { name: 'Save Changes', exact: true }).click();
  await expect(staffNotices.getByText('Pet updated', { exact: true })).toBeVisible();
  await staff.getByRole('button', { name: 'Switch to dark mode', exact: true }).click();
  await toastMatchesTheme(staff);
  await screenshot(staff, 'staff-success-dark');
  const dismissUpdated = staffNotices.getByRole('button', { name: 'Dismiss: Pet updated', exact: true });
  await dismissUpdated.focus();
  await dismissUpdated.press('Escape');
  await expect(staffNotices.locator('.toast-notice')).toHaveCount(0);
  await staff.clock.install();
  await staff.getByRole('navigation', { name: 'Staff portal sections' }).getByRole('link', { name: 'Health Records', exact: true }).click();
  await staff.getByRole('button', { name: 'Add Health Record', exact: true }).click();
  await staff.getByRole('combobox', { name: 'Pet', exact: true }).selectOption(pet.id);
  await staff.getByLabel('Record Date', { exact: true }).fill('2026-10-23');
  await staff.getByLabel('Diagnosis', { exact: true }).fill('Healthy');
  await staff.getByRole('button', { name: 'Save Record', exact: true }).click();
  await expect(staffNotices.getByText('Health record added', { exact: true })).toBeVisible();
  await expect(staffNotices.locator('.toast-notice')).toHaveCount(1);
  for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 568 }]) {
    await staff.setViewportSize(viewport);
    await insideViewport(staff);
  }
  await screenshot(staff, 'staff-success-mobile-dark');
  await expect(staffNotices.getByText('Health record added', { exact: true })).toBeVisible();
  await staff.mouse.move(0, 0);
  await staff.clock.fastForward(7100);
  await expect(staffNotices.locator('.toast-notice')).toHaveCount(0);
  assert.deepEqual(errors, []);
  console.log('PASS: real application submission and approval, pet create/edit, health save; no success before response or on HTTP 400; route persistence, dismissal, timed expiry, both themes and mobile bounds.');
} catch (error) {
  console.error('Browser errors:', errors);
  for (const [role, page] of Object.entries(pages)) console.error(role, page.url(), (await page.locator('body').innerText()).slice(0, 2400));
  throw error;
} finally {
  await browser?.close();
  for (const server of servers) server.kill();
}
