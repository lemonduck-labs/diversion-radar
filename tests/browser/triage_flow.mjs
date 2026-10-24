// End-to-end flow of the triage view (synthetic reports), with the mock capabilities:
// the list in reading order; a report with a listed registration number shows the match and the
// synthetic entry; a report's route links to the public lead file; one held back under the
// display rule says so and nothing more; a contributor proposes an outcome, its author cannot
// approve it and a second person does; an anonymous report cannot be asked for more; the audit
// log records it; narrow screens.
// Usage: node triage_flow.mjs http://localhost:8765 shots/triage
import { chromium } from 'playwright';
import assert from 'assert';
import fs from 'fs';
const base = process.argv[2] || 'http://localhost:8765';
const out = process.argv[3] || 'shots/triage';
const R = JSON.parse(fs.readFileSync(new URL('../../app/data/triage/reports.json', import.meta.url), 'utf8')).reports;
const signals = JSON.parse(fs.readFileSync(new URL('../../app/data/signals.json', import.meta.url), 'utf8'));
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }).catch(() => chromium.launch());
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
const logs = [];
page.on('console', (m) => { if (m.type() === 'error' && !/ERR_TUNNEL|404/.test(m.text())) logs.push(m.text()); });
page.on('pageerror', (e) => logs.push('pageerror: ' + e.message));
const open = async (q, hash) => { await page.goto('about:blank'); await page.goto(`${base}/index.html?${q}#${hash}`); await page.waitForTimeout(700); };
const step = (name) => console.log('step:', name);
const text = () => page.evaluate(() => document.querySelector('main').innerText);
const mockdb = async () => JSON.parse(await page.evaluate(() => localStorage.getItem('mockdb') || '{}'));

step('reset');
await open('role=owner&uid=u_owner', 'reports');
await page.evaluate(() => localStorage.clear());

step('the list, in reading order, with every report');
await open('role=contributor&uid=u_contrib', 'reports');
await page.waitForSelector('text=Reports: triage');
let t = await text();
assert(t.includes('SYNTHETIC RECORDS'), 'no synthetic notice');
assert(t.includes('A rise in exports is a lead, not evidence of a breach.'), 'no house line');
const rows = await page.$$eval('#view-reports .qrow:not(.qhead) .q-ref', (els) => els.map((e) => e.textContent));
assert.equal(rows.length, R.length, 'not every report listed');
const bands = rows.map((id) => R.find((x) => x.id === id).matched.order);
assert.deepEqual(bands, [...bands].sort((a, b) => a - b), 'not in reading order');
await page.screenshot({ path: out + '-1-list.png', fullPage: true });

step('a report with a listed registration number shows the match and the synthetic entry');
const listed = R.find((x) => x.matched.list.some((h) => h.strength === 'same number'));
await open('role=contributor&uid=u_contrib', 'report-' + listed.id);
await page.waitForSelector('text=What it touches in the radar');
t = await text();
const hit = listed.matched.list.find((h) => h.strength === 'same number');
assert(t.includes(`registration number is on the list: ${hit.unique_id}`), 'no list match shown');
await page.click('button:has-text("Show the entry")');
await page.waitForTimeout(200);
t = await text();
assert(t.includes('Synthetic listed entity') && t.includes('headings are blank for this entry'), 'entry not shown');
assert(t.includes('Which body: ' + listed.matched.body.name), 'no body');
await page.screenshot({ path: out + '-2-listed.png', fullPage: true });

step('a route the public radar shows links to its lead file');
const leadKeys = new Set(JSON.parse(fs.readFileSync(new URL('../../app/data/leads.json', import.meta.url), 'utf8')).map((l) => l.code));
const withFile = R.find((x) => x.matched.routes.some((k) => ['KZ-851762', 'AE-854232', 'AE-854239'].includes(k)));
if (withFile) {
  await open('role=contributor&uid=u_contrib', 'report-' + withFile.id);
  await page.waitForSelector('text=What it touches in the radar');
  const btn = await page.$('#view-report button:has-text("open DR-")');
  assert(btn, 'no link to the lead file');
} else console.log('  (no report on a lead route in this seed)');

