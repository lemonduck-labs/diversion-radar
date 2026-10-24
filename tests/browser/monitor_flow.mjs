// Phase 7, the monitor, with the rule-aware mock: items wait with the original beside an English
// summary and a proposed grade; a contributor accepts one with a grade or rejects one with a
// reason; an accepted item appears on the files it touches and leaves the console's count; a
// viewer reads and decides nothing. Public sources only; no person or firm named.
// Usage: node monitor_flow.mjs http://localhost:8765 shots/monitor
import { chromium } from 'playwright';
import assert from 'assert';
const base = process.argv[2] || 'http://localhost:8765';
const out = process.argv[3] || 'shots/monitor';
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }).catch(() => chromium.launch());
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
const logs = [];
page.on('console', (m) => { if (m.type() === 'error' && !/favicon|404/.test(m.text())) logs.push(m.text()); });
page.on('pageerror', (e) => logs.push('pageerror: ' + e.message));
const open = async (q, hash) => { await page.goto('about:blank'); await page.goto(`${base}/index.html?${q}#${hash}`); await page.waitForTimeout(500); };
const step = (name) => console.log('step:', name);

step('reset');
await open('role=owner&uid=u_owner', 'inbox');
await page.evaluate(() => localStorage.clear());
const items = await page.evaluate(() => fetch('data/monitor.json').then((r) => r.json()));
assert(items.length >= 1, 'no monitoring items in the build');
const tr = items.find((i) => (i.tags.corridors || []).includes('TR') && i.language !== 'en');
assert(tr, 'no translated item tagged to Turkey');

step('the monitor lists every item waiting, with its sources and a count in the sidebar');
await open('role=contributor&uid=u_contrib', 'monitor');
await page.waitForSelector('#view-monitor .mon-item');
assert.equal(await page.locator('#view-monitor .mon-item').count(), items.length);
assert.equal((await page.innerText('#tab-monitor .fs-count')).trim(), String(items.length));
assert((await page.innerText('#mon-sources')).includes('terms'));
const card = page.locator('#mon-' + tr.id);
await card.locator('summary').click();
assert.equal(await card.locator('blockquote').getAttribute('lang'), tr.language);
assert((await card.innerText()).includes('Translated by'));
assert((await card.locator('.mon-terms').innerText()).includes('Terms:'), 'the card does not show its source terms');
assert.equal(await card.locator('h2.mon-title').count(), 1, 'the item title is not a heading');

step('a contributor accepts the Turkish item with a grade of their own');
await card.locator('button:has-text("Decide")').click();
await card.locator('select >> nth=0').selectOption('B1');
await card.locator('button:has-text("Accept")').click();
await page.waitForTimeout(300);
assert.equal(await page.evaluate(() => document.activeElement && document.activeElement.closest('#view-monitor .seg') ? document.activeElement.getAttribute('aria-pressed') : null), 'true', 'focus was lost after the decision');
assert.equal(await page.locator('#view-monitor .mon-item').count(), items.length - 1, 'the accepted item still shows as waiting');
await page.click('#view-monitor .seg >> text=Accepted');
await page.waitForSelector('#mon-' + tr.id);
assert((await page.innerText('#mon-' + tr.id)).includes('B1: usually reliable source; confirmed by other sources'));

step('another is rejected with a reason');
await page.click('#view-monitor .seg >> text=Waiting');
const other = page.locator('#view-monitor .mon-item').first();
await other.locator('button:has-text("Decide")').click();
await other.locator('select >> nth=1').selectOption('duplicate');
await other.locator('button:has-text("Reject")').click();
await page.waitForTimeout(300);
assert.equal(await page.locator('#view-monitor .mon-item').count(), items.length - 2);

step('the accepted item is on the files it touches; the console counts what waits');
const file = await page.evaluate(() => fetch('data/leads.json').then((r) => r.json()).then((l) => l.find((x) => x.country === 'Turkey')));
await open('role=contributor&uid=u_contrib', 'file-TR-' + file.code);
await page.waitForSelector('#rail-monitor');
assert((await page.innerText('#rail-monitor')).includes(tr.title), 'the accepted item is not on the file');
await open('role=contributor&uid=u_contrib', 'overview');
await page.waitForSelector('#gl-mon');
await page.waitForTimeout(400);
assert.equal((await page.innerText('#gl-mon')).trim(), String(items.length - 2));
const pulsing = await page.innerText('#gl-monlist');
assert(/Items wait on the monitor for .*Thailand/.test(pulsing), 'no text equivalent for the corridors that pulse: ' + pulsing);
await page.screenshot({ path: out + '-1-console.png' });

step('a viewer reads the monitor and decides nothing');
await open('role=viewer&uid=u_viewer', 'monitor');
await page.waitForSelector('#view-monitor .mon-item');
assert.equal(await page.locator('#view-monitor button:has-text("Decide")').count(), 0);

assert.deepEqual(logs, [], 'console errors: ' + logs.join(' | '));
console.log('monitor flow passed');
await browser.close();
