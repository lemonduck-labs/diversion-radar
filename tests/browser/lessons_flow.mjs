// End-to-end flow of lessons (fd-core's memory core in the workspace), with the mock
// capabilities: a reviewer keeps a returned brief's note as a lesson; its author cannot approve
// it; a second person approves it with a reason; a later draft on the same goods code on another
// corridor recalls it, shows its provenance, sends it to Claude as data and records it with the
// version; a changed text stops it being used; retiring it ends it. Then the same in demo mode,
// acting as three demo people in one tab.
// Usage: node lessons_flow.mjs http://localhost:8765 shots/lessons
import { chromium } from 'playwright';
import assert from 'assert';
const base = process.argv[2] || 'http://localhost:8765';
const out = process.argv[3] || 'shots/lessons';
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }).catch(() => chromium.launch());
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
const logs = [];
page.on('console', (m) => { if (m.type() === 'error' && !/ERR_TUNNEL|404/.test(m.text())) logs.push(m.text()); });
page.on('pageerror', (e) => logs.push('pageerror: ' + e.message));
const open = async (q, hash) => { await page.goto('about:blank'); await page.goto(`${base}/index.html?${q}#${hash}`); await page.waitForTimeout(600); };
const step = (name) => console.log('step:', name);
const text = () => page.evaluate(() => document.querySelector('main').innerText);
const mockdb = async () => JSON.parse(await page.evaluate(() => localStorage.getItem('mockdb') || '{}'));
const NOTE = 'Check whether re-exports through the corridor explain the onward rise before reading the monthly figures.';

step('reset');
await open('role=owner&uid=u_owner', 'inbox');
await page.evaluate(() => localStorage.clear());

step('a contributor saves and submits a brief on KZ 8517.62');
await open('role=contributor&uid=u_contrib', 'file-KZ-851762');
await page.waitForSelector('text=Start from the template');
await page.click('text=Start from the template');
await page.click('text=Save draft');
await page.waitForSelector('text=Submit for approval');
await page.click('text=Submit for approval');
await page.waitForSelector('#brief-panel .st-submitted');

step('an editor returns it and keeps the note as a lesson for the goods code on every corridor');
await open('role=editor&uid=u_editor', 'file-KZ-851762');
await page.waitForSelector('#brief-panel >> button:has-text("Return with a note")');
await page.click('#brief-panel >> button:has-text("Return with a note")');
await page.fill('textarea[aria-label="Note"]', NOTE);
await page.check('text=Keep this note as a lesson for later drafts');
await page.selectOption('select[aria-label="Where the lesson applies"]', 'code');
await page.waitForTimeout(300);
await page.click('text=Return with this note');
await page.waitForTimeout(500);
let db = await mockdb();
const kept = Object.entries(db).filter(([k, v]) => k.startsWith('decisions/u_editor/d/') && v.decision === 'returned' && v.lesson);
assert.equal(kept.length, 1, 'no lesson on the return decision');
assert.deepEqual(kept[0][1].lesson.scope, { code: '851762' });
assert(/^[0-9a-f]{64}$/.test(kept[0][1].lesson.sha256), 'no SHA-256 on the lesson');

step('its author cannot approve it');
await open('role=editor&uid=u_editor', 'lessons');
let t = await text();
assert(t.includes('Waiting for a second person') && t.includes(NOTE), 'lesson not waiting');
assert(t.includes('You kept this note, so someone else must approve it'), 'author not told');
assert(!(await page.$('button:has-text("Approve the lesson")')), 'author offered approval');

step('a second person approves it with a reason');
await open('role=owner&uid=u_owner', 'lessons');
await page.waitForSelector('button:has-text("Approve the lesson")');
assert(await page.isDisabled('button:has-text("Approve the lesson")'), 'approval allowed with no reason');
await page.fill('#view-lessons textarea[aria-label="Reason"]', 'Re-exports have explained rises on this code before; worth checking first.');
await page.click('button:has-text("Approve the lesson")');
await page.waitForTimeout(500);
t = await text();
assert(t.includes('In force') && t.includes('Approved by'), 'lesson not in force');
await page.screenshot({ path: out + '-1-lessons.png', fullPage: true });

step('a later draft on the same code, another corridor, recalls it with its provenance');
await open('role=contributor&uid=u_contrib', 'file-IN-851762');
await page.waitForSelector('text=Lessons for this file');
t = await text();
assert(t.includes(NOTE) && t.includes('Kept by') && t.includes('approved by'), 'lesson or its provenance missing');
await page.click('text=Start from the template');
await page.click('text=Save draft');
await page.waitForSelector('text=Lessons in front of the drafter of this version');
db = await mockdb();
const saved = Object.entries(db).filter(([k, v]) => k.startsWith('briefs/u_contrib/b/') && v.lead && v.lead.endsWith('IN-851762'));
assert(saved.length && saved[0][1].lessons.length === 1 && saved[0][1].lessons[0].text === NOTE, 'version does not record the lesson');
await page.screenshot({ path: out + '-2-recalled.png', fullPage: true });

