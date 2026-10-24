// Phase 6.5 on one file, with the rule-aware mock: an approved brief leads to an outcome from a
// fixed list (screened note), a referral pack covering what OTSI's guidance asks for, an end-use
// controls decision record that cannot put a route forward without every check and needs a
// second editor, the overview's count, the case lessons and the pilot timings. Synthetic and
// aggregate data only.
// Usage: node outcome_flow.mjs http://localhost:8765 shots/outcome
import { chromium } from 'playwright';
import assert from 'assert';
const base = process.argv[2] || 'http://localhost:8765';
const out = process.argv[3] || 'shots/outcome';
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }).catch(() => chromium.launch());
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
const logs = [];
page.on('console', (m) => { if (m.type() === 'error' && !/favicon|404/.test(m.text())) logs.push(m.text()); });
page.on('pageerror', (e) => logs.push('pageerror: ' + e.message));
const open = async (q, hash) => { await page.goto('about:blank'); await page.goto(`${base}/index.html?${q}#${hash}`); await page.waitForTimeout(500); };
const step = (name) => console.log('step:', name);
const main = () => page.evaluate(() => document.querySelector('main').innerText);
const FILE = 'file-KZ-851762';
const downloads = () => page.evaluate(() => window.__downloads || []);

step('reset');
await open('role=owner&uid=u_owner', 'inbox');
await page.evaluate(() => localStorage.clear());

step('no outcome before the brief is decided');
await open('role=owner&uid=u_owner', FILE);
await page.waitForSelector('#sec-outcome');
assert((await page.locator('#slot-outcome').innerText()).includes('once the brief is approved or rejected'));

step('a brief from the template, submitted by the owner, approved by an editor');
await page.click('.rec-actions button.primary');
await page.waitForSelector('text=Start from the template');
await page.click('text=Start from the template');
await page.waitForSelector('text=Save draft');
await page.click('text=Save draft');
await page.waitForSelector('text=Submit for approval');
await page.click('text=Submit for approval');
await page.waitForSelector('#brief-panel .st-submitted');
await open('role=editor&uid=u_editor', FILE);
await page.click('#brief-panel >> button:has-text("Approve")');
await page.waitForSelector('text=Evidence pack (.md)');

step('the next step is to record the outcome; a note that names someone is refused');
await open('role=owner&uid=u_owner', FILE);
await page.waitForSelector('.rec-actions button.primary');
assert.equal((await page.innerText('.rec-actions button.primary')).trim(), 'Record the outcome');
await page.click('.rec-actions button.primary');
await page.waitForSelector('#slot-outcome input[type=radio]');
assert.equal(await page.locator('#slot-outcome input[name=outcome]').count(), 5, 'an approved brief offers all five outcomes');
assert(await page.evaluate(() => document.activeElement && document.activeElement.name === 'outcome'), 'focus did not move to the choices');
await page.check('#slot-outcome input[value=referral]');
await page.fill('textarea[aria-label="Outcome note"]', ['Passed to', 'Zzqel', 'Vantor', 'for a look'].join(' '));   // a made-up name, joined here so the repo's own screen never reads one
await page.click('text=Save the outcome');
await page.waitForSelector('#slot-outcome .task-msg');
await page.fill('textarea[aria-label="Outcome note"]', 'Passed to the trade sanctions team with the referral pack.');
await page.click('text=Save the outcome');
await page.waitForSelector('#slot-outcome .decision');
assert((await page.locator('#slot-outcome .decision').innerText()).includes('Referred on'));
assert((await page.locator('#sec-outcome .sec-meta').innerText()).includes('Referred on'));

step('the referral pack: a reason is required, screened, and the pack names no exporter');
await page.click('text=Prepare a referral pack');
await page.click('text=Save the pack (.md)');
assert((await page.locator('#slot-outcome .task-msg').innerText()).includes('Say why'));
await page.fill('textarea[aria-label="Why it is referred"]', 'UK exports of the code and the corridor’s own exports to Russia rose together over the same months; the checks are done and the brief is approved.');
await page.click('text=Save the pack (.md)');
await page.waitForTimeout(400);
const ref = (await downloads()).find((d) => d.filename === 'DR-2026-10-KZ-851762-referral.md');
assert(ref, 'referral pack not saved');
for (const s of ['names no exporter', 'The UK link and any parties', 'Rules that may apply', 'SI 2019/855', 'Open Government Licence', 'A rise in exports is a lead, not evidence of a breach.', 'SHA-256']) assert(ref.data.includes(s), 'pack lacks ' + s);
assert(!ref.data.includes('—'), 'em dash in the referral pack');

