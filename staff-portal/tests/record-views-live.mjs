// Real API and browser navigation; credentials come only from the isolated test DB.
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, expect } from '@playwright/test';
import { createServer } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from 'tailwindcss';
import autoprefixer from 'autoprefixer';

const fixture = JSON.parse(process.env.PAWCONNECT_RECORD_FIXTURE || 'null');
if (!fixture || !/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(fixture.api) || fixture.api.endsWith(':8000')) {
  throw Error('An isolated Django backend is required.');
}
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const origin = 'http://127.0.0.1:5198';
process.env.VITE_API_URL = '/api';
process.env.VITE_API_BASE_URL = '/api';
let server, browser;
const errors = [];
try {
  server = await createServer({
    configFile: false, envFile: false, root, plugins: [react()], logLevel: 'error',
    css: { postcss: { plugins: [tailwindcss(path.join(root, 'tailwind.config.js')), autoprefixer()] } },
    server: { host: '127.0.0.1', port: 5198, strictPort: true, proxy: { '/api': { target: fixture.api, changeOrigin: true } } },
  });
  await server.listen();
  browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await context.addInitScript(auth => {
    localStorage.setItem('staff_auth_token', auth.token);
    localStorage.setItem('staff_auth_user', JSON.stringify(auth.user));
  }, fixture.staff);
  await context.route('**/*', route => {
    const request = route.request(), url = new URL(request.url());
    if (url.hostname.startsWith('fonts.')) return route.abort();
    if (url.pathname.startsWith('/api/') && (url.origin !== origin || request.method() !== 'GET')) {
      errors.push(`Unexpected request: ${request.method()} ${url.pathname}`);
      return route.abort();
    }
    return route.continue();
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    if (response.url().includes('/api/') && !response.ok()) errors.push(`HTTP ${response.status()} ${new URL(response.url()).pathname}`);
  });
  const views = page.getByRole('group', { name: 'Record views' });
  await page.goto(origin);
  for (const [label, count] of [['Available Pets', 24], ['Active Applications', 23], ['Scheduled Adoptions', 1], ['Completed Adoptions', 1]]) {
    await expect(page.getByRole('link', { name: new RegExp(`${count} ${label}`) })).toBeVisible();
  }
  await expect(page.getByRole('heading', { name: 'Recent Active Applications' })).toBeVisible();
  await expect(page.locator('tbody tr')).toHaveCount(5);
  await page.getByRole('link', { name: '1 Completed Adoptions' }).click();
  await expect(views.getByRole('button', { name: 'History', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('tbody tr')).toHaveCount(1);
  await expect(page.locator('tbody')).toContainText('History pet completed');
  await views.getByRole('button', { name: 'History', exact: true }).click();
  await expect(page.locator('tbody tr')).toHaveCount(3);
  await expect(page.getByLabel('Status')).toHaveValue('');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export All Filtered PDF', exact: true }).click();
  const download = await downloadPromise;
  assert.equal(await download.failure(), null);

  for (const [route, navName, total, history] of [['pets', 'Pet record pages', 25, 2], ['applications', 'Application pages', 23, 3]]) {
    await page.goto(`${origin}/${route}`);
    await expect(views.getByRole('button', { name: 'Active', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('tbody tr')).toHaveCount(20);
    const first = await page.locator('tbody tr').allTextContents();
    const nav = page.getByRole('navigation', { name: navName });
    await expect(nav).toContainText(`Page 1 · ${total}`);
    await nav.getByRole('button', { name: 'Next', exact: true }).click();
    await expect(nav).toContainText(`Page 2 · ${total}`);
    await expect(page.locator('tbody tr')).toHaveCount(total - 20);
    assert.ok((await page.locator('tbody tr').allTextContents()).every(row => !first.includes(row)));
    await views.getByRole('button', { name: 'History', exact: true }).click();
    await expect(page).not.toHaveURL(/page=/);
    await expect(page.locator('tbody tr')).toHaveCount(history);
    await expect(nav).toContainText(`Page 1 · ${history}`);
    await page.reload();
    await expect(views.getByRole('button', { name: 'History', exact: true })).toHaveAttribute('aria-pressed', 'true');
    const status = page.getByRole('combobox');
    await status.selectOption(route === 'pets' ? 'adopted' : 'adoption_completed');
    await expect(page.locator('tbody tr')).toHaveCount(route === 'pets' ? 1 : 2);
    if (route === 'applications') {
      await page.getByRole('row').filter({ hasText: 'History pet completed' }).getByRole('link', { name: 'Review', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Application Review', exact: true })).toBeVisible();
      await page.goBack();
      await expect(status).toHaveValue('adoption_completed');
    }
    await views.getByRole('button', { name: 'All records', exact: true }).click();
    await expect(status).toHaveValue('');
    await expect(nav).toContainText(`Page 1 · ${route === 'pets' ? 27 : 26}`);
  }
  await page.goto(`${origin}/reports`);
  await expect(page.getByText('Total Pets Recorded').locator('..').locator('dd')).toHaveText('27');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${origin}/pets?scope=history`);
  await expect(page.locator('tbody tr')).toHaveCount(2);
  for (const label of ['Active', 'History', 'All records']) await expect(views.getByRole('button', { name: label, exact: true })).toBeVisible();
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Mobile page overflow');
  assert.deepEqual(errors, []);
  console.log('Real dashboard counts, Active/History/All views, pagination, filter resets, reload/back navigation, history PDF, all-time inventory and mobile layout passed.');
} finally {
  if (browser) await browser.close();
  if (server) await server.close();
}
