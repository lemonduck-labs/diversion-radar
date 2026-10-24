// The restricted layer in the workspace: list, case view, graph, checks, outcome with four-eyes,
// the answers view, and the link from the public lead file.
import { chromium } from 'playwright';
import assert from 'assert';
const base = process.argv[2] || 'http://localhost:8765';
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }).catch(() => chromium.launch());
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
const logs = [];
page.on('console', (m) => { if (m.type() === 'error' && !/404|favicon/.test(m.text())) logs.push(m.text()); });
page.on('pageerror', (e) => logs.push('pageerror: ' + e.message));
const open = async (q, hash) => { await page.goto('about:blank'); await page.goto(`${base}/index.html?${q}#${hash}`); await page.waitForTimeout(700); };
const text = () => page.evaluate(() => document.querySelector('main').innerText);
const step = (s) => console.log('step:', s);

step('reset and list');
await open('role=owner&uid=u_owner', 'declarations');
await page.evaluate(() => localStorage.clear());
await open('role=owner&uid=u_owner', 'declarations');
await page.waitForSelector('text=Declarations: the restricted layer');
let t = await text();
assert(t.includes('SYNTHETIC RECORDS') && t.includes('A rise in exports is a lead, not evidence of a breach.'), 'notice or house line missing');
assert.equal(await page.$$eval('#view-declarations .qrow:not(.qhead)', (e) => e.length), 48);
await page.screenshot({ path: 'shots/decl-1-list.png', fullPage: true });

step('case view with graph and questions');
await open('role=contrib&uid=u_contrib'.replace('contrib&', 'contributor&'), 'case-SYN-CASE-001');
await page.waitForSelector('text=Who is linked');
assert(await page.$('#view-case svg line'), 'no graph edges');
t = await text();
assert(t.includes('Questions to check') && t.includes('Public lead file KZ-851762'), 'questions or route link missing');
await page.click('#slot-case-checks .seg >> nth=0 >> text=Checked');
await page.waitForTimeout(300);

step('contributor proposes an outcome; a name in the note is blocked');
await page.click('#case-panel >> button:has-text("Propose an outcome")');
await page.selectOption('#case-panel select', 'more_information');
await page.fill('textarea[aria-label="Reason"]', 'Ask Ivan Petrov at the consignee why orders grew.');
await page.waitForTimeout(300);
assert(await page.isDisabled('#case-panel >> button:has-text("Propose this outcome")'), 'a name in the note was not blocked');
await page.fill('textarea[aria-label="Reason"]', 'The rise rests on one new consignee; ask the exporter for its end-use statement before anything else.');
await page.waitForTimeout(300);
await page.click('#case-panel >> button:has-text("Propose this outcome")');
await page.waitForSelector('#case-panel .st-submitted');
await page.screenshot({ path: 'shots/decl-2-proposed.png', fullPage: true });

step('editor approves');
await open('role=editor&uid=u_editor', 'case-SYN-CASE-001');
await page.waitForSelector('#case-panel >> button:has-text("Approve")');
await page.click('#case-panel >> button:has-text("Approve")');
await page.waitForSelector('#case-panel >> text=Approved by');
const db = await page.evaluate(() => JSON.parse(localStorage.getItem('mockdb')));
assert(Object.keys(db).some((k) => k.startsWith('decisions/u_editor/d/case_SYN-CASE-001~')), 'decision path');
assert(Object.keys(db).some((k) => k.startsWith('briefs/u_contrib/b/case_SYN-CASE-001~')), 'proposal path');

step('the answers view counts the approved outcome');
await open('role=owner&uid=u_owner', 'declarations');
await page.click('text=Show the answers');
await page.waitForTimeout(300);
t = await text();
assert(t.includes('Approved outcome') && t.includes('hold an injected pattern'), 'answers view missing');

step('public lead file links to the case');
await open('role=owner&uid=u_owner', 'file-KZ-851762');
await page.waitForSelector('#sec-connected >> text=SYN-CASE-001');
assert((await text()).includes('SYN-CASE-001'), 'case link missing on the lead file');

step('narrow screen');
await page.setViewportSize({ width: 390, height: 860 });
for (const hsh of ['declarations', 'case-SYN-CASE-001']) {
  await open('role=owner&uid=u_owner', hsh);
  const over = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  assert(!over, 'horizontal overflow on ' + hsh);
}
await page.screenshot({ path: 'shots/decl-3-narrow.png' });
assert.deepEqual(logs, [], logs.join(' | '));
console.log('decl flow passed');
await browser.close();
