// Captioned walkthrough videos of the four demos, recorded in Chromium from the built site.
//
//   node tests/site/walkthrough.mjs site/dist site/media [radar workspace ta planner]
//
// For each demo it writes <name>.mp4 (H.264, 1280 by 720, the captions drawn into the picture,
// so they show wherever the file plays), <name>.vtt (the same captions as subtitles), <name>.txt
// (the captions with their times, as a transcript) and <name>.jpg (a poster frame). The figures
// in the captions are read from the site's own datasets, so a caption cannot drift from the page;
// where a caption needs a count in words, the recorder stops if the data no longer give it. Each
// walkthrough ends with the Open Government Licence line, as each shows HMRC or MHCLG figures.
// The pages run as the site serves them (tests/site/serve.mjs), in demo mode: nothing is sent
// anywhere and nothing is saved beyond the tab.
//
// Synthetic records and published aggregates only. A rise in exports is a lead, not evidence of
// a breach.
import { mkdir, readFile, rm, writeFile, mkdtemp } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const { chromium } = await import(path.join(here, '..', 'browser', 'node_modules', 'playwright', 'index.mjs'));
const { serve } = await import(path.join(here, 'serve.mjs'));
const root = path.resolve(process.argv[2] || path.join(here, '..', '..', 'site', 'dist'));
const out = path.resolve(process.argv[3] || path.join(here, '..', '..', 'site', 'media'));
const only = process.argv.slice(4);
await mkdir(out, { recursive: true });
const json = async (rel) => JSON.parse(await readFile(path.join(root, rel), 'utf8'));
const fmt = (n) => Number(n).toLocaleString('en-GB');
const WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
// A count in words, for the start of a caption's sentence or inside one.
const words = (n) => { if (!Number.isInteger(n) || n < 0 || n >= WORDS.length) throw new Error(`no word for ${n}`); return WORDS[n]; };
const Words = (n) => words(n).charAt(0).toUpperCase() + words(n).slice(1);
const OGL = 'Contains public sector information licensed under the Open Government Licence v3.0.';

// ------------------------------------------------------------------ the overlay
// A caption bar and a pointer dot, added to every page the walkthrough opens. Only the recording
// sees them; the pages themselves are unchanged.
const OVERLAY = `(() => {
  function setup() {
    if (document.getElementById('wt-cap') || !document.documentElement) return;
    const cap = document.createElement('div');
    cap.id = 'wt-cap';
    cap.hidden = true;
    Object.assign(cap.style, {
      position: 'fixed', left: '50%', bottom: '26px', transform: 'translateX(-50%)', zIndex: '99999',
      maxWidth: '1040px', width: 'max-content', boxSizing: 'border-box', padding: '14px 22px', borderRadius: '12px',
      background: 'rgba(14, 19, 24, 0.9)', color: '#ffffff', font: '500 22px/1.4 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
      textAlign: 'center', boxShadow: '0 8px 28px rgba(0, 0, 0, 0.35)', pointerEvents: 'none', letterSpacing: '0.005em',
    });
    const dot = document.createElement('div');
    dot.id = 'wt-dot';
    Object.assign(dot.style, {
      position: 'fixed', left: '0', top: '0', width: '18px', height: '18px', borderRadius: '50%', zIndex: '99999',
      background: 'rgba(31, 95, 122, 0.9)', border: '2px solid #ffffff', boxShadow: '0 1px 4px rgba(0, 0, 0, 0.4)',
      pointerEvents: 'none', opacity: '0', transition: 'box-shadow 160ms ease',
    });
    document.documentElement.append(cap, dot);
    document.addEventListener('mousemove', (e) => { dot.style.transform = 'translate(' + (e.clientX - 9) + 'px,' + (e.clientY - 9) + 'px)'; dot.style.opacity = '1'; }, true);
    document.addEventListener('mousedown', () => { dot.style.boxShadow = '0 0 0 9px rgba(31, 95, 122, 0.28)'; setTimeout(() => { dot.style.boxShadow = '0 1px 4px rgba(0, 0, 0, 0.4)'; }, 220); }, true);
  }
  window.__wtCaption = (text) => { setup(); const c = document.getElementById('wt-cap'); if (!c) return; c.textContent = text; c.hidden = !text; };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setup); else setup();
})();`;

