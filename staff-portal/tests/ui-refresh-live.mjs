// Runs only with Django's isolated LiveServerTestCase fixture.
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { mkdir } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { chromium, expect as baseExpect } from '@playwright/test';
import { verifyPortalTheme } from './theme-checks.mjs';

const fixture = JSON.parse(process.env.PAWCONNECT_UI_FIXTURE || 'null');
if (!fixture || !/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(fixture.api) || fixture.api.endsWith(':8000')) throw Error('Isolated backend fixture is required.');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const origins = { adopter: 'http://127.0.0.1:5192', staff: 'http://127.0.0.1:5193' };
const servers = [];
let browser;
let checks = 0;
const pages = {};
const errors = [], unexpectedWrites = [];
const expect = baseExpect.configure({ timeout: 15000 });
process.env.VITE_API_URL = '/api';
process.env.VITE_API_BASE_URL = '/api';

async function shot(page, name) {
  if (!process.env.PAWCONNECT_UI_SCREENSHOTS) return;
  await mkdir(process.env.PAWCONNECT_UI_SCREENSHOTS, { recursive: true });
  await page.screenshot({ path: path.join(process.env.PAWCONNECT_UI_SCREENSHOTS, `${name}.png`), fullPage: false });
}
async function read(role, route) {
  const response = await fetch(`${fixture.api}/api${route}`, { headers: { Authorization: `Token ${fixture[role].token}` } });
  assert.equal(response.status, 200, route);
  return response.json();
}
async function noOverflow(page) {
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `Horizontal overflow at ${JSON.stringify(page.viewportSize())}`);
}
async function theme(page, mode) {
  const current = await page.locator('html').getAttribute('data-theme');
  if (current !== mode) await page.getByRole('button', { name: `Switch to ${mode} mode`, exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', mode);
}

// Check actual rendered surfaces: an icon changing color alone must never pass.
async function assertThemeSurfaces(page, mode) {
  await verifyPortalTheme(page, mode);
}
async function assertInputContrast(page) {
  const colors = await page.locator('.field-input').first().evaluate(el => {
    const style = getComputedStyle(el);
    return { foreground: style.color, background: style.backgroundColor };
  });
  function luminance(color) {
    const channels = color.match(/[\d.]+/g).slice(0,3).map(Number).map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
    return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
  }
  const a = luminance(colors.foreground), b = luminance(colors.background);
  assert.ok((Math.max(a,b) + .05) / (Math.min(a,b) + .05) >= 4.5, `Input text contrast: ${JSON.stringify(colors)}`);
}

try {
  for (const [folder, port] of [['adopter-portal', 5192], ['staff-portal', 5193]]) {
    // Separate processes prevent Tailwind/PostCSS contexts from one portal
    // being reused for the other portal's independently configured stylesheet.
    const source = `import { createServer } from 'vite'; const server = await createServer({ configFile:'vite.config.ts', envFile:false, logLevel:'error', server:{host:'127.0.0.1',port:${port},strictPort:true,proxy:{'/api':{target:${JSON.stringify(fixture.api)},changeOrigin:true}}} }); await server.listen(); console.log('PAWCONNECT_UI_READY');`;
    const child = spawn(process.execPath, ['--input-type=module', '-e', source], { cwd: path.join(root, folder), env: process.env, windowsHide: true, stdio: ['ignore','pipe','pipe'] });
    servers.push(child);
    await new Promise((resolve, reject) => {
      let errors = '';
      const timeout = setTimeout(() => reject(Error(`Vite startup timed out: ${errors}`)), 30000);
      child.stderr.on('data', data => { errors += data.toString(); });
      child.stdout.on('data', data => { if (data.toString().includes('PAWCONNECT_UI_READY')) { clearTimeout(timeout); resolve(); } });
      child.on('error', reject);
      child.on('exit', code => { clearTimeout(timeout); if (code) reject(Error(`Vite exited: ${errors}`)); });
    });
  }
  browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
  for (const role of ['adopter', 'staff']) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: 'light' });
    await context.addInitScript(({ role, auth }) => {
      localStorage.setItem(role === 'adopter' ? 'pam_token' : 'staff_auth_token', auth.token);
      localStorage.setItem(role === 'adopter' ? 'pam_user' : 'staff_auth_user', JSON.stringify(auth.user));
    }, { role, auth: fixture[role] });
    await context.route('**/api/**', route => {
      const request = route.request(), url = new URL(request.url());
      const allowedWrite = request.method() === 'PATCH' && /\/notifications\/[^/]+\/read\/$/.test(url.pathname) || request.method() === 'POST' && ['/api/notifications/mark-all-read/', '/api/auth/logout/'].includes(url.pathname);
      if (url.origin !== origins[role] || (request.method() !== 'GET' && !allowedWrite)) { unexpectedWrites.push(`${request.method()} ${url.pathname}`); return route.abort(); }
      return route.continue();
    });
    pages[role] = await context.newPage();
    pages[role].on('pageerror', error => errors.push(error.message));
  }
  const { adopter, staff } = pages;
  await adopter.goto(origins.adopter);
  await expect(adopter).toHaveTitle('PawConnect | Find a Pet');
  await expect(adopter.getByTestId('latest-pets').getByRole('link')).toHaveCount(3);
  await expect(adopter.getByRole('banner').getByRole('link', { name: 'My Applications', exact: true })).toHaveCount(0);
  await noOverflow(adopter);
  await assertThemeSurfaces(adopter, 'light');
  await shot(adopter, 'adopter-home-light');
  await theme(adopter, 'dark');
  await assertThemeSurfaces(adopter, 'dark');
  await shot(adopter, 'adopter-home-dark');
  await theme(adopter, 'light');
  await adopter.getByRole('button', { name: 'Profile menu', exact: true }).hover();
  await expect(adopter.getByRole('navigation', { name: 'Account', exact: true })).toBeVisible();
  await adopter.getByRole('navigation', { name: 'Account', exact: true }).getByRole('link', { name: 'My Applications', exact: true }).click();
  await expect(adopter).toHaveURL(`${origins.adopter}/applications`);
  await adopter.getByRole('button', { name: 'Profile menu', exact: true }).click();
  await expect(adopter.getByRole('navigation', { name: 'Account', exact: true })).toBeVisible();
  await adopter.getByRole('button', { name: 'Profile menu', exact: true }).press('Escape');
  await expect(adopter.getByRole('navigation', { name: 'Account', exact: true })).toHaveCount(0);
  checks++;

  await adopter.goto(`${origins.adopter}/pets`);
  await expect(adopter.getByRole('heading', { name: 'Find a Pet', exact: true })).toBeVisible();
  await expect(adopter.locator('.pet-card')).toHaveCount(20);
  const firstPageName = await adopter.locator('.pet-card h3').first().innerText();
  await adopter.getByRole('link', { name: 'Next page', exact: true }).click();
  await expect(adopter.locator('.pet-card')).toHaveCount(6);
  assert.notEqual(await adopter.locator('.pet-card h3').first().innerText(), firstPageName);
  await expect(adopter.locator('.pet-card').first()).toContainText('4.50 kg');
  await adopter.getByLabel('Min weight (kg)', { exact: true }).fill('5');
  await adopter.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(adopter.getByText('No pets match your search.', { exact: true })).toBeVisible();
  await adopter.getByLabel('Min weight (kg)', { exact: true }).fill('4');
  await adopter.getByLabel('Max weight (kg)', { exact: true }).fill('4.5');
  await adopter.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(adopter.locator('.pet-card')).toHaveCount(20);
  await noOverflow(adopter);
  checks++;

  const countBefore = (await read('adopter', '/notifications/unread-count/')).unread_count;
  await adopter.getByRole('button', { name: `Notifications (${countBefore} unread)`, exact: true }).click();
  const recent = adopter.getByRole('region', { name: 'Recent notifications', exact: true });
  await expect(recent).toContainText('Application Approved');
  await recent.getByRole('link').filter({ hasText: 'Application Approved' }).click();
  await expect(adopter).toHaveURL(`${origins.adopter}/applications/${fixture.applications.approved}`);
  await expect(adopter.getByRole('heading', { name: 'Application status', exact: true })).toBeVisible();
  await expect(adopter.getByRole('link', { name: 'For Milo', exact: false })).toBeVisible();
  await expect(adopter.getByLabel('Appointment status: Confirmed', { exact: true })).toBeVisible();
  await expect(adopter.getByText('Your visit is confirmed for', { exact: false })).toBeVisible();
  for (const text of ['Why you want to adopt', 'Experience with pets', 'Living situation', 'References', 'Uploaded documents', 'SAVED_FORM_ANSWER', 'SAVED_DOCUMENT_FILENAME.txt', 'PRIVATE_STAFF_NOTES']) await expect(adopter.getByText(text, { exact: false })).toHaveCount(0);
  await expect(adopter.getByRole('button', { name: 'Request Reschedule', exact: true })).toBeVisible();
  await expect.poll(async () => (await read('adopter', '/notifications/unread-count/')).unread_count).toBe(countBefore - 1);
  await shot(adopter, 'adopter-status-light');
  checks++;

  await adopter.goto(`${origins.adopter}/applications/${fixture.applications.rejected}`);
  await expect(adopter.getByText('Please discuss the housing requirement with staff.', { exact: false })).toBeVisible();
  await expect(adopter.getByText('SAVED_FORM_ANSWER', { exact: false })).toHaveCount(0);
  await adopter.goto(`${origins.adopter}/applications/${fixture.applications.pending_documents}`);
  await expect(adopter.getByRole('heading', { name: 'Staff feedback', exact: true })).toBeVisible();
  await expect(adopter.getByText('Please attach a clearer copy of your valid ID.', { exact: true })).toBeVisible();
  await expect(adopter.getByRole('button', { name: 'Upload document', exact: true })).toBeVisible();
  await expect(adopter.getByText('SAVED_DOCUMENT_FILENAME.txt', { exact: false })).toHaveCount(0);
  await adopter.goto(`${origins.adopter}/applications/${fixture.applications.adoption_completed}`);
  await expect(adopter.getByText('Adoption Completed', { exact: true })).toBeVisible();
  await expect(adopter.getByText('Your adoption is complete.', { exact: false })).toBeVisible();
  await expect(adopter.getByRole('button', { name: 'Upload document', exact: true })).toHaveCount(0);
  await expect(adopter.getByRole('button', { name: 'Request Reschedule', exact: true })).toHaveCount(0);
  checks++;

  await theme(adopter, 'dark');
  const darkBackground = await adopter.locator('body').evaluate(element => getComputedStyle(element).backgroundColor);
  await assertThemeSurfaces(adopter, 'dark');
  await shot(adopter, 'adopter-status-dark');
  await adopter.reload();
  await expect(adopter.locator('html')).toHaveAttribute('data-theme', 'dark');
  assert.equal(await adopter.locator('body').evaluate(element => getComputedStyle(element).backgroundColor), darkBackground);
  await adopter.getByRole('button', { name: /Notifications/ }).click();
  await adopter.getByRole('region', { name: 'Recent notifications' }).getByRole('link', { name: 'View all notifications', exact: true }).click();
  await expect(adopter.getByRole('heading', { name: 'Notifications', exact: true })).toBeVisible();
  await adopter.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(adopter.getByText('Page 2', { exact: true })).toBeVisible();
  await noOverflow(adopter);
  checks++;

  await staff.goto(origins.staff);
  await expect(staff).toHaveTitle('PawConnect | Staff Workspace');
  await expect(staff.getByRole('heading', { name: 'Dashboard', exact: true })).toBeVisible();
  await expect(staff.getByRole('button', { name: 'Notifications (131 unread)', exact: true })).toBeVisible();
  await expect(staff.getByRole('button', { name: 'Notifications (131 unread)', exact: true })).toContainText('99+');
  await assertThemeSurfaces(staff, 'light');
  await shot(staff, 'staff-dashboard-light');
  await staff.getByRole('button', { name: 'Notifications (131 unread)', exact: true }).click();
  await staff.getByRole('region', { name: 'Recent notifications' }).getByRole('link').filter({ hasText: 'Staff update 131' }).click();
  await expect(staff).toHaveURL(`${origins.staff}/applications`);
  await expect.poll(async () => (await read('staff', '/notifications/unread-count/')).unread_count).toBe(130);
  await expect(staff.getByRole('button', { name: 'Notifications (130 unread)', exact: true })).toBeVisible();
  await theme(staff, 'dark');
  await staff.reload();
  await expect(staff.locator('html')).toHaveAttribute('data-theme', 'dark');
  const staffBackground = await staff.locator('body').evaluate(element => getComputedStyle(element).backgroundColor);
  assert.notEqual(staffBackground, darkBackground, 'Portals need distinct palettes');
  await assertThemeSurfaces(staff, 'dark');
  await expect(staff.locator('tbody tr')).toHaveCount(4);
  await assertThemeSurfaces(staff, 'dark');
  await shot(staff, 'staff-applications-dark');
  checks++;

  // Staff editor and public pet detail must present the same saved labels.
  await staff.goto(`${origins.staff}/pets`);
  await staff.getByRole('row').filter({ hasText: 'Available Friend 26' }).getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(staff.getByLabel('Weight (kg)', { exact: true })).toHaveValue('4.50');
  await staff.getByRole('button', { name: 'Cancel', exact: true }).click();
  await staff.getByRole('button', { name: 'Add New Pet', exact: true }).click();
  await expect(staff.getByLabel('Size', { exact: true })).toHaveCount(0);
  const weight = staff.getByLabel('Weight (kg)', { exact: true });
  await expect(weight).toHaveValue('');
  await weight.fill('-1');
  assert.equal(await weight.evaluate(input => input.checkValidity()), false);
  await weight.fill('4.5');
  assert.equal(await weight.evaluate(input => input.checkValidity()), true);
  await staff.getByLabel('Name', { exact: true }).fill('  bRUNo  ');
  await staff.getByLabel('Breed', { exact: true }).fill('sHIH   tZU');
  await staff.getByLabel('Color', { exact: true }).fill('tAN  AND  wHITE');
  await staff.getByLabel('Age (Years)', { exact: true }).fill('2');
  await staff.getByLabel('Description', { exact: true }).fill('Friendly and gentle.\nEnjoys a quiet home.');
  const preview = staff.getByRole('complementary', { name: 'Adopter pet preview', exact: true });
  await expect(preview.getByRole('heading', { name: 'Bruno', exact: true })).toBeVisible();
  await expect(preview).toContainText('Shih Tzu');
  await expect(preview).toContainText('Tan And White');
  await expect(preview).toContainText('4.5 kg');
  await expect(staff.getByLabel('Name', { exact: true })).toHaveValue('  bRUNo  ');
  await adopter.goto(`${origins.adopter}/pets/${fixture.public_pet}`);
  await expect(adopter.getByRole('heading', { name: 'Bruno', exact: true })).toBeVisible();
  await expect(adopter.getByText('Tan And White', { exact: true })).toBeVisible();
  await expect(adopter.getByText('4.50 kg', { exact: true })).toBeVisible();
  await expect(adopter.getByText('Friendly and gentle.', { exact: false })).toBeVisible();
  for (const mode of ['light', 'dark']) {
    for (const page of [adopter, staff]) {
      await theme(page, mode);
      await assertThemeSurfaces(page, mode);
      await noOverflow(page);
    }
    await assertInputContrast(staff);
    assert.equal(await preview.locator('.pet-copy').evaluate(el => getComputedStyle(el).whiteSpace), 'pre-line');
    await shot(staff, `staff-pet-editor-${mode}`);
    await shot(adopter, `adopter-pet-detail-${mode}`);
  }
  // Refresh and switch back in both directions, verifying real canvas/cards/inputs.
  for (const page of [adopter, staff]) {
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await assertThemeSurfaces(page, 'dark');
    await theme(page, 'light');
    await assertThemeSurfaces(page, 'light');
    await theme(page, 'dark');
  }
  checks++;

  for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 568 }, { width: 844, height: 390 }]) {
    for (const page of [adopter, staff]) { await page.setViewportSize(viewport); await noOverflow(page); }
    await adopter.getByRole('button', { name: 'Profile menu', exact: true }).click();
    await expect(adopter.getByRole('navigation', { name: 'Account', exact: true })).toBeVisible();
    const box = await adopter.getByRole('navigation', { name: 'Account', exact: true }).boundingBox();
    assert.ok(box && box.x >= 0 && box.x + box.width <= viewport.width + 1);
    await adopter.getByRole('button', { name: 'Profile menu', exact: true }).press('Escape');
    if (viewport.width < 768) {
      await staff.getByRole('button', { name: 'Open navigation', exact: true }).click();
      await expect(staff.getByRole('navigation', { name: 'Staff portal sections', exact: true })).toBeVisible();
      await staff.getByRole('navigation', { name: 'Staff portal sections', exact: true }).getByRole('link', { name: 'Pets', exact: true }).click();
      await expect(staff).toHaveURL(`${origins.staff}/pets`);
      await expect(staff.getByText('Loading...', { exact: true })).toHaveCount(0);
      await staff.getByRole('button', { name: 'Add New Pet', exact: true }).click();
      await noOverflow(staff);
      await assertThemeSurfaces(staff, 'dark');
    }
    if (viewport.width === 390) { await shot(adopter, 'adopter-mobile-dark'); await shot(staff, 'staff-mobile-dark'); }
  }
  checks++;
  await adopter.getByRole('button', { name: 'Profile menu', exact: true }).click();
  await adopter.getByRole('navigation', { name: 'Account', exact: true }).getByRole('button', { name: 'Logout', exact: true }).click();
  await expect(adopter).toHaveURL(origins.adopter + '/');
  await expect(adopter.getByRole('button', { name: 'Profile menu', exact: true })).toHaveCount(0);
  await expect(adopter.getByRole('banner').getByRole('link', { name: 'Log in', exact: true })).toBeVisible();
  checks++;
  assert.deepEqual(errors, []);
  assert.deepEqual(unexpectedWrites, []);
  console.log(`PASS: ${checks} UI browser groups; both portal themes and persisted preference, three-pet cap vs full listing, hover/click profile menu, real notification counts and pagination, compact status view, requested-upload/reschedule controls, desktop/mobile bounds; no application/payment/adoption writes.`);
} catch (error) {
  console.error('Browser errors:', errors, 'Unexpected writes:', unexpectedWrites);
  for (const [role, page] of Object.entries(pages)) {
    console.error(role, page.url(), (await page.locator('body').innerText()).slice(0, 2500));
    await shot(page, `${role}-failure`);
  }
  throw error;
} finally {
  await browser?.close();
  for (const server of servers) server.kill();
}
