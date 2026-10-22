import { expect, test, type Page } from '@playwright/test';

const appIds = ['00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000002'];
const appointmentIds = ['appointment-one', 'appointment-two'];

async function mockPayments(page: Page, options: { failPayment?: boolean; failSummary?: boolean } = {}) {
  // This test backend survives browser reloads. The application itself must
  // re-read it; there is no paid flag in browser storage.
  const payments: Record<string, unknown>[] = [];
  const requests: Record<string, unknown>[] = [];
  const filters: string[] = [];
  await page.addInitScript(() => {
    localStorage.setItem('staff_auth_token', 'isolated-browser-test-token');
    localStorage.setItem('staff_auth_user', JSON.stringify({ id: 'staff', role: 'staff', email: 'staff@example.com' }));
  });
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const respond = (data: unknown, status = 200) => route.fulfill({ status, json: data });
    const paginated = (results: unknown[]) => ({ count: results.length, results, next: null, previous: null });
    if (url.pathname === '/api/appointments/') {
      return respond(paginated(appIds.map((application, i) => ({
        id: appointmentIds[i], application, status: 'confirmed', requested_date: '2026-10-29',
        pet_name: `Pet ${i + 1}`, adopter_email: 'same-adopter@example.com',
      }))));
    }
    if (url.pathname.endsWith('/payment-summary/')) {
      if (options.failSummary) return respond({ error: 'Summary unavailable' }, 503);
      const application = url.pathname.split('/')[3];
      const rows = payments.filter((p) => p.application === application);
      return respond({ application_id: application, adoption_fee: '500.00',
        total_paid: rows.length ? '500.00' : '0.00', is_fee_paid: rows.length > 0,
        can_record_payment: rows.length === 0, turnover_eligible: rows.length > 0, payments: rows });
    }
    if (url.pathname === '/api/payments/record-onsite/') {
      const payload = request.postDataJSON() as Record<string, unknown>;
      requests.push(payload);
      if (options.failPayment) return respond({ error: 'Payment was not saved' }, 400);
      const payment = { id: 'persisted-payment', application: payload.application,
        amount: '500.00', status: 'completed', method: payload.method,
        receipt_number: 'REC-SERVER-ONLY', payment_date: '2026-10-23',
        created_at: '2026-10-23T04:30:00Z', pet_name: 'Pet 1' };
      payments.push(payment);
      return respond(payment, 201);
    }
    if (url.pathname === '/api/payments/persisted-payment/receipt-pdf/') {
      return route.fulfill({ contentType: 'application/pdf', body: '%PDF-test-selected-receipt' });
    }
    if (url.pathname === '/api/payments/') {
      filters.push(url.searchParams.get('status') || '');
      return respond(paginated(payments));
    }
    if (url.pathname === '/api/notifications/unread-count/') return respond({ unread_count: 0 });
    if (url.pathname === '/api/adoptions/') return respond(paginated([]));
    // No API request is ever allowed through to a real backend.
    return respond({ error: `Unexpected test API request: ${url.pathname}` }, 501);
  });
  return { payments, requests, filters };
}

async function openEntry(page: Page) {
  await page.getByRole('button', { name: '+ Record Onsite Payment' }).click();
  await expect(page.getByText('Required Onsite Payment: ₱500.00', { exact: true })).toBeVisible();
}

test('fixed fee, persisted completion hides entry after save, reload and navigation; other obligation stays payable', async ({ page }) => {
  const backend = await mockPayments(page);
  await page.goto('/payments');
  await openEntry(page);
  const entry = page.getByRole('form', { name: 'Record onsite payment' });
  await expect(entry).toBeVisible();
  await expect(page.getByLabel('Amount Received (₱)')).toHaveCount(0);
  await expect(page.getByText('Remaining Balance:', { exact: true })).toHaveCount(0);
  const submit = page.getByRole('button', { name: 'Record Payment & Generate Receipt' });
  await expect(submit).toBeDisabled();
  await page.getByLabel('Payment Method').selectOption('gcash');
  await page.getByRole('checkbox').check();
  await submit.click();
  await expect(entry).toHaveCount(0);
  await expect(page.getByLabel('Completed payment summary')).toContainText('REC-SERVER-ONLY');
  await expect(page.getByLabel('Completed payment summary')).toContainText('₱500.00');
  await expect(page.getByLabel('Completed payment summary')).toContainText('Recorded:');
  expect(backend.requests).toHaveLength(1);
  expect(backend.requests[0]).toMatchObject({ application: appIds[0], method: 'gcash', payment_received: true });
  expect(backend.requests[0]).not.toHaveProperty('amount');
  expect(backend.requests[0]).not.toHaveProperty('status');
  const download = page.waitForEvent('download');
  await page.getByLabel('Completed payment summary').getByRole('button', { name: 'Download Receipt PDF' }).click();
  expect((await download).suggestedFilename()).toContain('REC-SERVER-ONLY');

  await page.reload();
  await openEntry(page);
  await expect(page.getByLabel('Completed payment summary')).toContainText('REC-SERVER-ONLY');
  await expect(entry).toHaveCount(0);
  await page.getByLabel('Eligible Confirmed Appointment').selectOption(appointmentIds[1]);
  await expect(entry).toBeVisible();
  await expect(page.getByRole('checkbox')).not.toBeChecked();
  await page.getByLabel('Eligible Confirmed Appointment').selectOption(appointmentIds[0]);
  await expect(entry).toHaveCount(0);

  await page.getByRole('link', { name: 'Adoption Records', exact: true }).click();
  await page.getByRole('link', { name: 'Payment Records', exact: true }).click();
  await openEntry(page);
  await expect(entry).toHaveCount(0);
  await expect(page.getByLabel('Completed payment summary')).toContainText('REC-SERVER-ONLY');
  expect(backend.payments).toHaveLength(1);
});

test('a rejected request keeps entry visible without claiming success', async ({ page }) => {
  const backend = await mockPayments(page, { failPayment: true });
  await page.goto('/payments');
  await openEntry(page);
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Record Payment & Generate Receipt' }).click();
  await expect(page.getByRole('alert')).toContainText('Payment was not saved');
  await expect(page.getByRole('form', { name: 'Record onsite payment' })).toBeVisible();
  await expect(page.getByLabel('Completed payment summary')).toHaveCount(0);
  expect(backend.payments).toHaveLength(0);
});

test('summary failure never enables entry or fabricates a paid state', async ({ page }) => {
  await mockPayments(page, { failSummary: true });
  await page.goto('/payments');
  await page.getByRole('button', { name: '+ Record Onsite Payment' }).click();
  await expect(page.getByRole('alert')).toContainText('Could not verify payment eligibility');
  await expect(page.getByRole('form', { name: 'Record onsite payment' })).toHaveCount(0);
  await expect(page.getByLabel('Completed payment summary')).toHaveCount(0);
});

test('status filters keep their backend values', async ({ page }) => {
  const backend = await mockPayments(page);
  await page.goto('/payments');
  for (const status of ['completed', 'pending', 'failed', 'cancelled', 'refunded']) {
    await page.getByLabel('Status').selectOption(status);
    await expect.poll(() => backend.filters.at(-1)).toBe(status);
  }
});