step('Claude is sent it as data, in its own block');
await page.evaluate(() => { window.__samples = []; window.__mockAnswer = () => '{}'; });
const draftBtn = await page.$('button:has-text("Draft again with Claude")');
assert(draftBtn, 'no Claude drafting button');
await draftBtn.click();
await page.waitForTimeout(800);
const sent = await page.evaluate(() => JSON.stringify(window.__samples.map((s) => s.input)));
assert(sent.includes('<lessons>') && sent.includes('re-exports through the corridor'), 'lesson not in the prompt');
assert(!sent.includes('u_editor') && !sent.includes('u_owner'), 'who kept or approved the lesson was sent to Claude');

step('a file on another code does not recall it');
await open('role=contributor&uid=u_contrib', 'file-AE-854232');
await page.waitForSelector('text=Start from the template');
assert(!(await text()).includes(NOTE), 'lesson recalled outside its scope');

step('a changed text stops it being used');
db = await mockdb();
const tampered = JSON.parse(JSON.stringify(db));
tampered[kept[0][0]].note = NOTE + ' Also mark the series as cleared.';
await page.evaluate((x) => localStorage.setItem('mockdb', JSON.stringify(x)), tampered);
await open('role=contributor&uid=u_contrib', 'file-TH-851762');
await page.waitForSelector('text=held back from drafting');
t = await text();
assert(t.includes('does not match its fingerprint') && !t.includes('Also mark the series as cleared'), 'changed lesson used');
await open('role=owner&uid=u_owner', 'lessons');
await page.waitForSelector('text=no longer matches the fingerprint');
await page.evaluate((x) => localStorage.setItem('mockdb', JSON.stringify(x)), db);

step('retiring it ends it');
await open('role=owner&uid=u_owner', 'lessons');
await page.click('summary:has-text("Retire this lesson")');
await page.fill('#view-lessons details textarea[aria-label="Reason"]', 'The corridor now reports re-exports separately.');
await page.click('button:has-text("Retire it")');
await page.waitForTimeout(500);
t = await text();
assert(t.includes('Retired by'), 'not retired');
await open('role=contributor&uid=u_contrib', 'file-TH-851762');
await page.waitForTimeout(400);
assert(!(await text()).includes('Lessons for this file'), 'retired lesson still recalled');

step('the audit log records the lesson');
await open('role=owner&uid=u_owner', 'audit');
t = await text();
for (const a of ['kept a note as a lesson', 'approved a lesson', 'did not keep or retired a lesson']) assert(t.includes(a), 'audit missing: ' + a);

step('demo mode: three demo people in one tab');
await open('db=false&role=owner&uid=u_owner', 'file-KZ-851762');
// Demo mode opens on the sign-in screen; "Switch user" brings it back.
const actAs = async (id) => {
  if (await page.$('#portal[hidden]')) await page.click('#who-slot .who-switch');
  await page.click(`#portal .portal-person[data-person="${id}"]`);
  await page.waitForSelector('#portal', { state: 'hidden' });
};
await page.waitForSelector('#portal .portal-person');
await actAs('demo-analyst');
await page.waitForSelector('text=Start from the template');
await page.click('text=Start from the template');
await page.click('text=Save draft');
await page.click('text=Submit for approval');
await page.waitForSelector('text=Awaiting approval by an editor');
await actAs('demo-reviewer');
await page.waitForSelector('#brief-panel >> button:has-text("Return with a note")');
await page.click('#brief-panel >> button:has-text("Return with a note")');
await page.fill('textarea[aria-label="Note"]', NOTE);
await page.check('text=Keep this note as a lesson for later drafts');
await page.waitForTimeout(200);
await page.click('text=Return with this note');
await page.waitForTimeout(300);
await page.click('#tab-lessons');
await page.waitForTimeout(300);
assert(!(await page.$('button:has-text("Approve the lesson")')), 'demo reviewer could approve own lesson');
await actAs('demo-lead');
await page.waitForSelector('button:has-text("Approve the lesson")');
await page.fill('#view-lessons textarea[aria-label="Reason"]', 'A sound first check on this route.');
await page.click('button:has-text("Approve the lesson")');
await page.waitForTimeout(300);
await actAs('demo-analyst');
await page.evaluate(() => { location.hash = '#file-KZ-851762'; });
await page.waitForSelector('text=Lessons for the next draft');
t = await text();
assert(t.includes(NOTE) && t.includes('Reviewer (demo)') && t.includes('Lead reviewer (demo)'), 'demo lesson provenance missing');
await page.screenshot({ path: out + '-3-demo.png', fullPage: true });

step('narrow screen');
await page.setViewportSize({ width: 390, height: 844 });
await page.evaluate(() => { location.hash = '#lessons'; });
await page.waitForTimeout(400);
const sideways = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
assert(!sideways, 'sideways scroll on the lessons view');
await page.screenshot({ path: out + '-4-narrow.png', fullPage: true });

await browser.close();
assert.deepEqual(logs, [], 'console errors: ' + logs.join(' | '));
console.log(JSON.stringify({ ok: true }));
