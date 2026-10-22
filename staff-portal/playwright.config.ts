import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: 'onsite-payment.spec.ts',
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:5186',
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5186 --strictPort',
    url: 'http://127.0.0.1:5186',
    reuseExistingServer: false,
    // Override local absolute API URLs. Browser tests intercept every API
    // request and must never record money against a developer's database.
    env: { VITE_API_BASE_URL: '/api' },
  },
});