// ------------------------------------------------------------------ helpers
const readTime = (text) => Math.max(2800, 1300 + text.split(/\s+/).length * 330);

function helpers(page, log, t0) {
  const say = async (text, ms) => {
    log.push({ at: (Date.now() - t0()) / 1000, text });
    await page.evaluate((t) => window.__wtCaption && window.__wtCaption(t), text);
    await page.waitForTimeout(ms ?? readTime(text));
  };
  const loc = (sel) => (typeof sel === 'string' ? page.locator(sel).first() : sel);
  const point = async (sel) => {
    const l = loc(sel);
    await l.waitFor({ state: 'visible', timeout: 15000 });
    await l.scrollIntoViewIfNeeded();
    const b = await l.boundingBox();
    if (b) await page.mouse.move(b.x + Math.min(b.width / 2, 160), b.y + Math.min(b.height / 2, 18), { steps: 22 });
    await page.waitForTimeout(220);
    return l;
  };
  const click = async (sel, wait = 650) => { const l = await point(sel); await l.click(); await page.waitForTimeout(wait); };
  const scrollTo = async (sel, offset = 76) => {
    await page.evaluate(([s, o]) => {
      const el = document.querySelector(s);
      if (el) window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - o, behavior: 'smooth' });
    }, [sel, offset]);
    await page.waitForTimeout(1200);
  };
  const top = async () => { await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' })); await page.waitForTimeout(900); };
  const type = async (sel, text, delay = 26) => { const l = await point(sel); await l.fill(''); await l.pressSequentially(text, { delay }); await page.waitForTimeout(450); };
  return { say, point, click, scrollTo, top, type };
}

const vttTime = (s) => {
  const ms = Math.max(0, Math.round(s * 1000));
  const hh = String(Math.floor(ms / 3600000)).padStart(2, '0');
  const mm = String(Math.floor(ms / 60000) % 60).padStart(2, '0');
  const ss = String(Math.floor(ms / 1000) % 60).padStart(2, '0');
  return `${hh}:${mm}:${ss}.${String(ms % 1000).padStart(3, '0')}`;
};