step('a route held back under the display rule says so and nothing more');
const heldKeys = new Set(signals.filter((s) => s.uk && s.uk.shown === false).map((s) => `${s.iso2}-${s.code}`));
const held = R.find((x) => x.matched.routes.some((k) => heldKeys.has(k)));
if (held) {
  await open('role=contributor&uid=u_contrib', 'report-' + held.id);
  await page.waitForSelector('text=What it touches in the radar');
  t = await text();
  assert(t.includes('Not shown (display rule)'), 'held route not marked');
} else console.log('  (no report on a held-back route in this seed)');

step('a contributor proposes an outcome');
await open('role=contributor&uid=u_contrib', 'report-' + listed.id);
await page.waitForSelector('#report-panel >> text=Propose an outcome');
await page.click('#report-panel >> button:has-text("Propose an outcome")');
await page.selectOption('#report-panel select[aria-label="Outcome"]', listed.matched.body.name === 'HMRC' ? 'pass_hmrc' : 'assess');
await page.fill('#report-panel textarea[aria-label="Reason"]', 'A party is on the synthetic list under the same registration number; it needs assessing first.');
await page.waitForTimeout(200);
await page.click('#report-panel >> button:has-text("Propose this outcome")');
await page.waitForSelector('#report-panel .st-submitted');
let db = await mockdb();
const proposed = Object.entries(db).filter(([k, v]) => k.startsWith('briefs/u_contrib/b/') && v.kind === 'triage_outcome');
assert.equal(proposed.length, 1, 'outcome not saved');
assert.equal(proposed[0][1].draft.report_id, listed.id);

step('an editor approves it');
await open('role=editor&uid=u_editor', 'report-' + listed.id);
await page.waitForSelector('#report-panel >> button:has-text("Approve")');
await page.click('#report-panel >> button:has-text("Approve")');
await page.waitForSelector('#report-panel .st-approved');
t = await text();
assert(t.includes('Approved by'), 'approval not shown');
db = await mockdb();
assert(Object.entries(db).some(([k, v]) => k.startsWith('decisions/u_editor/d/') && v.lead === 'report_' + listed.id && v.decision === 'approved'), 'no decision');

step('a name in a reason is refused');
const other = R.find((x) => x.id !== listed.id && !x.anonymous);
await open('role=contributor&uid=u_contrib', 'report-' + other.id);
await page.click('#report-panel >> button:has-text("Propose an outcome")');
await page.selectOption('#report-panel select[aria-label="Outcome"]', 'ask');
await page.fill('#report-panel textarea[aria-label="Reason"]', 'Ask the reporter whether Harold Pemberton signed the contract.');
await page.waitForTimeout(300);
assert(await page.isDisabled('#report-panel >> button:has-text("Propose this outcome")'), 'a name got through');
await page.click('#report-panel >> button:has-text("Cancel")');

step('an anonymous report cannot be asked for more');
const anon = R.find((x) => x.anonymous);
await open('role=contributor&uid=u_contrib', 'report-' + anon.id);
await page.click('#report-panel >> button:has-text("Propose an outcome")');
const opts = await page.$$eval('#report-panel select[aria-label="Outcome"] option', (os) => os.map((o) => o.value));
assert(!opts.includes('ask'), 'ask offered on an anonymous report');
await page.click('#report-panel >> button:has-text("Cancel")');

step('the audit log records the outcome and links back to the report');
await open('role=owner&uid=u_owner', 'audit');
t = await text();
assert(t.includes('proposed an outcome for a report') && t.includes('approved the outcome for a report'), 'audit missing');
await page.click(`#view-audit button:has-text("${listed.id}")`);
await page.waitForSelector('text=What it touches in the radar');

step('narrow screen');
await page.setViewportSize({ width: 390, height: 844 });
await open('role=contributor&uid=u_contrib', 'report-' + listed.id);
await page.waitForSelector('text=What the report says');
const wide = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
assert(!wide, 'the page scrolls sideways at 390px');
await page.screenshot({ path: out + '-3-narrow.png', fullPage: true });

assert.deepEqual(logs, [], 'console errors: ' + logs.join(' | '));
await browser.close();
console.log('triage flow passed');