step('end-use record: putting a route forward needs every check; the recorder cannot approve it');
await page.click('text=Change the outcome');
await page.check('#slot-outcome input[value=enduse]');
await page.click('text=Save the outcome');
await page.waitForSelector('text=Start the record');
await page.click('text=Start the record');
await page.fill('textarea[aria-label="Why this route"]', 'The rise holds over the months published and partner teams hold nothing that explains it.');
await page.check('#slot-outcome input[name=eu-rec] >> nth=0');
await page.click('text=Save the record');
assert((await page.locator('#slot-outcome .task-msg').innerText()).includes('never the sole basis'), 'forward without every check was not refused');
const boxes = page.locator('#slot-outcome .sub-card fieldset >> nth=0 >> input[type=checkbox]');
for (let i = 0; i < await boxes.count(); i++) await boxes.nth(i).check();
await page.click('text=Save the record');
await page.waitForSelector('text=Waiting for a second editor.');
assert(await page.locator('text=Approve the record').count() === 0, 'the recorder was offered the approval');
await open('role=contributor&uid=u_contrib', FILE);
await page.waitForSelector('text=Waiting for a second editor.');
assert(await page.locator('text=Approve the record').count() === 0, 'a contributor was offered the approval');
await open('role=editor&uid=u_editor', FILE);
await page.click('text=Approve the record');
await page.waitForSelector('#slot-outcome >> text=Approved by');
await page.screenshot({ path: out + '-1-record.png', fullPage: true });

step('a viewer reads the outcome and cannot change it');
await open('role=viewer&uid=u_viewer', FILE);
await page.waitForSelector('#slot-outcome .decision');
assert(await page.locator('text=Change the outcome').count() === 0);

step('the overview counts the outcome; the track record holds the case lessons');
await open('role=owner&uid=u_owner', 'overview');
await page.waitForSelector('#ov-outcomes');
const ov = await page.locator('#ov-outcomes').innerText();
assert(ov.includes('1 recorded'), 'overview did not count the outcome: ' + ov);
await open('role=owner&uid=u_owner', 'track');
await page.waitForSelector('#case-lessons li');
assert(await page.locator('#case-lessons li').count() >= 4);
assert(!(await page.locator('#case-lessons').innerText()).includes('—'));

step('pilot timings: the outcome and the referral were timed, in this browser only');
await open('role=owner&uid=u_owner', 'timings');
await page.waitForSelector('#view-timings table');
const rows = await page.$$eval('#view-timings tbody tr', (trs) => trs.map((tr) => [...tr.cells].map((c) => c.textContent)));
const n = (label) => Number((rows.find((r) => r[0].startsWith(label)) || [, '0'])[1]);
assert(n('Record an outcome') >= 2, 'outcomes not timed: ' + JSON.stringify(rows));
assert(n('Prepare a referral pack') >= 1, 'referral not timed');
assert(n('Write a brief') >= 1, 'brief not timed');
await page.click('text=Timings (.csv)');
await page.waitForTimeout(300);
const csv = (await downloads()).find((d) => d.filename === 'radar-pilot-timings.csv');
assert(csv && csv.data.startsWith('task,started,minutes,steps'), 'timings csv missing');
assert(!/KZ|851762|u_owner/.test(csv.data), 'the timings log holds a file or a person');

step('the console globe: it turns and sweeps, a corridor in the list turns it there, and Pause stops it');
await open('role=owner&uid=u_owner', 'overview');
await page.waitForSelector('#ov-console canvas');
const bearing = () => page.innerText('#gl-bearing');
const b1 = await bearing(); await page.waitForTimeout(700); const b2 = await bearing();
assert.notEqual(b1, b2, 'the sweep is not moving');
const listed = await page.$$eval('.gl-list button', (bs) => bs.map((b) => b.dataset.iso));
const shownIso = [...new Set(await page.evaluate(() => fetch('data/leads.json').then((r) => r.json()).then((l) => l.map((x) => x.country))))];
assert.equal(listed.length, shownIso.length, 'the list does not hold every corridor with something shown');
await page.click('.gl-list button >> nth=0');
assert.equal(await page.getAttribute('.gl-list button >> nth=0', 'aria-pressed'), 'true');
assert((await page.innerText('#gl-sel')).includes('Open the corridor'));
await page.click('#gl-pause');
assert.equal(await page.getAttribute('#gl-pause', 'aria-pressed'), 'true');
const p1 = await bearing(); await page.waitForTimeout(600); assert.equal(await bearing(), p1, 'Pause did not stop the sweep');
await page.click('#gl-pause');
await page.click('#gl-sel .gl-open');
await page.waitForFunction(() => /^#corridor-/.test(location.hash));
const held = await page.evaluate(() => fetch('data/summary.json').then((r) => r.json()).then((s) => s[0].leads_held + s[0].watch_held));
await open('role=owner&uid=u_owner', 'overview');
await page.waitForSelector('#ov-console');
assert((await page.innerText('.gl-tl')).includes(String(held).padStart(2, '0')), 'held-back count missing from the console');

assert.deepEqual(logs, [], 'console errors: ' + logs.join(' | '));
console.log('outcome flow passed');
await browser.close();
