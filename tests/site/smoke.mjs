// Smoke test for the built demo site (site/dist), in Chromium.
//
// tests/site/serve.mjs stands in for Netlify: it serves the built site with the headers its
// _headers file gives each path, a folder's index.html for /radar as well as /radar/, and
// 404.html for a missing path.
// Each page is opened at desktop and phone width and must: draw from its data, log no error,
// break no Content-Security-Policy rule, request nothing from another site, fail no request,
// and not scroll sideways at phone width. Screenshots go to the folder named on the command line.
//
//   node tests/site/smoke.mjs site/dist [shots-dir]
//
// Synthetic records and published aggregates only. A rise in exports is a lead, not evidence
// of a breach.
import { mkdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const { chromium } = await import(path.join(here, '..', 'browser', 'node_modules', 'playwright', 'index.mjs'));
const { serve } = await import(path.join(here, 'serve.mjs'));
const root = path.resolve(process.argv[2] || path.join(here, '..', '..', 'site', 'dist'));
const shots = process.argv[3] ? path.resolve(process.argv[3]) : null;
if (shots) await mkdir(shots, { recursive: true });

const { origin, served, close } = await serve(root);

// The Monitor page of a site copy lists every item the copy carries (only items under an open
// licence; scripts/build_site.py), so its manifest copy's checksum was accepted.
async function monitorShows(page, copy) {
  const items = JSON.parse(await readFile(path.join(root, copy, 'data', 'monitor.json'), 'utf8'));
  assert.ok(items.length > 0, `${copy}: the site copy carries no monitoring item`);
  await page.evaluate(() => { location.hash = '#monitor'; });
  await page.waitForFunction((n) => document.querySelectorAll('#view-monitor .mon-item').length === n, items.length, { timeout: 15000 });
}

// ------------------------------------------------------------------ the browser
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }).catch(() => chromium.launch());
const failures = [];
const step = (s) => console.log('  ' + s);

async function open(name, url, { width = 1280, height = 900, aborted = false } = {}, check) {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1, colorScheme: 'light' });
  const page = await ctx.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  page.on('pageerror', (e) => errors.push('page error: ' + e.message));
  page.on('requestfailed', (r) => {
    const why = r.failure() && r.failure().errorText;
    // A page reloading itself with its trailing slash cuts off the loads it had started.
    if (aborted && why === 'net::ERR_ABORTED') return;
    errors.push(`request failed: ${r.url()} (${why})`);
  });
  page.on('request', (r) => { if (!r.url().startsWith(origin) && !r.url().startsWith('data:') && !r.url().startsWith('blob:')) errors.push('request to another site: ' + r.url()); });
  page.on('response', (r) => { if (r.status() >= 400) errors.push(`HTTP ${r.status()}: ${r.url()}`); });
  await page.addInitScript(() => {
    window.__csp = [];
    document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(`${e.violatedDirective}: ${e.blockedURI || 'inline'}`));
  });
  const resp = await page.goto(origin + url, { waitUntil: 'networkidle' });
  assert.ok(resp.headers()['content-security-policy'] || url === '/404-test', `${name}: no CSP header`);
  try {
    await check(page);
  } catch (e) {
    errors.push('check: ' + e.message.split('\n')[0]);
  }
  // Text a view should never show: a null or an array written into the page as a string.
  const stray = await page.evaluate(() => {
    const m = document.body.innerText.match(/(^|[^A-Za-z])(null|undefined|NaN|\[object [A-Za-z]+\])/);
    return m ? m[0].trim() : null;
  });
  if (stray) errors.push('stray text on the page: ' + stray);
  const csp = await page.evaluate(() => window.__csp || []);
  for (const c of csp) errors.push('CSP: ' + c);
  const sideways = await page.evaluate(() => document.scrollingElement.scrollWidth - window.innerWidth);
  if (width < 500 && sideways > 1) errors.push(`scrolls sideways by ${sideways}px at ${width}px`);
  if (shots) await page.screenshot({ path: path.join(shots, `${name}.png`), fullPage: false });
  await ctx.close();
  if (errors.length) failures.push(`${name}:\n    ` + errors.join('\n    '));
  step(`${name}: ${errors.length ? 'FAILED' : 'ok'}`);
}

