// Read-only smoke test of the dev servers actually visible to the user.
// All API writes are blocked; browser storage belongs to isolated contexts.
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect } from '@playwright/test';
import { verifyPortalTheme } from './theme-checks.mjs';

const browser = await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL || 'msedge'});
const screenshotDir = process.env.PAWCONNECT_LIVE_SCREENSHOTS;
let checks = 0;
try {
  for (const [portal, port, routes] of [['adopter',5173,['/','/pets','/login']], ['staff',5174,['/login']]]) {
    const origin = `http://localhost:${port}`;
    const context = await browser.newContext({viewport:{width:1440,height:1000},colorScheme:'light'});
    const errors = [], writes = [];
    await context.route('**/api/**', route => {
      if(route.request().method() === 'GET') return route.continue();
      writes.push(route.request().method());return route.abort();
    });
    const page=await context.newPage();
    page.on('pageerror', error=>errors.push(error.message));
    for(const route of routes) {
      await page.goto(origin + route);
      await expect(page.locator('h1').first()).toBeVisible({timeout:15000});
      if(portal === 'adopter' && route !== '/login') await expect(page.getByRole('status').filter({hasText:/Loading (featured )?pets/})).toHaveCount(0,{timeout:20000});
      for (const mode of ['light','dark']) {
        if(await page.locator('html').getAttribute('data-theme') !== mode) await page.getByRole('button',{name:`Switch to ${mode} mode`,exact:true}).click();
        await expect(page.locator('html')).toHaveAttribute('data-theme',mode);
        await verifyPortalTheme(page,mode);
        await page.reload();
        await expect(page.locator('h1').first()).toBeVisible({timeout:15000});
        if(portal === 'adopter' && route !== '/login') await expect(page.getByRole('status').filter({hasText:/Loading (featured )?pets/})).toHaveCount(0,{timeout:20000});
        await verifyPortalTheme(page,mode);
        if(screenshotDir) {
          await mkdir(screenshotDir,{recursive:true});
          await page.screenshot({path:path.join(screenshotDir,`${portal}-${route === '/' ? 'home' : route.slice(1)}-${mode}.png`),fullPage:false});
        }
        for (const width of [320,390,768,1440]) {
          await page.setViewportSize({width,height:900});
          await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
          assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1), `${portal} overflow at ${width}`);
        }
        checks++;
      }
    }
    const css = await (await page.request.get(origin + '/src/index.css?direct')).text();
    assert.match(css,/\.text-stone-900\s*\{[^}]*var\(--neutral-900\)/,'Live server is serving stale fixed text colors');
    assert.match(css,/\.bg-white\s*\{[^}]*var\(--surface\)/,'Live server is serving stale white panels');
    assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
    await context.close();
  }
  console.log(`PASS: ${checks} live theme/refresh groups on existing localhost:5173 and :5174; painted text contrast, backgrounds, fonts, 320/390/768/1440px; no API writes.`);
} finally {await browser.close();}
