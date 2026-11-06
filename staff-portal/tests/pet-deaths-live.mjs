// Run only via Django's disposable LiveServerTestCase.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdir } from 'node:fs/promises';
import { chromium, expect as baseExpect } from '@playwright/test';

const fixture = JSON.parse(process.env.PAWCONNECT_DEATH_FIXTURE || 'null');
if (!fixture || !/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(fixture.api) || fixture.api.endsWith(':8000')) throw Error('Isolated live-server fixture required.');
const expect = baseExpect.configure({ timeout: 15000 });
const servers = [];
const errors = [];
let browser;

async function startPortal(root, port) {
  const source = `import { createServer } from 'vite'; const server = await createServer({root:${JSON.stringify(root)},configFile:${JSON.stringify(`${root}/vite.config.ts`)},envFile:false,logLevel:'error',server:{host:'127.0.0.1',port:${port},strictPort:true,proxy:{'/api':{target:${JSON.stringify(fixture.api)},changeOrigin:true}}}}); await server.listen(); console.log('DEATH_UI_READY');`;
  const server = spawn(process.execPath, ['--input-type=module', '-e', source], { env: { ...process.env, VITE_API_URL: '/api', VITE_API_BASE_URL: '/api' }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  servers.push(server);
  await new Promise((resolve, reject) => {
    let stderr = '';
    const timer = setTimeout(() => reject(Error(`Vite startup timed out: ${stderr}`)), 40000);
    server.stderr.on('data', data => { stderr += data.toString(); });
    server.stdout.on('data', data => { if (data.toString().includes('DEATH_UI_READY')) { clearTimeout(timer); resolve(); } });
    server.on('error', error => { clearTimeout(timer); reject(error); });
    server.on('exit', code => { clearTimeout(timer); reject(Error(`Vite exited (${code}): ${stderr}`)); });
  });
  return `http://127.0.0.1:${port}`;
}

async function contextFor(user, prefix) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await context.addInitScript(({ user, prefix }) => { localStorage.setItem(`${prefix}_token`, user.token); localStorage.setItem(`${prefix}_user`, JSON.stringify(user.user)); }, { user, prefix });
  await context.route('**/*', route => ['localhost', '127.0.0.1', ''].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  return page;
}

try {
  const cwd = process.cwd().replace(/\\/g, '/');
  const [ownerOrigin, staffOrigin] = await Promise.all([startPortal(`${cwd}/../adopter-portal`, 5198), startPortal(cwd, 5199)]);
  browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
  const staff = await contextFor(fixture.staff, 'staff_auth');
  const owner = await contextFor(fixture.owner, 'pam');
  const admin = await contextFor(fixture.admin, 'staff_auth');
  await staff.goto(`${staffOrigin}/pets`);
  await staff.getByRole('button', { name: 'Record pet death', exact: true }).click();
  let dialog = staff.getByRole('dialog');
  await expect(dialog.getByRole('heading', { name: 'Record pet death', exact: true })).toBeVisible();
  await dialog.getByLabel('Date of death', { exact: true }).fill(fixture.today);
  await dialog.getByLabel('Cause of death (enter Unknown if unconfirmed)', { exact: true }).fill('CONFIDENTIAL medical cause');
  await dialog.getByLabel('Veterinarian (optional)', { exact: true }).fill('Dr. Example');
  await dialog.getByLabel('Internal notes (staff only)', { exact: true }).fill('CONFIDENTIAL center notes');
  await dialog.getByRole('checkbox').check();
  await mkdir('../test-results', { recursive: true });
  await staff.screenshot({ path: '../test-results/pet-death-confirmation-mobile.png', fullPage: true });
  await dialog.getByRole('button', { name: 'Record death and close adoption activities', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(staff.getByRole('button', { name: 'Death record', exact: true })).toBeVisible();
  assert.equal(new URL(staff.url()).searchParams.get('scope'), 'history');
  await staff.reload();
  await staff.getByRole('button', { name: 'Death record', exact: true }).click();
  dialog = staff.getByRole('dialog');
  await expect(dialog).toContainText('CONFIDENTIAL medical cause');
  await expect(dialog.getByRole('button', { name: 'Correct mistaken entry', exact: true })).toHaveCount(0);
  await dialog.getByRole('button', { name: 'Close', exact: true }).click();

  await owner.goto(`${ownerOrigin}/pets/${fixture.pet}`);
  await expect(owner.getByText('This pet is currently not available for adoption.', { exact: true })).toBeVisible();
  assert(!(await owner.locator('body').innerText()).includes('CONFIDENTIAL'));
  await owner.goto(`${ownerOrigin}/applications/${fixture.application}`);
  await expect(owner.locator('body')).toContainText('The pet passed away while in the center');
  await expect(owner.getByRole('button', { name: /Request.*visit|Submit.*appointment/i })).toHaveCount(0);
  await owner.screenshot({ path: '../test-results/pet-death-owner-application-mobile.png', fullPage: true });
  await owner.goto(`${ownerOrigin}/pets`);
  await expect(owner.getByRole('heading', { name: 'Browser Mochi', exact: true })).toHaveCount(0);

  await staff.goto(`${staffOrigin}/payments`);
  const reviews = staff.getByRole('region', { name: 'Payments requiring review after pet death', exact: true });
  await expect(reviews).toContainText('Browser Mochi');
  await reviews.getByRole('button', { name: 'Record review outcome', exact: true }).click();
  dialog = staff.getByRole('dialog');
  await dialog.getByLabel('Review outcome (staff only)', { exact: true }).fill('Adopter contacted; any applicable refund will be coordinated onsite.');
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: 'Save payment review outcome', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(reviews).toHaveCount(0);

  await admin.goto(`${staffOrigin}/pets?scope=history&status=deceased`);
  await admin.getByRole('button', { name: 'Death record', exact: true }).click();
  dialog = admin.getByRole('dialog');
  await dialog.getByRole('button', { name: 'Correct mistaken entry', exact: true }).click();
  await dialog.getByLabel('Reason for correction', { exact: true }).fill('Incorrect pet was selected. Identity verified against the center record.');
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: 'Confirm correction', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(admin.locator('main')).toContainText('For Assessment');
  await owner.goto(`${ownerOrigin}/applications/${fixture.application}`);
  await expect(owner.locator('body')).toContainText('A previous death notice was corrected by an administrator.');
  assert(await admin.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await admin.setViewportSize({ width: 1440, height: 1000 });
  await admin.reload();
  await expect(admin.locator('tbody')).toContainText('Browser Mochi');
  assert.deepEqual(errors, []);
  console.log('PASS: mobile staff death reporting, retained private details, history reload, public unavailable page, adopter cancellation reason, payment review resolution, administrator correction, and desktop/mobile pet lists.');
} finally {
  if (browser) await browser.close();
  for (const server of servers) server.kill();
}