const filled = async (page, sel) => {
  await page.waitForFunction((s) => { const el = document.querySelector(s); return el && el.textContent.trim() && !el.textContent.includes('…'); }, sel, { timeout: 10000 });
};

console.log(`site smoke test on ${root}`);
for (const [w, h, tag] of [[1280, 900, 'desktop'], [390, 844, 'phone']]) {
  await open(`landing-${tag}`, '/', { width: w, height: h }, async (page) => {
    assert.equal(await page.locator('.card').count(), 4);
    assert.match(await page.locator('h1').innerText(), /Sanctions leads/);
    assert.ok(!(await page.content()).includes('{{'), 'a placeholder is left');
  });
  await open(`radar-${tag}`, '/radar/', { width: w, height: h }, async (page) => {
    await filled(page, '#takeaway');
    await page.waitForFunction(() => document.querySelectorAll('#leads-table tbody tr, table[data-source="leads"] tbody tr').length > 0, null, { timeout: 10000 });
    await page.click('#tab-track');
    await page.waitForSelector('#leadtime-chart svg', { timeout: 10000 });
    assert.ok((await page.locator('#tests-table tbody tr').count()) >= 6);
    await filled(page, '#kpi-cases .val');
    await page.click('#tab-method');
    await page.waitForFunction(() => location.hash === '#method');
    await page.click('#tab-now');
  });
  await open(`ta-${tag}`, '/ta/', { width: w, height: h }, async (page) => {
    await filled(page, '#v-gross');
    await page.waitForSelector('#spread-chart svg', { timeout: 10000 });
    await page.click('#tab-england');
    await filled(page, '#kpi-e-spend .val');
    await page.click('#tab-yours');
  });
  await open(`workspace-${tag}`, '/workspace/', { width: w, height: h }, async (page) => {
    await page.getByText('Demo mode: this view has no shared store').first().waitFor({ timeout: 15000 });
    // The demo opens on its sign-in screen; a synthetic person signs in.
    await page.click('#portal .portal-person[data-person="demo-analyst"]', { timeout: 15000 });
    await page.waitForSelector('#portal', { state: 'hidden' });
    // It opens on the overview, whose lists are drawn from the files.
    await page.waitForFunction(() => document.querySelectorAll('#view-overview button.ov-row').length > 0, null, { timeout: 15000 });
    await monitorShows(page, 'workspace');
  });
  await open(`planner-${tag}`, '/planner/', { width: w, height: h }, async (page) => {
    await page.getByText('Demo mode: this view has no shared store').first().waitFor({ timeout: 15000 });
    await page.click('#portal .portal-person[data-person="demo-officer"]', { timeout: 15000 });
    await page.waitForSelector('#portal', { state: 'hidden' });
    await page.waitForFunction(() => document.querySelectorAll('#view-overview .bar-row').length > 0, null, { timeout: 15000 });
    // The static planner runs on the caseload's demo day, so its clocks hold on any day.
    await page.getByText(/It runs on \d{1,2} \w{3} \d{4}, the day after the synthetic caseload was drawn/).first().waitFor({ timeout: 15000 });
    await monitorShows(page, 'planner');
  });
}

// A page opened without its trailing slash reloads itself with it, and still draws.
await open('radar-no-slash', '/radar', { aborted: true }, async (page) => {
  await page.waitForURL(/\/radar\/$/, { timeout: 5000 });
  await filled(page, '#takeaway');
});
// A missing page gets the 404 page.
{
  const r = await fetch(origin + '/no-such-page');
  assert.equal(r.status, 404);
  assert.match(await r.text(), /Nothing here/);
  step('404: ok');
}
// The datasets the shim loads are the ones on disk, and no data file is missing.
const missing = served.filter(([p, s]) => s === 404 && p !== '/no-such-page').map(([p]) => p);
if (missing.length) failures.push('files not found: ' + missing.join(', '));

await browser.close();
await close();
if (failures.length) {
  console.log('\nsite smoke test FAILED\n  ' + failures.join('\n  '));
  process.exit(1);
}
console.log('site smoke test passed');