// Frames come from Chrome's own screencast (the DevTools protocol), saved as JPEGs with their
// times, and are joined by the system's ffmpeg at 30 frames a second. Playwright's own video
// recorder needs an ffmpeg build this machine does not have.
async function record(name, title, url, script) {
  const tmp = await mkdtemp(path.join(os.tmpdir(), 'walkthrough-'));
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1, colorScheme: 'light' });
  await ctx.addInitScript(OVERLAY);
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  const frames = [];
  const writes = [];
  const cdp = await ctx.newCDPSession(page);
  cdp.on('Page.screencastFrame', (f) => {
    const file = path.join(tmp, `f${String(frames.length).padStart(6, '0')}.jpg`);
    frames.push({ t: f.metadata.timestamp * 1000, file });
    writes.push(writeFile(file, Buffer.from(f.data, 'base64')));
    cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
  });
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: 1280, maxHeight: 720, everyNthFrame: 1 });
  let loaded = Date.now();
  const log = [];
  const h = helpers(page, log, () => loaded);
  await page.goto(origin + url, { waitUntil: 'networkidle' });
  await page.waitForTimeout(600);
  loaded = Date.now();
  await script(page, h);
  await h.say('', 900);
  const stop = Date.now();
  await cdp.send('Page.stopScreencast');
  await ctx.close();
  await Promise.all(writes);
  if (errors.length) throw new Error(`${name}: the page logged errors:\n  ${errors.join('\n  ')}`);
  // The frame showing at `loaded` opens the film; each frame lasts until the next one.
  let first = frames.findIndex((f) => f.t > loaded);
  first = first <= 0 ? 0 : first - 1;
  const used = frames.slice(first);
  if (!used.length) throw new Error(`${name}: no frames were captured`);
  const lines = ['ffconcat version 1.0'];
  used.forEach((f, i) => {
    const from = Math.max(f.t, loaded);
    const to = i + 1 < used.length ? used[i + 1].t : stop;
    lines.push(`file '${f.file}'`, `duration ${Math.max(0.001, (to - from) / 1000).toFixed(4)}`);
  });
  lines.push(`file '${used[used.length - 1].file}'`);
  const list = path.join(tmp, 'frames.txt');
  await writeFile(list, lines.join('\n') + '\n');
  const mp4 = path.join(out, `${name}.mp4`);
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list,
    '-vf', 'fps=30,scale=1280:720:flags=lanczos,format=yuv420p', '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '20',
    '-movflags', '+faststart', '-metadata', `title=${title}`, mp4]);
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-ss', '3', '-i', mp4, '-frames:v', '1', '-q:v', '3', path.join(out, `${name}.jpg`)]);
  const end = (stop - loaded) / 1000;
  const cues = log.filter((c) => c.text);
  const vtt = ['WEBVTT', ''];
  const txt = [`${title}`, ''];
  cues.forEach((c, i) => {
    const next = log[log.indexOf(c) + 1];
    const until = next ? next.at : end;
    vtt.push(String(i + 1), `${vttTime(c.at)} --> ${vttTime(until)}`, c.text, '');
    txt.push(`[${vttTime(c.at).slice(3, 8)}] ${c.text}`);
  });
  await writeFile(path.join(out, `${name}.vtt`), vtt.join('\n'));
  await writeFile(path.join(out, `${name}.txt`), txt.join('\n') + '\n');
  await rm(tmp, { recursive: true, force: true });
  console.log(`  ${name}.mp4: ${end.toFixed(0)} s, ${used.length} frames, ${cues.length} captions`);
}

// ------------------------------------------------------------------ the four walkthroughs
const S = (await json('radar/data/summary.json'))[0];
const COST = Object.fromEntries((await json('radar/data/cost.json')).map((r) => [r.measure, r]));
const need = (o, k) => { if (!o[k]) throw new Error(`cost.json has no row "${k}"; update the captions`); return o[k]; };
const CASES = need(COST, 'Cases with a lead before the first public action');
// The caption says "since January 2022": the row's own label carries the dates.
const EVER = need(COST, 'Series a lead at some run, Jan 2022 to Aug 2026');
const RUNS = need(COST, 'Monthly runs as a lead, all series');
const TESTS = await json('radar/data/tests.json');
const HIDDEN = TESTS.filter((t) => t.shown === false).length;
const STOPPED = TESTS.filter((t) => t.shown !== false && /^no, stopped/.test(t.run2_on_the_day || '')).length;
const DETECTORS = (await json('workspace/data/declarations/evaluation.json')).detectors.length;
const CASELOAD = (await json('planner/data/caseload.json')).records.length;

