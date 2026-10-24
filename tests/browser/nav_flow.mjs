// The workspace's navigation (fd-core's shell), with the mock capabilities: the sidebar's queues
// and views with their counts and links, a file opened from a view with its place in it, j and k
// between files, Escape back to the row it came from, the same on cases and reports, the search
// palette, the shortcuts sheet, g then a letter, and the drawer on a narrow screen.
// SYNTHETIC records for cases and reports. A rise in exports is a lead, not evidence of a breach.
// Usage: node nav_flow.mjs http://localhost:8765 shots/nav
import { chromium } from 'playwright';
import assert from 'assert';
import fs from 'fs';
const base = process.argv[2] || 'http://localhost:8765';
const out = process.argv[3] || 'shots/nav';
const reports = JSON.parse(fs.readFileSync(new URL('../../app/data/triage/reports.json', import.meta.url), 'utf8')).reports;
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }).catch(() => chromium.launch());
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
const logs = [];
page.on('console', (m) => { if (m.type() === 'error' && !/ERR_TUNNEL|404/.test(m.text())) logs.push(m.text()); });
page.on('pageerror', (e) => logs.push('pageerror: ' + e.message));
const open = async (q, hash) => { await page.goto('about:blank'); await page.goto(`${base}/index.html?${q}#${hash}`); await page.waitForTimeout(700); };
const step = (name) => console.log('step:', name);
const esc = (t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const item = (label) => page.locator('.fs-item', { has: page.locator('.fs-label', { hasText: new RegExp('^' + esc(label) + '$') }) });
const count = async (label) => { const c = item(label).locator('.fs-count'); return (await c.count()) ? Number(await c.innerText()) : null; };
const rows = (view) => page.$$eval(`#view-${view} button.qrow`, (els) => els.map((e) => e.getAttribute('aria-label').replace('Open ', '')));
const focused = () => page.evaluate(() => document.activeElement && document.activeElement.getAttribute('aria-label'));

step('reset');
await open('role=owner&uid=u_owner', 'inbox');
await page.evaluate(() => localStorage.clear());
await open('role=owner&uid=u_owner', 'inbox');
await page.waitForSelector('#view-inbox button.qrow');

step('the sidebar: queues named for the job, views and pages with their counts');
for (const label of ['Inbox', 'Needs my review', 'Returned to me', 'Assigned to me', 'Leads', 'Watch items', 'Declarations', 'Reports', 'Exporter check', 'Lessons', 'Track record', 'Method', 'Audit log']) {
  assert.equal(await item(label).count(), 1, 'no sidebar item ' + label);
}
const leads = await count('Leads'), watch = await count('Watch items');
assert(leads > 0 && watch > 0, 'no counts for the views');
assert.equal(await count('Inbox'), leads + watch);
assert.equal((await rows('inbox')).length, leads + watch, 'the inbox lists every file');
assert.equal(await count('Needs my review'), null, 'an empty work queue shows no count');
await page.waitForFunction(() => document.querySelector('#tab-reports .fs-count'));
assert.equal(await count('Reports'), reports.length);
assert.equal(await page.getAttribute('#tab-inbox', 'aria-current'), 'page');

step('a view: its own link and its files');
await item('Leads').click();
await page.waitForFunction(() => location.hash === '#leads');
const list = await rows('inbox');
assert.equal(list.length, leads);
assert((await page.locator('.fs-crumbs').innerText()).includes('Leads'), 'the breadcrumb does not name the view');
await page.screenshot({ path: out + '-1-view.png' });

step('j and k move through the list; Enter opens the file with its place in the view');
await page.keyboard.press('j');
await page.keyboard.press('j');
assert.equal(await focused(), 'Open ' + list[1]);
await page.keyboard.press('Enter');
await page.waitForSelector('#view-file .pane-nav');
assert((await page.locator('#view-file .pane-nav').innerText()).includes(`2 of ${leads}`), 'no place in the view');
assert((await page.locator('#view-file .pane-nav .back').innerText()).includes(`Leads (${leads})`));

step('j on a file goes to the next one; Escape goes back to the row it came from');
await page.keyboard.press('j');
await page.waitForFunction(() => /3 of/.test(document.querySelector('#view-file .pane-nav').innerText));
await page.keyboard.press('k');
await page.waitForFunction(() => /2 of/.test(document.querySelector('#view-file .pane-nav').innerText));
await page.keyboard.press('Escape');
await page.waitForFunction(() => location.hash === '#leads');
assert.equal(await focused(), 'Open ' + list[1], 'focus not back on the row');

step('a report: its place in the list, j and k, and back to its row');
await open('role=owner&uid=u_owner', 'reports');
await page.waitForSelector('#view-reports button.qrow');
const rl = await rows('reports');
assert.equal(rl.length, reports.length);
await page.click(`#view-reports button.qrow[aria-label="Open ${rl[0]}"]`);
await page.waitForSelector('#view-report .pane-nav');
assert((await page.locator('#view-report .pane-nav').innerText()).includes(`1 of ${reports.length}`));
await page.keyboard.press('j');
await page.waitForFunction((id) => location.hash === '#report-' + id, rl[1]);
await page.keyboard.press('Escape');
await page.waitForFunction(() => location.hash === '#reports');
assert.equal(await focused(), 'Open ' + rl[1], 'focus not back on the report row');

step('a filtered list: the place and j and k follow the filter');
await page.selectOption('#view-reports select >> nth=0', 'OTSI');
await page.waitForTimeout(300);
const otsi = await rows('reports');
assert(otsi.length > 1 && otsi.length < reports.length, 'the filter did not narrow the list');
await page.click(`#view-reports button.qrow[aria-label="Open ${otsi[0]}"]`);
await page.waitForSelector('#view-report .pane-nav');
assert((await page.locator('#view-report .pane-nav').innerText()).includes(`1 of ${otsi.length}`), 'the place ignores the filter');
await page.keyboard.press('j');
await page.waitForFunction((id) => location.hash === '#report-' + id, otsi[1]);

step('a case: its place in the list');
await open('role=owner&uid=u_owner', 'declarations');
await page.waitForSelector('#view-declarations button.qrow');
const cl = await rows('declarations');
await page.click(`#view-declarations button.qrow[aria-label="Open ${cl[2]}"]`);
await page.waitForSelector('#view-case .pane-nav');
assert((await page.locator('#view-case .pane-nav').innerText()).includes(`3 of ${cl.length}`));
await page.keyboard.press('k');
await page.waitForFunction((id) => location.hash === '#case-' + id, cl[1]);

step('the search palette finds a file by its country and opens it');
await page.keyboard.press('Control+k');
await page.waitForSelector('.fs-pal input');
await page.keyboard.type('kazakhstan');
await page.waitForSelector('.fs-opt[aria-selected="true"]');
assert((await page.locator('.fs-opt[aria-selected="true"]').innerText()).includes('Kazakhstan'));
await page.screenshot({ path: out + '-2-palette.png' });
await page.keyboard.press('Enter');
await page.waitForFunction(() => /^#file-/.test(location.hash));
assert.equal(await page.locator('.fs-layer').count(), 0, 'the palette stayed open');

step('the palette finds pages too, and says when nothing matches');
await page.keyboard.press('/');
await page.keyboard.type('audit');
await page.waitForSelector('.fs-opt[aria-selected="true"]');
await page.keyboard.press('Enter');
await page.waitForFunction(() => location.hash === '#audit');
await page.keyboard.press('Control+k');
await page.keyboard.type('zzzz nothing');
await page.waitForSelector('.fs-empty');
await page.keyboard.press('Escape');
assert.equal(await page.locator('.fs-layer').count(), 0);

step('the shortcuts sheet, and g then a letter');
await page.keyboard.press('?');
await page.waitForSelector('.fs-sheet');
assert((await page.locator('.fs-sheet').innerText()).includes('Go to Declarations'));
await page.keyboard.press('Escape');
assert.equal(await page.locator('.fs-sheet').count(), 0);
assert.equal(await page.evaluate(() => location.hash), '#audit', 'Escape on the sheet also left the page');
await page.keyboard.press('g');
await page.keyboard.press('d');
await page.waitForFunction(() => location.hash === '#declarations');
await page.keyboard.press('g');
await page.keyboard.press('i');
await page.waitForFunction(() => location.hash === '#inbox');

step('a view reloads from its link');
await open('role=owner&uid=u_owner', 'watch');
await page.waitForSelector('#view-inbox button.qrow');
assert.equal((await rows('inbox')).length, watch);

step('How it works: from the sidebar, from its link, and the brand it carries');
await item('How it works').click();
await page.waitForFunction(() => location.hash === '#guide');
await page.waitForTimeout(300);
assert.equal((await page.locator('#view-guide h1').innerText()).trim(), 'How it works');
{
  const g = await page.locator('#view-guide').innerText();
  for (const want of ['Who uses it', 'A typical month', 'In this copy', 'What a deployment could add', 'Improving it']) assert(g.includes(want), 'the guide has no ' + want);
}
assert.equal(await page.getAttribute('#tab-guide', 'aria-current'), 'page');
await open('role=owner&uid=u_owner', 'guide');
assert(await page.locator('#view-guide').isVisible(), 'the guide does not open from its link');
assert.equal(await page.locator('.fs-brand b').innerText(), 'Diversion Radar');
assert(await page.evaluate(() => getComputedStyle(document.querySelector('.fs-mark')).backgroundImage.startsWith('url("data:image/svg+xml')), 'no brand mark in the sidebar');
await page.evaluate(() => document.fonts.ready);
assert(await page.evaluate((f) => document.fonts.check('16px "' + f + '"'), 'IBM Plex Sans'), 'the brand font is not loaded');

step('the overview: a fresh visit lands on it, with what changed and what waits');
await page.evaluate(() => localStorage.clear());
await page.goto('about:blank'); await page.goto(`${base}/index.html?role=owner&uid=u_owner`); await page.waitForTimeout(800);
assert.equal(await page.evaluate(() => location.hash), '#overview', 'a fresh visit does not land on the overview');
assert.equal(await page.getAttribute('#tab-overview', 'aria-current'), 'page');
{
  const ov = await page.locator('#view-overview').innerText();
  for (const want of ['Needs a decision', 'Since the', 'What a lead is worth', 'Who holds what', 'The data', '12 November 2026']) assert(ov.includes(want), 'the overview has no ' + want);
}
step('what a lead is worth: arithmetic on the hours and cost entered, nothing else');
{
  const card = page.locator('.worth');
  assert((await card.innerText()).includes('Enter the hours'), 'the calculator shows a figure before any input');
  await card.locator('input[type="number"]').nth(0).fill('6');
  await card.locator('input[type="number"]').nth(1).fill('50');
  const shown = await page.evaluate(() => JSON.parse(document.querySelector('#view-overview .kpi .val').textContent));
  const t = await card.locator('.worth-out').innerText();
  assert(t.includes(`${6 * shown} analyst hours`) && t.includes(`£${(6 * shown * 50).toLocaleString('en-GB')}`), 'the calculator arithmetic: ' + t);
}
step('the corridor map: only corridors with a file shown, and a corridor lists its files');
await open('role=owner&uid=u_owner', 'map');
await page.waitForSelector('#view-map .map-node');
{
  const isos = await page.$$eval('#view-map .map-node', (els) => els.map((e) => e.dataset.iso));
  assert(isos.length > 0 && isos.length <= 18, 'map nodes: ' + isos.length);
  await page.locator('#view-map .map-node').nth(1).click();
  await page.waitForTimeout(300);
  const panel = await page.locator('.map-panel').innerText();
  assert(panel.includes('shown'), 'the corridor panel did not open');
  assert(await page.locator('#view-map svg.map-lines path').count() > 0, 'no lines on the map');
}
step('a lead file: what supports it, what is connected, and the bar that stays at the top');
await open('role=owner&uid=u_owner', 'file-KZ-851762');
await page.waitForSelector('#sec-support');
assert((await page.locator('#sec-support').innerText()).includes('factors, present or not'), 'no factors on the file');
assert((await page.locator('#sec-connected').innerText()).includes('elsewhere'), 'no connected panel');
await page.locator('.fs-secbar nav button', { hasText: 'Connected' }).click();
await page.waitForTimeout(600);
assert(await page.locator('.fs-secbar').isVisible(), 'the section bar scrolled away');
step('taking a file says so, and Undo puts it back');
await page.locator('button', { hasText: 'Take the file' }).first().click();
await page.waitForSelector('.fs-toast');
assert((await page.locator('.fs-toast').innerText()).includes('You have the file'));
await page.locator('.fs-toast button', { hasText: 'Undo' }).click();
await page.waitForSelector('button:has-text("Take the file")');

step('phase 6: no sign-in screen in a live view; the file reads as sections and a rail');
assert(await page.locator('#portal').isHidden(), 'the demo sign-in showed in a live view');
for (const id of ['#sec-figures', '#sec-support', '#sec-history', '#sec-brief', '#sec-checks', '#rail-tasks', '#rail-refs', '#rail-addons']) assert.equal(await page.locator(id).count(), 1, 'missing ' + id);
const limits = page.locator('#sec-limits .sec-toggle');
const wasOpen = (await limits.getAttribute('aria-expanded')) === 'true';
await limits.click();
assert.equal(await limits.getAttribute('aria-expanded'), String(!wasOpen), 'a section did not fold or open');
assert.equal(await page.locator('#sec-limits-body').isHidden(), wasOpen, 'the section body did not follow its button');
await limits.click();
assert.equal(await page.locator('#sec-limits h2').count(), 1, 'a section lost its heading');
for (const href of await page.$$eval('#rail-refs a', (as) => as.map((a) => a.href))) assert(/^https:\/\//.test(href), 'a reference is not https: ' + href);
assert((await page.locator('#rail-refs a').count()) >= 4, 'too few references');

step('follow-ups: a template adds one with a date and an owner, and ticking it off is audited');
await page.click('#rail-tasks >> text=+ Add a follow-up');
const tpl = await page.locator('#rail-tasks .tpl-chip').first().innerText();
await page.locator('#rail-tasks .tpl-chip').first().click();
await page.waitForSelector('#rail-tasks li.task');
assert((await page.locator('#rail-tasks').innerText()).includes('1 open'), 'the follow-up count');
assert(/\d{1,2} [A-Z][a-z]{2} \d{4}/.test(await page.locator('#slot-props').innerText()), 'no next due date in the properties');
await page.click('#rail-addons >> text=Preview what it would send');
assert((await page.locator('#rail-addons pre').innerText()).includes(tpl.replace(/^\+ /, '')), 'the task tracker preview misses the follow-up');
await page.click('#tab-tasks');
await page.waitForSelector('#view-tasks li.task');
await page.locator('#view-tasks li.task input[type=checkbox]').first().check();
await page.waitForSelector('.fs-toast:has-text("Follow-up done")');
await page.click('#tab-audit');
await page.waitForTimeout(400);
const auditText = await page.locator('#view-audit').innerText();
assert(auditText.includes('added a follow-up') && auditText.includes('finished a follow-up'), 'follow-ups are not in the audit log');

step('drill-through: a file opens its corridor, the corridor lists its files');
await open('role=owner&uid=u_owner', 'file-KZ-851762');
await page.click('.rec-actions >> text=All files on');
await page.waitForFunction(() => location.hash === '#corridor-KZ');
assert((await page.locator('#view-corridor button.ov-row').count()) >= 1, 'the corridor page lists no file');
await open('role=owner&uid=u_owner', 'code-851762');
assert((await page.locator('#view-code button.ov-row').count()) >= 2, 'the code page lists fewer than two corridors');
await page.locator('#view-code button.ov-row').first().click();
await page.waitForFunction(() => /^#file-/.test(location.hash));

step('a follow-up written by hand is screened for names, and one that passes shows at once');
await open('role=owner&uid=u_owner', 'file-KZ-851762');
await page.click('#rail-tasks >> text=+ Add a follow-up');
await page.fill('#task-text', ['Ask', 'Zzqel', 'Vantor', 'for their papers'].join(' '));   // a made-up name, put together here so the repo's own screen never reads one
await page.press('#task-text', 'Enter');   // the Enter path: focus stays in the box while the refusal shows
await page.waitForSelector('#rail-tasks .task-msg');
assert((await page.locator('#rail-tasks .task-msg').innerText()).includes('may name a person or firm'), 'a name got past the screen');
const before = await page.locator('#rail-tasks #task-list li.task').count();
await page.fill('#task-text', 'Ask the corridor for its own import figures');
await page.click('#rail-tasks button[type=submit]');
await page.waitForFunction((n) => document.querySelectorAll('#rail-tasks #task-list li.task').length === n + 1, before);
assert.equal(await page.evaluate(() => document.activeElement && document.activeElement.id), 'task-text', 'focus left the follow-up box');

step('a viewer reads follow-ups but adds none');
await open('role=viewer&uid=u_viewer', 'file-KZ-851762');
await page.waitForSelector('#rail-tasks');
assert.equal(await page.locator('#rail-tasks >> text=+ Add a follow-up').count(), 0, 'a viewer can add a follow-up');
assert.equal(await page.locator('.rec-actions >> text=+ Follow-up').count(), 0, 'a viewer sees the follow-up button');

step('narrow screen: a drawer in place of the sidebar');
await page.setViewportSize({ width: 390, height: 860 });
await open('role=owner&uid=u_owner', 'inbox');
assert((await page.locator('.fs-side').boundingBox()).x < -100, 'the sidebar shows on a phone');
await page.click('.fs-menu');
await page.waitForTimeout(300);
assert((await page.locator('.fs-side').boundingBox()).x >= 0, 'the drawer did not open');
await page.screenshot({ path: out + '-3-drawer.png' });
await item('Watch items').click();
await page.waitForFunction(() => location.hash === '#watch');
await page.waitForTimeout(300);
assert(!(await page.locator('.fs').getAttribute('class')).includes('fs-drawer'), 'the drawer stayed open');
const over = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
assert(!over, 'horizontal overflow on a phone');

assert.deepEqual(logs, [], 'console errors: ' + logs.join(' | '));
console.log('nav flow passed');
await browser.close();