const WALKS = {
  radar: ['Diversion Radar: the dashboard', '/radar/', async (page, { say, point, click, scrollTo, top }) => {
    await say('Diversion Radar. Each month it looks for goods on the high-priority list where UK exports to a third country rose, and that country’s own exports of the same goods to Russia rose too.');
    await point('#kpi-leads');
    await say(`The ${S.run_label} run, on HMRC data to ${S.uk_data_to}: ${fmt(S.series)} series, ${fmt(S.leads)} leads and ${fmt(S.watch)} watch items.`);
    await scrollTo('#card-flagged');
    await say('Each lead sets the UK side beside the onward side. Small UK flows are held back by the display rule, so a lead is less likely to point at one exporter: counted, never shown by corridor or code.');
    await scrollTo('#card-history');
    await say('How each signal built up, run by run, with the line it had to clear.');
    await top();
    await click('#tab-track');
    await say('The backtest: would the radar have made the routes in published enforcement cases a lead before the first public action?');
    await point('#kpi-cases');
    await say(`With the monthly check, ${fmt(CASES.run2)} of ${fmt(CASES.of)} cases had a lead before the first public action, and ${fmt(CASES.run1)} with the annual check alone. ${Words(CASES.of)} cases is a small test, and not a blind one.`);
    await scrollTo('#card-leadtime');
    await say(`Months from the first lead to the action, test by test; in ${words(STOPPED)} of them the lead had stopped before the action. ${Words(HIDDEN)} tests are held back by the display rule, with no route and no result.`);
    await scrollTo('#card-cost');
    await say(`Earlier warning has a cost: more leads. On the backtest's corridors, ${fmt(EVER.run2)} of ${fmt(EVER.of)} series were a lead at some run since January 2022 with the monthly check, against ${fmt(EVER.run1)} with the annual check alone; counted at each run, ${fmt(RUNS.run2)} leads against ${fmt(RUNS.run1)}.`);
    await top();
    await click('#tab-method');
    await scrollTo('#card-display');
    await say('Every rule and source is written down, with what could make it wrong.');
    await say('A rise in exports is a lead, not evidence of a breach.', 3200);
    await say(OGL, 2600);
  }],

  workspace: ['Diversion Radar: the analyst workspace', '/workspace/', async (page, { say, point, click, scrollTo, top, type }) => {
    await point('#portal .portal-card');
    await say('The analyst workspace opens on sign-in. Each person has a role: analysts work files, editors decide, a partner liaison reads, and the owner sets access. Here the people are synthetic.');
    await click('#portal .portal-person[data-person="demo-analyst"]', 1000);
    await point('#ov-console .gl-stage');
    await say(`It opens on the console: the run’s ${S.leads_shown} leads and ${S.watch_shown} watch items on a turning globe, with routes from the UK to their corridors and on to Russia. The sweep lights each corridor as it passes; held-back series are counted, never placed.`);
    await click('#ov-console .gl-list button[data-iso="TR"]', 1600);
    await point('#gl-sel');
    await say('Choose a corridor and the globe turns to it, with what is shown there and a way into its files. The figures are the monthly run’s; the motion is the scan, not live data.');
    await scrollTo('#view-overview .worth');
    await point('#view-overview .worth');
    await say('Below it, what changed since the last run, what waits for a decision, and what a lead is worth: a question ranked for an analyst, not evidence. In this demo, changes stay in your browser tab.');
    await point('#nav-review');
    await say('The sidebar sets out the work by job: what needs your review, what came back to you, what you have taken, and the views of this run.');
    await page.keyboard.press('Control+k');
    await page.waitForTimeout(400);
    await page.keyboard.type('kazakhstan', { delay: 70 });
    await page.waitForTimeout(500);
    await say('Search finds a file, a case, a report or a page from anywhere, and the keyboard moves through lists and files.');
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    await click('#tab-inbox', 900);
    await point('button.qrow >> nth=1');
    await say('Each file shows the UK flow and the corridor’s onward trade, who has it and what has happened to it.');
    await click('button.qrow[aria-label="Open DR-2026-10-KZ-851762"]', 900);
    await point('.rec-actions');
    await say('A file reads as one record: the next step at the top, sections that fold away, and a rail with its owner, follow-ups, official references and add-ons.');
    await click('#rail-tasks >> text=+ Add a follow-up', 600);
    await click('#rail-tasks .tpl-chip >> nth=0', 900);
    await say('Each next step gets an owner and a date, and every one is audited. A deployment can send them on to a task tracker or a calendar; here the add-ons show what they would send.');
    await point('#rail-addons');
    await scrollTo('#sec-support');
    await say('The evidence, the factors behind the lead and how it built up sit in sections, with a checklist of questions from official guidance.');
    await click('text=Start from the template', 900);
    await say('Here the brief starts from the template. Inside Claude, Claude is asked to draft it from these facts only, and the screen checks its figures and names.');
    await click('#brief-panel >> text=Edit', 700);
    const field = 'textarea[aria-label="Headline"]';
    const orig = await page.inputValue(field);
    const wrong = orig.replace(/\d+(?:\.\d+)?x/, '99.9x');
    await type(field, wrong, 14);
    await point('text=A figure that appears nowhere in the context');
    await say('Every draft and every edit passes the screen. A figure that is not in the evidence is stopped before it can be saved.');
    await page.fill(field, orig);
    await page.waitForTimeout(500);
    await click('text=Done editing', 700);
    await click('text=Save draft', 900);
    await say('Fixed, it passes, and is saved as a version with its fingerprint.');
    await click('#checks-panel .seg >> nth=0 >> text=Checked', 500);
    await click('text=Submit for approval', 900);
    await point('#brief-panel .st-submitted');
    await say('Submitted. With four-eyes on, as it is by default, the person who saved a brief cannot approve it: a second person does.');
    await click('.who-switch', 700);
    await click('#portal .portal-person[data-person="demo-reviewer"]', 1000);
    await click('#brief-panel >> button:has-text("Approve")', 1000);
    await top();
    await point('.rec-actions button.primary');
    await say('A reviewer approves it. The file’s next step is now to record what happened after the lead.');
    await click('.rec-actions button.primary', 900);
    await click('#slot-outcome input[value=referral]', 400);
    await type('textarea[aria-label="Outcome note"]', 'Passed to the trade sanctions team with the referral pack.', 18);
    await click('text=Save the outcome', 900);
    await say('Outcomes come from a fixed list, from no further action to a route proposed for an end-use controls decision, and the overview counts them. A count of what the team did, never a finding.');
    await point('text=Prepare a referral pack');
    await say('A referral pack follows the headings OTSI asks for, fills what the lead can, and leaves the UK link and any parties to the analyst. It names no exporter. This static copy saves no files, so the button is off here.');
    await top();
    await click('#tab-tasks', 1000);
    await say('Follow-ups gathers every open step on every file, overdue first, so a morning starts with what is due.');
    await click('#tab-monitor', 1000);
    await point('#view-monitor .mon-item');
    await say('The monitor: official notices and releases read from public pages, the source’s own words beside an English summary, each with a proposed grade on the six-by-six scale.');
    await click('#view-monitor .mon-item >> nth=0 >> button:has-text("Decide")', 700);
    await click('#view-monitor .mon-item >> nth=0 >> button:has-text("Accept")', 900);
    await say('A person accepts an item onto the files it touches, setting its grade, or rejects it with a reason. Nothing reaches a brief unless a person writes it in.');
    await click('#tab-declarations', 1200);
    await say(`The restricted layer, on synthetic export declarations: ${words(DETECTORS)} detectors raise questions, grouped into cases for a person to check.`);
    await click('#tab-audit', 900);
    await say('Drafts, checks, decisions, screens and exports go in the audit log, under the person who took them.');
    await click('#tab-guide', 900);
    await say('How it works sets out who uses the workspace, a typical month with it, what is demo data here and what a deployment adds.');
    await say('A rise in exports is a lead, not evidence of a breach.', 3000);
    await say(OGL, 2600);
  }],

  ta: ['Move forward: the market picture', '/ta/', async (page, { say, point, click, scrollTo, top, type }) => {
    await say('Move forward’s market picture: temporary accommodation in England, one council set against the others in its group. No council is named.');
    await point('#kpi-gross');
    await say('Households, spend per household-year and where it sits among its peers, from MHCLG’s published statistics.');
    await scrollTo('#spread-chart', 220);
    await say('Each grey dot is another London borough, unnamed. The band is the middle half of them; the line is their median.');
    await top();
    await click('button:has-text("A metropolitan council")', 900);
    await say('Switch to a council outside London and the comparison moves to its own group.');
    await scrollTo('#card-savings', 300);
    await type('#in-hh', '100', 90);
    await type('#in-gap', '1000', 90);
    await point('#card-savings .ta-cap');
    await say('The savings illustration takes the price gap as your input. It is arithmetic, never a forecast.');
    await top();
    await click('#tab-england', 900);
    await say('England as a whole: households in temporary accommodation, and what councils spend on it, by type.');
    await click('#tab-method', 900);
    await say('How the figures are made and what could make them wrong, with their sources.');
    await say('A council far from its peers is a question to ask, not a finding.', 3200);
    await say(OGL, 2600);
  }],

  planner: ['Move forward: the planner', '/planner/', async (page, { say, point, click, scrollTo, top, type }) => {
    await point('#portal .portal-card');
    await say(`Move forward’s planner, on ${fmt(CASELOAD)} made-up households in temporary accommodation. None of them is a real person. It opens on sign-in, with a synthetic person at each role.`);
    await click('#portal .portal-person[data-person="demo-officer"]', 1000);
    await say('Then its overview: plans waiting, the pipeline, time in TA and the checks raised.');
    await point('#view-overview .pipe');
    await click('#tab-board', 1000);
    await say('The board: every household by where its plan stands. A card opens the household; a plan moves on only through its file, so each step keeps its approval.');
    await point('#nav-ood');
    await say('The sidebar holds the queues and views: plans to approve, plans returned to you, and households out of district or in temporary accommodation for two years or more.');
    await click('#tab-compliance', 1000);
    await point('#view-compliance section.card');
    await say('Compliance at risk: every statutory clock that needs an officer now. The s.208 notice when a household is placed in another district, six weeks for a family in B&B, eight weeks for a review decision, and since 1 September 2026, once agreed, a notice to the bodies that serve each child.');
    await click('#tab-caseload', 900);
    await point('button.crow >> nth=2');
    await say('The caseload, longest in temporary accommodation first, with the checks each record raises.');
    await click('button.crow[title="Open SYN-0114"]', 900);
    await say('A file: the household’s facts, the routes out it could take, and a selection of the checks legislation and guidance set.');
    await click('text=Start from the template', 900);
    await say('A move-forward plan from the template. Inside Claude, Claude is asked to draft it from this record, its suggested routes and checks, any reviewer notes and any lessons a second officer approved.');
    await click('#plan-panel >> text=Edit', 700);
    const field = 'textarea[aria-label="Summary"]';
    const orig = await page.inputValue(field);
    await type(field, 'The main housing duty has ended and the household must accept the offer.', 22);
    await point('text=States a decision');
    await say('The screen stops this plan: it states a decision. Plans are suggestions for an officer, and the screen is a net, so the officer reads every plan.');
    await page.fill(field, orig);
    await page.waitForTimeout(500);
    await click('text=Done editing', 700);
    await click('text=Save draft', 900);
    await click('text=Submit for approval', 900);
    await point('#plan-panel .st-submitted');
    await say('Saved and submitted. With four-eyes on, as it is by default, a second officer approves it: the person who saved it cannot.');
    await top();
    await click('#tab-scenario', 900);
    await say('The scenario: what moving households from one type of accommodation to another would come to, on figures you set.');
    await click('#tab-monitor', 1000);
    await point('#view-monitor article.mon-item');
    await say('The monitor: official statistics and guidance read from public pages, each with its source’s terms and a proposed grade. An officer accepts an item onto the households and references it touches, or rejects it with a reason.');
    await click('#tab-audit', 900);
    await say('Drafts, checks, decisions and exports go in the audit log, under the person who took them.');
    await click('#tab-guide', 900);
    await say('How it works sets out who uses the planner, a typical week with it, what is demo data here and what a deployment adds.');
    await say('Synthetic records only. Each statutory decision is made and recorded outside the planner.', 3400);
    await say(OGL, 2600);
  }],
};

const { origin, close } = await serve(root);
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }).catch(() => chromium.launch());
console.log(`walkthroughs from ${root} into ${out}`);
try {
  for (const [name, [title, url, script]] of Object.entries(WALKS)) {
    if (only.length && !only.includes(name)) continue;
    await record(name, title, url, script);
  }
} finally {
  await browser.close();
  await close();
}
