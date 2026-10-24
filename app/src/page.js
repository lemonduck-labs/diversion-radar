/* The radar workspace page. scripts/build_app_page.py copies this file into app/index.html
 * after the shared screen (app/src/screen.js). Edit this file, then run the build.
 */
(() => {
'use strict';

/* ============================================================== helpers */
const $ = (sel, el = document) => el.querySelector(sel);
const SVGNS = 'http://www.w3.org/2000/svg';
function build(ns, tag, props, kids) {
  const el = ns ? document.createElementNS(ns, tag) : document.createElement(tag);
  if (props) for (const k in props) {
    const v = props[k];
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') el.setAttribute('class', v);
    else if (k === 'text') el.textContent = v;
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (k === 'dataset') Object.assign(el.dataset, v);
    else if (!ns && (k === 'value' || k === 'checked' || k === 'disabled' || k === 'hidden' || k === 'selected')) el[k] = v;
    else el.setAttribute(k, v === true ? '' : String(v));
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}
const h = (tag, props, ...kids) => build(null, tag, props, kids);
const sv = (tag, props, ...kids) => build(SVGNS, tag, props, kids);
// Element.append writes null as the text "null", so a card's children go through add(), which
// skips null, undefined and false as h() does.
const add = (el, ...kids) => { for (const k of kids.flat(Infinity)) if (k !== null && k !== undefined && k !== false) el.append(k); return el; };
// Element.replaceChildren, like append, writes null as the text "null" and an array as its
// string, so views are redrawn through swap(), which skips null, undefined and false and
// flattens arrays, as h() and add() do.
const swap = (el, ...kids) => { el.replaceChildren(); return add(el, ...kids); };
const isNum = (v) => v !== null && v !== undefined && v !== '' && !isNaN(+v);
const halfUp = (x, nd) => { const f = Math.pow(10, nd); return Math.round(x * f) / f; };
function money(v, sign) {
  if (!isNum(v)) return 'n/a';
  v = +v;
  const a = Math.abs(v);
  if (a >= 999500) return sign + halfUp(v / 1e6, 1).toFixed(1) + 'm';
  if (a >= 1e3) return sign + Math.round(v / 1e3).toLocaleString('en-GB') + 'k';
  return sign + Math.round(v).toLocaleString('en-GB');
}
const gbp = (v) => money(v, '£');
const usd = (v) => money(v, '$');
const ratio = (v, zero) => isNum(v) ? halfUp(+v, 1).toFixed(1) + 'x' : (zero ? 'zero baseline' : 'n/a');
const intGB = (v) => isNum(v) ? Math.round(+v).toLocaleString('en-GB') : 'n/a';
// One to nine in words, larger counts in figures, as in the reports.
const inWords = (n) => (['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'][n] || intGB(n));
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTH_FULL = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
function monthLabel(s, full) {
  const m = /^(\d{4})-(\d{2})/.exec(String(s || ''));
  return m ? (full ? MONTH_FULL : MON)[+m[2] - 1] + ' ' + m[1] : String(s || '');
}
function stamp(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return '';
  return `${d.getDate()} ${MON[d.getMonth()]} ${d.getFullYear()}, ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}
// Corridor names that take "the" in running text, as in radar/brief/context.py (ARTICLE).
const ARTICLE = new Set(['United Arab Emirates', 'Kyrgyz Republic']);
const inText = (c, start) => { const s = ARTICLE.has(c) ? 'the ' + c : String(c); return start ? s[0].toUpperCase() + s.slice(1) : s; };
const possOf = (c, start) => { const s = inText(c, start); return s + (s.endsWith('s') ? '\u2019' : '\u2019s'); };
const fmtCode = (c) => /^\d{6}$/.test(String(c)) ? String(c).slice(0, 4) + '.' + String(c).slice(4) : String(c);
const nowIso = () => new Date().toISOString();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const local = {
  get(k, d) { try { const v = localStorage.getItem('dr.' + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('dr.' + k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
};
async function sha256(text) {
  try {
    const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
    return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
  } catch { return ''; }
}
// Canonical JSON: keys sorted at every level, so a hash does not depend on key order.
function canon(v) {
  if (Array.isArray(v)) return '[' + v.map(canon).join(',') + ']';
  if (v && typeof v === 'object') return '{' + Object.keys(v).sort().map((k) => JSON.stringify(k) + ':' + canon(v[k])).join(',') + '}';
  return JSON.stringify(v);
}
const clone = (o) => o === undefined ? undefined : JSON.parse(JSON.stringify(o));

/* ============================================================== state */
const S = {
  D: {}, spec: {}, contexts: {}, files: [], byKey: new Map(),
  store: null, storeState: 'connecting', readOnly: false,
  me: { id: null, name: '', avatar: '', isOwner: false, canEdit: false, canData: null, role: '' },
  caps: { db: undefined, user: undefined, sample: undefined, downloads: undefined },
  // Shared records: leads (status pointer, current brief, assignee) and checks. Author-bound
  // records sit under each person's own path (briefs/<id>/b, decisions/<id>/d, audit/<id>/e),
  // which the store's rules let only that person write, so the path says who wrote them.
  leads: new Map(), checks: new Map(), tasks: new Map(), outcomes: new Map(), enduse: new Map(), outForm: null, refForm: null, euForm: null, monitorDec: new Map(), monOpen: null, workflow: { four_eyes: true },
  members: new Set(), memberIds: new Set(), byMember: { briefs: new Map(), decisions: new Map(), audit: new Map() },
  briefs: new Map(), decisions: new Map(), audit: [], verified: new Map(), auditCapped: false,
  // Lessons (fd-core's memory core): kept notes from returned briefs, the decisions on them, and
  // whether each one's text still matches the SHA-256 saved with it.
  lessons: new Map(), lessonDecisions: new Map(), lessonVerified: new Map(),
  demoAs: local.get('demo_as', 'demo-analyst'),
  people: {}, view: 'inbox', fileKey: null, filter: local.get('filter', 'all'),
  ui: {}, // per-file transient UI state: { mode, working, problems, busy, ctl, confirm, msg }
  exporter: { text: null, name: '', mapping: null, header: null, rows: null, result: null, msg: '' },
};
const uiFor = (docId) => (S.ui[docId] = S.ui[docId] || { mode: 'view', working: null, problems: null, busy: false, ctl: null, confirm: null, msg: '', note: '', reason: '' });

/* ============================================================== capabilities */
const hasClaude = typeof window.claude === 'object' && window.claude !== null && typeof window.claude.use === 'function';
// The hosted build (hosted/README.md) loads app/src/hosted.js first, which sets window.RadarHosted.
const HOSTED = typeof window.RadarHosted === 'object' && window.RadarHosted !== null;
async function useCap(name) {
  if (!hasClaude) return null;
  try { return await window.claude.use(name); } catch { return null; }
}

/* ============================================================== stores
   One small interface, two backends: the artifact's shared database, or a store held in
   this tab when the view has none. A hosted version swaps in a Supabase backend with the
   same five calls (see app/README.md). */
async function withRetry(fn) {
  try { return await fn(); } catch (e) {
    if (e && e.code === 'unavailable') { await sleep(300 + Math.random() * 600); return fn(); }
    throw e;
  }
}
function dbStore(db) {
  const coll = (c) => db.collection(c);
  return {
    kind: 'db',
    watch(c, opts, cb, onErr) {
      let q = coll(c);
      if (opts && opts.orderBy) q = q.orderBy(opts.orderBy, opts.dir || 'asc');
      if (opts && opts.limit) q = q.limit(opts.limit);
      return q.onSnapshot((snap) => cb(snap.docs.filter((d) => d.exists).map((d) => ({ id: d.id, data: d.data() }))), (e) => onErr && onErr(e));
    },
    watchDoc(c, id, cb, onErr) { return coll(c).doc(id).onSnapshot((d) => cb(d.exists ? d.data() : null), (e) => onErr && onErr(e)); },
    async get(c, id) { const d = await withRetry(() => coll(c).doc(id).get()); return d.exists ? d.data() : null; },
    set(c, id, data) { return withRetry(() => coll(c).doc(id).set(data)); },
    update(c, id, data) { return withRetry(() => coll(c).doc(id).update(data)); },
    async add(c, data) { const ref = coll(c).doc(); await withRetry(() => ref.set(data)); return ref.id; },
  };
}
function memoryStore() {
  const colls = new Map(), subs = new Map();
  const bucket = (c) => { if (!colls.has(c)) colls.set(c, new Map()); return colls.get(c); };
  const emit = (c) => { for (const fn of subs.get(c) || []) fn(); };
  const merge = (a, b) => {
    const out = Object.assign({}, a);
    for (const k in b) out[k] = b[k] && typeof b[k] === 'object' && !Array.isArray(b[k]) && a[k] && typeof a[k] === 'object' && !Array.isArray(a[k]) ? merge(a[k], b[k]) : b[k];
    return out;
  };
  const listen = (c, fn) => { if (!subs.has(c)) subs.set(c, new Set()); subs.get(c).add(fn); setTimeout(fn, 0); return () => subs.get(c).delete(fn); };
  return {
    kind: 'memory',
    watch(c, opts, cb) {
      return listen(c, () => {
        let rows = [...bucket(c).entries()].map(([id, data]) => ({ id, data: clone(data) }));
        if (opts && opts.orderBy) { const k = opts.orderBy, dir = opts.dir === 'desc' ? -1 : 1; rows.sort((x, y) => (x.data[k] > y.data[k] ? 1 : x.data[k] < y.data[k] ? -1 : 0) * dir); }
        else rows.sort((x, y) => (x.id < y.id ? -1 : x.id > y.id ? 1 : 0));
        if (opts && opts.limit) rows = rows.slice(0, opts.limit);
        cb(rows);
      });
    },
    watchDoc(c, id, cb) { return listen(c, () => { const v = bucket(c).get(id); cb(v ? clone(v) : null); }); },
    async get(c, id) { const v = bucket(c).get(id); return v ? clone(v) : null; },
    async set(c, id, data) { bucket(c).set(id, clone(data)); emit(c); },
    async update(c, id, data) { const cur = bucket(c).get(id); if (!cur) throw { code: 'invalid_argument', message: 'no such document' }; bucket(c).set(id, merge(cur, clone(data))); emit(c); },
    async add(c, data) { const id = 'm' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8); bucket(c).set(id, clone(data)); emit(c); return id; },
  };
}
async function upsert(c, id, data) {
  const cur = await S.store.get(c, id);
  if (cur) return S.store.update(c, id, data);
  return S.store.set(c, id, data);
}

/* ============================================================== permissions */
// Demo mode has no real sign-in, so the sign-in screen offers synthetic people, one for each
// role the hosted version has (viewer, contributor, editor, owner), and two editors so that
// four-eyes on briefs and on lessons can be tried in one tab. The choice is kept in this browser.
const DEMO_PEOPLE = {
  'demo-analyst': { name: 'Analyst (demo)', role: 'Contributor', edit: false, initials: 'AN',
    does: 'Takes files, drafts briefs, works the checks and follow-ups, and sends files for approval.' },
  'demo-reviewer': { name: 'Reviewer (demo)', role: 'Editor', edit: true, initials: 'RV',
    does: 'Everything an analyst does, and approves, returns or rejects briefs; with four-eyes on, never approves a brief they saved.' },
  'demo-lead': { name: 'Lead reviewer (demo)', role: 'Editor', edit: true, initials: 'LR',
    does: 'A second editor, so that four-eyes can be tried in one tab.' },
  'demo-partner': { name: 'Partner liaison (demo)', role: 'Viewer', edit: false, view: true, initials: 'PL',
    does: 'Reads files, briefs and the audit log, and exports evidence packs; changes nothing.' },
  'demo-owner': { name: 'Workspace owner (demo)', role: 'Owner', edit: true, owner: true, initials: 'WO',
    does: 'Everything an editor does. In a deployment the owner also decides who has access, and at which role.' },
};
const isDemo = () => !!S.store && S.store.kind === 'memory';
const demoMe = () => (DEMO_PEOPLE[S.demoAs] ? S.demoAs : 'demo-analyst');
const canWrite = () => !!S.store && S.storeState !== 'connecting' && !S.readOnly && (S.store.kind === 'memory' ? !DEMO_PEOPLE[demoMe()].view : (!!S.me.id && S.me.canData !== false));
const canApprove = () => !!S.store && (isDemo() ? DEMO_PEOPLE[demoMe()].edit : (S.me.isOwner || S.me.canEdit));
const myId = () => (isDemo() ? demoMe() : S.me.id);
function writeFailed(e, what) {
  const code = e && e.code;
  if (code === 'invalid_argument' && S.store && S.store.kind === 'db') {
    S.readOnly = true;
    banner('ro', 'warn', 'Your access lets you read this workspace but not change it. Ask the owner for Contributor access to work on files.');
  } else if (code === 'quota_exceeded') {
    banner('quota', 'bad', 'The workspace store is full, so nothing new can be saved. The owner can archive older runs to make room.');
  } else {
    banner('write', 'bad', `Could not save ${what}. Try again in a moment.`);
  }
  refresh();
}

/* ============================================================== people */
const pending = new Set();
async function resolvePeople(ids) {
  const want = [...new Set(ids.filter((i) => i && i !== 'local-viewer' && !DEMO_PEOPLE[i] && !S.people[i] && !pending.has(i)))];
  if (!want.length || !S.caps.user) return;
  want.forEach((i) => pending.add(i));
  try {
    const ps = await S.caps.user.profiles(want);
    let changed = false;
    for (const id of want) { if (ps[id]) { S.people[id] = { name: ps[id].name || '', avatar: ps[id].avatarUrl || '' }; changed = true; } }
    if (changed) refresh();
  } finally { want.forEach((i) => pending.delete(i)); }
}
// "Analyst (demo)" becomes "Analyst (demo, you)", not "(demo) (you)".
const withYou = (name) => (/\)$/.test(name) ? name.replace(/\)$/, ', you)') : name + ' (you)');
function person(id) {
  if (!id) return { name: 'Nobody', avatar: '' };
  if (DEMO_PEOPLE[id]) return { name: id === myId() ? withYou(DEMO_PEOPLE[id].name) : DEMO_PEOPLE[id].name, avatar: '' };
  if (id === 'local-viewer' || id === S.me.id) return { name: S.me.name ? withYou(S.me.name) : 'You', avatar: S.me.avatar };
  const p = S.people[id];
  return { name: (p && p.name) || 'Someone', avatar: (p && p.avatar) || '' };
}
// Names for exported files: never "You", and the id itself when a name does not resolve.
function nameFor(id) {
  if (!id) return 'nobody';
  if (DEMO_PEOPLE[id]) return DEMO_PEOPLE[id].name;
  if (id === 'local-viewer') return 'the demo viewer';
  if (id === S.me.id && S.me.name) return S.me.name;
  const p = S.people[id];
  return (p && p.name) || id;
}
function whoLine(id, extra) {
  const p = person(id);
  return h('span', { class: 'who-line' }, p.avatar ? h('img', { src: p.avatar, alt: '' }) : null, h('span', null, p.name), extra || null);
}

/* ============================================================== banners */
const banners = new Map();
function banner(key, kind, text) { if (text) banners.set(key, { kind, text }); else banners.delete(key); drawBanners(); }
function drawBanners() {
  const box = $('#banners');
  swap(box, ...[...banners.values()].map((b) => h('div', { class: 'banner ' + (b.kind || '') }, b.text)));
}

/* ============================================================== data */
async function getJSON(p) { const r = await fetch(p, { cache: 'no-cache' }); if (!r.ok) throw new Error(`${p}: HTTP ${r.status}`); return r.json(); }
async function getText(p) { const r = await fetch(p, { cache: 'no-cache' }); if (!r.ok) throw new Error(`${p}: HTTP ${r.status}`); return r.text(); }
async function loadStatic() {
  const names = ['summary', 'leads', 'history', 'onward_years', 'tests', 'cases', 'placebo', 'cost', 'signals', 'codes', 'corridors', 'manifest'];
  const vals = await Promise.all(names.map((n) => getJSON(`data/${n}.json`)));
  names.forEach((n, i) => { S.D[n] = vals[i]; });
  const opt = await Promise.allSettled([
    getText('spec/prompt.md'), getJSON('spec/brief.schema.json'), getJSON('spec/screen_rules.json'),
    getJSON('spec/redflags.json'), getJSON('data/briefs/index.json'), getJSON('spec/memory_rules.json'), getJSON('spec/references.json'), getJSON('data/monitor.json'), getJSON('spec/monitor_sources.json'),
  ]);
  const val = (i) => (opt[i].status === 'fulfilled' ? opt[i].value : null);
  S.spec = { prompt: val(0), schema: val(1), rules: val(2), redflags: val(3), index: val(4), memRules: null, refs: val(6) && Array.isArray(val(6).references) ? val(6).references : [],
    monSources: val(8) && Array.isArray(val(8).sources) ? val(8).sources : [] };
  S.D.monitor = Array.isArray(val(7)) ? val(7) : [];
  if (val(5) && window.FdMemory && !HOSTED) { try { S.spec.memRules = window.FdMemory.compileMemoryRules(val(5)); } catch (e) { console.warn('memory rules did not compile', e); } }
  if (S.spec.rules) { try { S.spec.C = Screen.compile(S.spec.rules); } catch (e) { S.spec.C = null; console.warn('screen rules did not compile', e); } }
}
function buildFiles() {
  const iso = {};
  for (const c of S.D.corridors[0].corridors) iso[c.name] = c.iso2;
  const run = S.D.summary[0].run;
  S.files = S.D.leads.map((l) => {
    const key = `${iso[l.country]}-${l.code}`;
    return Object.assign({}, l, { key, iso2: iso[l.country], run, docId: `${run}_${key}`, ref: `DR-${run}-${key}` });
  });
  S.files.sort((a, b) => (a.status === b.status ? 0 : a.status === 'lead' ? -1 : 1));
  S.byKey = new Map(S.files.map((f) => [f.key, f]));
}
const contextLoads = new Map();
function contextFor(f) {
  if (S.contexts[f.key] !== undefined) return Promise.resolve(S.contexts[f.key]);
  if (!contextLoads.has(f.key)) contextLoads.set(f.key, loadContext(f));
  return contextLoads.get(f.key);
}
async function loadContext(f) {
  const idx = S.spec.index;
  let name = null;
  if (idx && Array.isArray(idx.series)) { const e = idx.series.find((x) => x.series === f.series); name = e ? e.file : null; }
  else if (Array.isArray(idx) && idx[0] && idx[0].files) name = idx[0].files[f.series] || null;
  if (!name) { S.contexts[f.key] = null; return null; }
  try { S.contexts[f.key] = await getJSON('data/briefs/' + name); } catch { S.contexts[f.key] = null; }
  return S.contexts[f.key];
}

/* ============================================================== workflow */
const STATE_LABEL = { new: 'New', drafting: 'Drafting', submitted: 'Awaiting approval', returned: 'Returned', approved: 'Approved', rejected: 'Rejected' };
// State is worked out from the records, never stored as "approved": a brief is approved only by
// a decision under an editor's own path, for a version whose text still matches the
// fingerprint saved with it, and saved by someone else. An approval by the person who saved
// the version counts only while the shared four-eyes setting is off and the decision says so.
const OWN = { briefs: 'b', decisions: 'd', audit: 'e' };
const ownColl = (kind, uid) => `${kind}/${uid}/${OWN[kind]}`;
const byTime = (k) => (a, b) => (a[k] < b[k] ? -1 : a[k] > b[k] ? 1 : a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
const decisionsFor = (f) => (S.decisions.get(f.docId) || []).slice().sort(byTime('decided_at'));
function approvalCheck(d) {
  const b = S.briefs.get(d.brief_id);
  if (!b || b.lead !== d.lead) return { ok: false, why: 'the approved version is missing' };
  if (!S.verified.has(b.key)) return { ok: null, why: 'checking' };
  if (S.verified.get(b.key) !== true || b.sha256 !== d.brief_sha256) return { ok: false, why: 'the brief text does not match the fingerprint that was approved' };
  if (b.author === d.author) {
    // The decision's own four_eyes field is written by the approver, so it never decides alone.
    if (S.workflow.four_eyes !== false) return { ok: false, why: 'the person who saved it also approved it, and four-eyes is on' };
    if (d.four_eyes !== false) return { ok: false, why: 'the person who saved it also approved it, with four-eyes on' };
  }
  return { ok: true, why: '' };
}
function workflowOf(f) {
  const ds = decisionsFor(f);
  let Dn = null;
  for (let i = ds.length - 1; i >= 0; i--) { if (ds[i].decision === 'approved' && approvalCheck(ds[i]).ok !== true) continue; Dn = ds[i]; break; }
  const L = S.leads.get(f.docId);
  const lAt = L && (L.status === 'drafting' || L.status === 'submitted') ? L.updated_at || '' : '';
  const dAt = Dn ? Dn.decided_at || '' : '';
  if (Dn && (Dn.decision === 'approved' || Dn.decision === 'rejected')) return { state: Dn.decision, at: dAt, by: Dn.author, decision: Dn };
  if (lAt && lAt >= dAt) return { state: L.status, at: lAt, by: L.updated_by, decision: Dn };
  if (Dn && Dn.decision === 'returned') return { state: 'returned', at: dAt, by: Dn.author, decision: Dn };
  if (Dn && Dn.decision === 'reopened') return { state: 'drafting', at: dAt, by: Dn.author, decision: Dn };
  return { state: briefsFor(f).length ? 'drafting' : 'new', at: '', by: null, decision: Dn };
}
const badApprovals = (f) => decisionsFor(f).filter((d) => d.decision === 'approved').map((d) => [d, approvalCheck(d)]).filter(([, c]) => c.ok === false);
// An approval by the person who saved the version (it counts only while four-eyes is off) is
// marked wherever the state shows, and in the evidence pack.
const onePerson = (w) => { const D = w && w.state === 'approved' ? w.decision : null; const b = D ? S.briefs.get(D.brief_id) : null; return !!(b && b.author === D.author); };
const selfChip = (w) => onePerson(w) ? h('span', { class: 'st st-self', title: 'Approved by the person who saved it, with four-eyes off' }, 'One person') : null;
const stChip = (state) => h('span', { class: 'st st-' + state }, STATE_LABEL[state] || state);
const sigTag = (f) => h('span', { class: 'sig ' + (f.status === 'lead' ? 'lead' : '') }, f.status === 'lead' ? 'Lead' : 'Watch');
function briefsFor(f) { return [...S.briefs.values()].filter((b) => b.lead === f.docId).sort(byTime('created_at')); }
// The brief a file shows: on a decided file the version its decision names, never a later save.
function currentBrief(f) {
  const w = workflowOf(f);
  if ((w.state === 'approved' || w.state === 'rejected') && w.decision) return S.briefs.get(w.decision.brief_id) || null;
  const L = S.leads.get(f.docId);
  if (L && L.brief_id) { const b = S.briefs.get(L.brief_id); if (b && b.lead === f.docId) return b; }
  const all = briefsFor(f);
  return all.length ? all[all.length - 1] : null;
}
function lastActivity(f) {
  const ev = S.audit.find((e) => e.lead === f.docId);
  return ev ? ev.at : '';
}
// The first write anyone makes registers them, so other viewers know whose records to read.
let registered = false;
async function ensureMember() {
  const id = myId();
  if (registered || !id) return;
  if (!S.memberIds.has(id)) await S.store.set('members', id, { joined_at: nowIso() });
  registered = true;
}
const newId = (prefix) => `${prefix}~${Date.now().toString(36)}~${Math.random().toString(36).slice(2, 6)}`;
async function audit(action, f, detail) {
  const ev = { at: nowIso(), lead: f ? f.docId : null, ref: f ? f.ref : null, run: S.D.summary[0].run, action, detail: detail || '' };
  if (action === 'brief_submitted') Timing.end('brief');
  const write = async () => { await ensureMember(); await S.store.add(ownColl('audit', myId()), ev); };
  try { await write(); } catch (e) {
    try { await sleep(500); await write(); } catch (e2) { banner('audit', 'bad', 'An action was saved but its audit entry was not. Note what you did and tell the owner.'); }
  }
}
const ACTION_LABEL = {
  draft_created: 'drafted a brief', draft_failed_screen: 'had a draft stopped by the screen', brief_saved: 'saved a brief',
  brief_submitted: 'submitted the brief for approval', brief_approved: 'approved the brief', brief_returned: 'returned the brief',
  brief_rejected: 'rejected the lead', reopened: 'reopened the file', check_updated: 'updated a check', assigned: 'took the file',
  unassigned: 'released the file', workflow_changed: 'changed the workflow', pack_exported: 'exported the evidence pack',
  case_outcome_proposed: 'proposed an outcome', case_outcome_approved: 'approved the outcome', case_outcome_returned: 'returned the outcome',
  case_outcome_rejected: 'rejected the outcome', case_reopened: 'reopened the case',
  triage_outcome_proposed: 'proposed an outcome for a report', triage_outcome_approved: 'approved the outcome for a report',
  triage_outcome_returned: 'returned the outcome for a report', triage_outcome_rejected: 'rejected the outcome for a report', triage_reopened: 'reopened the report',
  exporter_screened: 'screened a shipments file', exporter_exported: 'exported the exporter screen results',
  audit_exported: 'exported the audit log', lesson_proposed: 'kept a note as a lesson', lesson_not_kept: 'had a note refused as a lesson',
  lesson_approved: 'approved a lesson', lesson_rejected: 'did not keep or retired a lesson',
  task_added: 'added a follow-up', task_done: 'finished a follow-up', task_reopened: 'reopened a follow-up', task_changed: 'changed a follow-up',
  outcome_recorded: 'recorded an outcome', outcome_changed: 'changed the outcome', referral_exported: 'exported a referral pack',
  enduse_recorded: 'recorded an end-use decision record', enduse_approved: 'approved the end-use decision record',
  monitor_accepted: 'accepted a monitoring item', monitor_rejected: 'rejected a monitoring item', monitor_changed: 'changed the decision on a monitoring item',
};

/* ============================================================== routing */
const VIEWS = ['overview', 'inbox', 'tasks', 'map', 'declarations', 'reports', 'lessons', 'exporter', 'audit', 'team', 'track', 'method', 'guide', 'timings', 'monitor'];
// Records with an address of their own: a file, a synthetic case or report, a corridor, a goods code.
const RECORDS = ['file', 'case', 'report', 'corridor', 'code'];
// The inbox's queues, each named after the job it holds; each has its own address (#review and so on).
const PRESETS = { all: 'Inbox', review: 'Needs my review', returned: 'Returned to me', mine: 'Assigned to me', leads: 'Leads', watch: 'Watch items' };
const PAGE_LABEL = { overview: 'Overview', tasks: 'Follow-ups', team: 'Team and access', map: 'Corridor map', inbox: 'Inbox', declarations: 'Declarations', reports: 'Reports', lessons: 'Lessons', exporter: 'Exporter check', audit: 'Audit log', track: 'Track record', method: 'Method', guide: 'How it works', timings: 'Pilot timings', monitor: 'Monitor' };
function goList(preset) {
  S.inboxPreset = PRESETS[preset] ? preset : 'all';
  local.set('inbox_preset', S.inboxPreset);
  go('inbox');
}
function go(view, key) {
  const from = S.view;
  S.view = view; S.fileKey = view === 'file' ? key || null : null; S.caseId = view === 'case' ? key || null : null; S.reportId = view === 'report' ? key || null : null;
  S.corrKey = view === 'corridor' ? key || null : null; S.codeKey = view === 'code' ? key || null : null;
  for (const v of [...VIEWS, ...RECORDS]) $('#view-' + v).hidden = v !== view;
  if (!RECORDS.includes(view)) local.set('view', view);
  if (view !== 'file') $('#view-file').dataset.doc = '';
  if (view !== 'case') $('#view-case').dataset.doc = '';
  if (view !== 'report') $('#view-report').dataset.doc = '';
  if (view === 'file' && key) { const r = local.get('recent', []).filter((k) => k !== key); r.unshift(key); local.set('recent', r.slice(0, 5)); }
  const listToken = view === 'inbox' && S.inboxPreset && S.inboxPreset !== 'all' ? S.inboxPreset : view;
  try { history.replaceState(null, '', '#' + (RECORDS.includes(view) ? view + '-' + key : listToken)); } catch { /* history unavailable */ }
  render();
  // Back from a record restores the row it came from; anything else starts at the top.
  if (['file', 'case', 'report'].includes(from) && ['inbox', 'declarations', 'reports'].includes(view) && S.lastRow) {
    const row = document.querySelector(`#view-${view} [aria-label="Open ${S.lastRow}"]`);
    if (row) { row.focus({ preventScroll: true }); row.scrollIntoView({ block: 'center' }); return; }
  }
  window.scrollTo({ top: 0 });
}
function routeFromHash() {
  const t = (location.hash || '').slice(1);
  if (t.startsWith('file-') && S.byKey.has(t.slice(5))) return go('file', t.slice(5));
  if (/^case-SYN-CASE-\d{3}$/.test(t)) return go('case', t.slice(5));
  if (/^report-RPT-SYN-\d{3}$/.test(t)) return go('report', t.slice(7));
  if (t.startsWith('corridor-') && S.files.some((f) => f.iso2 === t.slice(9))) return go('corridor', t.slice(9));
  if (t.startsWith('code-') && S.files.some((f) => f.code === t.slice(5))) return go('code', t.slice(5));
  if (PRESETS[t] && t !== 'all') return goList(t);
  if (t === 'inbox') return goList('all');
  if (VIEWS.includes(t)) return go(t);
  const v = local.get('view', 'overview');
  if (v === 'inbox') return goList(local.get('inbox_preset', 'all'));
  go(VIEWS.includes(v) ? v : 'overview');
}

/* ============================================================== navigation (fd-core's shell) */
// Which queue a file belongs to. "Needs my review": submitted, and I may approve it (with
// four-eyes on, not one I saved). "Returned to me": returned, and I saved the version returned.
function inPreset(f, p) {
  if (p === 'all') return true;
  if (p === 'leads') return f.status === 'lead';
  if (p === 'watch') return f.status !== 'lead';
  const w = workflowOf(f);
  if (p === 'review') { if (w.state !== 'submitted' || !canApprove()) return false; const b = currentBrief(f); return !(b && b.author === myId() && S.workflow.four_eyes !== false); }
  if (p === 'returned') { if (w.state !== 'returned') return false; const b = currentBrief(f); return !!b && b.author === myId(); }
  if (p === 'mine') { const L = S.leads.get(f.docId); return !!L && L.assignee === myId(); }
  return false;
}
function filesIn(p) { return S.files.filter((f) => inPreset(f, p)); }
function navModel() {
  const n = (p) => filesIn(p).length;
  const waiting = typeof Lessons !== 'undefined' && Lessons.waitingCount ? Lessons.waitingCount() : 0;
  const item = (id, label, count, onSelect, extra) => Object.assign({ id, label, count, onSelect }, extra || {});
  return [
    { title: 'Work', items: [
      item('overview', 'Overview', null, () => go('overview'), { domId: 'tab-overview' }),
      item('all', 'Inbox', S.files.length, () => goList('all'), { domId: 'tab-inbox' }),
      item('tasks', 'Follow-ups', myOpenTasks().length || null, () => go('tasks'), { domId: 'tab-tasks' }),
      item('monitor', 'Monitor', monWaiting().length || null, () => go('monitor'), { domId: 'tab-monitor' }),
      item('review', 'Needs my review', n('review') || null, () => goList('review'), { domId: 'nav-review' }),
      item('returned', 'Returned to me', n('returned') || null, () => goList('returned'), { domId: 'nav-returned' }),
      item('mine', 'Assigned to me', n('mine') || null, () => goList('mine'), { domId: 'nav-mine' }) ] },
    { title: 'Views', items: [item('leads', 'Leads', n('leads'), () => goList('leads'), { domId: 'nav-leads' }), item('watch', 'Watch items', n('watch'), () => goList('watch'), { domId: 'nav-watch' }),
      item('map', 'Corridor map', null, () => go('map'), { domId: 'tab-map' })] },
    { title: 'Synthetic data', items: [
      item('declarations', 'Declarations', Decl.isLoaded() ? Decl.count() : null, () => go('declarations'), { domId: 'tab-declarations' }),
      item('reports', 'Reports', Triage.isLoaded() ? Triage.count() : null, () => go('reports'), { domId: 'tab-reports' }) ] },
    { title: 'Tools', items: [
      item('exporter', 'Exporter check', null, () => go('exporter'), { domId: 'tab-exporter' }),
      item('lessons', 'Lessons', waiting || null, () => go('lessons'), { domId: 'tab-lessons' }) ] },
    { title: 'Reference', items: [
      item('guide', 'How it works', null, () => go('guide'), { domId: 'tab-guide' }),
      item('track', 'Track record', null, () => go('track'), { domId: 'tab-track' }),
      item('method', 'Method', null, () => go('method'), { domId: 'tab-method' }),
      item('audit', 'Audit log', null, () => go('audit'), { domId: 'tab-audit' }),
      item('team', 'Team and access', null, () => go('team'), { domId: 'tab-team' }),
      item('timings', 'Pilot timings', null, () => go('timings'), { domId: 'tab-timings' }) ] },
  ];
}
function activeNav() {
  if (S.view === 'inbox' || S.view === 'file') return S.inboxPreset || 'all';
  if (S.view === 'case') return 'declarations';
  if (S.view === 'report') return 'reports';
  if (S.view === 'corridor' || S.view === 'code') return 'map';
  return S.view;
}
function backToList() {
  if (S.view === 'file') { S.lastRow = S.fileKey ? (S.byKey.get(S.fileKey) || {}).ref : null; return goList(S.inboxPreset || 'all'); }
  if (S.view === 'case') { S.lastRow = S.caseId; return go('declarations'); }
  if (S.view === 'report') { S.lastRow = S.reportId; return go('reports'); }
  if (S.view === 'corridor' || S.view === 'code') return go('map');
}
function crumbsModel() {
  const list = { label: PRESETS[S.inboxPreset || 'all'], onSelect: () => goList(S.inboxPreset || 'all') };
  if (S.view === 'inbox') return S.inboxPreset && S.inboxPreset !== 'all' ? [{ label: 'Inbox', onSelect: () => goList('all') }, { label: PRESETS[S.inboxPreset] }] : [{ label: 'Inbox' }];
  if (S.view === 'file') {
    const f = S.byKey.get(S.fileKey);
    return f ? [list, { label: f.country, onSelect: () => go('corridor', f.iso2) }, { label: `HS ${fmtCode(f.code)}` }] : [list, { label: 'File' }];
  }
  if (S.view === 'corridor') { const f = S.files.find((x) => x.iso2 === S.corrKey); return [{ label: 'Corridor map', onSelect: () => go('map') }, { label: f ? f.country : S.corrKey }]; }
  if (S.view === 'code') return [{ label: 'Corridor map', onSelect: () => go('map') }, { label: `HS ${fmtCode(S.codeKey)}` }];
  if (S.view === 'case') return [{ label: 'Declarations', onSelect: () => go('declarations') }, { label: S.caseId || 'Case' }];
  if (S.view === 'report') return [{ label: 'Reports', onSelect: () => go('reports') }, { label: S.reportId || 'Report' }];
  return [{ label: PAGE_LABEL[S.view] || S.view }];
}
// The next or previous record in the list it was opened from.
function stepRecord(delta) {
  if (S.view === 'file') {
    const list = orderedFiles(S.inboxPreset || 'all'), i = list.findIndex((f) => f.key === S.fileKey);
    if (i >= 0 && list[i + delta]) go('file', list[i + delta].key);
  } else if (S.view === 'case') { const ids = Decl.ids(), i = ids.indexOf(S.caseId); if (i >= 0 && ids[i + delta]) go('case', ids[i + delta]); }
  else if (S.view === 'report') { const ids = Triage.ids(), i = ids.indexOf(S.reportId); if (i >= 0 && ids[i + delta]) go('report', ids[i + delta]); }
}
function searchModel(q) {
  const items = [];
  const page = (label, run, keywords) => items.push({ group: 'Go to', label, run, keywords });
  for (const [k, label] of Object.entries(PRESETS)) page(label, () => goList(k), k === 'all' ? 'inbox queue files' : 'inbox queue');
  for (const v of VIEWS.filter((x) => x !== 'inbox')) page(PAGE_LABEL[v], () => go(v));
  const recent = local.get('recent', []).map((k) => S.byKey.get(k)).filter(Boolean);
  if (!String(q || '').trim()) {
    const out = [];
    if (recent.length) out.push({ group: 'Recent files', items: recent.map((f) => ({ group: 'Recent files', label: `${f.country} · HS ${fmtCode(f.code)}`, sub: f.ref, hint: f.status === 'lead' ? 'Lead' : 'Watch', run: () => go('file', f.key) })) });
    out.push({ group: 'Go to', items: items.filter((x) => x.group === 'Go to').slice(0, 8) });
    return out;
  }
  for (const f of S.files) {
    const w = workflowOf(f);
    items.push({ group: 'Lead files', label: `${f.country} · HS ${fmtCode(f.code)}`, sub: `${f.ref} · ${STATE_LABEL[w.state] || w.state}`, hint: f.status === 'lead' ? 'Lead' : 'Watch',
      keywords: [f.iso2, f.code, f.description, f.ref].join(' '), run: () => go('file', f.key) });
  }
  for (const x of Decl.searchItems()) items.push(Object.assign({ group: 'Declaration cases' }, x));
  for (const x of Triage.searchItems()) items.push(Object.assign({ group: 'Reports' }, x));
  {
    const seen = new Set();
    for (const f of S.files) {
      if (!seen.has('c' + f.iso2)) { seen.add('c' + f.iso2); items.push({ group: 'Corridors and codes', label: `${f.country}: every file shown`, hint: 'Corridor', keywords: f.iso2, run: () => go('corridor', f.iso2) }); }
      if (!seen.has('h' + f.code)) { seen.add('h' + f.code); items.push({ group: 'Corridors and codes', label: `HS ${fmtCode(f.code)}: every corridor shown`, sub: f.description, hint: 'Code', keywords: f.code, run: () => go('code', f.code) }); }
    }
    for (const t of [...S.tasks.entries()].map(([id, d]) => Object.assign({ id }, d)).filter((t) => !t.done)) {
      const f = S.files.find((x) => x.docId === t.lead);
      if (f) items.push({ group: 'Follow-ups', label: t.text, sub: `${f.country} · HS ${fmtCode(f.code)}${t.due ? ' · due ' + dayLabel(t.due) : ''}`, hint: 'Follow-up', keywords: f.ref, run: () => go('file', f.key) });
    }
  }
  if (S.view === 'file') {
    const f = S.byKey.get(S.fileKey);
    if (f) {
      items.push({ group: 'This file', label: 'Back to the list', hint: 'Esc', run: () => backToList() });
      if (canWrite()) { const L = S.leads.get(f.docId); const mine = L && L.assignee === myId(); items.push({ group: 'This file', label: mine ? 'Release the file' : 'Take the file', run: () => assign(f, mine ? null : myId()) }); }
    }
  }
  return window.FdShell ? FdShell.pick(q, items, 6) : [];
}
const SHORTCUTS = [
  { keys: ['g', 'o'], label: 'Go to the overview', run: () => go('overview') },
  { keys: ['g', 'i'], label: 'Go to the inbox', run: () => goList('all') },
  { keys: ['g', 'f'], label: 'Go to your follow-ups', run: () => go('tasks') },
  { keys: ['g', 'c'], label: 'Go to the corridor map', run: () => go('map') },
  { keys: ['g', 'r'], label: 'Go to Needs my review', run: () => goList('review') },
  { keys: ['g', 'd'], label: 'Go to Declarations', run: () => go('declarations') },
  { keys: ['g', 'p'], label: 'Go to Reports', run: () => go('reports') },
  { keys: ['g', 'l'], label: 'Go to Lessons', run: () => go('lessons') },
  { keys: ['g', 'e'], label: 'Go to the exporter check', run: () => go('exporter') },
  { keys: ['g', 'a'], label: 'Go to the audit log', run: () => go('audit') },
  { keys: ['g', 'm'], label: 'Go to Method', run: () => go('method') },
  { keys: ['g', 'w'], label: 'Go to How it works', run: () => go('guide') },
];
function mountShell() {
  if (!window.FdShell || S.shell) return;
  S.shell = FdShell.mountShell({
    brand: { title: 'Diversion Radar', sub: 'Analyst workspace', mark: true },
    // The hosted version's sign-in bar (app/src/hosted.js), when there is one, goes under the top bar.
    move: [document.querySelector('.hs-bar'), $('#banners'), $('#main'), $('#page-foot')],
    topRight: $('#chips'), footer: $('#who-slot'),
    nav: navModel, active: activeNav, crumbs: crumbsModel, search: searchModel, shortcuts: SHORTCUTS,
    findLabel: 'Search files, cases and pages', findPlaceholder: 'A country, a goods code, an id or a page',
    emptyHint: 'Try a country, a goods code, an id or a page name.',
    rows: '.view:not([hidden]) button.qrow', step: stepRecord, back: () => { if (RECORDS.includes(S.view)) backToList(); },
  });
}

/* ============================================================== render loop */
let queued = false;
function refresh() { if (queued) return; queued = true; requestAnimationFrame(() => { queued = false; render(); }); }
function render() {
  // A redraw replaces the rows; keep the keyboard's place across it (a row, by its label), as a
  // late load such as the reports' count can redraw a list while someone moves through it.
  const was = document.activeElement;
  const label = was && was !== document.body && was.closest && was.closest('#main') ? was.getAttribute('aria-label') : null;
  drawView();
  if (label && !was.isConnected) {
    const again = document.querySelector(`#main [aria-label="${label.replace(/["\\]/g, '\\$&')}"]`);
    if (again) again.focus({ preventScroll: true });
  }
}
function drawView() {
  if (S.shell) S.shell.update();
  drawChips();
  if (!S.files.length) return;
  if (S.view === 'overview') drawOverview();
  else if (S.view === 'tasks') drawTasks();
  else if (S.view === 'team') drawTeam();
  else if (S.view === 'corridor') drawCorridor();
  else if (S.view === 'code') drawCode();
  else if (S.view === 'map') drawMap();
  else if (S.view === 'inbox') drawInbox();
  else if (S.view === 'file') drawFile();
  else if (S.view === 'declarations') Decl.drawList();
  else if (S.view === 'case') Decl.drawCase();
  else if (S.view === 'reports') Triage.drawList();
  else if (S.view === 'report') Triage.drawReport();
  else if (S.view === 'lessons') Lessons.draw();
  else if (S.view === 'exporter') drawExporter();
  else if (S.view === 'audit') drawAudit();
  else if (S.view === 'track') drawTrack();
  else if (S.view === 'method') drawMethod();
  else if (S.view === 'guide') drawGuide();
  else if (S.view === 'timings') drawTimings();
  else if (S.view === 'monitor') drawMonitor();
}
function drawChips() {
  const s = S.D.summary && S.D.summary[0];
  if (s) $('#run-chip').textContent = `${s.run_label} run · HMRC data to ${s.uk_data_to}`;
  const sc = $('#store-chip');
  sc.className = 'chip ' + (S.storeState === 'live' ? 'live' : S.storeState === 'demo' ? 'demo' : '');
  swap(sc, h('span', { class: 'dot' }), S.storeState === 'live' ? 'Shared store' : S.storeState === 'demo' ? 'Demo mode' : 'Connecting…');
  const wc = $('#who-chip');
  if (S.storeState === 'connecting') { wc.hidden = true; return; }
  wc.hidden = false;
  if (isDemo()) {
    const p = DEMO_PEOPLE[demoMe()];
    swap(wc, h('span', { class: 'who-av', 'aria-hidden': 'true' }, p.initials), h('span', { class: 'who-t' }, h('b', null, p.name), h('span', null, p.role)),
      h('button', { class: 'btn quiet small who-switch', onclick: () => showPortal() }, 'Switch user'));
    return;
  }
  const role = S.me.role;
  swap(wc, S.me.avatar ? h('img', { src: S.me.avatar, alt: '' }) : null, (S.me.name || 'You') + (role ? ' · ' + role : ''),
    !HOSTED && S.storeState === 'live' ? h('button', { class: 'btn quiet small who-switch', title: 'Try each role in this tab, on a store of its own', onclick: () => enterDemo() }, 'Try the demo roles') : null);
}

/* ============================================================== inbox */
// The inbox groups files by the job they need, in this order; a file sits in the first group it fits.
const JOBS = [
  ['review', 'Needs my review', (f) => inPreset(f, 'review')],
  ['returned', 'Returned to me', (f) => inPreset(f, 'returned')],
  ['awaiting', 'Awaiting approval', (f, w) => w.state === 'submitted'],
  ['progress', 'In progress', (f, w) => ['drafting', 'returned'].includes(w.state)],
  ['new-leads', 'Leads with no brief yet', (f, w) => w.state === 'new' && f.status === 'lead'],
  ['new-watch', 'Watch items with no brief yet', (f, w) => w.state === 'new' && f.status !== 'lead'],
  ['decided', 'Decided', (f, w) => ['approved', 'rejected'].includes(w.state)],
];
function inboxGroups(preset) {
  const files = filesIn(preset);
  if (preset !== 'all') return [[preset, PRESETS[preset], files]];
  const out = JOBS.map(([id, label]) => [id, label, []]);
  for (const f of files) {
    const w = workflowOf(f);
    const k = JOBS.findIndex(([, , test]) => test(f, w));
    out[k < 0 ? out.length - 1 : k][2].push(f);
  }
  return out.filter((g) => g[2].length);
}
const orderedFiles = (preset) => inboxGroups(preset).flatMap((g) => g[2]);
const PRESET_LEDE = {
  review: 'Files submitted for approval that you can approve: with four-eyes on, not those you saved yourself.',
  returned: 'Briefs you saved that an editor sent back with a note. The next draft answers each note.',
  mine: 'Files you have taken. Release one when you stop working on it.',
  leads: 'Files where both signals rose: UK exports to the corridor, and the corridor’s exports of the same goods to Russia.',
  watch: 'Files where UK exports rose but the onward check did not pass.',
};
const PRESET_EMPTY = {
  review: 'Nothing needs your review. Files others submit for approval appear here.',
  returned: 'Nothing has been returned to you.',
  mine: 'You have not taken a file. Open one and choose Take the file.',
  leads: 'No leads at this run.', watch: 'No watch items at this run.',
};
function fileRow(f, ids) {
  const w = workflowOf(f);
  const L = S.leads.get(f.docId);
  const assignee = L && L.assignee;
  if (assignee) ids.push(assignee);
  const last = lastActivity(f);
  return h('button', { class: 'qrow', onclick: () => { S.lastRow = f.ref; go('file', f.key); }, 'aria-label': `Open ${f.ref}` },
    h('div', { class: 'q-cell q-main' },
      h('span', { class: 'q-ref' }, f.ref),
      h('span', { class: 'q-title' }, `${f.country} · ${fmtCode(f.code)}`),
      h('span', { class: 'q-desc' }, f.description)),
    h('div', { class: 'q-cell' }, h('div', { class: 'q-st' }, sigTag(f), stChip(w.state), selfChip(w))),
    h('div', { class: 'q-cell' }, h('span', { class: 'big' }, gbp(f.uk_trailing12_gbp), ' ', deltaChip(f, true)), h('span', { class: 'muted' }, `UK, 12 months · ${ratio(f.uk_ratio)}`)),
    h('div', { class: 'q-cell' }, h('span', { class: 'big' }, f.status === 'lead' ? ratio(f.onward_ratio, f.onward_baseline_zero) : 'Not passed'),
      h('span', { class: 'muted' }, f.status === 'lead' ? `Onward · ${f.onward_check}` : 'Onward check')),
    h('div', { class: 'q-cell' }, assignee ? whoLine(assignee) : h('span', { class: 'muted' }, 'Unassigned'), h('span', { class: 'muted' }, last ? 'Last activity ' + stamp(last) : 'No activity yet')));
}
function drawInbox() {
  const v = $('#view-inbox');
  const s = S.D.summary[0];
  const preset = S.inboxPreset || 'all';
  const ids = [];
  const groups = inboxGroups(preset);
  const total = groups.reduce((n, g) => n + g[2].length, 0);
  const body = [];
  for (const [id, label, files] of groups) {
    if (preset === 'all') body.push(h('div', { class: 'qgroup', role: 'presentation', 'data-group': id }, h('span', null, label), h('span', { class: 'count' }, String(files.length))));
    for (const f of files) body.push(fileRow(f, ids));
  }
  resolvePeople(ids);
  const head = preset === 'all'
    ? h('div', { class: 'head' },
      h('h1', { class: 'h1' }, `${s.run_label} run`),
      h('p', { class: 'lede' }, `HMRC data to ${s.uk_data_to}: ${s.leads} leads and ${s.watch} watch items among ${s.series} series (${s.corridors} corridors × ${s.codes} goods codes). ${s.leads_shown} leads and ${s.watch_shown} watch items are files you can work here; the other ${s.leads_held + s.watch_held} are held back by the display rule: counted, never shown by corridor or code.`),
      h('p', { class: 'house' }, 'A rise in exports is a lead, not evidence of a breach. Nothing here names an exporter, and a lead never means a UK party was involved.'))
    : h('div', { class: 'head' },
      h('div', { class: 'head-row' }, h('h1', { class: 'h1' }, PRESETS[preset]),
        h('button', { class: 'filter-chip', onclick: () => goList('all'), 'aria-label': `Clear: show the whole inbox` }, `${PRESETS[preset]} ×`),
        h('span', { class: 'muted small' }, `${total} of ${S.files.length} files`)),
      h('p', { class: 'lede' }, PRESET_LEDE[preset] || ''));
  swap(v,
    head,
    h('div', { class: 'queue', role: 'list' },
      h('div', { class: 'qrow qhead', role: 'presentation' }, h('span', null, 'File'), h('span', null, 'Signal and status'), h('span', null, 'UK exports'), h('span', null, 'Corridor to Russia'), h('span', null, 'Owner and activity')),
      body.length ? body : h('div', { class: 'empty' }, h('p', null, PRESET_EMPTY[preset] || 'No files in this view.'), preset !== 'all' ? h('button', { class: 'btn small', onclick: () => goList('all') }, 'Show the whole inbox') : null)),
    preset === 'all' ? h('div', { class: 'held' }, `Held back: ${s.leads_held} leads and ${s.watch_held} watch items. Their UK flow over the 12 published months is under £${intGB(s.display_min_gbp)} or came in fewer than ${s.display_min_months} months, so they are counted, never shown by corridor or code [Certain]. They cannot be worked in a shared workspace.`) : null,
    h('p', { class: 'note' }, 'j and k move through the list, Enter opens a file, and ⌘K or Ctrl K searches everything. A watch item is a file where UK exports rose but the onward check did not pass. Every saved step on a file is kept in the audit log.'));
}

// A short confirmation at the foot of the screen (fd-core's shell), with an action such as Undo.
const say = (text, action) => (window.FdShell && FdShell.toast ? FdShell.toast(text, action ? { action } : {}) : null);
const DECIDED = { approved: 'Approved.', returned: 'Returned with your note.', rejected: 'Rejected.', reopened: 'Reopened.' };

/* ============================================================== since the last run
   The history the workspace holds is today's rule rerun on today's figures for each series it
   shows, run by run (radar/app_data.py), so "since the last run" compares the two latest runs
   of that rerun, not two runs as the radar made them at the time. */
// HMRC's next overseas trade release, as its release calendar gave it when read.
const NEXT_RELEASE = { date: '12 November 2026', covers: 'September 2026', source: 'uktradeinfo release calendar', read: '22 Oct 2026' };
let runsCache = null;
function lastRuns() {
  if (!runsCache) {
    const runs = [...new Set(S.D.history.map((x) => x.run))].sort();
    runsCache = { cur: runs[runs.length - 1], prev: runs[runs.length - 2] || null };
  }
  return runsCache;
}
function runDelta(f) {
  const { cur, prev } = lastRuns();
  const at = (run) => S.D.history.find((x) => x.series === f.series && x.run === run) || null;
  const now = at(cur), before = prev ? at(prev) : null;
  const shownBoth = !!(now && before && now.shown && before.shown && isNum(now.uk_trailing12_gbp) && isNum(before.uk_trailing12_gbp) && +before.uk_trailing12_gbp > 0);
  return {
    pct: shownBoth ? (+now.uk_trailing12_gbp / +before.uk_trailing12_gbp - 1) * 100 : null,
    wasLead: !!(before && before.lead), wasShown: !!(before && before.shown), isLead: f.status === 'lead',
  };
}
const pctText = (p) => (p === null ? '' : `${p >= 0 ? '+' : '−'}${Math.abs(p) >= 10 ? Math.round(Math.abs(p)) : halfUp(Math.abs(p), 1).toFixed(1)}%`);
function deltaChip(f, short) {
  const d = runDelta(f);
  if (d.pct === null) return null;
  const { prev } = lastRuns();
  const dir = d.pct > 0.5 ? 'up' : d.pct < -0.5 ? 'down' : 'flat';
  return h('span', { class: 'delta ' + dir, title: `UK exports over 12 months against the ${monthLabel(prev, true)} run, today’s rule rerun on today’s figures` },
    `${dir === 'up' ? '▲' : dir === 'down' ? '▼' : '■'} ${pctText(d.pct)}${short ? '' : ' on ' + monthLabel(prev)}`);
}
function ageText(iso) {
  const t = Date.parse(iso);
  if (isNaN(t)) return '';
  const days = Math.floor((Date.now() - t) / 86400000);
  return days <= 0 ? 'today' : days === 1 ? '1 day' : `${days} days`;
}
const openFile = (f) => () => { S.lastRow = f.ref; go('file', f.key); };

/* ============================================================== overview */
function drawOverview() {
  const v = $('#view-overview');
  // A store update while someone types in the calculator would rebuild its inputs; wait.
  if (v.contains(document.activeElement) && document.activeElement.closest('.worth-calc')) return;
  const s = S.D.summary[0];
  const { prev } = lastRuns();
  const prevName = prev ? monthLabel(prev, true) : 'previous';
  const rows = S.files.map((f) => ({ f, w: workflowOf(f), d: runDelta(f), L: S.leads.get(f.docId) }));
  const waiting = rows.filter((r) => r.w.state === 'submitted').sort((a, b) => (a.w.at < b.w.at ? -1 : 1));
  const returned = rows.filter((r) => r.w.state === 'returned');
  const unassignedLeads = rows.filter((r) => r.f.status === 'lead' && !(r.L && r.L.assignee) && !['approved', 'rejected'].includes(r.w.state));
  const newLeads = rows.filter((r) => r.d.isLead && !r.d.wasLead);
  const nowWatch = rows.filter((r) => !r.d.isLead && r.d.wasLead);
  const moves = rows.filter((r) => r.d.pct !== null).sort((a, b) => b.d.pct - a.d.pct);
  const rises = moves.filter((r) => r.d.pct > 0.5).slice(0, 5), falls = moves.filter((r) => r.d.pct < -0.5).reverse().slice(0, 3);
  const ids = [];
  const fileLine = (r, right) => {
    const a = r.L && r.L.assignee; if (a) ids.push(a);
    return h('button', { class: 'ov-row', onclick: openFile(r.f), 'aria-label': `Open ${r.f.ref}` },
      h('span', { class: 'ov-main' }, h('span', { class: 'ov-title' }, `${r.f.country} · ${fmtCode(r.f.code)}`), h('span', { class: 'ov-sub' }, r.f.description)),
      h('span', { class: 'ov-side' }, right));
  };
  const card = (title, sub, kids, foot) => h('section', { class: 'card ov-card' }, h('div', { class: 'card-head' }, h('h2', { class: 'h2' }, title), sub ? h('span', { class: 'note' }, sub) : null), kids, foot || null);
  const empty = (t) => h('p', { class: 'ov-empty' }, t);
  // Workload: each person who has taken a file or saved a brief, by the state of those files.
  const people = new Map();
  const bump = (id, k) => { if (!id) return; const x = people.get(id) || { taken: 0, drafting: 0, submitted: 0, decided: 0 }; x[k] += 1; people.set(id, x); };
  for (const r of rows) {
    if (r.L && r.L.assignee) bump(r.L.assignee, 'taken');
    const b = currentBrief(r.f);
    if (b) bump(b.author, r.w.state === 'submitted' ? 'submitted' : ['approved', 'rejected'].includes(r.w.state) ? 'decided' : 'drafting');
  }
  for (const id of people.keys()) ids.push(id);
  resolvePeople(ids);
  const tile = (lbl, val, cap, onclick, extra) => h(onclick ? 'button' : 'div', { class: 'kpi' + (onclick ? ' kpi-link' : ''), onclick: onclick || null }, h('span', { class: 'lbl' }, lbl), h('span', { class: 'val' }, val), extra || null, h('span', { class: 'cap' }, cap));
  swap(v,
    h('div', { class: 'head' },
      h('p', { class: 'eyebrow' }, `${s.run_label} run · HMRC data to ${s.uk_data_to}`),
      h('h1', { class: 'h1' }, 'Overview'),
      h('p', { class: 'lede' }, `What changed since the ${prevName} run, what is waiting for a decision, and who holds what.`)),
    Globe.el(),
    h('div', { class: 'kpis' },
      tile('Leads you can work', String(s.leads_shown), `of ${s.leads} at this run; ${s.leads_held} held back by the display rule`, () => goList('leads'),
        newLeads.length ? h('span', { class: 'delta up' }, `▲ ${newLeads.length} new since ${monthLabel(prev)}`) : h('span', { class: 'delta flat' }, `No new leads since ${monthLabel(prev)}`)),
      tile('Watch items you can work', String(s.watch_shown), `of ${s.watch}; UK rise, onward check not passed`, () => goList('watch')),
      tile('Awaiting approval', String(waiting.length), waiting.length ? `the oldest waiting ${ageText(waiting[0].w.at)}` : 'nothing waiting', waiting.length ? () => goList('review') : null),
      tile('Leads nobody has taken', String(unassignedLeads.length), unassignedLeads.length ? 'open one and take the file' : 'every open lead has an owner', () => goList('leads'))),
    h('div', { class: 'ov-grid' },
      h('div', { class: 'ov-stack' }, card('Needs a decision', waiting.length ? 'oldest first' : null, h('div', { class: 'ov-list' },
        waiting.length ? waiting.map((r) => fileLine(r, [h('span', { class: 'st st-submitted' }, 'Awaiting approval'), h('span', { class: 'ov-age' }, ageText(r.w.at))])) : empty('Nothing is waiting for approval. A brief submitted for approval appears here, oldest first.'),
        returned.map((r) => fileLine(r, [h('span', { class: 'st st-returned' }, 'Returned'), h('span', { class: 'ov-age' }, ageText(r.w.at))]))),
        h('button', { class: 'btn quiet small', onclick: () => goList('all') }, 'Open the inbox →')), outcomesCard(), worthCard()),
      card(`Since the ${prevName} run`, 'today’s rule on today’s figures', h('div', { class: 'ov-list' },
        h('h3', { class: 'h3' }, 'Status'),
        newLeads.length || nowWatch.length
          ? [newLeads.map((r) => fileLine(r, [sigTag(r.f), h('span', { class: 'ov-age' }, r.d.wasShown ? 'new lead' : 'new lead; not shown before')])),
            nowWatch.map((r) => fileLine(r, [sigTag(r.f), h('span', { class: 'ov-age' }, `a lead in ${monthLabel(prev)}`)]))]
          : empty(`No file changed between lead and watch item since the ${prevName} run.`),
        h('h3', { class: 'h3' }, 'Largest UK rises'),
        rises.length ? rises.map((r) => fileLine(r, [sigTag(r.f), deltaChip(r.f, true)])) : empty('No UK series rose.'),
        falls.length ? [h('h3', { class: 'h3' }, 'Largest UK falls'), falls.map((r) => fileLine(r, [sigTag(r.f), deltaChip(r.f, true)]))] : null),
        h('p', { class: 'note' }, 'UK exports over the 12 published months, against the same 12-month figure at the previous run. Only series the display rule lets the workspace show are compared [Certain].'))),
    h('div', { class: 'ov-grid' },
      card('Who holds what', null, people.size
        ? h('div', { class: 'scroll' }, h('table', null,
          h('thead', null, h('tr', null, h('th', null, 'Person'), h('th', { class: 'num' }, 'Files taken'), h('th', { class: 'num' }, 'Drafting'), h('th', { class: 'num' }, 'Awaiting approval'), h('th', { class: 'num' }, 'Decided'))),
          h('tbody', null, [...people.entries()].map(([id, x]) => h('tr', null, h('td', null, whoLine(id)), h('td', { class: 'num' }, String(x.taken)), h('td', { class: 'num' }, String(x.drafting)), h('td', { class: 'num' }, String(x.submitted)), h('td', { class: 'num' }, String(x.decided)))))))
        : empty('Nobody has taken a file or saved a brief yet. Open a lead and choose Take the file.')),
      card('The data', null, h('dl', { class: 'ov-dl' },
        h('dt', null, 'UK trade'), h('dd', null, `HMRC overseas trade statistics to ${s.uk_data_to}. The next release, on ${NEXT_RELEASE.date}, adds ${NEXT_RELEASE.covers} (${NEXT_RELEASE.source}, read ${NEXT_RELEASE.read}).`),
        h('dt', null, 'Onward trade'), h('dd', null, 'UN Comtrade, each year or month counted from the date it was released.'),
        h('dt', null, 'Series'), h('dd', null, `${s.series}: ${s.corridors} corridors × ${s.codes} goods codes from the Common High Priority List.`),
        h('dt', null, 'Held back'), h('dd', null, `${s.leads_held + s.watch_held} flagged series under £${intGB(s.display_min_gbp)} over 12 months or with exports in fewer than ${s.display_min_months} of them: counted, never shown by corridor or code.`)),
        h('div', { class: 'row' }, h('button', { class: 'btn small', onclick: () => go('map') }, 'Open the corridor map'), h('button', { class: 'btn quiet small', onclick: () => go('method') }, 'Method →')))),
    h('p', { class: 'house' }, 'A rise in exports is a lead, not evidence of a breach.'));
  Globe.start();
}

/* ============================================================== the monitor (phase 7)
   Items the monitoring layer filed (data/monitor.json, from monitor/items.jsonl): official notices,
   statistics releases and guidance, read from the public pages of the sources in
   spec/monitor_sources.json, with the original beside an English summary and a proposed grade on
   the six-by-six scale. A person accepts an item, setting its grade, or rejects it with a reason
   (monitor/<item>, a shared record, audited); only accepted items appear on a file. Nothing reaches
   a brief unaccepted, and drafting does not read them yet. */
const RELIABILITY = { A: 'completely reliable', B: 'usually reliable', C: 'fairly reliable', D: 'not usually reliable', E: 'unreliable', F: 'reliability cannot be judged' };
const CREDIBILITY = { 1: 'confirmed by other sources', 2: 'probably true', 3: 'possibly true', 4: 'doubtful', 5: 'improbable', 6: 'truth cannot be judged' };
const gradeWords = (g) => (/^[A-F][1-6]$/.test(String(g || '')) ? `${g}: ${RELIABILITY[g[0]]} source; ${CREDIBILITY[g[1]]}` : String(g || ''));
const GRADES = Object.keys(RELIABILITY).flatMap((r) => Object.keys(CREDIBILITY).map((c) => r + c));
const MON_REJECT = [['not_relevant', 'Not relevant to the radar’s routes or goods'], ['duplicate', 'Already held from another source'], ['unreliable', 'Not reliable enough to keep'], ['out_of_date', 'Superseded or out of date']];
const LANG_NAME = { en: 'English', tr: 'Turkish', ru: 'Russian', kk: 'Kazakh', ky: 'Kyrgyz', hy: 'Armenian', ka: 'Georgian', az: 'Azerbaijani', uz: 'Uzbek', tg: 'Tajik', zh: 'Chinese', hi: 'Hindi', he: 'Hebrew', ms: 'Malay', sr: 'Serbian', th: 'Thai', vi: 'Vietnamese', ar: 'Arabic' };
const monItems = () => (Array.isArray(S.D.monitor) ? S.D.monitor : []);
const monDec = (it) => S.monitorDec.get(it.id) || null;
const monSource = (id) => ((S.spec.monSources || []).find((s) => s.id === id) || { name: id, publisher: '' });
// The files an item touches: its corridors, narrowed to its codes or headings when it names any.
function monFiles(it) {
  const t = it.tags || {}, cors = t.corridors || [], codes = t.codes || [], heads = t.headings || [];
  if (!cors.length && !codes.length && !heads.length) return [];
  return S.files.filter((f) => (!cors.length || cors.includes(f.iso2)) && ((!codes.length && !heads.length) || codes.includes(f.code) || heads.includes(String(f.code).slice(0, 4))));
}
const monWaiting = () => monItems().filter((it) => !monDec(it));
// A copy of the workspace on the public site carries only items under an open licence; its
// manifest says how many it left off (scripts/build_site.py).
const siteLeftOff = () => { const m = S.D.manifest && S.D.manifest[0]; return (m && m.site_copy && m.site_copy.monitor_items_left_off) || 0; };
async function decideItem(it, decision, grade, reason) {
  if (!canWrite()) return;
  const doc = { item: it.id, decision, grade: decision === 'accepted' ? grade : null, reason: decision === 'rejected' ? reason : null, by: myId(), at: nowIso() };
  const prev = monDec(it);
  const words = (d) => `${d.decision} (${d.decision === 'accepted' ? d.grade : (MON_REJECT.find(([k]) => k === d.reason) || [, d.reason])[1]})`;
  try {
    await upsert('monitor', it.id, doc);
    // A second decision on an item is a change, audited with what it was and what it is now.
    await audit(prev ? 'monitor_changed' : decision === 'accepted' ? 'monitor_accepted' : 'monitor_rejected', null,
      prev ? `${it.title}: ${words(prev)} to ${words(doc)}` : `${it.title} ${words(doc)}`);
    S.monOpen = null; S.monForm = null;
    say(decision === 'accepted' ? 'Item accepted; it now shows on the files it touches.' : 'Item rejected.');
  } catch (e) { writeFailed(e, 'the decision on the item'); }
}
function monItemCard(it, opts) {
  const D = monDec(it), src = monSource(it.source), files = monFiles(it), t = it.tags || {};
  if (D) resolvePeople([D.by]);
  const open = S.monOpen === it.id, lang = String(it.language || '').split('-')[0];
  // What the person has chosen in the open form lives in S.monForm, so a redraw keeps it.
  const F = open && S.monForm && S.monForm.id === it.id ? S.monForm : null;
  const keep = (k) => (e) => { S.monForm = { ...(S.monForm && S.monForm.id === it.id ? S.monForm : { id: it.id }), [k]: e.target.value }; };
  const grade = h('select', { id: `mon-grade-${it.id}`, 'aria-label': `Grade for ${it.title}`, onchange: keep('grade') }, GRADES.map((g) => h('option', { value: g, selected: g === ((F && F.grade) || (D && D.grade) || it.grade_proposed) }, gradeWords(g))));
  const reason = h('select', { id: `mon-reason-${it.id}`, 'aria-label': `Reason for rejecting ${it.title}`, onchange: keep('reason') }, MON_REJECT.map(([k, l]) => h('option', { value: k, selected: F && F.reason === k }, l)));
  return h('article', { class: 'mon-item' + (D ? ' decided ' + D.decision : ''), id: 'mon-' + it.id },
    h('div', { class: 'mon-top' },
      h('span', { class: 'mon-src' }, src.name), h('span', { class: 'muted small' }, `published ${dayLabel(it.published)} · read ${dayLabel(String(it.retrieved_at).slice(0, 10))}${lang !== 'en' ? ` · ${LANG_NAME[lang] || lang}, translated` : ''}`),
      D ? h('span', { class: 'st ' + (D.decision === 'accepted' ? 'st-approved' : 'st-rejected') }, D.decision === 'accepted' ? 'Accepted' : 'Rejected') : h('span', { class: 'st st-submitted' }, 'Waiting')),
    h('h2', { class: 'h3 mon-title' }, it.title),
    h('p', { class: 'mon-sum' }, it.summary),
    h('div', { class: 'mon-tags' },
      (t.corridors || []).map((iso) => { const f = S.files.find((x) => x.iso2 === iso); const name = f ? f.country : ((S.D.corridors[0].corridors.find((c) => c.iso2 === iso) || {}).name || iso); return f ? h('button', { class: 'tag-chip', onclick: () => go('corridor', iso) }, name) : h('span', { class: 'tag-chip quiet' }, name); }),
      (t.codes || []).map((c) => h('button', { class: 'tag-chip', onclick: () => go('code', c) }, `HS ${fmtCode(c)}`)),
      (t.topics || []).map((x) => h('span', { class: 'tag-chip quiet' }, x.replace(/_/g, ' '))),
      h('span', { class: 'muted small' }, files.length ? `touches ${files.length} ${files.length === 1 ? 'file' : 'files'}` : 'touches no file')),
    h('div', { class: 'mon-grade' }, h('span', { class: 'muted small' }, D && D.decision === 'accepted' ? 'Grade set' : 'Proposed grade'), h('b', null, gradeWords(D && D.decision === 'accepted' ? D.grade : it.grade_proposed))),
    h('details', { class: 'given' }, h('summary', null, lang === 'en' ? 'The source’s own words' : `The original, in ${LANG_NAME[lang] || lang}`),
      h('p', { lang: it.language }, h('b', null, it.title_original)), h('blockquote', { lang: it.language, class: 'mon-quote' }, it.excerpt_original),
      lang !== 'en' ? h('p', { class: 'muted small' }, `Translated by ${it.translated_by}.`) : null,
      h('p', { class: 'muted small mono' }, `SHA-256 of the excerpt ${String(it.excerpt_sha256 || '').slice(0, 16)}…`)),
    h('p', { class: 'muted small mon-terms' }, `${src.publisher || src.name}. Terms: ${src.terms_note || 'see the source'}`),
    h('div', { class: 'row' }, h('a', { href: it.url, target: '_blank', rel: 'noopener noreferrer', class: 'small' }, 'Open the source ↗'),
      opts && opts.compact ? null : h('span', { class: 'spacer' }),
      D ? h('span', { class: 'muted small' }, `${D.decision === 'accepted' ? 'Accepted' : 'Rejected'} by ${person(D.by).name}, ${stamp(D.at)}${D.reason ? ': ' + (MON_REJECT.find(([k]) => k === D.reason) || [, D.reason])[1] : ''}`) : null,
      canWrite() && !(opts && opts.compact) ? h('button', { class: 'btn small' + (D ? ' quiet' : ' primary'), 'aria-expanded': String(open), onclick: () => { S.monOpen = open ? null : it.id; S.monForm = null; drawMonitor(); const g = document.querySelector(`#mon-${it.id} select`); if (g) g.focus(); } }, D ? (open ? 'Close' : 'Change') : (open ? 'Close' : 'Decide')) : null),
    open && canWrite() ? h('div', { class: 'mon-decide' },
      h('div', { class: 'row' }, h('label', { class: 'field' }, 'Grade', grade), h('button', { class: 'btn primary small', onclick: () => decideItem(it, 'accepted', grade.value) }, 'Accept')),
      h('div', { class: 'row' }, h('label', { class: 'field' }, 'Or reject it', reason), h('button', { class: 'btn small', onclick: () => decideItem(it, 'rejected', null, reason.value) }, 'Reject')),
      h('p', { class: 'note' }, 'Accepting puts the item on the files it touches, with the grade you set. Nothing reaches a brief unless a person writes it in.')) : null);
}
function drawMonitor() {
  const v = $('#view-monitor');
  const scope = ['waiting', 'accepted', 'rejected', 'all'].includes(S.monScope) ? S.monScope : 'waiting';
  const all = monItems();
  const pick = (k) => all.filter((it) => { const D = monDec(it); return k === 'all' || (k === 'waiting' ? !D : D && D.decision === k); });
  const list = pick(scope);
  const tab = (k, label) => h('button', { 'aria-pressed': String(scope === k), onclick: () => { S.monScope = k; drawMonitor(); } }, `${label} (${pick(k).length})`);
  const srcs = S.spec.monSources || [];
  // A redraw replaces the cards: when focus was in the view (a decided card leaves its list), it
  // goes back to the same control if it still exists, or to the list's tabs, never to the page top.
  const was = document.activeElement, hadFocus = !!(was && v.contains(was) && was !== v), wasId = hadFocus ? was.id : '';
  swap(v,
    h('div', { class: 'head' }, h('p', { class: 'eyebrow' }, 'Work'), h('h1', { class: 'h1' }, 'Monitor'),
      h('p', { class: 'lede' }, 'Official notices, statistics releases and guidance from the sources below, read from their public pages, each with the original beside an English summary and a proposed grade. Accept an item to put it on the files it touches, or reject it.')),
    h('div', { class: 'seg', role: 'group', 'aria-label': 'Which items' }, tab('waiting', 'Waiting'), tab('accepted', 'Accepted'), tab('rejected', 'Rejected'), tab('all', 'All')),
    siteLeftOff() ? h('p', { class: 'note' }, `This copy leaves off ${siteLeftOff()} ${siteLeftOff() === 1 ? 'item' : 'items'} from sources without an open licence: those serve internal monitoring only, until their publishers’ permission is recorded.`) : null,
    list.length ? h('div', { class: 'mon-list' }, list.map((it) => monItemCard(it))) : h('div', { class: 'card' }, h('p', { class: 'note' }, scope === 'waiting' ? 'Nothing is waiting. A collection run files new items here (monitor/RUNBOOK.md).' : 'No item here.')),
    section('mon-sources', 'Sources', `${srcs.length}`, h('div', { class: 'scroll' }, h('table', null,
      h('thead', null, h('tr', null, h('th', null, 'Source'), h('th', null, 'Language'), h('th', null, 'Standing grade'), h('th', null, 'Read every'), h('th', null, 'Terms'))),
      h('tbody', null, srcs.map((s) => h('tr', null, h('td', null, h('a', { href: s.url, target: '_blank', rel: 'noopener noreferrer' }, s.name), h('div', { class: 'muted small' }, s.publisher)),
        h('td', null, LANG_NAME[s.language] || s.language), h('td', null, `${s.reliability}: ${RELIABILITY[s.reliability]}`), h('td', null, `${s.cadence_days} days`),
        h('td', { class: 'small' }, h('a', { href: s.terms_url, target: '_blank', rel: 'noopener noreferrer' }, 'terms'), ' ', s.terms_note))))))),
    h('p', { class: 'note' }, 'Sources are read only through their public pages, as a person would read them: never behind a sign-in, through a VPN or under a hidden identity. Items name no person or firm; a notice that names parties is summarised by counts, countries of address and kinds of goods. The grade is the six-by-six scale: the source’s reliability (A to F) and the information’s credibility (1 to 6) [Certain].'),
    h('p', { class: 'house' }, 'An item is context for a person, never a finding. A rise in exports is a lead, not evidence of a breach.'));
  if (hadFocus && !v.contains(document.activeElement)) {
    const back = (wasId && document.getElementById(wasId)) || v.querySelector('.seg button[aria-pressed="true"]');
    if (back) back.focus();
  }
}
// The file rail's card: accepted items that touch this file, and how many wait.
function monitorCard(f) {
  const touching = monItems().filter((it) => monFiles(it).some((x) => x.docId === f.docId));
  const accepted = touching.filter((it) => { const D = monDec(it); return D && D.decision === 'accepted'; });
  const waiting = touching.filter((it) => !monDec(it)).length;
  return h('div', { class: 'rail-card', id: 'rail-monitor' },
    h('div', { class: 'rail-hrow' }, h('h2', { class: 'rail-h' }, 'Monitoring'), h('span', { class: 'muted small' }, `${accepted.length} accepted`)),
    accepted.length ? h('ul', { class: 'refs' }, accepted.map((it) => h('li', null, h('a', { href: it.url, target: '_blank', rel: 'noopener noreferrer' }, it.title),
      h('span', { class: 'muted small' }, `${monSource(it.source).name} · ${dayLabel(it.published)} · ${monDec(it).grade}`)))) : h('p', { class: 'note' }, 'No accepted item touches this file.'),
    waiting ? h('button', { class: 'btn quiet small', onclick: () => { S.monScope = 'waiting'; go('monitor'); } }, `${waiting} waiting on the Monitor page →`) : null);
}

/* ============================================================== the console globe (phase 6.5)
   The overview's hero: a globe that turns, with a sweep that lights each corridor as it passes.
   A blip is a corridor with series the display rule lets the workspace show (violet for a lead,
   pale blue for a watch item); every corridor on the scan has a small mark, whether or not
   anything is shown there, so a quiet mark says nothing about what is held back. Routes run from
   the UK to each corridor with a blip and on to Russia; the moving dots show the direction of
   trade, not shipments. The figures are the latest monthly run's: the sweep is continuous, the
   data is not. Land outlines: Natural Earth, public domain (spec/land.json). Drawn on a canvas,
   with nothing loaded from elsewhere; the corridor list beside it is the keyboard's way in. */
const PLACES = { // capitals or main cities, for placing a mark only
  GB: [-1.5, 52.6, 'United Kingdom'], RU: [37.6, 55.75, 'Russia'],
  KG: [74.6, 42.9], AM: [44.5, 40.2], KZ: [71.4, 51.2], GE: [44.8, 41.7], AE: [55.3, 25.2], TR: [32.9, 39.9], UZ: [69.2, 41.3], AZ: [49.9, 40.4],
  TJ: [68.8, 38.6], CN: [116.4, 39.9], HK: [114.2, 22.3], MO: [113.5, 22.2], IN: [77.2, 28.6], IL: [34.8, 32.1], MY: [101.7, 3.1], RS: [20.5, 44.8],
  TH: [100.5, 13.75], VN: [105.8, 21.0],
};
const Globe = (() => {
  const RAD = Math.PI / 180;
  const C = { ground: '#0b1830', sphere: '#10264a', sphereEdge: '#1a3a6b', grid: 'rgba(143,180,239,0.16)', land: 'rgba(143,180,239,0.20)', landLine: 'rgba(171,200,245,0.55)',
    corridor: 'rgba(167,139,250,0.20)', home: 'rgba(143,180,239,0.34)', bezel: 'rgba(171,200,245,0.55)', bezelText: 'rgba(201,214,234,0.85)',
    lead: '#a78bfa', watch: '#9cc3f0', quiet: 'rgba(201,214,234,0.55)', uk: '#8fb4ef', onward: '#a78bfa', sweep: '167,139,250', ping: '#f2c66d' };
  let el = null, cv = null, ctx2 = null, bez = null, size = 0, dpr = 1;
  let lon0 = -20, lat0 = 32, spin = true, dragging = null, resumeAt = 0, sweep = 0, last = 0, running = false, target = null;
  let land = null, blips = [], routes = [], hover = null, selected = null, hits = new Map();
  const reduced = (() => { try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch { return false; } })();
  let paused = reduced;
  const unit = (lon, lat) => { const l = lon * RAD, p = lat * RAD; return [Math.cos(p) * Math.sin(l), Math.sin(p), Math.cos(p) * Math.cos(l)]; };
  // Orthographic view centred on (lon0, lat0): [x, y, z], z > 0 on the near side.
  function project(v, r) {
    const l = lon0 * RAD, p = lat0 * RAD;
    const x1 = v[0] * Math.cos(l) - v[2] * Math.sin(l), z1 = v[0] * Math.sin(l) + v[2] * Math.cos(l);
    const y2 = v[1] * Math.cos(p) - z1 * Math.sin(p), z2 = v[1] * Math.sin(p) + z1 * Math.cos(p);
    return [x1 * r, y2 * r, z2];
  }
  const P = (lon, lat, r) => project(unit(lon, lat), r);
  function slerp(a, b, t) {
    const d = Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2])), w = Math.acos(d);
    if (w < 1e-6) return a;
    const s = Math.sin(w), ka = Math.sin((1 - t) * w) / s, kb = Math.sin(t * w) / s;
    return [a[0] * ka + b[0] * kb, a[1] * ka + b[1] * kb, a[2] * ka + b[2] * kb];
  }
  function model() {
    const names = new Map(((S.D.corridors && S.D.corridors[0] && S.D.corridors[0].corridors) || []).map((c) => [c.iso2, c.name]));
    const by = new Map();
    for (const f of S.files) {
      const b = by.get(f.iso2) || { iso2: f.iso2, name: f.country, leads: 0, watch: 0 };
      if (f.status === 'lead') b.leads++; else b.watch++;
      by.set(f.iso2, b);
    }
    blips = [...names.entries()].filter(([iso]) => PLACES[iso]).map(([iso, name]) => Object.assign({ iso2: iso, name, leads: 0, watch: 0 }, by.get(iso) || {}, { lon: PLACES[iso][0], lat: PLACES[iso][1] }));
    const uk = unit(...PLACES.GB.slice(0, 2)), ru = unit(...PLACES.RU.slice(0, 2));
    routes = [];
    for (const b of blips.filter((x) => x.leads || x.watch)) {
      const c = unit(b.lon, b.lat);
      routes.push({ a: uk, b: c, kind: 'uk', lead: b.leads > 0, iso2: b.iso2 });
      routes.push({ a: c, b: ru, kind: 'onward', lead: b.leads > 0, iso2: b.iso2 });
    }
  }
  function resize() {
    if (!cv) return;
    const w = Math.round(cv.parentElement.getBoundingClientRect().width);
    if (!w || w === size) return;
    size = w; dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = Math.round(size * dpr); cv.height = Math.round(size * dpr);
    cv.style.height = size + 'px';
    drawBezel();
  }
  // The bezel is drawn once per size: a ring with a tick every 2 degrees and a bearing every 10.
  function drawBezel() {
    bez = document.createElement('canvas'); bez.width = cv.width; bez.height = cv.height;
    const g = bez.getContext('2d'); g.scale(dpr, dpr);
    const c = size / 2, Rb = size * 0.43;
    g.strokeStyle = C.bezel; g.lineWidth = 1;
    g.beginPath(); g.arc(c, c, Rb, 0, 2 * Math.PI); g.stroke();
    g.beginPath(); g.arc(c, c, Rb * 0.93, 0, 2 * Math.PI); g.globalAlpha = 0.5; g.stroke(); g.globalAlpha = 1;
    g.font = `${Math.max(9, size * 0.019)}px Aldrich, "IBM Plex Mono", monospace`; g.fillStyle = C.bezelText; g.textAlign = 'center'; g.textBaseline = 'middle';
    for (let d = 0; d < 360; d += 2) {
      const a = (d - 90) * RAD, long = d % 10 === 0, r1 = Rb, r2 = Rb - (long ? size * 0.022 : size * 0.011);
      g.beginPath(); g.moveTo(c + Math.cos(a) * r1, c + Math.sin(a) * r1); g.lineTo(c + Math.cos(a) * r2, c + Math.sin(a) * r2); g.stroke();
      if (long && size > 300) g.fillText(String(d).padStart(3, '0'), c + Math.cos(a) * (Rb + size * 0.022), c + Math.sin(a) * (Rb + size * 0.022));
    }
  }
  function ringPath(g, ring, c, R) {
    let first = true;
    for (let i = 0; i < ring.length; i += 2) {
      let [x, y, z] = P(ring[i] / 10, ring[i + 1] / 10, R);
      if (z < 0) { const k = R / (Math.hypot(x, y) || 1); x *= k; y *= k; } // hidden points sit on the rim, so a fill still closes
      if (first) { g.moveTo(c + x, c - y); first = false; } else g.lineTo(c + x, c - y);
    }
    g.closePath();
  }
  function linePath(g, pts, c, alt) {
    let pen = false;
    for (const v of pts) {
      const [x, y, z] = project(v, alt);
      if (z < 0.02) { pen = false; continue; }
      if (!pen) { g.moveTo(c + x, c - y); pen = true; } else g.lineTo(c + x, c - y);
    }
  }
  const bearing = (x, y) => (Math.atan2(x, y) / RAD + 360) % 360; // clockwise from the top, y up
  function frame(t) {
    if (!el || !el.isConnected || document.hidden || el.closest('.view').hidden) { running = false; return; }
    const dt = last ? Math.min(0.1, (t - last) / 1000) : 0; last = t;
    resize();
    if (!size) { requestAnimationFrame(frame); return; }
    const prev = sweep;
    if (!paused) {
      sweep = (sweep + dt * 72) % 360; // one turn of the sweep every 5 seconds
      if (target) {
        const k = Math.min(1, dt * 4);
        let dl = ((target[0] - lon0 + 540) % 360) - 180;
        lon0 += dl * k; lat0 += (target[1] - lat0) * k;
        if (Math.abs(dl) < 0.3 && Math.abs(target[1] - lat0) < 0.3) target = null;
      } else if (spin && !dragging && t >= resumeAt) lon0 = (lon0 - dt * 6 + 540) % 360 - 180; // a turn every minute, west to east as the Earth turns
    }
    const g = ctx2, c = size / 2, R = size * 0.335, Rb = size * 0.43;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, size, size);
    // the sweep: a fading wedge behind its leading edge
    if (g.createConicGradient) {
      const cg = g.createConicGradient((sweep - 90) * RAD - 1.1, c, c);
      cg.addColorStop(0, `rgba(${C.sweep},0)`); cg.addColorStop(0.175, `rgba(${C.sweep},0.20)`); cg.addColorStop(0.176, `rgba(${C.sweep},0)`); cg.addColorStop(1, `rgba(${C.sweep},0)`);
      g.fillStyle = cg; g.beginPath(); g.arc(c, c, Rb * 0.93, 0, 2 * Math.PI); g.fill();
    }
    // the sphere
    const sg = g.createRadialGradient(c - R * 0.3, c - R * 0.35, R * 0.1, c, c, R);
    sg.addColorStop(0, C.sphereEdge); sg.addColorStop(1, C.sphere);
    g.fillStyle = sg; g.beginPath(); g.arc(c, c, R, 0, 2 * Math.PI); g.fill();
    g.save(); g.beginPath(); g.arc(c, c, R, 0, 2 * Math.PI); g.clip();
    // graticule every 15 degrees
    g.strokeStyle = C.grid; g.lineWidth = 0.8; g.beginPath();
    for (let lon = -180; lon < 180; lon += 15) { const pts = []; for (let lat = -90; lat <= 90; lat += 5) pts.push(unit(lon, lat)); linePath(g, pts, c, R); }
    for (let lat = -75; lat <= 75; lat += 15) { const pts = []; for (let lon = -180; lon <= 180; lon += 5) pts.push(unit(lon, lat)); linePath(g, pts, c, R); }
    g.stroke();
    if (land) {
      g.beginPath(); for (const r of land.land) ringPath(g, r, c, R);
      g.fillStyle = C.land; g.fill('evenodd'); g.strokeStyle = C.landLine; g.lineWidth = 0.6; g.stroke();
      for (const [iso, rings] of Object.entries(land.countries || {})) {
        const b = blips.find((x) => x.iso2 === iso), home = iso === 'GB' || iso === 'RU';
        if (!home && !(b && (b.leads || b.watch))) continue;
        g.beginPath(); for (const r of rings) ringPath(g, r, c, R);
        g.fillStyle = home ? C.home : C.corridor; g.fill('evenodd');
      }
    }
    g.restore();
    // routes, lifted off the surface, with dots moving from the UK to the corridor and on to Russia
    const ts = t / 1000;
    for (const rt of routes) {
      const dim = selected && rt.iso2 !== selected;
      const pts = []; for (let i = 0; i <= 40; i++) { const k = i / 40, v = slerp(rt.a, rt.b, k), lift = 1 + 0.10 * Math.sin(Math.PI * k); pts.push([v[0] * lift, v[1] * lift, v[2] * lift]); }
      g.beginPath(); linePath(g, pts, c, R);
      g.strokeStyle = rt.kind === 'uk' ? C.uk : C.onward; g.globalAlpha = dim ? 0.12 : rt.kind === 'uk' ? 0.55 : rt.lead ? 0.75 : 0.35; g.lineWidth = rt.lead ? 1.4 : 1; g.stroke();
      g.globalAlpha = dim ? 0.15 : 1;
      for (let j = 0; j < 3; j++) {
        const k = paused ? (j + 0.5) / 3 : ((ts * 0.22 + j / 3 + (rt.kind === 'onward' ? 0.5 : 0)) % 1);
        const v = pts[Math.round(k * 40)], [x, y, z] = project(v, R);
        if (z < 0.02) continue;
        g.fillStyle = rt.kind === 'uk' ? C.uk : C.onward; g.beginPath(); g.arc(c + x, c - y, 1.8, 0, 2 * Math.PI); g.fill();
      }
      g.globalAlpha = 1;
    }
    // the UK and Russia
    for (const iso of ['GB', 'RU']) {
      const [x, y, z] = P(PLACES[iso][0], PLACES[iso][1], R);
      if (z < 0.02) continue;
      g.strokeStyle = C.uk; g.lineWidth = 1.2; g.beginPath(); g.rect(c + x - 4, c - y - 4, 8, 8); g.stroke();
      g.fillStyle = C.bezelText; g.font = `${Math.max(9, size * 0.018)}px Aldrich, "IBM Plex Mono", monospace`; g.textAlign = 'left'; g.textBaseline = 'middle';
      g.fillText(iso === 'GB' ? 'UK' : 'RUSSIA', c + x + 8, c - y);
    }
    // blips: lit as the sweep passes, then fading; a name is written only where it overlaps no other
    const taken = [];
    const free = (x, y, w, hh) => !taken.some((q) => x < q[0] + q[2] && x + w > q[0] && y < q[1] + q[3] && y + hh > q[1]);
    const order = blips.slice().sort((p, q) => ((q.iso2 === selected) - (p.iso2 === selected)) || ((hover && q === hover) - (hover && p === hover)));
    for (const b of order) {
      const [x, y, z] = P(b.lon, b.lat, R);
      b.sx = c + x; b.sy = c - y; b.front = z > 0.02;
      if (!b.front) continue;
      const br = bearing(x, y);
      const crossed = prev <= sweep ? br > prev && br <= sweep : br > prev || br <= sweep;
      if (crossed && !paused) hits.set(b.iso2, t);
      const age = (t - (hits.get(b.iso2) || -1e9)) / 1000, glow = Math.max(0, 1 - age / 2.6);
      const col = b.leads ? C.lead : b.watch ? C.watch : C.quiet, n = b.leads + b.watch;
      const base = n ? 3 + Math.min(4, n) : 1.8, isSel = selected === b.iso2 || (hover && hover.iso2 === b.iso2);
      if (n && glow > 0) { g.fillStyle = col; g.globalAlpha = 0.35 * glow; g.beginPath(); g.arc(b.sx, b.sy, base + 10 * glow, 0, 2 * Math.PI); g.fill(); g.globalAlpha = 1; }
      g.fillStyle = col; g.globalAlpha = n ? 0.55 + 0.45 * Math.max(glow, isSel ? 1 : 0) : 0.7; g.beginPath(); g.arc(b.sx, b.sy, base, 0, 2 * Math.PI); g.fill(); g.globalAlpha = 1;
      if (isSel) { g.strokeStyle = col; g.lineWidth = 1.2; g.beginPath(); g.arc(b.sx, b.sy, base + 5, 0, 2 * Math.PI); g.stroke(); }
      if (isSel || (n && glow > 0.6 && size > 420)) {
        const fs = Math.max(9, size * 0.019), label = b.name.toUpperCase();
        g.font = `${fs}px Aldrich, "IBM Plex Mono", monospace`;
        const w = g.measureText(label).width, lx = b.sx + base + 4, ly = b.sy - 2 - fs;
        if (isSel || free(lx, ly, w, fs + 2)) {
          taken.push([lx, ly, w, fs + 2]);
          g.fillStyle = '#e8eef8'; g.textAlign = 'left'; g.textBaseline = 'bottom'; g.fillText(label, lx, b.sy - 2);
        }
      }
    }
    // the sweep's leading edge and the bezel
    const a = (sweep - 90) * RAD;
    g.strokeStyle = `rgba(${C.sweep},0.9)`; g.lineWidth = 1.2; g.beginPath(); g.moveTo(c, c); g.lineTo(c + Math.cos(a) * Rb * 0.93, c + Math.sin(a) * Rb * 0.93); g.stroke();
    if (bez) { g.setTransform(1, 0, 0, 1, 0, 0); g.drawImage(bez, 0, 0); g.setTransform(dpr, 0, 0, dpr, 0, 0); }
    // corridors with an item waiting on the monitor: a ring that pulses
    const waitIso = new Set(monWaiting().flatMap((it) => (it.tags && it.tags.corridors) || []));
    for (const b of blips) {
      if (!b.front || !waitIso.has(b.iso2)) continue;
      const ph = paused ? 0.5 : (ts * 0.8) % 1;
      g.strokeStyle = C.ping; g.globalAlpha = 0.9 * (1 - ph); g.lineWidth = 1.4;
      g.beginPath(); g.arc(b.sx, b.sy, 6 + 14 * ph, 0, 2 * Math.PI); g.stroke(); g.globalAlpha = 1;
    }
    readout();
    requestAnimationFrame(frame);
  }
  function readout() {
    const r = el && el.querySelector('#gl-bearing'); if (r) r.textContent = String(Math.round(sweep)).padStart(3, '0') + '°';
    const mw = el && el.querySelector('#gl-mon'); if (mw) { const n = String(monWaiting().length); if (mw.textContent !== n) mw.textContent = n; }
    const ml = el && el.querySelector('#gl-monlist');
    if (ml) {
      const names = [...new Set(monWaiting().flatMap((it) => (it.tags && it.tags.corridors) || []))].map((iso) => (blips.find((b) => b.iso2 === iso) || { name: iso }).name).sort();
      const txt = names.length ? `Items wait on the monitor for ${names.join(', ')}; their marks pulse on the near side of the globe.` : '';
      if (ml.textContent !== txt) ml.textContent = txt;
    }
    const l = el && el.querySelector('#gl-lon'); if (l) { const v = Math.round(lon0); l.textContent = `${Math.abs(v)}°${v < 0 ? 'W' : 'E'}`; }
  }
  function pick(e) {
    const box = cv.getBoundingClientRect(), x = e.clientX - box.left, y = e.clientY - box.top;
    let best = null, bd = 16;
    for (const b of blips) { if (!b.front) continue; const d = Math.hypot(b.sx - x, b.sy - y); if (d < bd) { bd = d; best = b; } }
    return best;
  }
  function select(iso, turn) {
    selected = iso;
    const b = blips.find((x) => x.iso2 === iso);
    if (b && turn) {
      const to = [b.lon, Math.max(-20, Math.min(55, b.lat))];
      // Turning is motion: while paused the globe jumps there instead.
      if (paused) { lon0 = to[0]; lat0 = to[1]; target = null; } else { target = to; resumeAt = performance.now() + 6000; }
    }
    showSelection();
  }
  function showSelection() {
    const box = el.querySelector('#gl-sel'); if (!box) return;
    const b = blips.find((x) => x.iso2 === selected);
    for (const btn of el.querySelectorAll('.gl-list button')) btn.setAttribute('aria-pressed', String(btn.dataset.iso === selected));
    if (!b) { box.replaceChildren(h('span', { class: 'gl-k' }, 'Selected'), h('span', { class: 'gl-dim' }, 'Click a blip or a corridor.')); return; }
    box.replaceChildren(h('span', { class: 'gl-k' }, 'Selected'), h('b', null, b.name.toUpperCase()),
      h('span', null, b.leads || b.watch ? `${b.leads} ${b.leads === 1 ? 'lead' : 'leads'} · ${b.watch} watch` : 'On the scan; nothing shown here'),
      b.leads || b.watch ? h('button', { class: 'gl-open', onclick: () => go('corridor', b.iso2) }, 'Open the corridor →') : null);
  }
  function bind() {
    cv.addEventListener('pointerdown', (e) => { dragging = { x: e.clientX, y: e.clientY, lon: lon0, lat: lat0, moved: false }; target = null; cv.setPointerCapture(e.pointerId); });
    cv.addEventListener('pointermove', (e) => {
      if (dragging) {
        const dx = e.clientX - dragging.x, dy = e.clientY - dragging.y;
        if (Math.abs(dx) + Math.abs(dy) > 3) dragging.moved = true;
        lon0 = ((dragging.lon - dx * 0.35) + 540) % 360 - 180; lat0 = Math.max(-60, Math.min(80, dragging.lat + dy * 0.35));
        return;
      }
      const b = pick(e); hover = b; cv.style.cursor = b ? 'pointer' : 'grab';
      cv.title = b ? `${b.name}: ${b.leads || b.watch ? `${b.leads} lead${b.leads === 1 ? '' : 's'}, ${b.watch} watch` : 'on the scan, nothing shown'}` : '';
    });
    const up = (e) => { if (!dragging) return; const moved = dragging.moved; dragging = null; resumeAt = performance.now() + 2000; if (!moved) { const b = pick(e); select(b ? b.iso2 : null, false); } };
    cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', () => { dragging = null; });
    cv.addEventListener('pointerleave', () => { hover = null; });
    el.querySelector('#gl-pause').addEventListener('click', (e) => { paused = !paused; e.currentTarget.setAttribute('aria-pressed', String(paused)); });
    // Coming back to the tab starts the globe again where it stopped.
    document.addEventListener('visibilitychange', () => { if (!document.hidden) Globe.start(); });
    window.addEventListener('resize', () => { size = 0; });
  }
  // Widths are set through the style object, never a style attribute, so the hosted page's policy holds.
  const widthOf = (node, share) => { node.style.width = `${Math.round(share * 1000) / 10}%`; return node; };
  function build() {
    const s = S.D.summary[0];
    const held = s.leads_held + s.watch_held;
    const shown = blips.filter((b) => b.leads || b.watch).sort((a, b) => (b.leads - a.leads) || (b.leads + b.watch - a.leads - a.watch));
    const most = Math.max(1, ...shown.map((b) => b.leads + b.watch));
    const runs = [...new Set(S.D.history.map((x) => x.run))].sort();
    const perRun = runs.map((r) => S.D.history.filter((x) => x.run === r && x.lead === true && x.shown).length);
    const top = Math.max(1, ...perRun);
    const spark = sv('svg', { viewBox: `0 0 ${runs.length * 4} 28`, class: 'gl-spark', 'aria-hidden': 'true', preserveAspectRatio: 'none' },
      sv('polyline', { points: perRun.map((n, i) => `${i * 4 + 2},${26 - (n / top) * 24}`).join(' '), fill: 'none', stroke: 'currentColor', 'stroke-width': '1.2' }));
    cv = h('canvas', { class: 'gl-canvas', role: 'img', 'aria-label': `A turning globe: ${s.leads_shown} leads and ${s.watch_shown} watch items on ${shown.length} corridors, with routes from the UK to each and on to Russia. The corridor list beside it opens each one.` });
    el = h('section', { class: 'console', id: 'ov-console', 'aria-label': 'Radar console' },
      h('div', { class: 'gl-panel gl-tl' },
        h('span', { class: 'gl-k' }, 'Scan'), h('span', { class: 'gl-dim' }, `${s.run_label.toUpperCase()} RUN · HMRC TO ${String(s.uk_data_to).toUpperCase()}`),
        h('div', { class: 'gl-nums' },
          h('span', null, h('b', { class: 'gl-lead' }, String(s.leads_shown).padStart(2, '0')), 'Leads'),
          h('span', null, h('b', { class: 'gl-watch' }, String(s.watch_shown).padStart(2, '0')), 'Watch'),
          h('span', null, h('b', null, String(s.corridors).padStart(2, '0')), 'Corridors'),
          h('span', null, h('b', null, String(held).padStart(2, '0')), 'Held back')),
        h('span', { class: 'gl-dim' }, 'Held back: counted, never placed on the globe.')),
      h('div', { class: 'gl-panel gl-tr' },
        h('span', { class: 'gl-k' }, 'Sweep'),
        h('div', { class: 'gl-row' }, h('span', null, 'Bearing'), h('b', { id: 'gl-bearing' }, '000°')),
        h('div', { class: 'gl-row' }, h('span', null, 'Facing'), h('b', { id: 'gl-lon' }, '0°')),
        h('div', { class: 'gl-row' }, h('span', null, 'Next HMRC month'), h('b', null, NEXT_RELEASE.date.replace(/ 20\d\d$/, ''))),
        h('div', { class: 'gl-row' }, h('button', { class: 'gl-link', onclick: () => go('monitor') }, 'Monitor items waiting'), h('b', { id: 'gl-mon' }, '0')),
        h('span', { class: 'gl-k gl-gap' }, 'Leads shown at each run'), spark,
        h('span', { class: 'gl-dim' }, `${monthLabel(runs[0])} to ${monthLabel(runs[runs.length - 1])}, among the series shown today, with today’s rule on today’s figures`),
        h('div', { id: 'gl-sel', class: 'gl-sel', 'aria-live': 'polite' })),
      h('div', { class: 'gl-stage' }, cv),
      h('div', { class: 'gl-panel gl-bl' },
        h('span', { class: 'gl-k' }, 'Key'),
        h('ul', { class: 'gl-key' },
          h('li', null, h('i', { class: 'k-lead' }), 'Lead: both checks pass'), h('li', null, h('i', { class: 'k-watch' }), 'Watch: UK rise only'),
          h('li', null, h('i', { class: 'k-quiet' }), 'On the scan'), h('li', null, h('i', { class: 'k-uk' }), 'UK exports to the corridor'), h('li', null, h('i', { class: 'k-on' }), 'Corridor exports to Russia'), h('li', null, h('i', { class: 'k-ping' }), 'An item waiting on the monitor')),
        h('span', { class: 'gl-dim' }, 'Moving dots show the direction of trade, not shipments. Marks sit on capitals. Land: Natural Earth.'),
        h('button', { id: 'gl-pause', class: 'gl-btn', 'aria-pressed': String(paused), title: reduced ? 'Paused because your system asks for reduced motion' : 'Pause the motion' }, 'Pause motion')),
      h('div', { class: 'gl-panel gl-br' },
        h('span', { class: 'gl-k' }, 'Corridors with something shown'),
        h('ul', { class: 'gl-list' }, shown.map((b) => h('li', null, h('button', { 'data-iso': b.iso2, 'aria-pressed': 'false', 'aria-label': `${b.name}: ${b.leads} ${b.leads === 1 ? 'lead' : 'leads'}, ${b.watch} ${b.watch === 1 ? 'watch item' : 'watch items'}`, onclick: () => select(b.iso2, true) },
          h('span', { class: 'gl-name' }, b.name), h('span', { class: 'gl-bar', 'aria-hidden': 'true' }, widthOf(h('i', { class: 'gl-bl-lead' }), b.leads / most), widthOf(h('i', { class: 'gl-bl-watch' }), b.watch / most)),
          h('span', { class: 'gl-n' }, h('b', { class: 'gl-nl' }, String(b.leads)), ' ', h('b', { class: 'gl-nw' }, String(b.watch))))))),
        h('span', { class: 'gl-dim' }, 'Leads (violet) and watch items (blue). Choosing a corridor turns the globe to it.'),
        h('span', { class: 'gl-dim', id: 'gl-monlist', 'aria-live': 'polite' })),
      h('p', { class: 'gl-foot' }, 'The sweep runs all the time; the figures are the latest monthly run’s and change when HMRC publishes. A rise in exports is a lead, not evidence of a breach.'));
    ctx2 = cv.getContext('2d');
    bind(); showSelection();
  }
  return {
    // The same element is placed on every redraw of the overview, so the globe keeps turning.
    el() {
      if (!el) { model(); build(); getJSON('spec/land.json').then((d) => { land = d; }).catch(() => { land = null; }); }
      return el;
    },
    start() { if (!running && el) { running = true; last = 0; size = 0; requestAnimationFrame(frame); } },
    state: () => ({ lon0, lat0, sweep, paused, selected, running, blips: blips.length, routes: routes.length, land: !!land }),
  };
})();

/* ============================================================== what a lead is worth
   A lead's worth, said without inventing a figure: what it is and is not, what the backtest
   says it bought and what it cost in leads, and what working the run's leads would take, on an
   analyst's hours and cost that the viewer sets. Nothing here estimates the value of a case. */
function leadRecord() {
  const cost = (m) => S.D.cost.find((c) => c.measure === m) || {};
  const cases = cost('Cases with a lead before the first public action'), ever = cost('Series a lead at some run, Jan 2022 to Aug 2026');
  const hits = S.D.tests.filter((t) => t.role === 'primary' && t.shown && t.run2_outcome === 'hit' && isNum(t.run2_lead_time_months));
  const months = hits.map((t) => +t.run2_lead_time_months).sort((a, b) => a - b);
  const stopped = hits.filter((t) => /^no, stopped/.test(String(t.run2_on_the_day || '')));
  return { cases, ever, hits, months, stopped };
}
function worthCard() {
  const s = S.D.summary[0];
  const R = leadRecord();
  if (!S.worth) S.worth = Object.assign({ hours: '', rate: '', watch: false }, local.get('worth', {}));
  const out = h('div', { class: 'worth-out', 'aria-live': 'polite' });
  const n = () => s.leads_shown + (S.worth.watch ? s.watch_shown : 0);
  const calc = () => {
    const hrs = parseFloat(S.worth.hours), rate = parseFloat(S.worth.rate);
    if (!(hrs > 0)) { swap(out, h('span', { class: 'muted' }, 'Enter the hours a brief takes your team to see what this run would take.')); return; }
    const total = hrs * n();
    swap(out, h('b', null, `${intGB(total)} analyst hours`), rate > 0 ? h('b', null, ` · £${intGB(total * rate)}`) : null,
      h('span', { class: 'muted' }, ` to brief ${n()} ${S.worth.watch ? 'leads and watch items' : 'leads'} at this run: arithmetic on your figures only, nothing here is the tool’s estimate.`));
  };
  const set = (k) => (e) => { S.worth[k] = e.target.type === 'checkbox' ? e.target.checked : e.target.value; local.set('worth', S.worth); calc(); };
  calc();
  const range = R.months.length ? `${R.months[0]} to ${R.months[R.months.length - 1]} months` : 'n/a';
  return h('section', { class: 'card ov-card worth' },
    h('div', { class: 'card-head' }, h('h2', { class: 'h2' }, 'What a lead is worth'), h('span', { class: 'note' }, 'no figure invented')),
    h('ul', { class: 'worth-list' },
      h('li', null, h('b', null, 'It is a question, ranked. '), 'A lead says two published series rose together on one route: worth an analyst’s look before anything else. It is not evidence of a breach, not a finding and never a named exporter.'),
      h('li', null, h('b', null, 'What it bought. '), `In the backtest the monthly check had a lead before the first public action in ${R.cases.run2} of ${R.cases.of} published cases, from ${range} ahead across the ${R.hits.length} primary tests shown; in the ${inWords(R.stopped.length)} with the longest lead times the lead had stopped before the action. Four cases is a small test, and not a blind one [Likely].`),
      h('li', null, h('b', null, 'What it cost. '), `${R.ever.run2} of the ${R.ever.of} series on the backtest’s nine corridors were a lead at some run since January 2022, so most leads will never become a case [Likely]. Its worth is the order it puts the checks in, not a forecast of outcomes.`)),
    h('div', { class: 'worth-calc' },
      h('label', { class: 'field' }, 'Hours to brief one lead', h('input', { type: 'number', min: '0', step: '0.5', inputmode: 'decimal', value: S.worth.hours, placeholder: 'yours', oninput: set('hours') })),
      h('label', { class: 'field' }, 'Cost per analyst hour, £', h('input', { type: 'number', min: '0', step: '1', inputmode: 'decimal', value: S.worth.rate, placeholder: 'optional', oninput: set('rate') })),
      h('label', { class: 'check' }, h('input', { type: 'checkbox', checked: S.worth.watch, onchange: set('watch') }), 'Brief the watch items too')),
    out);
}
// The factors behind a lead, present or not. They are not weighted or added into a score, as no
// weighting has been tested; the thresholds are judgement calls, said as such.
function supportCard(f) {
  const s = S.D.summary[0];
  const thisYear = +String(s.uk_data_to).slice(-4) || new Date().getFullYear();
  const monthlyToo = !!(f.onward_monthly && f.onward_monthly.passes) && !!(f.onward_annual && f.onward_annual.passes);
  const factors = [
    [f.status === 'lead', 'Both checks pass at this run', f.status === 'lead' ? 'UK exports and the corridor’s onward exports both rose.' : 'Only the UK check passed: a watch item.'],
    [monthlyToo, 'The annual and the monthly onward checks both pass', monthlyToo ? 'Two readings of the corridor’s exports agree.' : `Onward check: ${f.onward_check || 'not passed'}.`],
    [(f.runs_shown_as_lead || 0) >= 3, 'A lead at three or more of the runs shown', `A lead at ${f.runs_shown_as_lead || 0} of the ${f.runs_shown} runs that can be shown.`],
    [(f.uk_months_with_exports || 0) >= 10, 'UK exports in ten or more of the 12 months', `Exports in ${f.uk_months_with_exports} of 12 months: ${(f.uk_months_with_exports || 0) >= 10 ? 'a steady flow, not one consignment' : 'fewer months, so one large consignment weighs more'}.`],
    [isNum(f.onward_year) && +f.onward_year >= thisYear - 1, 'Onward data from the last two years', isNum(f.onward_year) ? `The corridor’s latest annual figure is for ${f.onward_year}.` : 'No annual onward figure.'],
    [!!f.case_route, 'The route appears in a published enforcement case', f.case_route ? `${f.case_route}, ${f.case_match === 'route' ? 'on this code' : f.case_match === 'heading' ? 'on its four-digit heading only' : 'on this code or its heading'}; the cases named no UK goods or UK party.` : 'No tested case on this route.'],
  ];
  return section('sec-support', f.status === 'lead' ? 'What supports this lead' : 'What supports this watch item', 'factors, present or not', [
    h('ul', { class: 'factors' }, factors.map(([ok, t, d]) => h('li', { class: ok ? 'yes' : 'no' }, h('span', { class: 'fx', 'aria-label': ok ? 'present' : 'absent' }, ok ? '✓' : '–'), h('span', null, h('b', null, t), h('span', { class: 'muted' }, ' ' + d))))),
    h('p', { class: 'note' }, 'Factors, not a score: they are not weighted or counted up, as no weighting has been tested, and the thresholds are judgement calls [Guessing]. A file with every factor present is still a question, not a finding.')]);
}

/* ============================================================== corridor map
   UK on the left, the corridor countries in the middle, Russia on the right. A line from the UK
   for each corridor with a file the workspace shows, thicker for more UK exports; a violet line
   on to Russia where a file is a lead. Corridors with nothing shown are listed without lines, so
   a held-back series is never placed on the map. */
function corridorGroups() {
  const corr = S.D.corridors[0].corridors;
  return corr.map((c) => {
    const files = S.files.filter((f) => f.iso2 === c.iso2);
    return { c, files, leads: files.filter((f) => f.status === 'lead'), uk: files.reduce((t, f) => t + (+f.uk_trailing12_gbp || 0), 0) };
  }).sort((a, b) => b.leads.length - a.leads.length || b.files.length - a.files.length || b.uk - a.uk || (a.c.name < b.c.name ? -1 : 1));
}
function drawMap() {
  const v = $('#view-map');
  const s = S.D.summary[0];
  const groups = corridorGroups();
  const shown = groups.filter((g) => g.files.length), quiet = groups.filter((g) => !g.files.length);
  if (!S.mapSel || !groups.find((g) => g.c.iso2 === S.mapSel)) S.mapSel = shown.length ? shown[0].c.iso2 : null;
  const sel = groups.find((g) => g.c.iso2 === S.mapSel);
  const maxUk = Math.max(1, ...shown.map((g) => g.uk));
  const stage = h('div', { class: 'map-stage' });
  const svg = sv('svg', { class: 'map-lines', 'aria-hidden': 'true' });
  const uk = h('div', { class: 'map-end map-uk' }, h('b', null, 'United Kingdom'), h('span', null, `UK exports, 12 months to ${s.uk_data_to}`));
  const ru = h('div', { class: 'map-end map-ru' }, h('b', null, 'Russia'), h('span', null, 'as each corridor reports its exports'));
  const nodes = h('ul', { class: 'map-nodes', 'aria-label': 'Corridors with a file shown' }, shown.map((g) => h('li', null, h('button', {
    class: 'map-node' + (g.c.iso2 === S.mapSel ? ' on' : '') + (g.leads.length ? ' has-lead' : ''), 'data-iso': g.c.iso2,
    'aria-pressed': g.c.iso2 === S.mapSel ? 'true' : 'false', 'aria-label': `${g.c.name}: ${g.leads.length} leads, ${g.files.length - g.leads.length} watch items shown`,
    onclick: () => { S.mapSel = g.c.iso2; drawMap(); const again = document.querySelector(`#view-map .map-node[data-iso="${g.c.iso2}"]`); if (again) again.focus({ preventScroll: true }); },
  }, h('span', { class: 'map-name' }, g.c.name), h('span', { class: 'map-meta' }, `${gbp(g.uk)} · ${g.leads.length ? `${g.leads.length} lead${g.leads.length > 1 ? 's' : ''}` : ''}${g.leads.length && g.files.length > g.leads.length ? ', ' : ''}${g.files.length > g.leads.length ? `${g.files.length - g.leads.length} watch` : ''}`)))));
  add(stage, svg, uk, nodes, ru);
  const panel = sel ? h('aside', { class: 'card map-panel', 'aria-live': 'polite' },
    h('div', { class: 'card-head' }, h('h2', { class: 'h2' }, sel.c.name), h('span', { class: 'note' }, `${sel.files.length} file${sel.files.length === 1 ? '' : 's'} shown`)),
    h('div', { class: 'ov-list' }, sel.files.map((f) => h('button', { class: 'ov-row', onclick: openFile(f), 'aria-label': `Open ${f.ref}` },
      h('span', { class: 'ov-main' }, h('span', { class: 'ov-title' }, `HS ${fmtCode(f.code)}`), h('span', { class: 'ov-sub' }, f.description)),
      h('span', { class: 'ov-side' }, sigTag(f), h('span', { class: 'ov-num' }, gbp(f.uk_trailing12_gbp)), deltaChip(f, true))))),
    h('p', { class: 'note' }, 'Figures are this corridor’s files the workspace shows. A series the display rule holds back is not counted here, by corridor or code [Certain].')) : null;
  swap(v,
    h('div', { class: 'head' },
      h('p', { class: 'eyebrow' }, `${s.run_label} run · HMRC data to ${s.uk_data_to}`),
      h('h1', { class: 'h1' }, 'Corridor map'),
      h('p', { class: 'lede' }, `Where the files sit: UK exports to each corridor and, where a file is a lead, that corridor’s own exports of the same goods to Russia. ${shown.length} of ${groups.length} corridors have a file the workspace shows.`)),
    h('div', { class: 'map-wrap' }, h('div', { class: 'card map-card' }, h('div', { class: 'legend' }, h('span', null, h('i'), 'UK exports, thicker for more'), h('span', null, h('i', { class: 'lead' }), 'A lead: the onward check passed')), stage), panel),
    quiet.length ? h('p', { class: 'note' }, `No file shown on ${quiet.map((g) => inText(g.c.name)).join(', ')}: nothing flagged there that the display rule lets the workspace show, or nothing flagged at all; the two are not told apart [Certain].`) : null,
    h('p', { class: 'house' }, 'A rise in exports is a lead, not evidence of a breach. A line is a route to check, never a shipment.'));
  // Lines, drawn once the layout is known, and again when the window changes size.
  const drawLines = () => {
    if (!stage.isConnected) return;
    const box = stage.getBoundingClientRect();
    svg.setAttribute('viewBox', `0 0 ${box.width} ${box.height}`);
    svg.setAttribute('width', box.width); svg.setAttribute('height', box.height);
    const r = (el) => { const b = el.getBoundingClientRect(); return { l: b.left - box.left, r: b.right - box.left, y: b.top - box.top + b.height / 2 }; };
    const a = r(uk), z = r(ru);
    const paths = [];
    for (const btn of nodes.querySelectorAll('.map-node')) {
      const g = shown.find((x) => x.c.iso2 === btn.dataset.iso); if (!g) continue;
      const m = r(btn), w = 1.5 + 6 * Math.sqrt(g.uk / maxUk), on = g.c.iso2 === S.mapSel;
      const cx1 = (a.r + m.l) / 2;
      paths.push(sv('path', { class: 'map-in' + (on ? ' on' : ''), d: `M${a.r},${a.y} C${cx1},${a.y} ${cx1},${m.y} ${m.l},${m.y}`, 'stroke-width': w.toFixed(1) }));
      if (g.leads.length) { const cx2 = (m.r + z.l) / 2; paths.push(sv('path', { class: 'map-out' + (on ? ' on' : ''), d: `M${m.r},${m.y} C${cx2},${m.y} ${cx2},${z.y} ${z.l},${z.y}`, 'stroke-width': (1.5 + 1.2 * g.leads.length).toFixed(1) })); }
    }
    svg.replaceChildren(...paths);
  };
  requestAnimationFrame(drawLines);
  if (!S.mapResize) { S.mapResize = true; window.addEventListener('resize', () => { if (S.view === 'map') requestAnimationFrame(() => drawMap()); }); }
}

/* ============================================================== connected */
// What touches a file's route in the rest of the workspace: the same goods on other corridors,
// the same corridor with other goods, synthetic declaration cases and reports on the route.
function connectedCard(f) {
  const sameCode = S.files.filter((x) => x.code === f.code && x.key !== f.key);
  const sameCorr = S.files.filter((x) => x.iso2 === f.iso2 && x.key !== f.key);
  const cases = Decl.casesOnRoute(f.key), reports = Triage.onRoute(f.key);
  const chip = (x, label) => h('button', { class: 'link-chip', onclick: openFile(x), 'aria-label': `Open ${x.ref}` }, h('span', { class: 'sig ' + (x.status === 'lead' ? 'lead' : '') }, x.status === 'lead' ? 'Lead' : 'Watch'), label);
  const row = (title, kids, none) => h('div', { class: 'link-row' }, h('span', { class: 'link-k' }, title), h('div', { class: 'link-v' }, kids.length ? kids : h('span', { class: 'muted small' }, none)));
  return h('div', { class: 'rail-card', id: 'sec-connected' },
    h('h2', { class: 'rail-h' }, 'Connected'), h('span', { class: 'muted small' }, 'Files and records that share this route, its goods or its corridor.'),
    row(`HS ${fmtCode(f.code)} elsewhere`, sameCode.map((x) => chip(x, x.country)), 'No other corridor shows a file on this code.'),
    row(`${inText(f.country, true)}, other goods`, sameCorr.map((x) => chip(x, `HS ${fmtCode(x.code)}`)), 'No other file on this corridor.'),
    row('Declaration cases', cases.map((c) => h('button', { class: 'link-chip', onclick: () => go('case', c.id) }, h('span', { class: 'syn-mini' }, 'synthetic'), c.id)), 'None on this route.'),
    row('Reports', reports.map((x) => h('button', { class: 'link-chip', onclick: () => go('report', x.id) }, h('span', { class: 'syn-mini' }, 'synthetic'), x.id)), 'None on this route.'),
    h('p', { class: 'note' }, 'The declaration cases and reports are synthetic: made up for testing, with some patterns placed on routes the public radar shows and the rest (exporters, consignees, dates and values) drawn at random. They say nothing about the real route or real exporters [Certain].'));
}

/* ============================================================== charts */
function niceStep(range, n) {
  const raw = range / Math.max(1, n);
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const m = raw / p;
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p;
}
function tipAt(box, x, lines) {
  let tip = box.querySelector('.tip');
  if (!tip) { tip = h('div', { class: 'tip' }); box.append(tip); }
  tip.hidden = false;
  swap(tip, ...lines.map((l, i) => h('div', { class: i === 0 ? 'when' : '' }, l)));
  const w = tip.offsetWidth || 180;
  tip.style.left = Math.max(0, Math.min(x - w / 2, box.clientWidth - w)) + 'px';
}
function hideTip(box) { const t = box.querySelector('.tip'); if (t) t.hidden = true; }
function lineChart(box, pts, label) {
  swap(box);
  const W = Math.max(300, box.clientWidth || 560), H = 200, m = { t: 12, r: 10, b: 24, l: 54 };
  const drawn = pts.filter((p) => p.v !== null);
  const t0 = pts[0].t, t1 = pts[pts.length - 1].t;
  const X = (t) => m.l + (t1 === t0 ? 0 : (t - t0) / (t1 - t0)) * (W - m.l - m.r);
  const top = Math.max(1, ...drawn.map((p) => p.v), ...pts.map((p) => p.thr || 0));
  const step = niceStep(top, 4), yMax = Math.ceil((top * 1.05) / step) * step;
  const Y = (v) => H - m.b - (v / yMax) * (H - m.t - m.b);
  const svg = sv('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': label });
  for (let v = 0; v <= yMax + 1e-9; v += step) {
    svg.append(sv('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), class: 'g-grid' }), sv('text', { x: m.l - 6, y: Y(v), class: 'g-lab', 'text-anchor': 'end', 'dominant-baseline': 'middle' }, gbp(v)));
  }
  const bw = (W - m.l - m.r) / Math.max(1, pts.length - 1);
  for (const p of drawn) if (p.lead) svg.append(sv('rect', { x: X(p.t) - bw / 2, y: m.t, width: bw, height: H - m.b - m.t, class: 'g-shade' }));
  let thr = '';
  pts.forEach((p, i) => { if (isNum(p.thr)) thr += (i && thr ? 'L' : 'M') + X(p.t).toFixed(1) + ',' + Y(p.thr).toFixed(1); });
  svg.append(sv('path', { d: thr, class: 'g-thr' }));
  const years = [...new Set(pts.map((p) => new Date(p.t).getUTCFullYear()))];
  for (const y of years) {
    const t = Date.UTC(y, 0, 1);
    if (t < t0 || t > t1) continue;
    svg.append(sv('line', { x1: X(t), x2: X(t), y1: H - m.b, y2: H - m.b + 4, class: 'g-axis' }), sv('text', { x: X(t), y: H - 6, class: 'g-lab', 'text-anchor': 'middle' }, String(y)));
  }
  svg.append(sv('line', { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, class: 'g-axis' }));
  let d = '', pen = false;
  for (const p of pts) { if (p.v === null) { pen = false; continue; } d += (pen ? 'L' : 'M') + X(p.t).toFixed(1) + ',' + Y(p.v).toFixed(1); pen = true; }
  svg.append(sv('path', { d, class: 'g-line' }));
  for (const p of drawn) svg.append(sv('circle', { cx: X(p.t), cy: Y(p.v), r: 1.8, class: 'g-dot' }));
  const focus = sv('circle', { r: 4, class: 'g-dot', visibility: 'hidden' });
  svg.append(focus);
  const hit = sv('rect', { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, class: 'g-hit' });
  svg.append(hit);
  const move = (ev) => {
    const r = svg.getBoundingClientRect();
    const px = ((ev.clientX - r.left) / r.width) * W;
    let best = 0, bd = Infinity;
    pts.forEach((p, i) => { const dd = Math.abs(X(p.t) - px); if (dd < bd) { bd = dd; best = i; } });
    const p = pts[best];
    if (p.v === null) focus.setAttribute('visibility', 'hidden');
    else { focus.setAttribute('cx', X(p.t)); focus.setAttribute('cy', Y(p.v)); focus.setAttribute('visibility', 'visible'); }
    tipAt(box, (X(p.t) / W) * r.width, ['Run of ' + monthLabel(p.run), p.v === null ? (p.why === 'case' ? 'Not drawn: window starts before the case' : 'Not drawn: under the display rule') : 'UK, 12 months: ' + gbp(p.v) + (p.lead ? ' · would have been a lead' : p.uk ? ' · UK signal' : '')]);
  };
  hit.addEventListener('pointermove', move);
  hit.addEventListener('pointerleave', () => { hideTip(box); focus.setAttribute('visibility', 'hidden'); });
  box.append(svg);
}
function barChart(box, pts, label) {
  swap(box);
  const W = Math.max(300, box.clientWidth || 560), H = 180, m = { t: 12, r: 10, b: 24, l: 54 };
  const top = Math.max(1, ...pts.map((p) => Math.max(p.usd, p.thr || 0)));
  const step = niceStep(top, 4), yMax = Math.ceil((top * 1.05) / step) * step;
  const Y = (v) => H - m.b - (v / yMax) * (H - m.t - m.b);
  const band = (W - m.l - m.r) / pts.length, bw = Math.max(4, band * 0.62);
  const svg = sv('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': label });
  for (let v = 0; v <= yMax + 1e-9; v += step) {
    svg.append(sv('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), class: 'g-grid' }), sv('text', { x: m.l - 6, y: Y(v), class: 'g-lab', 'text-anchor': 'end', 'dominant-baseline': 'middle' }, usd(v)));
  }
  const every = band < 30 ? 2 : 1;
  pts.forEach((p, i) => {
    const x = m.l + band * i + (band - bw) / 2;
    const rect = sv('rect', { x, width: bw, y: Y(p.usd), height: Math.max(0, Y(0) - Y(p.usd)), rx: 3, class: 'g-bar' + (+p.year < 2022 ? ' pre' : '') });
    rect.addEventListener('pointerenter', () => tipAt(box, ((x + bw / 2) / W) * box.clientWidth, [p.year + (p.rel ? ', released ' + p.rel : ''), 'To Russia: ' + usd(p.usd)]));
    rect.addEventListener('pointerleave', () => hideTip(box));
    svg.append(rect);
    if ((pts.length - 1 - i) % every === 0) svg.append(sv('text', { x: x + bw / 2, y: H - 6, class: 'g-lab', 'text-anchor': 'middle' }, p.year));
  });
  if (isNum(pts[0] && pts[0].thr)) svg.append(sv('line', { x1: m.l, x2: W - m.r, y1: Y(pts[0].thr), y2: Y(pts[0].thr), class: 'g-thr' }));
  svg.append(sv('line', { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, class: 'g-axis' }));
  box.append(svg);
}
const chartJobs = new Map();
const ro = typeof ResizeObserver === 'function' ? new ResizeObserver((entries) => {
  for (const e of entries) { const job = chartJobs.get(e.target); if (job && Math.abs((e.target._w || 0) - e.contentRect.width) > 4) { e.target._w = e.contentRect.width; job(); } }
}) : null;
function chartBox(job) {
  const box = h('div', { class: 'chart' });
  chartJobs.set(box, () => job(box));
  requestAnimationFrame(() => { box._w = box.clientWidth; job(box); if (ro) ro.observe(box); });
  return box;
}

/* ============================================================== lead file */
const caseById = () => new Map(S.D.cases.map((c) => [c.case_id, c]));
function caseLine(f) {
  if (!f.case_route) return '';
  const many = f.case_route.includes(',');
  return `This corridor, and this code or its four-digit goods heading, also appear in enforcement case${many ? 's' : ''} ${f.case_route.replace(', ', ' and ')}, which named no UK goods or UK party. Only windows that start after ${many ? 'their' : 'its'} first public action${many ? 's' : ''} are drawn.`;
}
// Which past runs of a file are not drawn, and why: the case window on a case route, the
// display rule elsewhere. Nothing is said when every run since January 2022 is drawn.
function heldRunsLine(f) {
  const held = S.D.history.filter((x) => x.series === f.series && !x.shown);
  const caseWindow = (x) => String(x.not_shown_because || '').startsWith('window starts');
  const inWindow = held.some(caseWindow);
  const small = held.some((x) => !caseWindow(x));
  if (inWindow && small) return ' Earlier runs on this route, and runs under the display rule, are not drawn.';
  if (inWindow) return ' Earlier runs on this route are not drawn.';
  return small ? ' Runs under the display rule are not drawn.' : '';
}
function limitsFor(f) {
  const out = [
    ['Ordinary trade can pass both tests: a corridor’s own demand can rise with its exports to Russia.', 'Certain'],
    ['The codes are broad, and most of what they cover is in ordinary use.', 'Certain'],
    ['HMRC and UN Comtrade revise published figures; later releases may change these.', 'Likely'],
  ];
  if (f.status === 'lead' && /2023/.test(f.onward_check)) out.push(['This onward check rests on 2023, the latest year the corridor has released.', 'Certain']);
  if (/monthly/.test(f.onward_check)) out.push(['One month can carry the monthly onward check. The rule itself does not test how spread out the exports are on either side; only the display rule’s months test does, on the UK side.', 'Certain']);
  out.push(['The onward check rests on what each corridor reports to UN Comtrade as its exports to Russia.', 'Certain']);
  return out;
}
function drawFile() {
  const f = S.byKey.get(S.fileKey);
  const v = $('#view-file');
  if (!f) { go('inbox'); return; }
  const w = workflowOf(f), u = uiFor(f.docId);
  if (S.contexts[f.key] === undefined) contextFor(f).then(() => refresh());
  const ctxState = S.contexts[f.key] === undefined ? 'loading' : S.contexts[f.key] ? 'ok' : 'none';
  // The main column (figures, charts, cases) is drawn once per file; the brief, the checks and
  // the rail are redrawn on every store update, except a panel a person is typing in.
  const declState = (Decl.isLoaded() ? '1' : '0') + (Triage.isLoaded() ? '1' : '0');
  if (v.dataset.doc !== f.docId || v.dataset.ctx !== ctxState || v.dataset.decl !== declState) {
    v.dataset.doc = f.docId; v.dataset.ctx = ctxState; v.dataset.decl = declState;
    const main = fileMain(f);
    swap(v, h('div', { id: 'f-head' }), h('div', { id: 'f-bar' }),
      h('div', { class: 'rec' },
        h('div', { class: 'rec-main' }, main.top, section('sec-brief', 'Analyst brief', null, h('div', { id: 'slot-brief' })),
          section('sec-checks', 'Questions to check', null, h('div', { id: 'slot-checks' })),
          section('sec-outcome', 'What happened', null, h('div', { id: 'slot-outcome' })), main.rest),
        h('aside', { class: 'rec-rail', id: 'rec-rail', 'aria-label': 'About this file', dataset: { doc: f.docId } },
          h('div', { id: 'slot-props' }), h('div', { id: 'slot-tasks' }), h('div', { id: 'slot-monitor' }), references(f), h('div', { id: 'slot-addons' }), connectedCard(f), h('div', { id: 'slot-activity' }))));
  }
  swap($('#f-head'), fileHead(f, w));
  if (window.FdShell && FdShell.sectionBar) swap($('#f-bar'), FdShell.sectionBar(`${f.country} · ${fmtCode(f.code)}`, [sigTag(f), stChip(w.state)],
    [['Figures', '#sec-figures'], ['Support', '#sec-support'], ['History', '#sec-history'], ['Brief', '#sec-brief'], ['Checks', '#sec-checks'], ['Outcome', '#sec-outcome'], ['Follow-ups', '#rail-tasks'], ['Connected', '#sec-connected']].map(([label, target]) => ({ label, target }))));
  const slot = $('#slot-brief'), cur = slot.firstElementChild;
  const open = ((u.working && u.mode === 'edit' && !u.busy) || !!u.confirm) && cur && cur.dataset.mode === 'edit' && cur.dataset.doc === f.docId;
  if (!open) swap(slot, drawBriefPanel(f, w));
  swap($('#slot-checks'), drawChecks(f, w));
  const b = currentBrief(f);
  const metaOf = (id, text) => { const m = $(`#${id} .sec-head .sec-meta`); if (m) m.textContent = text; else { const s = $(`#${id} .sec-toggle`); if (s) s.append(h('span', { class: 'sec-meta' }, text)); } };
  metaOf('sec-brief', b ? `version ${b.version || 1} · ${STATE_LABEL[w.state] || w.state}` : 'not started');
  const items = checkItemsFor(f, S.contexts[f.key]), st = (S.checks.get(f.docId) || {}).items || {};
  metaOf('sec-checks', items.length ? `${items.filter((it) => (st[it.id] || {}).state === 'done').length} of ${items.length} checked` : 'after the first brief');
  drawOutcome(f);
  drawRail(f);
}
// Where a file sits in the list it was opened from, with the previous and next ones.
function listNav(f) {
  const preset = S.inboxPreset || 'all';
  const list = orderedFiles(preset);
  const i = list.findIndex((x) => x.key === f.key);
  return h('div', { class: 'pane-nav' },
    h('button', { class: 'btn quiet back', onclick: () => backToList() }, `\u2039 ${PRESETS[preset]} (${list.length})`),
    h('span', { class: 'spacer' }),
    i >= 0 ? h('span', { class: 'muted small' }, `${i + 1} of ${list.length}`) : h('span', { class: 'muted small' }, 'Not in this list now'),
    h('button', { class: 'btn quiet small step', 'aria-label': 'Previous file (k)', title: 'Previous file (k)', disabled: i <= 0, onclick: () => stepRecord(-1) }, '\u2191'),
    h('button', { class: 'btn quiet small step', 'aria-label': 'Next file (j)', title: 'Next file (j)', disabled: i < 0 || i >= list.length - 1, onclick: () => stepRecord(1) }, '\u2193'));
}
// A case's or a report's place in the list it was opened from, as on a file.
function recordNav(label, ids, id) {
  const i = ids.indexOf(id);
  return h('div', { class: 'pane-nav' },
    h('button', { class: 'btn quiet back', onclick: () => backToList() }, `\u2039 ${label} (${ids.length})`),
    h('span', { class: 'spacer' }),
    i >= 0 ? h('span', { class: 'muted small' }, `${i + 1} of ${ids.length}`) : h('span', { class: 'muted small' }, 'Not in this list now'),
    h('button', { class: 'btn quiet small step', 'aria-label': 'Previous (k)', title: 'Previous (k)', disabled: i <= 0, onclick: () => stepRecord(-1) }, '\u2191'),
    h('button', { class: 'btn quiet small step', 'aria-label': 'Next (j)', title: 'Next (j)', disabled: i < 0 || i >= ids.length - 1, onclick: () => stepRecord(1) }, '\u2193'));
}
// The file's approval trail in one line per step, from the records: who saved the version
// shown, and who returned, approved or rejected it.
function trailFor(f, w) {
  const b = currentBrief(f), D = w.decision;
  const who = (id) => person(id).name;
  if (w.state === 'new') return [['todo', 'No brief yet']];
  const steps = [];
  if (b) steps.push(['done', `Saved by ${who(b.author)}, ${stamp(b.created_at)}`]);
  if (w.state === 'drafting') steps.push(['now', 'Not yet sent for approval']);
  if (w.state === 'submitted') steps.push(['now', b && b.author === myId() && S.workflow.four_eyes !== false ? 'Sent for approval; you saved this version, so another editor decides' : 'Sent for approval; an editor who did not save this version decides']);
  if (w.state === 'returned' && D) steps.push(['back', `Sent back by ${who(D.author)}, ${stamp(D.decided_at)}, with a note`]);
  if (w.state === 'approved' && D) steps.push(['done', `Signed off by ${who(D.author)}, ${stamp(D.decided_at)}; the file is locked`]);
  if (w.state === 'rejected' && D) steps.push(['back', `Rejected by ${who(D.author)}, ${stamp(D.decided_at)}`]);
  return steps;
}
function fileHead(f, w) {
  const L = S.leads.get(f.docId), assignee = L && L.assignee;
  const b = currentBrief(f);
  resolvePeople([assignee, b && b.author, w.decision && w.decision.author].filter(Boolean));
  return h('div', { class: 'file-head' },
    listNav(f),
    h('div', { class: 'file-meta' }, h('span', { class: 'q-ref' }, f.ref), sigTag(f), stChip(w.state), selfChip(w), assignee ? whoLine(assignee, h('span', { class: 'muted' }, ' has the file')) : null),
    h('h1', { class: 'h1' }, `${f.country} \u00b7 ${fmtCode(f.code)}`),
    h('p', { class: 'lede' }, f.description),
    h('ol', { class: 'trail', 'aria-label': 'Approval trail' }, trailFor(f, w).map(([k, t]) => h('li', { class: 'trail-' + k }, t))),
    fileActions(f, w));
}
// The onward figures the header's main figure does not show: the monthly check for a lead on
// the annual one and for a watch item, the annual check for a lead on the monthly one, as in
// the dashboard's table. Reasons come from radar/onward.py by way of leads.json.
function onwardFigure(c, monthly, lead) {
  const when = monthly ? `Monthly, 12 months to ${monthLabel(c.to, true)}: ` : `Annual ${c.year}: `;
  if (c.no_exports) return when + 'no exports reported' + (lead && !c.passes ? ', not passed' : '');
  const vs = isNum(c.ratio) ? `${ratio(c.ratio)} the 2019-21 average` : (c.baseline_zero ? 'a zero 2019-21 baseline' : 'no 2019-21 baseline');
  return when + `${usd(c.usd)}, ${vs}` + (c.passes ? '' : ` (${lead ? 'not passed: ' : ''}${c.why_not_short})`);
}
function otherOnward(f) {
  if (!f.onward_annual) return '';
  if (f.status !== 'lead') {
    return ' ' + onwardFigure(f.onward_annual, false, false) + '.' +
      (f.onward_monthly ? ' ' + onwardFigure(f.onward_monthly, true, false) + '.' : ' No monthly check at this run.');
  }
  const onMonthly = String(f.onward_check).startsWith('monthly');
  const c = onMonthly ? f.onward_annual : f.onward_monthly;
  if (!c) return onMonthly ? '' : ' No monthly check at this run.';
  return ' ' + onwardFigure(c, !onMonthly, true) + '.';
}
function fileMain(f) {
  const s = S.D.summary[0];
  const facts = h('div', { class: 'facts' },
    h('div', { class: 'fact' },
      h('span', { class: 'k' }, `UK exports to ${inText(f.country)}, ${fmtCode(f.code)}`),
      h('span', { class: 'v' }, gbp(f.uk_trailing12_gbp), ' ', deltaChip(f)),
      h('span', { class: 's' }, `12 published months to ${s.uk_data_to}; ${ratio(f.uk_ratio)} the 2019-21 annual average of ${gbp(f.uk_baseline_gbp)}; exports in ${f.uk_months_with_exports} of 12 months.`),
      h('span', { class: 'src' }, h('span', { class: 'cite' }, 'HMRC overseas trade statistics'), h('span', { class: 'tag Certain' }, 'Certain'))),
    h('div', { class: 'fact' },
      h('span', { class: 'k' }, `${possOf(f.country, true)} exports of the code to Russia`),
      h('span', { class: 'v' }, f.status === 'lead' ? usd(f.onward_usd) : 'Not passed'),
      h('span', { class: 's' }, f.status === 'lead' ? `Onward check: ${f.onward_check}; ${ratio(f.onward_ratio, f.onward_baseline_zero)} the 2019-21 average, as ${inText(f.country)} reports it.${otherOnward(f)}` : `Onward check not passed.${otherOnward(f)} A UK rise alone makes a watch item.`),
      h('span', { class: 'src' }, h('span', { class: 'cite' }, 'UN Comtrade'), h('span', { class: 'tag Certain' }, 'Certain'))),
    h('div', { class: 'fact' },
      h('span', { class: 'k' }, 'Lead at the runs that can be shown'),
      h('span', { class: 'v' }, f.runs_shown_as_lead ? `${f.runs_shown_as_lead} ${f.runs_shown_as_lead === 1 ? 'run' : 'runs'}` : 'None'),
      h('span', { class: 's' }, `${f.status === 'lead' ? 'A lead' : 'A watch item'} at this run. ` + (f.runs_shown_as_lead
        ? `A lead at ${f.runs_shown_as_lead} of the ${f.runs_shown} runs that can be shown, the first in ${monthLabel(f.first_lead_shown)}, with today’s rule rerun on today’s figures.`
        : `None of the ${f.runs_shown} runs that can be shown since ${monthLabel(f.history_from)} was a lead.`) + heldRunsLine(f)),
      h('span', { class: 'src' }, h('span', { class: 'cite' }, 'Radar rerun, run 2 rule'), h('span', { class: 'tag Certain' }, 'Certain'))));
  const hist = S.D.history.filter((x) => x.series === f.series).map((x) => ({
    run: x.run, t: Date.parse(x.run + 'T00:00:00Z'), v: x.shown && isNum(x.uk_trailing12_gbp) ? +x.uk_trailing12_gbp : null,
    thr: +x.uk_threshold_gbp, lead: x.lead === true, uk: x.uk_signal === true, why: String(x.not_shown_because || '').startsWith('window starts') ? 'case' : 'size' }));
  const onward = S.D.onward_years.filter((x) => x.series === f.series).map((x) => ({ year: x.year, usd: +x.usd, thr: isNum(x.threshold_usd) ? +x.threshold_usd : null, rel: x.first_released ? x.first_released : '' }));
  const cmap = caseById();
  const linked = f.case_route ? f.case_route.split(',').map((c) => c.trim()).filter(Boolean) : [];
  const limits = (S.contexts[f.key] && S.contexts[f.key].limits) ? S.contexts[f.key].limits.map((x) => [x.text, x.confidence]) : limitsFor(f);
  const top = [
    section('sec-figures', 'What rose', factsLine(f), [facts, h('p', { class: 'note' }, 'Figures as published, rounded.')]),
    supportCard(f),
    section('sec-history', 'How it built up', hist.length ? `${hist.filter((x) => x.v !== null).length} runs drawn` : null, [
      h('div', { class: 'sub-head' }, h('h3', { class: 'h3' }, 'UK exports at each monthly run'), h('div', { class: 'legend' }, h('span', null, h('i'), 'UK, trailing 12 months'), h('span', null, h('i', { class: 'thr' }), 'Line the UK test needs'), h('span', null, h('i', { class: 'shade' }), 'Would have been a lead'))),
      hist.length ? chartBox((box) => lineChart(box, hist, `${f.series}: UK exports over 12 months at each run drawn`)) : h('p', { class: 'note' }, 'No runs to draw.'),
      h('p', { class: 'note' }, 'A run is drawn only when its own 12 months pass the display rule; gaps are runs that do not. Shaded runs would have been leads: today’s rule rerun on today’s figures, not runs the radar made at the time.'),
      caseLine(f) ? h('p', { class: 'note' }, caseLine(f)) : null,
      onward.length ? [
        h('div', { class: 'sub-head' }, h('h3', { class: 'h3' }, `What ${inText(f.country)} reported sending to Russia`), h('div', { class: 'legend' }, h('span', null, h('i', { class: 'pre' }), '2019-21'), h('span', null, h('i', { class: 'bar' }), '2022 on'), h('span', null, h('i', { class: 'thr' }), 'Line the annual check needs'))),
        chartBox((box) => barChart(box, onward, `${f.series}: corridor exports to Russia by year`)),
        h('p', { class: 'note' }, 'Totals from all exporters, as the corridor reports them, not figures for any one shipment or case [Certain].')] : null]),
  ];
  const rest = [
    linked.length ? section('sec-cases', 'Linked enforcement cases', `${linked.length}`, [
      h('p', { class: 'note' }, `Match: ${f.case_match === 'route' ? 'the cases link this code' : f.case_match === 'heading' ? 'the cases link only its four-digit heading' : 'some cases link this code, others only its heading'}. The cases named no UK goods or UK party [Certain].`),
      h('div', { class: 'scroll' }, h('table', null,
        h('thead', null, h('tr', null, h('th', null, 'Case'), h('th', null, 'Jurisdiction'), h('th', null, 'Outcome'), h('th', null, 'Basis'), h('th', null, 'First public action'))),
        h('tbody', null, linked.map((id) => { const c = cmap.get(id); return c ? h('tr', null, h('td', { class: 'mono' }, c.case_id), h('td', null, c.jurisdiction), h('td', null, c.outcome), h('td', null, c.basis), h('td', null, c.first_public_action)) : null; }))))]) : null,
    section('sec-limits', f.status === 'lead' ? 'Limits of this lead' : 'Limits of this watch item', `${limits.length}`, h('ul', { class: 'plain' }, limits.map(([t, c]) => h('li', null, t + ' ', h('span', { class: 'tag ' + c }, c))))),
  ];
  return { top, rest };
}
async function assign(f, who, quiet) {
  if (!canWrite()) return;
  const L = S.leads.get(f.docId), before = (L && L.assignee) || null;
  try {
    await upsert('leads', f.docId, { run: f.run, series: f.series, assignee: who });
    await audit(who ? 'assigned' : 'unassigned', f, '');
    if (!quiet) say(who === myId() ? 'You have the file.' : who ? 'File assigned.' : 'File released.', { label: 'Undo', run: () => assign(f, before, true) });
  } catch (e) { writeFailed(e, 'the file owner'); }
}

/* ============================================================== checklist */
function checkItemsFor(f, ctx) {
  // The checklist is the current brief's questions, with the guidance behind each.
  const b = currentBrief(f);
  if (!b || !ctx || !b.draft || !Array.isArray(b.draft.questions_to_check)) return [];
  const flags = new Map((ctx.red_flags || []).map((r) => [r.id, r]));
  return b.draft.questions_to_check.map((q) => { const r = flags.get(q.red_flag) || {}; return { id: q.red_flag, q: q.question, why: r.why, cite: r.citation, also: r.also_cited || [] }; });
}
function drawChecks(f, w) {
  const ctx = S.contexts[f.key];
  const items = checkItemsFor(f, ctx);
  const card = h('div', { class: 'card', id: 'checks-panel' }, h('div', { class: 'card-head' }, h('h2', { class: 'h2' }, 'Questions to check'), h('span', { class: 'note' }, 'From official guidance, as questions')));
  if (!items.length) { add(card, h('p', { class: 'note' }, 'The questions appear here once a brief is saved: the ones it picks from official guidance for this file.')); return card; }
  const st = (S.checks.get(f.docId) || {}).items || {};
  const locked = ['approved', 'rejected'].includes(w.state) || !canWrite();
  const ids = [];
  const list = h('div', { class: 'checks' }, items.map((it) => {
    const cur = st[it.id] || {};
    if (cur.by) ids.push(cur.by);
    const set = (state) => setCheck(f, it.id, state);
    const btn = (state, label) => h('button', { 'aria-pressed': String((cur.state || 'open') === state), disabled: locked, onclick: () => set(state) }, label);
    return h('div', { class: 'check' },
      h('div', null, h('div', { class: 'q' }, it.q), it.why ? h('div', { class: 'why' }, it.why) : null,
        h('div', { class: 'why' }, it.cite ? `${it.cite.publisher}, ${it.cite.title}, ${it.cite.date}` : '', it.also.length ? `; also ${it.also.map((c) => `${c.publisher}, ${c.title}, ${c.date}`).join('; ')}` : '', cur.by ? ` · ${cur.state === 'done' ? 'Checked' : cur.state === 'na' ? 'Marked not applicable' : 'Reopened'} by ${person(cur.by).name}, ${stamp(cur.at)}` : '')),
      h('div', { class: 'seg', role: 'group', 'aria-label': 'Check state' }, btn('open', 'Open'), btn('done', 'Checked'), btn('na', 'N/A')));
  }));
  resolvePeople(ids);
  const done = items.filter((it) => (st[it.id] || {}).state === 'done').length;
  const na = items.filter((it) => (st[it.id] || {}).state === 'na').length;
  add(card, h('p', { class: 'note' }, `${done} checked, ${na} not applicable, ${items.length - done - na} open.${locked && canWrite() ? ' Locked while the file is decided; reopen it to change.' : ''}`), list);
  return card;
}
async function setCheck(f, id, state) {
  if (!canWrite()) return;
  const entry = { state, by: myId(), at: nowIso() };
  try {
    await upsert('checks', f.docId, { run: f.run, series: f.series, items: { [id]: entry } });
    await audit('check_updated', f, `${id}: ${state === 'done' ? 'checked' : state === 'na' ? 'not applicable' : 'open'}`);
  } catch (e) { writeFailed(e, 'the check'); }
}

/* ============================================================== activity */
function drawActivity(f) {
  const evs = S.audit.filter((e) => e.lead === f.docId).slice(0, 40);
  resolvePeople(evs.map((e) => e.author));
  const item = (e) => {
    const p = person(e.author);
    return h('li', null, p.avatar ? h('img', { src: p.avatar, alt: '' }) : h('span'),
      h('div', null, h('div', null, h('b', null, p.name), ' ', ACTION_LABEL[e.action] || e.action, e.detail ? ': ' + e.detail : ''), h('div', { class: 'when' }, stamp(e.at))));
  };
  return h('div', { class: 'rail-card', id: 'rail-activity' }, h('h2', { class: 'rail-h' }, 'Activity'),
    evs.length ? [h('ul', { class: 'timeline' }, evs.slice(0, 6).map(item)),
      evs.length > 6 ? h('details', { class: 'given' }, h('summary', null, `${evs.length - 6} earlier`), h('ul', { class: 'timeline' }, evs.slice(6).map(item))) : null]
      : h('p', { class: 'note' }, 'Nothing yet. Every saved draft, check, follow-up, submission and decision is recorded here and in the audit log.'));
}

/* ============================================================== the record page
   A file reads as one record: a header with the next step, sections that fold away, and a rail
   with the file's properties, follow-ups, references, add-ons and what it connects to. A folded
   section stays folded on this browser. */
const SEC_CLOSED = new Set(local.get('sec_closed', ['sec-limits']));
// A section is a heading whose button folds its body (aria-expanded), so the heading keeps its
// role for screen readers; a details element's summary would read as a button and lose it.
function section(id, title, meta, body, opts) {
  const isOpen = !SEC_CLOSED.has(id);
  const bodyEl = h('div', { class: 'sec-body', id: id + '-body', hidden: !isOpen }, body);
  const btn = h('button', { type: 'button', class: 'sec-toggle', 'aria-expanded': String(isOpen), 'aria-controls': id + '-body' },
    h('span', { class: 'sec-caret', 'aria-hidden': 'true' }), h('span', { class: 'sec-title' }, title), meta ? h('span', { class: 'sec-meta' }, meta) : null);
  const d = h('section', { class: 'sec' + (isOpen ? ' open' : ''), id },
    h('div', { class: 'sec-head' }, h('h2', { class: 'h2 sec-h' }, btn), opts && opts.right ? h('span', { class: 'sec-right' }, opts.right) : null), bodyEl);
  d.setOpen = (v) => {
    btn.setAttribute('aria-expanded', String(v)); bodyEl.hidden = !v; d.classList.toggle('open', v);
    if (v) SEC_CLOSED.delete(id); else SEC_CLOSED.add(id);
    local.set('sec_closed', [...SEC_CLOSED]);
  };
  btn.addEventListener('click', () => d.setOpen(bodyEl.hidden));
  // The section bar focuses a section's heading: open the section it lands on.
  d.addEventListener('focusin', (e) => { if (e.target.matches('h2.sec-h')) d.setOpen(true); });
  return d;
}
const openSection = (id) => { const s = document.getElementById(id); if (s && s.setOpen) { s.setOpen(true); s.scrollIntoView({ block: 'start' }); } };
// The one thing to do next on a file, for the person looking at it.
function nextStep(f, w) {
  const b = currentBrief(f);
  const toBrief = () => openSection('sec-brief');
  // Writing a brief is one of the timed tasks: it starts here and ends when the brief is submitted.
  const work = () => { Timing.start('brief'); toBrief(); };
  if (!canWrite()) return w.state === 'approved' ? { label: 'Read the approved brief', run: toBrief } : null;
  if (w.state === 'new') return { label: 'Start the brief', run: work, primary: true };
  if (w.state === 'drafting') return { label: 'Continue the brief', run: work, primary: true };
  if (w.state === 'returned') return { label: b && b.author === myId() ? 'Revise the brief' : 'Read the note and revise', run: work, primary: true };
  if ((w.state === 'approved' || w.state === 'rejected') && !outcomeOf(f)) return { label: 'Record the outcome', primary: true, run: () => {
    openSection('sec-outcome'); S.outForm = { doc: f.docId, outcome: null, note: '', msg: '' }; Timing.start('outcome'); drawOutcome(f);
    const r0 = document.querySelector('#slot-outcome input[type=radio]'); if (r0) r0.focus(); } };
  if (w.state === 'submitted') return canApprove() && !(b && b.author === myId() && S.workflow.four_eyes !== false) ? { label: 'Review and decide', run: toBrief, primary: true } : { label: 'Waiting for an editor', run: toBrief };
  if (w.state === 'approved') return { label: 'Export the evidence pack', run: toBrief, primary: true };
  return { label: 'Read the decision', run: toBrief };
}
function fileActions(f, w) {
  const L = S.leads.get(f.docId), assignee = L && L.assignee;
  const ns = nextStep(f, w);
  return h('div', { class: 'rec-actions' },
    ns ? h('button', { class: 'btn' + (ns.primary ? ' primary' : ''), onclick: ns.run }, ns.label) : null,
    canWrite() ? h('button', { class: 'btn', onclick: () => { S.taskForm = f.docId; drawRail(f); const i = $('#task-text'); if (i) { i.scrollIntoView({ block: 'center' }); i.focus(); } } }, '+ Follow-up') : null,
    !canWrite() ? null : assignee === myId()
      ? h('button', { class: 'btn', onclick: () => assign(f, null) }, 'Release the file')
      : h('button', { class: 'btn', onclick: () => assign(f, myId()) }, assignee ? 'Take it over' : 'Take the file'),
    h('span', { class: 'spacer' }),
    h('button', { class: 'btn quiet small', onclick: () => go('corridor', f.iso2) }, `All files on ${inText(f.country)} →`),
    h('button', { class: 'btn quiet small', onclick: () => go('code', f.code) }, `HS ${fmtCode(f.code)} on every corridor →`));
}
function factsLine(f) {
  return `UK ${gbp(f.uk_trailing12_gbp)} · onward ${f.status === 'lead' ? usd(f.onward_usd) : 'not passed'} · a lead at ${f.runs_shown_as_lead || 0} of ${f.runs_shown} runs`;
}

/* ---------- the rail */
function properties(f, w) {
  const s = S.D.summary[0];
  const L = S.leads.get(f.docId), assignee = L && L.assignee;
  const open = tasksFor(f).filter((t) => !t.done && t.due).sort((a, b) => (a.due < b.due ? -1 : 1));
  const row = (k, v) => [h('dt', null, k), h('dd', null, v)];
  return h('div', { class: 'rail-card' },
    h('h2', { class: 'rail-h' }, 'Properties'),
    h('dl', { class: 'props' },
      row('Status', [stChip(w.state), selfChip(w)]),
      row('Signal', [sigTag(f), h('span', { class: 'muted small' }, f.status === 'lead' ? ' both checks pass' : ' UK check only')]),
      row('Owner', assignee ? whoLine(assignee) : h('span', { class: 'muted' }, 'Nobody yet')),
      row('Next due', open.length ? dueChip(open[0].due) : h('span', { class: 'muted' }, 'No follow-up with a date')),
      row('Corridor', h('button', { class: 'linkish', onclick: () => go('corridor', f.iso2) }, f.country)),
      row('Goods code', h('button', { class: 'linkish', onclick: () => go('code', f.code) }, `HS ${fmtCode(f.code)}`)),
      row('Run', `${s.run_label}; HMRC data to ${s.uk_data_to}`),
      row('Reference', h('span', { class: 'mono small' }, f.ref))));
}
// Official pages for this file's goods and route, from spec/references.json: each publisher's
// own page, with the date it was read. Never a case record.
const refTitle = (r, f) => String(r.title).replace('{code}', fmtCode(f.code)).replace('{country_poss}', possOf(f.country));
function references(f) {
  return h('div', { class: 'rail-card', id: 'rail-refs' },
    h('h2', { class: 'rail-h' }, 'References'),
    (S.spec.refs || []).length ? h('ul', { class: 'refs' }, S.spec.refs.filter((r) => /^https:\/\//.test(r.url)).map((r) => h('li', null, h('a', { href: r.url, target: '_blank', rel: 'noopener noreferrer' }, refTitle(r, f)), h('span', { class: 'muted small' }, `${r.by} · read ${dayLabel(r.read)}`)))) : h('p', { class: 'note' }, 'The reference list did not load.'),
    h('div', { class: 'row' }, h('button', { class: 'btn quiet small', onclick: () => copyText(f.ref, 'File reference copied.') }, 'Copy the file reference'),
      h('button', { class: 'btn quiet small', onclick: () => copyText(f.code, 'Goods code copied.') }, 'Copy the code')));
}
async function copyText(t, done) {
  try { await navigator.clipboard.writeText(t); say(done); } catch { say('Copying is not allowed here. The text is: ' + t); }
}
// Add-ons: where a deployment would send a file's work. Each shows what it would send; the demo
// sends nothing and connects nothing.
const ADDONS = [
  { id: 'tracker', name: 'Task tracker', eg: 'Jira, Planner or Asana', does: 'Sends the open follow-ups as tasks, with owners and due dates.' },
  { id: 'calendar', name: 'Calendar', eg: 'Outlook or Google Calendar', does: 'Puts each follow-up’s due date in a calendar, as an all-day entry.' },
  { id: 'message', name: 'Email or Teams', eg: 'a colleague or a channel', does: 'Sends a short summary of the file, never the brief’s text.' },
  { id: 'cms', name: 'Case management', eg: 'the team’s case system', does: 'Opens a case record for an approved file, with the evidence pack.' },
];
function addonPayload(id, f, w) {
  const s = S.D.summary[0];
  const open = tasksFor(f).filter((t) => !t.done);
  if (id === 'tracker') return open.length ? open.map((t) => `- [ ] ${t.text} (due ${t.due ? dayLabel(t.due) : 'no date'}; ${t.assignee ? 'has an owner' : 'no owner yet'}) · ${f.ref}`).join('\n') : 'No open follow-ups to send.';
  if (id === 'calendar') return open.filter((t) => t.due).length ? ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Diversion Radar//demo//EN',
    ...open.filter((t) => t.due).flatMap((t) => ['BEGIN:VEVENT', `UID:${t.id}@diversion-radar.demo`, `DTSTAMP:${nowIso().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z')}`, `DTSTART;VALUE=DATE:${t.due.replace(/-/g, '')}`, `SUMMARY:${t.text} (${f.ref})`, 'END:VEVENT']), 'END:VCALENDAR'].join('\n') : 'No follow-up has a due date.';
  if (id === 'message') return [`Subject: ${f.ref}, ${f.country} · HS ${fmtCode(f.code)}: ${STATE_LABEL[w.state] || w.state}`, '',
    `${f.status === 'lead' ? 'A lead' : 'A watch item'} at the ${s.run_label} run (HMRC data to ${s.uk_data_to}). ${factsLine(f)}.`,
    `Open follow-ups: ${open.length}.`, '', 'A rise in exports is a lead, not evidence of a breach.',
    'Contains public sector information licensed under the Open Government Licence v3.0.'].join('\n');
  return w.state === 'approved' ? JSON.stringify({ reference: f.ref, corridor: f.country, code: f.code, run: f.run, signal: f.status, state: w.state, attachments: [`${f.ref}-evidence.md`] }, null, 2)
    : 'Opens a case only for an approved file. This file is ' + (STATE_LABEL[w.state] || w.state).toLowerCase() + '.';
}
function addons(f, w) {
  return h('div', { class: 'rail-card', id: 'rail-addons' },
    h('h2', { class: 'rail-h' }, 'Add-ons'),
    h('ul', { class: 'addons' }, ADDONS.map((a) => {
      const open = S.addonOpen === f.docId + '/' + a.id;
      return h('li', null,
        h('div', { class: 'addon-top' }, h('span', null, h('b', null, a.name), h('span', { class: 'muted small' }, ` · ${a.eg}`)), h('span', { class: 'addon-st' }, 'Not connected')),
        h('span', { class: 'small' }, a.does),
        h('button', { class: 'btn quiet small', 'aria-expanded': String(open), onclick: () => { S.addonOpen = open ? null : f.docId + '/' + a.id; drawRail(f); } }, open ? 'Hide the preview' : 'Preview what it would send'),
        open ? h('pre', { class: 'addon-pre' }, addonPayload(a.id, f, w)) : null);
    })),
    h('p', { class: 'note' }, 'Demo: nothing is connected and nothing is sent. A deployment connects these to the organisation’s own systems, once the owner signs them off.'));
}
function drawRail(f) {
  const rail = $('#rec-rail');
  if (!rail || rail.dataset.doc !== f.docId) return;
  const w = workflowOf(f);
  // A follow-up being typed is not redrawn under the person typing it.
  const ae = document.activeElement;
  // A follow-up being written is not redrawn under the person writing it; the list above it is.
  const typing = rail.contains(ae) && ae.matches('input:not([type="checkbox"]), select, textarea') && ae.closest('.task-form');
  swap($('#slot-props'), properties(f, w));
  if (typing && $('#task-list')) { $('#task-list').replaceWith(taskList(f)); const m = $('#task-msg-slot'); if (m) swap(m, S.taskMsg ? h('p', { class: 'task-msg', role: 'alert' }, S.taskMsg) : null); }
  else swap($('#slot-tasks'), tasksCard(f));
  swap($('#slot-monitor'), monitorCard(f));
  swap($('#slot-addons'), addons(f, w));
  swap($('#slot-activity'), drawActivity(f));
}

/* ============================================================== follow-ups
   Small jobs on a file, each with an owner and a due date: a shared record (tasks/<id>) any
   Contributor can add to or tick off, audited like the checks. They are the file's to-do list,
   not part of the brief, and never a finding. */
const todayIso = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
const plusDays = (n) => { const d = new Date(); d.setDate(d.getDate() + n); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
function dayLabel(iso) { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || '')); return m ? `${+m[3]} ${MON[+m[2] - 1]} ${m[1]}` : ''; }
function dueChip(iso) {
  if (!iso) return h('span', { class: 'due' }, 'No date');
  const t = todayIso(), soon = plusDays(7);
  const k = iso < t ? 'late' : iso <= soon ? 'soon' : '';
  return h('span', { class: 'due ' + k }, (iso < t ? 'Overdue · ' : iso === t ? 'Due today · ' : k === 'soon' ? 'Due soon · ' : 'Due ') + dayLabel(iso));
}
const NEXT_RELEASE_ISO = '2026-11-12';
const TASK_TEMPLATES = [
  { id: 'release', text: () => (todayIso() <= NEXT_RELEASE_ISO ? `Recheck after HMRC adds ${NEXT_RELEASE.covers} on ${NEXT_RELEASE.date}` : 'Recheck after HMRC’s next monthly release'), due: () => (todayIso() <= NEXT_RELEASE_ISO ? NEXT_RELEASE_ISO : plusDays(7)) },
  { id: 'chpl', text: (f) => `Confirm where HS ${fmtCode(f.code)} sits on the Common High Priority Items List`, due: () => plusDays(5) },
  { id: 'mirror', text: (f) => `Compare with ${possOf(f.country)} own figures for imports from the UK`, due: () => plusDays(7) },
  { id: 'exporter', text: (f) => `Ask exporters on this route to run the exporter check for HS ${fmtCode(f.code)}`, due: () => plusDays(10) },
  { id: 'partner', text: () => 'Decide whether a partner agency should see this file', due: () => plusDays(14) },
];
function tasksFor(f) { return [...S.tasks.entries()].map(([id, d]) => Object.assign({ id }, d)).filter((t) => t.lead === f.docId).sort((a, b) => (a.done - b.done) || String(a.due || '9').localeCompare(String(b.due || '9')) || String(a.created_at).localeCompare(String(b.created_at))); }
function myOpenTasks() { const me = myId(); return [...S.tasks.entries()].map(([id, d]) => Object.assign({ id }, d)).filter((t) => !t.done && t.assignee === me); }
async function addTask(f, text, due, kind, assignee) {
  if (!canWrite() || !String(text || '').trim()) return false;
  // Text a person writes goes through the notes screen: no names of people or firms, no judging
  // words. It reaches the audit log, the add-ons' previews and the search, so it is checked first.
  if ((kind || 'custom') === 'custom') {
    const probs = Brief.screenNote(String(text), S.contexts[f.key] || null);
    if (probs.length) { S.taskMsg = probs.some((x) => x.code === 'possible_name') ? 'The follow-up may name a person or firm. Describe the step without naming anyone.' : 'The follow-up did not pass the screen: ' + probs.map((x) => x.code.replace(/_/g, ' ')).join(', ') + '.'; drawRail(f); return false; }
  }
  S.taskMsg = '';
  const doc = { lead: f.docId, run: f.run, series: f.series, text: String(text).trim().slice(0, 240), due: due || null, assignee: assignee === undefined ? myId() : assignee, kind: kind || 'custom', done: false, created_by: myId(), created_at: nowIso() };
  try {
    const id = newId('task');
    await S.store.set('tasks', id, doc);
    await audit('task_added', f, doc.text);
    say('Follow-up added.');
    return true;
  } catch (e) { writeFailed(e, 'the follow-up'); return false; }
}
async function setTask(f, id, patch, quiet) {
  if (!canWrite()) return;
  const cur = S.tasks.get(id); if (!cur) return;
  const next = Object.assign({}, patch);
  if ('done' in patch) { next.done_by = patch.done ? myId() : null; next.done_at = patch.done ? nowIso() : null; }
  try {
    await S.store.update('tasks', id, next);
    await audit('done' in patch ? (patch.done ? 'task_done' : 'task_reopened') : 'task_changed', f, cur.text);
    if (!quiet && 'done' in patch && patch.done) say('Follow-up done.', { label: 'Undo', run: () => setTask(f, id, { done: false }, true) });
  } catch (e) { writeFailed(e, 'the follow-up'); }
}
function peopleOptions(sel) {
  // Who can own a follow-up: people who can tick it off. A member the store marks inactive or a
  // viewer is left out (the hosted database refuses an inactive owner).
  const ids = isDemo() ? Object.keys(DEMO_PEOPLE).filter((id) => !DEMO_PEOPLE[id].view)
    : [...S.members].filter((id) => { const m = S.memberInfo && S.memberInfo.get(id); return !m || (m.active !== false && m.role !== 'viewer'); });
  resolvePeople(ids);
  return [h('option', { value: '', selected: !sel }, 'Nobody'), ids.map((id) => h('option', { value: id, selected: id === sel }, person(id).name))];
}
function taskRow(f, t, opts) {
  const editing = S.taskEdit === t.id;
  const can = canWrite();
  const fileLink = opts && opts.withFile ? h('button', { class: 'linkish small', onclick: openFile(f) }, `${f.country} · HS ${fmtCode(f.code)}`) : null;
  return h('li', { class: 'task' + (t.done ? ' done' : '') },
    h('input', { type: 'checkbox', checked: !!t.done, disabled: !can, 'aria-label': `Done: ${f.ref}, ${t.text}`, onchange: (e) => setTask(f, t.id, { done: e.target.checked }) }),
    h('div', { class: 'task-main' },
      h('span', { class: 'task-t' }, t.text),
      h('span', { class: 'task-meta' }, fileLink, t.done ? h('span', { class: 'muted small' }, `Done by ${person(t.done_by).name}${t.done_at ? ', ' + stamp(t.done_at) : ''}`) : [dueChip(t.due), h('span', { class: 'muted small' }, t.assignee ? person(t.assignee).name : 'No owner')],
        can && !t.done ? h('button', { class: 'linkish small', 'aria-expanded': String(editing), 'aria-label': `Change: ${f.ref}, ${t.text}`, onclick: () => { S.taskEdit = editing ? null : t.id; refresh(); } }, editing ? 'Close' : 'Change') : null),
      editing ? h('div', { class: 'task-edit' },
        h('label', { class: 'field' }, 'Due', h('input', { type: 'date', value: t.due || '', 'aria-label': `Due date: ${f.ref}, ${t.text}`, onchange: (e) => setTask(f, t.id, { due: e.target.value || null }) })),
        h('label', { class: 'field' }, 'Owner', h('select', { 'aria-label': `Owner: ${f.ref}, ${t.text}`, onchange: (e) => setTask(f, t.id, { assignee: e.target.value || null }) }, peopleOptions(t.assignee)))) : null));
}
function taskList(f) {
  const list = tasksFor(f), open = list.filter((t) => !t.done), done = list.filter((t) => t.done);
  resolvePeople(list.flatMap((t) => [t.assignee, t.done_by]).filter(Boolean));
  return h('div', { id: 'task-list' },
    h('div', { class: 'rail-hrow' }, h('h2', { class: 'rail-h' }, 'Follow-ups'), h('span', { class: 'muted small' }, `${open.length} open`)),
    open.length ? h('ul', { class: 'tasks' }, open.map((t) => taskRow(f, t))) : h('p', { class: 'note' }, canWrite() ? 'Nothing to follow up yet. Add the next steps for this file, each with an owner and a date.' : 'No open follow-ups.'),
    done.length ? h('details', { class: 'given' }, h('summary', null, `${done.length} done`), h('ul', { class: 'tasks' }, done.map((t) => taskRow(f, t)))) : null);
}
function tasksCard(f) {
  const list = tasksFor(f);
  const formOpen = S.taskForm === f.docId;
  const form = !canWrite() ? null : formOpen ? h('form', { class: 'task-form', onsubmit: async (e) => {
    e.preventDefault();
    const el = e.target, fd = new FormData(el);
    if (await addTask(f, fd.get('text'), fd.get('due') || null, 'custom', fd.get('owner') || null)) { const i = el.querySelector('#task-text'); if (i) { i.value = ''; i.focus(); } }
  } },
    h('span', { class: 'small muted' }, 'Common next steps, added with a date and you as owner:'),
    h('div', { class: 'tpl' }, TASK_TEMPLATES.filter((tp) => !list.some((t) => !t.done && t.kind === tp.id)).map((tp) => h('button', { type: 'button', class: 'tpl-chip', onclick: () => addTask(f, tp.text(f), tp.due(), tp.id) }, '+ ' + tp.text(f)))),
    h('label', { class: 'field' }, 'Or write one', h('input', { id: 'task-text', name: 'text', maxlength: '240', placeholder: 'What needs doing', autocomplete: 'off' })),
    h('div', { class: 'row' },
      h('label', { class: 'field' }, 'Due', h('input', { type: 'date', name: 'due', value: plusDays(7) })),
      h('label', { class: 'field' }, 'Owner', h('select', { name: 'owner' }, peopleOptions(myId())))),
    h('div', { id: 'task-msg-slot' }, S.taskMsg ? h('p', { class: 'task-msg', role: 'alert' }, S.taskMsg) : null),
    h('div', { class: 'row' }, h('button', { class: 'btn primary small', type: 'submit' }, 'Add'), h('button', { class: 'btn quiet small', type: 'button', onclick: () => { S.taskForm = null; S.taskMsg = ''; drawRail(f); } }, 'Done adding')))
    : h('button', { class: 'btn small', onclick: () => { S.taskForm = f.docId; drawRail(f); const i = $('#task-text'); if (i) i.focus(); } }, '+ Add a follow-up');
  return h('div', { class: 'rail-card', id: 'rail-tasks' }, taskList(f), h('div', { id: 'task-form-slot' }, form));
}
function drawTasks() {
  const v = $('#view-tasks');
  const all = [...S.tasks.entries()].map(([id, d]) => Object.assign({ id }, d)).map((t) => Object.assign(t, { f: S.files.find((x) => x.docId === t.lead) })).filter((t) => t.f);
  const scope = S.taskScope === 'all' ? 'all' : 'mine';
  const pool = all.filter((t) => scope === 'all' || t.assignee === myId());
  const open = pool.filter((t) => !t.done).sort((a, b) => String(a.due || '9').localeCompare(String(b.due || '9')));
  const t0 = todayIso(), wk = plusDays(7);
  const groups = [
    ['Overdue', open.filter((t) => t.due && t.due < t0)],
    ['Due in the next seven days', open.filter((t) => t.due && t.due >= t0 && t.due <= wk)],
    ['Later', open.filter((t) => t.due && t.due > wk)],
    ['No date', open.filter((t) => !t.due)],
  ];
  const done = pool.filter((t) => t.done).sort((a, b) => String(b.done_at).localeCompare(String(a.done_at))).slice(0, 30);
  resolvePeople(pool.flatMap((t) => [t.assignee, t.done_by]).filter(Boolean));
  const tab = (k, label, n) => h('button', { 'aria-pressed': String(scope === k), 'aria-label': label, onclick: () => { S.taskScope = k; drawTasks(); const b = document.querySelector(`#view-tasks .seg button[aria-label="${label}"]`); if (b) b.focus(); } }, `${label} (${n})`);
  swap(v,
    h('div', { class: 'head' },
      h('p', { class: 'eyebrow' }, 'Work'),
      h('h1', { class: 'h1' }, 'Follow-ups'),
      h('p', { class: 'lede' }, 'Open follow-ups by when they are due: yours, or everyone’s on every file. Tick one off here or open its file.')),
    h('div', { class: 'seg', role: 'group', 'aria-label': 'Whose follow-ups' }, tab('mine', 'Mine', all.filter((t) => !t.done && t.assignee === myId()).length), tab('all', 'Everyone’s', all.filter((t) => !t.done).length)),
    open.length ? groups.filter(([, ts]) => ts.length).map(([title, ts]) => section('tg-' + title.split(' ')[0].toLowerCase(), title, `${ts.length}`, h('ul', { class: 'tasks wide' }, ts.map((t) => taskRow(t.f, t, { withFile: true })))))
      : h('div', { class: 'card' }, h('p', { class: 'note' }, scope === 'mine' ? 'Nothing open is yours. Follow-ups you own on any file appear here, overdue first.' : 'No file has an open follow-up. Add one from a file’s rail.')),
    done.length ? section('tg-done', 'Done recently', `${done.length}`, h('ul', { class: 'tasks wide' }, done.map((t) => taskRow(t.f, t, { withFile: true })))) : null,
    h('p', { class: 'house' }, 'A follow-up is a step in checking a lead. A rise in exports is a lead, not evidence of a breach.'));
}

/* ============================================================== closing the loop (phase 6.5)
   What happened after a lead: an outcome from a fixed list once the brief is decided, a referral
   pack covering what OTSI's guidance asks a report to hold, and a decision record for a route
   put forward for an end-use controls decision, approved by a second editor. Each is a shared
   record (outcomes/<file>, enduse/<file>), audited. None of them is a finding: a person decides
   every step, and a lead is never the sole basis for a notice. */
const OUTCOMES = [
  ['no_action', 'No further action', 'Looked at; nothing to pursue now.'],
  ['watch', 'Keep on watch', 'Look again when HMRC publishes the next months.'],
  ['outreach', 'Guidance or outreach to the trade', 'Guidance for the trade in these goods on this route; never contact with a named exporter on this lead alone.'],
  ['referral', 'Referred on', 'Sent to another team or agency with a referral pack.'],
  ['enduse', 'Proposed for an end-use controls decision', 'Goes forward only with a decision record that has every check and a second editor’s approval; a person decides whether exporters are informed.'],
];
const OUTCOME_LABEL = Object.fromEntries(OUTCOMES.map(([k, l]) => [k, l]));
// A step beyond watching: what "worth a look" counts. A count of what teams did, not a test of the rule.
// A proposal for an end-use decision counts only once its decision record recommends putting the
// route forward and a second editor has approved it.
const STEPPED = new Set(['outreach', 'referral', 'enduse']);
const forwardApproved = (f) => { const R = S.enduse.get(f.docId); return !!(R && R.run === f.run && R.recommendation === 'forward' && R.approved_by); };
const stepped = (f, o) => STEPPED.has(o.outcome) && (o.outcome !== 'enduse' || forwardApproved(f));
const outcomeOf = (f) => { const o = S.outcomes.get(f.docId); return o && o.run === f.run ? o : null; };
// An outcome needs a decided brief. A rejected lead can only be closed or kept on watch.
const outcomeChoices = (w) => (w.state === 'approved' ? OUTCOMES : w.state === 'rejected' ? OUTCOMES.filter(([k]) => k === 'no_action' || k === 'watch') : []);
function screenText(f, text) {
  const probs = Brief.screenNote(String(text || ''), S.contexts[f.key] || null);
  if (!probs.length) return '';
  return probs.some((x) => x.code === 'possible_name') ? 'The text may name a person or firm. Describe it without naming anyone.' : 'The text did not pass the screen: ' + probs.map((x) => x.code.replace(/_/g, ' ')).join(', ') + '.';
}
async function saveOutcome(f, w, outcome, note) {
  if (!canWrite() || !outcomeChoices(w).some(([k]) => k === outcome)) return false;
  const text = String(note || '').trim().slice(0, 240);
  const bad = text ? screenText(f, text) : '';
  if (bad) { S.outForm.msg = bad; drawOutcome(f); return false; }
  const cur = outcomeOf(f);
  const R = S.enduse.get(f.docId);
  if (cur && cur.outcome === 'enduse' && outcome !== 'enduse' && R && R.run === f.run && R.recommendation === 'forward') { S.outForm.msg = 'A decision record puts this route forward. Change the record to “not put forward now” first.'; drawOutcome(f); return false; }
  const doc = { lead: f.docId, run: f.run, series: f.series, outcome, note: text, by: myId(), at: nowIso() };
  try {
    await upsert('outcomes', f.docId, doc);
    await audit(cur ? 'outcome_changed' : 'outcome_recorded', f, OUTCOME_LABEL[outcome] + (text ? ': ' + text : ''));
    S.outForm = null;
    Timing.end('outcome');
    say('Outcome recorded.');
    focusOutcome();
    return true;
  } catch (e) { writeFailed(e, 'the outcome'); return false; }
}
function outcomeForm(f, w) {
  const F = S.outForm;
  const choices = outcomeChoices(w);
  const save = h('button', { class: 'btn primary small', type: 'submit', disabled: !F.outcome }, 'Save the outcome');
  return h('form', { class: 'out-form', 'data-mode': 'edit', onsubmit: (e) => { e.preventDefault(); saveOutcome(f, w, F.outcome, F.note); } },
    h('fieldset', { class: 'out-choices' }, h('legend', null, 'What happened after this lead'),
      choices.map(([k, label, what]) => h('label', { class: 'out-choice' },
        h('input', { type: 'radio', name: 'outcome', value: k, checked: F.outcome === k, onchange: () => { F.outcome = k; save.disabled = false; } }),
        h('span', null, h('b', null, label), h('span', { class: 'muted small' }, what))))),
    h('label', { class: 'field' }, 'Note (optional, 240 characters at most)', h('textarea', { rows: 2, maxlength: '240', 'aria-label': 'Outcome note', placeholder: 'No names of people or firms.', oninput: (e) => { F.note = e.target.value; } }, F.note || '')),
    F.msg ? h('p', { class: 'task-msg', role: 'alert' }, F.msg) : null,
    h('div', { class: 'row' }, save, h('button', { class: 'btn quiet small', type: 'button', onclick: () => { S.outForm = null; Timing.cancel('outcome'); drawOutcome(f); } }, 'Cancel')));
}
function outcomePanel(f) {
  const w = workflowOf(f), o = outcomeOf(f);
  const editing = S.outForm && S.outForm.doc === f.docId;
  if (o) resolvePeople([o.by]);
  const open = () => { S.outForm = { doc: f.docId, outcome: o ? o.outcome : null, note: o ? o.note || '' : '', msg: '' }; Timing.start('outcome'); drawOutcome(f); const r = document.querySelector('#slot-outcome input[type=radio]'); if (r) r.focus(); };
  const parts = [];
  if (editing) parts.push(outcomeForm(f, w));
  else if (o) parts.push(h('div', { class: 'decision' }, h('b', null, OUTCOME_LABEL[o.outcome] || o.outcome), h('span', null, `Recorded by ${person(o.by).name}, ${stamp(o.at)}.`), o.note ? h('span', null, o.note) : null),
    canWrite() && outcomeChoices(w).length ? h('div', { class: 'row' }, h('button', { class: 'btn small', onclick: open }, 'Change the outcome')) : null);
  else if (!outcomeChoices(w).length) parts.push(h('p', { class: 'note' }, 'An outcome is recorded once the brief is approved or rejected.'));
  else parts.push(h('p', { class: 'note' }, 'Nothing recorded yet. Record what happened, so the track record counts what teams did with the radar’s leads, not only published cases.'),
    canWrite() ? h('div', { class: 'row' }, h('button', { class: 'btn primary small', onclick: open }, 'Record the outcome')) : null);
  if (w.state === 'approved') parts.push(referralCard(f, w));
  if (o && o.outcome === 'enduse') parts.push(enduseCard(f, w));
  return h('div', { id: 'outcome-panel', dataset: { doc: f.docId, mode: editing || (S.refForm && S.refForm.doc === f.docId) || (S.euForm && S.euForm.doc === f.docId) ? 'edit' : 'view' } }, parts);
}
function drawOutcome(f) {
  const slot = $('#slot-outcome');
  if (!slot) return;
  const cur = slot.firstElementChild, ae = document.activeElement;
  // A form being typed in is not redrawn under the person typing.
  if (cur && cur.dataset.mode === 'edit' && cur.dataset.doc === f.docId && slot.contains(ae) && ae.matches('textarea, input[type=text]')) return;
  swap(slot, outcomePanel(f));
  const o = outcomeOf(f), m = $('#sec-outcome .sec-meta');
  const t = o ? OUTCOME_LABEL[o.outcome] : 'not recorded';
  if (m) m.textContent = t; else { const s = $('#sec-outcome .sec-toggle'); if (s) s.append(h('span', { class: 'sec-meta' }, t)); }
}

// After a save the form goes, so focus returns to the section's heading.
const focusOutcome = () => requestAnimationFrame(() => requestAnimationFrame(() => { const b = $('#sec-outcome .sec-toggle'); if (b) b.focus({ preventScroll: true }); }));

/* ---------- the referral pack */
// The rules a referral may cite, each as a possibility for the receiving team to weigh.
const REF_RULES = [
  ['russia_trade', 'The Russia (Sanctions) (EU Exit) Regulations 2019 (SI 2019/855), Part 5: trade'],
  ['end_use', 'Sanctions end-use controls: The Sanctions (EU Exit) (Miscellaneous Amendments) Regulations 2026 (SI 2026/443), in force from 13 May 2026'],
  ['chpl', 'The goods are on the Common High Priority Items List'],
];
const REF_TOLD = [['unknown', 'Not recorded'], ['none', 'None yet'], ['yes', 'Yes: recorded in the team’s own system']];
const REF_TO = [['otsi', 'OTSI'], ['hmrc', 'HMRC'], ['team', 'Another team in this organisation'], ['partner', 'A partner agency']];
function referralCard(f, w) {
  const F = S.refForm && S.refForm.doc === f.docId ? S.refForm : null;
  if (!F) return h('div', { class: 'sub-card' }, h('h3', { class: 'h3' }, 'Referral pack'),
    h('p', { class: 'note' }, 'A pack for the team or agency a lead goes to, following the headings of OTSI’s guidance on reporting (16 December 2025) where a lead can fill them: the goods, the dates, the rules that may apply, the documents behind it and whether other authorities have been told. The UK link, any parties and the narrative of who did what come from the analyst’s own enquiries in a deployment: trade statistics do not identify exporters.'),
    h('div', { class: 'row' }, h('button', { class: 'btn small', disabled: !S.caps.downloads, onclick: () => { S.refForm = { doc: f.docId, to: 'otsi', rules: new Set(['russia_trade', 'chpl']), summary: '', told: 'unknown', msg: '' }; Timing.start('referral'); drawOutcome(f); } }, 'Prepare a referral pack')));
  return h('div', { class: 'sub-card' }, h('h3', { class: 'h3' }, 'Referral pack'),
    h('label', { class: 'field' }, 'Going to', h('select', { onchange: (e) => { F.to = e.target.value; } }, REF_TO.map(([k, l]) => h('option', { value: k, selected: F.to === k }, l)))),
    h('fieldset', { class: 'out-choices' }, h('legend', null, 'Rules that may apply (for the receiving team to weigh)'),
      REF_RULES.map(([k, l]) => h('label', { class: 'out-choice' }, h('input', { type: 'checkbox', checked: F.rules.has(k), onchange: (e) => { if (e.target.checked) F.rules.add(k); else F.rules.delete(k); } }), h('span', null, l)))),
    h('label', { class: 'field' }, 'Other authorities told', h('select', { onchange: (e) => { F.told = e.target.value; } }, REF_TOLD.map(([k, l]) => h('option', { value: k, selected: F.told === k }, l)))),
    h('label', { class: 'field' }, 'Why it is referred (600 characters at most)', h('textarea', { rows: 3, maxlength: '600', 'aria-label': 'Why it is referred', placeholder: 'What the analyst found and what they ask the receiving team to look at. No names of people or firms.', oninput: (e) => { F.summary = e.target.value; } }, F.summary)),
    F.msg ? h('p', { class: 'task-msg', role: 'alert' }, F.msg) : null,
    h('div', { class: 'row' }, h('button', { class: 'btn primary small', onclick: () => referralPack(f, w) }, 'Save the pack (.md)'), h('button', { class: 'btn quiet small', onclick: () => { S.refForm = null; Timing.cancel('referral'); drawOutcome(f); } }, 'Cancel')));
}
async function referralPack(f, w) {
  const F = S.refForm;
  if (!F || !S.caps.downloads) return;
  const summary = String(F.summary || '').trim();
  if (!summary) { F.msg = 'Say why it is referred.'; drawOutcome(f); return; }
  const bad = screenText(f, summary);
  if (bad) { F.msg = bad; drawOutcome(f); return; }
  const s = S.D.summary[0], m = S.D.manifest[0], b = currentBrief(f), o = outcomeOf(f), ctx = S.contexts[f.key] || {};
  const st = (S.checks.get(f.docId) || {}).items || {}, items = checkItemsFor(f, S.contexts[f.key]);
  const L = [`# Referral pack: ${f.ref}`, '',
    `Diversion Radar, ${s.run_label} run. Prepared ${stamp(nowIso())} by ${nameFor(myId())} for ${(REF_TO.find(([k]) => k === F.to) || [, 'the receiving team'])[1]}.`, '',
    '> This pack refers a lead for a person to assess. It is not a report of a breach, and it names no exporter. A rise in exports is a lead, not evidence of a breach.', '',
    'Headings follow OTSI’s guidance on reporting (What does good breach reporting look like?, OTSI blog, 16 December 2025) where a lead can fill them.', '',
    '## Why it is referred', '', summary, '',
    '## The goods', '', `HS ${fmtCode(f.code)}: ${f.description}. ` + (f.status === 'lead' ? `A lead: UK exports to ${f.country} and ${possOf(f.country)} own exports of the code to Russia rose together.` : `A watch item: UK exports to ${f.country} rose; the onward check did not pass.`), '',
    '## When', '', `UK exports: the 12 published months to ${s.uk_data_to}, ${gbp(f.uk_trailing12_gbp)}, ${ratio(f.uk_ratio)} the 2019-21 annual average of ${gbp(f.uk_baseline_gbp)}.`,
    f.status === 'lead' ? `Onward: ${possOf(f.country)} exports of the code to Russia, ${usd(f.onward_usd)} (${f.onward_check}), as ${inText(f.country)} reports it to UN Comtrade.` : 'Onward check not passed.',
    f.runs_shown_as_lead ? `A lead at ${f.runs_shown_as_lead} of the ${f.runs_shown} monthly runs that can be shown, the first in ${monthLabel(f.first_lead_shown)}.` : '', '',
    '## The UK link and any parties', '', 'Not in this pack. The radar works on aggregate trade statistics, which do not identify exporters, consignees or shipments. In a deployment the analyst adds what their own enquiries found, under the organisation’s own powers and records.', '',
    '## Other authorities told', '', (REF_TOLD.find(([k]) => k === F.told) || [, 'Not recorded'])[1] + '.', '',
    '## Rules that may apply', '', ...(F.rules.size ? REF_RULES.filter(([k]) => F.rules.has(k)).map(([, l]) => `- ${l}`) : ['- None selected.']), '', 'For the receiving team to weigh; the radar applies no rule to any party.', '',
    '## What was checked', '', ...(items.length ? items.map((it) => { const c = st[it.id] || {}; return `- [${c.state === 'done' ? 'x' : c.state === 'na' ? '-' : ' '}] ${it.q}`; }) : ['- No checks recorded.']), '',
    '## Supporting documents', '',
    b ? `- The approved brief, version ${b.version || 1}, SHA-256 ${b.sha256}; its evidence pack is ${f.ref}-evidence.md.` : '- No approved brief.',
    o ? `- Outcome recorded: ${OUTCOME_LABEL[o.outcome]}, ${stamp(o.at)}.` : '- No outcome recorded yet.',
    `- Data: HMRC overseas trade statistics to ${s.uk_data_to}; UN Comtrade. Built from commit ${m.source_commit}${m.source_dirty ? ', with uncommitted changes' : ''}. Data files and their SHA-256:`,
    ...Object.entries(m.files).map(([k, v]) => `  - ${k}: ${v}`), '',
    '---', '', `${ctx.ogl_line || 'Contains public sector information licensed under the Open Government Licence v3.0.'} https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/`, 'Onward figures: UN Comtrade.'];
  const out = L.filter((x, i, a) => !(x === '' && a[i - 1] === '')).join('\n') + '\n';
  try {
    await S.caps.downloads.save({ filename: `${f.ref}-referral.md`, data: out });
    await audit('referral_exported', f, (REF_TO.find(([k]) => k === F.to) || [, ''])[1]);
    S.refForm = null;
    Timing.end('referral');
    drawOutcome(f);
  } catch (e) { if (e && e.code !== 'declined') banner('dl', 'warn', 'The file could not be saved from this view.'); }
}

/* ---------- the end-use controls decision record */
// What a team records before a route is put to the people who decide whether exporters are
// informed. Putting a route forward needs every check, including information beyond the trade
// statistics: a lead is never the sole basis for a notice. A second editor approves the record.
const EU_CHECKS = [
  ['onward', 'The corridor’s own exports to Russia were checked in its published figures'],
  ['chpl', 'The code was checked against the Common High Priority Items List'],
  ['display', 'No figure in the record points at one exporter (the display rule)'],
  ['cases', 'Published enforcement cases on this route were read'],
  ['partners', 'Partner teams were asked whether they hold anything on this route'],
  ['beyond', 'Information beyond the trade statistics is recorded in the team’s own system'],
];
const EU_REC = [['forward', 'Put forward for a decision on informing exporters of these goods to this destination'], ['not_now', 'Not put forward now']];
const enduseOf = (f) => { const r = S.enduse.get(f.docId); return r && r.run === f.run ? r : null; };
function enduseCard(f, w) {
  const R = enduseOf(f), F = S.euForm && S.euForm.doc === f.docId ? S.euForm : null;
  if (R) resolvePeople([R.recorded_by, R.approved_by].filter(Boolean));
  const head = h('h3', { class: 'h3' }, 'End-use controls decision record');
  if (F) {
    return h('div', { class: 'sub-card' }, head,
      h('label', { class: 'field' }, 'Why this route (600 characters at most)', h('textarea', { rows: 3, maxlength: '600', 'aria-label': 'Why this route', placeholder: 'What was found and why it matters. No names of people or firms.', oninput: (e) => { F.reasons = e.target.value; } }, F.reasons)),
      h('fieldset', { class: 'out-choices' }, h('legend', null, 'Checked'),
        EU_CHECKS.map(([k, l]) => h('label', { class: 'out-choice' }, h('input', { type: 'checkbox', checked: F.checks.has(k), onchange: (e) => { if (e.target.checked) F.checks.add(k); else F.checks.delete(k); } }), h('span', null, l)))),
      h('fieldset', { class: 'out-choices' }, h('legend', null, 'Recommendation'),
        EU_REC.map(([k, l]) => h('label', { class: 'out-choice' }, h('input', { type: 'radio', name: 'eu-rec', checked: F.rec === k, onchange: () => { F.rec = k; } }), h('span', null, l)))),
      F.msg ? h('p', { class: 'task-msg', role: 'alert' }, F.msg) : null,
      h('div', { class: 'row' }, h('button', { class: 'btn primary small', onclick: () => saveEnduse(f) }, 'Save the record'), h('button', { class: 'btn quiet small', onclick: () => { S.euForm = null; drawOutcome(f); } }, 'Cancel')));
  }
  const startForm = () => { S.euForm = { doc: f.docId, reasons: R ? R.reasons : '', checks: new Set(R ? R.checks : []), rec: R ? R.recommendation : 'not_now', msg: '' }; drawOutcome(f); };
  if (!R) return h('div', { class: 'sub-card' }, head,
    h('p', { class: 'note' }, 'Before a route goes to the people who decide whether exporters are informed, record why, what was checked and the team’s recommendation. A second editor approves it. Putting a route forward needs information beyond the trade statistics: a lead is never the sole basis for a notice.'),
    canWrite() ? h('div', { class: 'row' }, h('button', { class: 'btn small', onclick: startForm }, 'Start the record')) : null);
  const mine = (R.recorders || [R.recorded_by]).includes(myId());
  return h('div', { class: 'sub-card' }, head,
    h('div', { class: 'decision' }, h('b', null, (EU_REC.find(([k]) => k === R.recommendation) || [, R.recommendation])[1]),
      h('span', null, `Recorded by ${person(R.recorded_by).name}, ${stamp(R.recorded_at)}. ${R.approved_by ? `Approved by ${person(R.approved_by).name}, ${stamp(R.approved_at)}.` : 'Waiting for a second editor.'}`),
      h('span', null, R.reasons)),
    h('ul', { class: 'plain small' }, EU_CHECKS.map(([k, l]) => h('li', null, (R.checks.includes(k) ? '✓ ' : '○ ') + l))),
    h('div', { class: 'row' },
      !R.approved_by && canApprove() && !mine ? h('button', { class: 'btn primary small', onclick: () => approveEnduse(f) }, 'Approve the record') : null,
      !R.approved_by && mine ? h('span', { class: 'muted small' }, 'You wrote part of it, so another editor approves it.') : null,
      canWrite() ? h('button', { class: 'btn quiet small', onclick: startForm }, 'Change the record') : null));
}
async function saveEnduse(f) {
  const F = S.euForm;
  if (!F || !canWrite()) return;
  const reasons = String(F.reasons || '').trim().slice(0, 600);
  if (!reasons) { F.msg = 'Say why this route.'; drawOutcome(f); return; }
  const bad = screenText(f, reasons);
  if (bad) { F.msg = bad; drawOutcome(f); return; }
  if (F.rec === 'forward' && EU_CHECKS.some(([k]) => !F.checks.has(k))) { F.msg = 'Putting a route forward needs every check, including information beyond the trade statistics. A lead is never the sole basis for a notice.'; drawOutcome(f); return; }
  // Everyone who wrote the content since the last approval: none of them may approve it.
  const prev = enduseOf(f), recorders = prev && !prev.approved_by ? [...new Set([...(prev.recorders || [prev.recorded_by]), myId()])] : [myId()];
  const doc = { lead: f.docId, run: f.run, series: f.series, reasons, checks: EU_CHECKS.map(([k]) => k).filter((k) => F.checks.has(k)), recommendation: F.rec, recorded_by: myId(), recorded_at: nowIso(), recorders, approved_by: null, approved_at: null };
  try {
    await upsert('enduse', f.docId, doc);
    await audit('enduse_recorded', f, (EU_REC.find(([k]) => k === F.rec) || [, F.rec])[1]);
    S.euForm = null; say('Decision record saved; a second editor approves it.'); drawOutcome(f); focusOutcome();
  } catch (e) { writeFailed(e, 'the decision record'); }
}
async function approveEnduse(f) {
  const R = enduseOf(f);
  if (!R || R.approved_by || !canApprove() || (R.recorders || [R.recorded_by]).includes(myId())) return;
  try {
    await S.store.update('enduse', f.docId, { approved_by: myId(), approved_at: nowIso() });
    await audit('enduse_approved', f, (EU_REC.find(([k]) => k === R.recommendation) || [, R.recommendation])[1]);
    say('Decision record approved.'); drawOutcome(f); focusOutcome();
  } catch (e) { writeFailed(e, 'the approval'); }
}
// The overview's card: what the run's leads led to, as recorded by the team.
function outcomesCard(id) {
  const rec = S.files.map((f) => [f, outcomeOf(f)]).filter(([, o]) => o);
  const decided = S.files.filter((f) => ['approved', 'rejected'].includes(workflowOf(f).state)).length;
  const n = (k) => rec.filter(([, o]) => o.outcome === k).length;
  const stepN = rec.filter(([f, o]) => stepped(f, o)).length;
  return h('section', { class: 'card ov-card', id: id || 'ov-outcomes' },
    h('div', { class: 'card-head' }, h('h2', { class: 'h2' }, 'What the leads led to'), h('span', { class: 'note' }, `${rec.length} recorded of ${decided} decided`)),
    rec.length ? [
      h('div', { class: 'ov-list' }, OUTCOMES.map(([k, label]) => h('div', { class: 'ov-row static' }, h('span', { class: 'ov-main' }, h('span', { class: 'ov-title' }, label)), h('span', { class: 'ov-side' }, h('b', null, String(n(k))))))),
      h('p', { class: 'note' }, `A step beyond watching in ${stepN} of ${rec.length} recorded (an end-use proposal counts once its decision record is approved): a count of what the team did with the leads, not a test of the rule [Certain].`)]
      : h('p', { class: 'ov-empty' }, 'No outcome recorded yet. Once a brief is decided, record what happened on its file, so the track record can count what teams did with the leads.'));
}

/* ---------- task timings for a pilot
   How long three common tasks take, in minutes and in steps, logged in this browser only: no
   file, no text, no person, just the task, when it started and ended, and how many clicks and
   key presses it took. The pilot compares these with the same tasks done without the tool. */
const TIMED = { brief: 'Write a brief and send it for approval', outcome: 'Record an outcome', referral: 'Prepare a referral pack' };
const Timing = (() => {
  const active = new Map();
  const log = () => { const v = local.get('timings', []); return Array.isArray(v) ? v : []; };
  document.addEventListener('pointerdown', () => active.forEach((a) => { a.steps += 1; }), true);
  document.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') active.forEach((a) => { a.steps += 1; }); }, true);
  return {
    start(task) { if (TIMED[task] && !active.has(task)) active.set(task, { at: Date.now(), steps: 0 }); },
    cancel(task) { active.delete(task); },
    end(task) {
      const a = active.get(task); if (!a) return;
      active.delete(task);
      const rows = log().concat([{ task, started: new Date(a.at).toISOString(), minutes: Math.round((Date.now() - a.at) / 600) / 100, steps: a.steps }]).slice(-500);
      local.set('timings', rows);
    },
    rows: log,
    clear() { local.set('timings', []); active.clear(); },
  };
})();
const median = (xs) => { const s = xs.slice().sort((a, b) => a - b); return s.length ? (s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : null; };
function drawTimings() {
  const v = $('#view-timings'), rows = Timing.rows();
  const fmtN = (x, d) => (x === null ? 'none yet' : x.toFixed(d));
  swap(v,
    h('div', { class: 'head' }, h('p', { class: 'eyebrow' }, 'Reference'), h('h1', { class: 'h1' }, 'Pilot timings'),
      h('p', { class: 'lede' }, 'How long three common tasks take here, in minutes and in steps (clicks and key presses), for comparing with the same tasks done the usual way in a pilot.')),
    h('div', { class: 'card' }, h('div', { class: 'scroll' }, h('table', null,
      h('thead', null, h('tr', null, h('th', null, 'Task'), h('th', { class: 'num' }, 'Times done'), h('th', { class: 'num' }, 'Median minutes'), h('th', { class: 'num' }, 'Median steps'))),
      h('tbody', null, Object.entries(TIMED).map(([k, label]) => { const r = rows.filter((x) => x.task === k); return h('tr', null, h('td', null, label), h('td', { class: 'num' }, String(r.length)), h('td', { class: 'num' }, fmtN(median(r.map((x) => x.minutes)), 1)), h('td', { class: 'num' }, fmtN(median(r.map((x) => x.steps)), 0))); })))),
      h('p', { class: 'note' }, 'Kept in this browser only, never in the shared store: no file, no text and no person is logged, only the task, its start, its minutes and its steps. A task starts at its first button (Start the brief, Record the outcome, Prepare a referral pack) and ends when it is sent, saved or exported; one cancelled is not counted [Certain].'),
      h('div', { class: 'row' },
        h('button', { class: 'btn small', disabled: !S.caps.downloads || !rows.length, onclick: async () => {
          const csv = ['task,started,minutes,steps', ...rows.map((r) => `${r.task},${r.started},${r.minutes},${r.steps}`)].join('\n') + '\n';
          try { await S.caps.downloads.save({ filename: 'radar-pilot-timings.csv', data: csv }); } catch (e) { if (e && e.code !== 'declined') banner('dl', 'warn', 'The file could not be saved from this view.'); }
        } }, 'Timings (.csv)'),
        h('button', { class: 'btn quiet small', disabled: !rows.length, onclick: () => { Timing.clear(); drawTimings(); say('Timings cleared in this browser.'); } }, 'Clear'))),
    h('p', { class: 'house' }, 'A measure of the work, not of anyone doing it.'));
}
// Lessons from the published cases: what the radar showed on each case route the display rule
// lets the workspace show, in the backtest's own figures, and the general point each one makes.
function caseLessonsCard() {
  const shown = S.D.tests.filter((t) => t.shown), held = S.D.tests.length - shown.length;
  const lesson = (t) => {
    const what = `${t.case_id}, ${t.corridor}, HS ${t.codes}`;
    if (t.run2_outcome === 'hit' && t.run2_on_the_day === 'yes') return [what, `With the monthly check, a lead from ${monthLabel(t.run2_first_lead)}, ${t.run2_lead_time_months} ${t.run2_lead_time_months === 1 ? 'month' : 'months'} before the first public action (${t.first_public_action}), and still a lead on the day [Certain].`, 'A lead can come close to the action: look at a route when it first appears, not after it has held for a while [Likely].'];
    if (t.run2_outcome === 'hit') return [what, `With the monthly check, a lead from ${monthLabel(t.run2_first_lead)}, ${t.run2_lead_time_months} months before the first public action (${t.first_public_action}); on the day: ${t.run2_on_the_day} [Certain].`, 'A lead that stops is not cleared: record an outcome for it rather than letting it drop [Likely].'];
    if (t.run2_outcome === 'miss') return [what, `No lead on these codes before the first public action (${t.first_public_action}) [Certain].`, 'Codes mapped from a case’s description of the goods can miss its route; the primary codes for the same case are the better test [Likely].'];
    return [what, `Annual check: ${t.run1_outcome}; with monthly: ${t.run2_outcome} [Certain].`, ''];
  };
  return h('div', { class: 'card', id: 'case-lessons' }, h('h2', { class: 'h2' }, 'Lessons from the published cases'),
    h('p', { class: 'note' }, `What the radar showed on each case route the display rule lets the workspace show, and the point it makes for working a lead. ${held} ${held === 1 ? 'test is' : 'tests are'} not shown under the display rule. Official references only; no party is named.`),
    h('ul', { class: 'plain' }, shown.map((t) => { const [w, fact, point] = lesson(t); return h('li', null, h('b', null, `${t.test_id} · ${w}. `), fact, point ? h('span', { class: 'muted' }, ' ' + point) : null); })));
}

/* ============================================================== corridor and code pages
   One click through from the map, a file or the search: every file the workspace shows on a
   corridor, or on a goods code across corridors. Held-back series are not counted here. */
function recordList(files, title) {
  return h('div', { class: 'ov-list' }, files.map((f) => {
    const w = workflowOf(f);
    return h('button', { class: 'ov-row', onclick: openFile(f), 'aria-label': `Open ${f.ref}` },
      h('span', { class: 'ov-main' }, h('span', { class: 'ov-title' }, title(f)), h('span', { class: 'ov-sub' }, f.description)),
      h('span', { class: 'ov-side' }, sigTag(f), stChip(w.state), h('span', { class: 'ov-num' }, gbp(f.uk_trailing12_gbp)), deltaChip(f, true)));
  }));
}
function groupPage(v, eyebrow, title, lede, files, rowTitle, other, pre) {
  const s = S.D.summary[0];
  const leads = files.filter((f) => f.status === 'lead').length;
  const open = files.flatMap((f) => tasksFor(f)).filter((t) => !t.done).length;
  const decided = files.filter((f) => ['approved', 'rejected'].includes(workflowOf(f).state)).length;
  swap(v,
    h('div', { class: 'head' }, h('p', { class: 'eyebrow' }, eyebrow), h('h1', { class: 'h1' }, title), h('p', { class: 'lede' }, lede)),
    h('div', { class: 'statline' },
      h('span', null, h('b', null, String(files.length)), files.length === 1 ? ' file shown' : ' files shown'),
      h('span', null, h('b', null, String(leads)), leads === 1 ? ' lead' : ' leads'),
      h('span', null, h('b', null, gbp(files.reduce((t, f) => t + (+f.uk_trailing12_gbp || 0), 0))), ` UK exports on the files shown, 12 months to ${s.uk_data_to}`),
      h('span', null, h('b', null, String(open)), ' open follow-ups'),
      h('span', null, h('b', null, String(decided)), ' decided')),
    section(pre + '-files', 'Files', null, recordList(files, rowTitle)),
    other,
    h('p', { class: 'note' }, 'Only series the display rule lets the workspace show are listed or added up; a held-back series is not counted here [Certain].'),
    h('p', { class: 'house' }, 'A rise in exports is a lead, not evidence of a breach.'));
}
function drawCorridor() {
  const files = S.files.filter((f) => f.iso2 === S.corrKey);
  if (!files.length) return go('map');
  const c = files[0].country;
  const codes = files.map((f) => f.code);
  const sameCodes = S.files.filter((f) => codes.includes(f.code) && f.iso2 !== S.corrKey);
  groupPage($('#view-corridor'), 'Corridor', c, `UK exports of high-priority goods to ${inText(c)}, and ${possOf(c)} own exports of the same goods to Russia.`, files, (f) => `HS ${fmtCode(f.code)}`,
    sameCodes.length ? section('corr-related', 'The same goods on other corridors', `${sameCodes.length}`, recordList(sameCodes, (f) => `${f.country} · HS ${fmtCode(f.code)}`)) : null, 'corr');
}
function drawCode() {
  const files = S.files.filter((f) => f.code === S.codeKey);
  if (!files.length) return go('map');
  groupPage($('#view-code'), 'Goods code', `HS ${fmtCode(S.codeKey)}`, String(files[0].description).replace(/\.$/, '') + '. Every corridor the workspace shows on this code.', files, (f) => f.country,
    h('p', { class: 'note' }, 'The dashboard draws these corridors together, each as a multiple of its own UK line, under How each signal built up, grouped by goods code.'), 'code');
}

/* ============================================================== team and access */
function drawTeam() {
  const v = $('#view-team');
  const roles = [
    ['Viewer', 'Reads everything shared; exports evidence packs, the audit log and their own exporter screen results.'],
    ['Contributor', 'Also takes files, drafts and submits briefs, works the checks and the follow-ups, and proposes outcomes on synthetic cases.'],
    ['Editor', 'Also approves, returns, rejects and reopens briefs and outcomes, and turns four-eyes on or off.'],
    ['Owner', 'Also adds people and changes their roles.'],
  ];
  const people = isDemo() ? Object.entries(DEMO_PEOPLE).map(([id, p]) => ({ id, name: p.name, role: p.role })) : [...S.members].map((id) => ({ id, name: person(id).name, role: id === S.me.id ? S.me.role : '' }));
  if (!isDemo()) resolvePeople([...S.members]);
  const owner = isDemo() ? !!DEMO_PEOPLE[demoMe()].owner : S.me.isOwner;
  swap(v,
    h('div', { class: 'head' }, h('p', { class: 'eyebrow' }, 'Reference'), h('h1', { class: 'h1' }, 'Team and access'),
      h('p', { class: 'lede' }, 'Who works in this workspace, at which role, and what each role can do.')),
    section('team-people', 'People', `${people.length}`, h('div', { class: 'scroll' }, h('table', null,
      h('thead', null, h('tr', null, h('th', null, 'Person'), h('th', null, 'Role'), h('th', { class: 'num' }, 'Files held'), h('th', { class: 'num' }, 'Open follow-ups'))),
      h('tbody', null, people.map((p) => h('tr', null, h('td', null, whoLine(p.id)), h('td', null, p.role || h('span', { class: 'muted' }, 'Not known')),
        h('td', { class: 'num' }, String(S.files.filter((f) => (S.leads.get(f.docId) || {}).assignee === p.id).length)),
        h('td', { class: 'num' }, String([...S.tasks.values()].filter((t) => !t.done && t.assignee === p.id).length)))))))),
    section('team-roles', 'Roles', null, h('dl', { class: 'ov-dl' }, roles.map(([r, d]) => [h('dt', null, r), h('dd', null, d)]))),
    section('team-invite', 'Adding people', null, [
      h('p', { class: 'note' }, HOSTED ? 'The owner invites people by work email in the project’s authentication settings and sets each role in the members table; new sign-ups are off, so only invited people can sign in (hosted/README.md).'
        : isDemo() ? 'In this demo the people and roles are fixed. In the hosted version the owner invites people by work email, sign-in is by a one-time code, and only invited people can sign in [Certain].'
          : 'Inside Claude, access follows the artifact’s sharing levels: Viewer, Contributor, Editor and owner.'),
      owner ? h('div', { class: 'row' }, h('button', { class: 'btn', disabled: true, title: 'Not available in this version' }, 'Invite someone'), h('span', { class: 'muted small' }, 'Off in this version: nothing is sent.')) : null]),
    h('p', { class: 'house' }, 'Every change to a file is in the audit log, with who made it and when.'));
}

/* ============================================================== sign-in (demo) */
const session = {
  get() { try { return sessionStorage.getItem('dr.signed_in'); } catch { return S.signedIn || null; } },
  set(v) { S.signedIn = v; try { if (v) sessionStorage.setItem('dr.signed_in', v); else sessionStorage.removeItem('dr.signed_in'); } catch { /* storage unavailable */ } },
};
function landingFor(id) {
  const p = DEMO_PEOPLE[id];
  if (p.edit && filesIn('review').length) return () => goList('review');
  if (!p.view && myOpenTasks().length) return () => go('tasks');
  return () => go('overview');
}
function signIn(id, land) {
  S.demoAs = id; local.set('demo_as', id); session.set(id);
  $('#portal').hidden = true; document.body.classList.remove('portal-on');
  portalInert(false);
  refresh();
  // The first sign-in opens where that role's work is; switching person keeps the page.
  if (land) landingFor(id)();
  say(`Signed in as ${DEMO_PEOPLE[id].name}, ${DEMO_PEOPLE[id].role}.`);
  // Focus goes to the page's heading, not the body the sign-in screen leaves behind.
  requestAnimationFrame(() => { const t = document.querySelector('.view:not([hidden]) h1'); if (t) { if (!t.hasAttribute('tabindex')) t.setAttribute('tabindex', '-1'); t.focus({ preventScroll: true }); } });
}
function showPortal(land) {
  const s = S.D.summary && S.D.summary[0];
  const el = $('#portal');
  const cur = session.get();
  swap(el, h('div', { class: 'portal-in' },
    h('section', { class: 'portal-brand' },
      h('div', { class: 'portal-mark' }, h('span', { class: 'fs-mark', 'aria-hidden': 'true' }), h('span', null, h('b', null, 'Diversion Radar'), h('span', null, 'Analyst workspace'))),
      h('h1', { class: 'portal-h' }, 'Leads on trade routes, for a person to check.'),
      h('p', null, 'Monthly leads where UK exports of high-priority goods to a third country rose, and that country’s own exports of the same goods to Russia rose too.'),
      s ? h('ul', { class: 'portal-facts' },
        h('li', null, h('b', null, s.run_label), ' run'), h('li', null, 'HMRC data to ', h('b', null, s.uk_data_to)), h('li', null, h('b', null, String(s.leads_shown)), ' leads and ', h('b', null, String(s.watch_shown)), ' watch items to work')) : null,
      h('p', { class: 'portal-house' }, 'A rise in exports is a lead, not evidence of a breach.')),
    h('section', { class: 'portal-card', 'aria-labelledby': 'portal-title' },
      h('h2', { id: 'portal-title' }, 'Sign in'),
      h('p', { class: 'muted' }, 'Demo: choose a synthetic person. There is no password, and what you do stays in this tab.'),
      h('ul', { class: 'portal-people' }, Object.entries(DEMO_PEOPLE).map(([id, p]) => h('li', null, h('button', { class: 'portal-person' + (cur === id ? ' on' : ''), 'aria-current': cur === id ? 'true' : null, 'data-person': id, onclick: () => signIn(id, land) },
        h('span', { class: 'who-av', 'aria-hidden': 'true' }, p.initials),
        h('span', { class: 'pp-t' }, h('span', { class: 'pp-n' }, h('b', null, p.name), h('span', { class: 'pp-role' }, p.role)), h('span', { class: 'pp-d' }, p.does)))))),
      h('div', { class: 'portal-or' }, h('span', null, 'In a deployment')),
      h('label', { class: 'field' }, 'Work email', h('input', { type: 'email', disabled: true, placeholder: 'Your work email' })),
      h('button', { class: 'btn', disabled: true }, 'Send me a sign-in code'),
      h('p', { class: 'note' }, 'The hosted version signs people in with a one-time code sent to their work email. Only people the owner has invited can sign in, and the owner sets each role [Certain].'))));
  el.hidden = false; document.body.classList.add('portal-on');
  portalInert(true);
  // Opened to switch person, Escape keeps the one signed in.
  el.onkeydown = (e) => { if (e.key === 'Escape' && DEMO_PEOPLE[session.get()]) { e.stopPropagation(); signIn(session.get(), false); } };
  const first = el.querySelector('.portal-person.on') || el.querySelector('.portal-person');
  if (first) first.focus();
}
// While the sign-in screen is open, nothing behind it can be reached by keyboard or pointer.
function portalInert(on) {
  for (const n of document.body.children) { if (n.id === 'portal' || n.tagName === 'SCRIPT' || n.tagName === 'STYLE') continue; if (on) n.setAttribute('inert', ''); else n.removeAttribute('inert'); }
}
// From the live workspace: try the roles in this tab, on a store of its own. Nothing done here
// reaches the shared store; a reload goes back to it.
function enterDemo() {
  unsubs.forEach((u) => { try { u(); } catch { /* closed */ } }); unsubs = [];
  for (const us of memberUnsubs.values()) us.forEach((u) => { try { u(); } catch { /* closed */ } });
  memberUnsubs.clear(); seq.clear();
  Object.assign(S, { members: new Set(), memberIds: new Set(), byMember: { briefs: new Map(), decisions: new Map(), audit: new Map() },
    briefs: new Map(), decisions: new Map(), audit: [], verified: new Map(), leads: new Map(), checks: new Map(), tasks: new Map(), outcomes: new Map(), enduse: new Map(), outForm: null, refForm: null, euForm: null, monitorDec: new Map(), monOpen: null,
    lessons: new Map(), lessonDecisions: new Map(), lessonVerified: new Map(), readOnly: false });
  registered = false;
  S.store = memoryStore(); S.storeState = 'demo';
  banner('demo', 'warn', 'Demo roles: this tab now works on a store of its own, so nothing done here reaches the shared workspace. Reload the page to go back to it.');
  subscribeAll();
  showPortal(false);
}

/* ============================================================== brief panel (filled by Brief below) */
function drawBriefPanel(f, w) {
  return Brief.panel(f, w);
}

/* ============================================================== exporter screen */
const EX_FIELDS = [
  ['destination', 'Destination country', ['destination', 'country', 'dest', 'country of destination', 'destination country', 'ship to country', 'ship_to_country']],
  ['code', 'Commodity code', ['commodity_code', 'commodity code', 'hs code', 'hs_code', 'tariff code', 'cn8', 'cn code', 'code', 'comm code']],
  ['month', 'Month (YYYY-MM)', ['month', 'period', 'date', 'ship date', 'invoice date', 'shipment month', 'despatch date']],
  ['value', 'Value (GBP)', ['value_gbp', 'value', 'value gbp', 'amount', 'gbp', 'invoice value', 'net value', 'value (gbp)']],
  ['customer', 'Customer reference', ['customer_ref', 'customer ref', 'customer', 'customer id', 'consignee ref', 'buyer', 'account']],
];
function parseCSV(text) {
  text = text.replace(/^﻿/, '');
  const first = text.split(/\r?\n/, 1)[0] || '';
  const sep = (first.match(/;/g) || []).length > (first.match(/,/g) || []).length ? ';' : ',';
  const rows = []; let row = [], cell = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; }
      else cell += c;
    } else if (c === '"') q = true;
    else if (c === sep) { row.push(cell); cell = ''; }
    else if (c === '\n' || c === '\r') { if (c === '\r' && text[i + 1] === '\n') i++; row.push(cell); rows.push(row); row = []; cell = ''; }
    else cell += c;
  }
  if (cell !== '' || row.length) { row.push(cell); rows.push(row); }
  return rows.filter((r) => r.some((x) => String(x).trim() !== ''));
}
function guessMapping(header) {
  const norm = header.map((x) => String(x).trim().toLowerCase());
  const map = {};
  for (const [key, , names] of EX_FIELDS) {
    const i = norm.findIndex((n) => names.includes(n));
    map[key] = i >= 0 ? i : null;
  }
  return map;
}
function parseMonth(s) {
  s = String(s || '').trim();
  let m;
  if ((m = /^(\d{4})-(\d{1,2})(?:-\d{1,2})?$/.exec(s))) return mm(+m[1], +m[2]);
  if ((m = /^(\d{4})(\d{2})$/.exec(s))) return mm(+m[1], +m[2]);
  if ((m = /^\d{1,2}\/(\d{1,2})\/(\d{4})$/.exec(s))) return mm(+m[2], +m[1]);
  if ((m = /^(\d{1,2})\/(\d{4})$/.exec(s))) return mm(+m[2], +m[1]);
  return null;
  function mm(y, mo) { return mo >= 1 && mo <= 12 && y >= 2000 && y <= 2100 ? `${y}-${String(mo).padStart(2, '0')}` : null; }
}
const monthIndex = (s) => { const [y, m] = s.split('-').map(Number); return y * 12 + m - 1; };
const indexMonth = (i) => `${Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, '0')}`;
function exporterRun(rows, map) {
  const C = S.D.corridors[0];
  const dest = new Map(), stop = new Map();
  for (const c of C.corridors) { dest.set(c.iso2.toLowerCase(), c.iso2); for (const a of c.aliases) dest.set(a.toLowerCase(), c.iso2); }
  for (const c of C.stop) { stop.set(c.iso2.toLowerCase(), c.iso2); for (const a of c.aliases) stop.set(a.toLowerCase(), c.iso2); }
  const codes = S.D.codes.map((c) => c.code);
  const sig = new Map(S.D.signals.map((x) => [x.iso2 + '|' + x.code, x]));
  const out = { read: 0, problems: [], outside: { corridor: 0, code: 0, value: 0 }, stops: [], groups: new Map(), latest: null, earliest: null };
  rows.forEach((r, n) => {
    const line = n + 2;
    const rawDest = map.destination !== null ? String(r[map.destination] || '').trim() : '';
    const rawCode = map.code !== null ? String(r[map.code] || '').replace(/[\s.]/g, '') : '';
    const month = map.month !== null ? parseMonth(r[map.month]) : null;
    const value = map.value !== null ? Number(String(r[map.value] || '').replace(/[£,\s]/g, '')) : NaN;
    const cust = map.customer !== null ? String(r[map.customer] || '').trim() : '';
    // A row to Russia or Belarus is a stop whatever else is wrong with it: it needs a sanctions
    // check before anything, so it is never counted as unreadable.
    const key = rawDest.toLowerCase();
    if (stop.has(key)) { out.stops.push([line, stop.get(key)]); return; }
    if (!month) { out.problems.push([line, 'month not readable (use YYYY-MM)']); return; }
    if (!isFinite(value) || value < 0) { out.problems.push([line, 'value not a number']); return; }
    if (!/^\d+$/.test(rawCode)) { out.problems.push([line, 'commodity code not digits']); return; }
    out.read++;
    out.latest = !out.latest || month > out.latest ? month : out.latest;
    out.earliest = !out.earliest || month < out.earliest ? month : out.earliest;
    if (!rawDest) { out.problems.push([line, 'no destination']); return; }
    if (!dest.has(key)) { out.outside.corridor++; out.outside.value += value; return; }
    if (rawCode.length < 6) { out.problems.push([line, 'commodity code too short: give at least 6 digits']); return; }
    const code = rawCode.startsWith('8548') ? '8548' : codes.includes(rawCode.slice(0, 6)) ? rawCode.slice(0, 6) : null;
    if (!code) { out.outside.code++; out.outside.value += value; return; }
    const iso = dest.get(key);
    const g = out.groups.get(iso + '|' + code) || { iso, code, rows: [], sig: sig.get(iso + '|' + code) };
    g.rows.push({ month, value, cust });
    out.groups.set(iso + '|' + code, g);
  });
  const end = out.latest ? monthIndex(out.latest) : null;
  const start = out.earliest ? monthIndex(out.earliest) : null;
  // What the file covers decides what can be said: a rise needs some of the 12 months
  // before, and a new customer needs months before the last 6.
  out.coversPrev = end !== null && start <= end - 12;
  out.coversFull = end !== null && start <= end - 23;
  out.coversNew = end !== null && start <= end - 6;
  out.results = [...out.groups.values()].map((g) => {
    const by = (lo, hi) => g.rows.filter((r) => { const i = monthIndex(r.month); return i >= lo && i <= hi; });
    const last = by(end - 11, end), prev = by(end - 23, end - 12);
    const sum = (a) => a.reduce((s2, r) => s2 + r.value, 0);
    const v12 = sum(last), p12 = sum(prev);
    const months = new Set(last.filter((r) => r.value > 0).map((r) => r.month)).size;
    const firstSeen = new Map();
    for (const r of g.rows) if (r.cust && (!firstSeen.has(r.cust) || r.month < firstSeen.get(r.cust))) firstSeen.set(r.cust, r.month);
    const cust12 = new Set(last.map((r) => r.cust).filter(Boolean));
    const newCust = out.coversNew ? [...cust12].filter((c) => monthIndex(firstSeen.get(c)) >= end - 5) : [];
    const byCust = new Map();
    for (const r of last) if (r.cust) byCust.set(r.cust, (byCust.get(r.cust) || 0) + r.value);
    const topShare = v12 > 0 && byCust.size ? Math.max(...byCust.values()) / v12 : null;
    // A series the display rule holds back shows nothing from the radar, on either side, so a
    // held-back lead looks like every other series not shown (N7 in the research log).
    const held = !!(g.sig && g.sig.onward && g.sig.onward.shown === false);
    const onwardOn = !held && !!(g.sig && g.sig.onward.signal);
    const ukFlag = !held && !!(g.sig && g.sig.uk.shown && ['lead', 'watch'].includes(g.sig.uk.status));
    const rose = out.coversPrev && (p12 > 0 ? v12 >= 2 * p12 : v12 > 0);
    let order = 'none';
    if (held) order = 'held';
    else if (onwardOn && (newCust.length > 0 || rose)) order = 'first';
    else if (onwardOn || ukFlag) order = 'check';
    const tags = ['chpl', 'corridor'];
    if (newCust.length) tags.push('new_customer');
    if (rose) tags.push('volume_rise');
    if (order !== 'none') tags.push('end_use', 'end_user', 'payment', 'routing', 'customer_profile', 'paperwork');
    return { g, v12, p12, months, cust12: cust12.size, newCust: newCust.length, topShare, onwardOn, ukFlag, held, rose, order, tags };
  }).sort((a, b) => (ORDER_RANK[a.order] - ORDER_RANK[b.order]) || b.v12 - a.v12);
  out.window = end !== null ? { from: indexMonth(end - 11), to: out.latest, prevFrom: indexMonth(end - 23), prevTo: indexMonth(end - 12) } : null;
  return out;
}
function questionsFor(tags) {
  const rf = S.spec.redflags;
  const flags = Array.isArray(rf) ? rf : (rf && Array.isArray(rf.items) ? rf.items : []);
  return flags.filter((r) => Array.isArray(r.tags) && r.tags.some((t) => tags.includes(t)));
}
function onwardText(sg, compact) {
  if (!sg) return 'n/a';
  if (sg.onward && sg.onward.shown === false) return 'not shown (display rule)';
  const o = sg.onward, a = o.annual, mo = o.monthly;
  const verdict = (c) => (c.passes ? 'passed' : c.why_not || 'not passed');
  const part = (label, c) => {
    if (c.usd === null || c.usd === undefined) return `${label}: no record`;
    if (+c.usd === 0) return `${label}: none reported`;
    const r = c.ratio !== null && c.ratio !== undefined ? ratio(c.ratio) : c.baseline_zero ? 'zero baseline' : 'n/a';
    return compact ? `${label}: ${usd(c.usd)} (${r}), ${verdict(c)}` : `${label}: ${usd(c.usd)}, ${r === 'zero baseline' ? 'against a zero 2019-21 baseline' : r + ' the 2019-21 average'}, ${verdict(c)}`;
  };
  const parts = [];
  if (a && a.year) parts.push(part(compact ? String(a.year) : `annual ${a.year}`, a));
  if (mo) parts.push(part(`12 months to ${monthLabel(mo.to)}`, mo));
  return parts.join(compact ? ' · ' : '; ');
}
function ukText(sg) {
  if (!sg) return 'n/a';
  const u = sg.uk;
  if (!u.shown) return 'Not shown (display rule)';
  if (u.status === 'not flagged') return 'Not flagged';
  return `${u.status === 'lead' ? 'Lead' : 'Watch'}: ${gbp(u.trailing12_gbp)} over 12 months, ${ratio(u.ratio)} the 2019-21 average`;
}
const ORDER_LABEL = { first: 'Check first', check: 'Check', held: 'Not shown (display rule)', none: 'No radar signal' };
const ORDER_RANK = { first: 0, check: 1, held: 2, none: 3 };
const onwardLabel = (r) => (r.held ? 'Not shown (display rule)' : r.onwardOn ? 'Onward check on' : 'Onward check off');
function drawExporter() {
  const v = $('#view-exporter');
  const E = S.exporter;
  const intro = h('div', { class: 'head' },
    h('h1', { class: 'h1' }, 'Exporter check'),
    h('p', { class: 'lede' }, 'Check your own shipments against the radar’s corridor signals. Your file is read in this browser: it is not uploaded, stored or sent to Claude [Certain].'),
    h('p', { class: 'house' }, 'The screen sets an order for your own checks. It finds nothing about any customer: a rise in exports is a lead, not evidence of a breach.'));
  const fileInput = h('input', { type: 'file', accept: '.csv,text/csv', 'aria-label': 'Choose a CSV file', onchange: (e) => { const file = e.target.files && e.target.files[0]; if (file) readFile(file); } });
  const drop = h('div', { class: 'drop' },
    h('div', null, h('b', null, 'Drop a CSV of shipments here'), ' or choose one.'),
    fileInput,
    h('div', { class: 'note' }, 'One row per shipment or order line, with destination country, commodity code (6 to 10 digits), month and value in pounds. A customer reference helps; use your own codes, never names.'),
    h('div', { class: 'row' }, h('button', { class: 'btn', onclick: loadSample }, 'Try the synthetic sample'), h('span', { class: 'note' }, 'Made-up shipments: every reference starts SYN-.')));
  drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('over'));
  drop.addEventListener('drop', (e) => { e.preventDefault(); drop.classList.remove('over'); const file = e.dataTransfer.files && e.dataTransfer.files[0]; if (file) readFile(file); });
  const parts = [intro, drop];
  if (E.msg) parts.push(h('div', { class: 'banner warn' }, E.msg));
  if (E.header) {
    const sel = (key, label) => h('label', { class: 'field' }, label, h('select', { onchange: (e) => { E.mapping[key] = e.target.value === '' ? null : +e.target.value; runExporter(); } },
      h('option', { value: '', selected: E.mapping[key] === null }, '(none)'), E.header.map((c, i) => h('option', { value: String(i), selected: E.mapping[key] === i }, c || `Column ${i + 1}`))));
    parts.push(h('div', { class: 'card' }, h('div', { class: 'card-head' }, h('h2', { class: 'h2' }, `Columns in ${E.name}`), h('span', { class: 'note' }, `${E.rows.length} rows`)),
      h('div', { class: 'map-grid' }, EX_FIELDS.map(([k, label]) => sel(k, label)))));
  }
  const R = E.result;
  if (R) {
    const n = (o) => R.results.filter((r) => r.order === o).length;
    parts.push(h('div', { class: 'kpis' },
      kpi('Rows in the file', intGB(S.exporter.rows.length), `${R.problems.length} could not be read or placed`),
      kpi('In scope', intGB(R.results.reduce((s2, r) => s2 + r.g.rows.length, 0)), `${R.results.length} destination and code pairs`),
      kpi('Check first', String(n('first')), 'onward check on, with a new customer or a rise'),
      kpi('Check', String(n('check')), 'a radar signal, no new customer or rise'),
      n('held') ? kpi('Not shown', String(n('held')), 'pairs the radar holds back under its display rule: use your usual checks') : null,
      kpi('Outside the radar', intGB(R.outside.corridor + R.outside.code), `${gbp(R.outside.value)} to other destinations or codes, including any destination the screen does not recognise`)));
    if (R.stops.length) parts.push(h('div', { class: 'banner bad' }, `${R.stops.length} row${R.stops.length > 1 ? 's go' : ' goes'} straight to Russia or Belarus (line${R.stops.length > 1 ? 's' : ''} ${R.stops.map((x) => x[0]).slice(0, 8).join(', ')}). The screen does not look at these: check them against UK sanctions rules before anything else.`));
    const w = R.window;
    parts.push(h('div', { class: 'card' },
      h('div', { class: 'card-head' }, h('h2', { class: 'h2' }, 'Your shipments against the radar'), h('div', { class: 'row' },
        h('button', { class: 'btn small', onclick: () => exportResults('csv'), disabled: !S.caps.downloads }, 'Results (.csv)'),
        h('button', { class: 'btn small', onclick: () => exportResults('md'), disabled: !S.caps.downloads }, 'Note (.md)'))),
      w ? h('p', { class: 'note' }, `Your last 12 months: ${monthLabel(w.from)} to ${monthLabel(w.to)}, against the 12 before (${monthLabel(w.prevFrom)} to ${monthLabel(w.prevTo)}). A new customer is one first seen in the last 6 months. UK-wide figures are the radar’s, to ${S.D.summary[0].uk_data_to}; onward figures are each corridor’s own exports to Russia.`) : null,
      w && !R.coversFull ? h('p', { class: 'note' }, R.coversPrev ? 'Your file starts inside the 12 months before, so the change is measured on part of that year.' : 'Your file covers 12 months or fewer, so no change or rise is measured.') : null,
      w && !R.coversNew ? h('p', { class: 'note' }, 'Your file covers 6 months or fewer, so no customer is counted as new.') : null,
      R.results.length ? h('div', { class: 'scroll' }, h('table', null,
        h('thead', null, h('tr', null, h('th', null, 'Destination and code'), h('th', { class: 'num' }, 'Your 12 months'), h('th', { class: 'num' }, 'The 12 before'), h('th', { class: 'num' }, 'Customers (new)'), h('th', null, 'Corridor to Russia'), h('th', null, 'UK-wide'), h('th', null, 'Order of checks'))),
        h('tbody', null, R.results.map((r) => resultRows(r))))) : h('p', { class: 'note' }, `Nothing in this file goes to the ${inWords(S.D.corridors[0].corridors.length)} corridors with the radar’s codes.`),
      R.problems.length ? h('details', { class: 'given' }, h('summary', null, `${R.problems.length} rows could not be read`), h('ul', { class: 'plain' }, R.problems.slice(0, 50).map(([l, why]) => h('li', null, `Line ${l}: ${why}`)))) : null,
      h('p', { class: 'note' }, `The radar watches ${inWords(S.D.corridors[0].corridors.length)} corridors and ${inWords(S.D.codes.length)} goods codes from the Common High Priority List. A code outside them may still be on that list or controlled; this screen does not check that [Certain].`)));
  }
  swap(v, ...parts);
}
function kpi(lbl, val, cap) { return h('div', { class: 'kpi' }, h('span', { class: 'lbl' }, lbl), h('span', { class: 'val' }, val), h('span', { class: 'cap' }, cap)); }
function resultRows(r) {
  const c = S.D.corridors[0].corridors.find((x) => x.iso2 === r.g.iso);
  const code = S.D.codes.find((x) => x.code === r.g.code);
  const qs = questionsFor(r.tags);
  const open = { v: false };
  const sub = h('tr', { class: 'sub', hidden: true }, h('td', { colspan: 7 },
    h('div', null, h('b', null, 'Questions to ask, from official guidance'), qs.length ? h('ol', { class: 'qlist' }, qs.map((q) => h('li', null, q.question, ' ', h('span', { class: 'muted' }, q.citation ? `(${q.citation.publisher}, ${q.citation.date})` : '')))) : h('p', { class: 'note' }, 'The question list loads with the brief engine’s red flags.')),
    r.topShare !== null ? h('p', { class: 'note' }, `Your largest customer here took ${Math.round(r.topShare * 100)}% of the last 12 months. Exports in ${r.months} of 12 months.`) : null));
  const toggle = h('button', { class: 'btn quiet small', 'aria-expanded': 'false', onclick: () => { open.v = !open.v; sub.hidden = !open.v; toggle.setAttribute('aria-expanded', String(open.v)); toggle.textContent = open.v ? 'Hide questions' : 'Questions'; } }, 'Questions');
  const change = r.p12 > 0 ? `${r.v12 >= r.p12 ? '+' : ''}${Math.round((r.v12 / r.p12 - 1) * 100)}%` : (r.v12 > 0 ? 'new' : '');
  return [h('tr', null,
    h('td', null, h('div', null, h('b', null, c ? c.name : r.g.iso), ' · ', h('span', { class: 'mono' }, fmtCode(r.g.code))), h('div', { class: 'muted' }, code ? code.description : '')),
    h('td', { class: 'num' }, gbp(r.v12), h('div', { class: 'muted' }, change)),
    h('td', { class: 'num' }, gbp(r.p12)),
    h('td', { class: 'num' }, `${r.cust12} (${r.newCust})`),
    h('td', null, h('div', null, onwardLabel(r)), r.held ? null : h('div', { class: 'muted' }, onwardText(r.g.sig, true))),
    h('td', null, ukText(r.g.sig)),
    h('td', null, h('div', { class: 'order ' + r.order }, ORDER_LABEL[r.order]), toggle)), sub];
}
function readFile(file) {
  if (file.size > 20 * 1024 * 1024) { S.exporter.msg = 'That file is over 20 MB. Split it by year and screen each part.'; refresh(); return; }
  const fr = new FileReader();
  fr.onload = () => { setExporterText(String(fr.result || ''), file.name); };
  fr.onerror = () => { S.exporter.msg = 'The file could not be read.'; refresh(); };
  fr.readAsText(file);
}
async function loadSample() {
  try { setExporterText(await getText('data/synthetic_shipments.csv'), 'synthetic_shipments.csv (made up)'); }
  catch { S.exporter.msg = 'The synthetic sample could not be loaded.'; refresh(); }
}
function setExporterText(text, name) {
  const E = S.exporter;
  const rows = parseCSV(text);
  E.msg = '';
  if (rows.length < 2) { E.msg = 'The file has no rows under its header.'; E.header = null; E.result = null; refresh(); return; }
  E.name = name; E.header = rows[0].map((x) => String(x).trim()); E.rows = rows.slice(1); E.mapping = guessMapping(E.header);
  runExporter();
}
function runExporter() {
  const E = S.exporter;
  const missing = EX_FIELDS.filter(([k]) => k !== 'customer' && E.mapping[k] === null).map(([, label]) => label);
  if (missing.length) { E.result = null; E.msg = 'Choose the column for: ' + missing.join(', ') + '.'; refresh(); return; }
  E.msg = '';
  E.result = exporterRun(E.rows, E.mapping);
  // One entry per file and column choice: how many rows and pairs, never the file's name or
  // contents, which stay in this browser.
  const runKey = E.name + '|' + JSON.stringify(E.mapping);
  if (canWrite() && E.logged !== runKey) {
    E.logged = runKey;
    audit('exporter_screened', null, `${E.rows.length} rows, ${E.result.results.length} destination and code pairs`);
  }
  refresh();
}
async function exportResults(kind) {
  const R = S.exporter.result;
  if (!R || !S.caps.downloads) return;
  const s = S.D.summary[0];
  let data, name;
  if (kind === 'csv') {
    const esc = (x) => { const t = String(x === null || x === undefined ? '' : x); return /[",\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t; };
    const lines = [['destination', 'code', 'description', 'your_12m_gbp', 'previous_12m_gbp', 'months_with_exports', 'customers_12m', 'new_customers_6m', 'onward_check', 'onward_detail', 'uk_wide', 'order_of_checks', 'question_ids'].join(',')];
    for (const r of R.results) {
      const c = S.D.corridors[0].corridors.find((x) => x.iso2 === r.g.iso);
      const code = S.D.codes.find((x) => x.code === r.g.code);
      lines.push([c ? c.name : r.g.iso, r.g.code, code ? code.description : '', Math.round(r.v12), Math.round(r.p12), r.months, r.cust12, r.newCust, r.held ? 'not shown' : r.onwardOn ? 'on' : 'off', onwardText(r.g.sig), ukText(r.g.sig), ORDER_LABEL[r.order], questionsFor(r.tags).map((q) => q.id).join(' ')].map(esc).join(','));
    }
    lines.push('', esc(`Radar run ${s.run_label}, HMRC data to ${s.uk_data_to}. A rise in exports is a lead, not evidence of a breach. Contains public sector information licensed under the Open Government Licence v3.0.`));
    data = lines.join('\n') + '\n'; name = 'exporter-screen-results.csv';
  } else {
    const out = [`# Exporter screen note`, '', `Radar run: ${s.run_label}, HMRC data to ${s.uk_data_to}. File screened: ${S.exporter.name}. Screened in the browser; the file was not uploaded or stored.`, '', 'A rise in exports is a lead, not evidence of a breach. This note sets an order for your own checks; it finds nothing about any customer.', ''];
    for (const r of R.results) {
      const c = S.D.corridors[0].corridors.find((x) => x.iso2 === r.g.iso);
      out.push(`## ${ORDER_LABEL[r.order]}: ${c ? c.name : r.g.iso}, ${fmtCode(r.g.code)}`, '',
        `- Your last 12 months: ${gbp(r.v12)} (the 12 before: ${gbp(r.p12)}), in ${r.months} of 12 months, ${r.cust12} customers, ${r.newCust} new in the last 6 months.`,
        r.held ? '- Corridor to Russia: not shown (display rule).' : `- Corridor to Russia: ${r.onwardOn ? 'onward check on' : 'onward check off'} (${onwardText(r.g.sig)}).`,
        `- UK-wide: ${ukText(r.g.sig)}.`, '');
      const qs = questionsFor(r.tags);
      if (qs.length && r.order !== 'none') { out.push('Questions to ask:', ''); qs.forEach((q) => out.push(`- ${q.question} (${q.citation ? q.citation.publisher + ', ' + q.citation.title + ', ' + q.citation.date : ''})`)); out.push(''); }
    }
    out.push('---', '', 'Contains public sector information licensed under the Open Government Licence v3.0: https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/', 'Onward figures: UN Comtrade.');
    data = out.join('\n') + '\n'; name = 'exporter-screen-note.md';
  }
  try {
    await S.caps.downloads.save({ filename: name, data });
    if (canWrite()) await audit('exporter_exported', null, kind === 'csv' ? 'results (.csv)' : 'note (.md)');
  } catch (e) { if (e && e.code !== 'declined') banner('dl', 'warn', 'The file could not be saved from this view.'); }
}

/* ============================================================== audit log */
function drawAudit() {
  const v = $('#view-audit');
  const shown = S.audit.slice(0, 500);
  resolvePeople(shown.map((e) => e.author));
  const rows = shown.map((e) => h('tr', null,
    h('td', { class: 'num' }, stamp(e.at)), h('td', null, person(e.author).name),
    h('td', null, e.ref ? h('button', { class: 'btn quiet small', onclick: () => { const lead = String(e.lead || ''); if (lead.startsWith('case_')) return go('case', lead.slice(5)); if (lead.startsWith('report_')) return go('report', lead.slice(7)); const f = S.files.find((x) => x.docId === e.lead); if (f) go('file', f.key); } }, e.ref) : 'Workspace'),
    h('td', null, ACTION_LABEL[e.action] || e.action), h('td', null, e.detail || '')));
  swap(v, 
    h('div', { class: 'head' }, h('h1', { class: 'h1' }, 'Audit log'),
      h('p', { class: 'lede' }, 'Every saved draft, check, submission, decision, shipments screen and export, newest first, with who did it and when. Someone who can only view the workspace leaves no entries.'),
      h('p', { class: 'note' }, S.store && S.store.kind === 'db' ? (HOSTED ? 'The database writes this log itself, from every change to the shared records, and no member can change or delete an entry [Certain]. Whoever holds the database password could still drop its triggers, so the log is as trustworthy as the people who hold it [Certain]. Exports and the exporter screen are recorded by the page, with the database setting who and when.' : 'Each person\u2019s entries are stored under their own path, which only they can write, so nobody can add an entry in someone else\u2019s name. A person can still change or delete their own entries, and the owner can write anywhere [Certain]. The hosted version, in which the database writes the log itself and nobody can edit or delete it, is built and tested but not deployed (hosted/README.md).') : 'Demo mode: this log lives in this tab and goes when it closes.')),
    S.auditCapped ? h('div', { class: 'banner warn' }, 'This view holds the latest 1,000 entries per person, so older entries are not shown or exported.') : null,
    h('div', { class: 'row' }, h('button', { class: 'btn small', disabled: !S.caps.downloads || !S.audit.length, onclick: exportAudit }, 'Audit log (.csv)'), h('span', { class: 'note' }, `${shown.length} of ${S.audit.length} entries shown, newest first; the export holds all of them.`)),
    S.audit.length ? h('div', { class: 'card' }, h('div', { class: 'scroll' }, h('table', null,
      h('thead', null, h('tr', null, h('th', null, 'When'), h('th', null, 'Who'), h('th', null, 'File'), h('th', null, 'Action'), h('th', null, 'Detail'))),
      h('tbody', null, rows)))) : h('p', { class: 'note' }, 'Nothing recorded yet.'));
}
async function exportAudit() {
  const esc = (x) => { const t = String(x === null || x === undefined ? '' : x); return /[",\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t; };
  await resolvePeople(S.audit.map((e) => e.author));
  const lines = ['when,who,file,action,detail', ...S.audit.map((e) => [e.at, nameFor(e.author), e.ref || 'workspace', ACTION_LABEL[e.action] || e.action, e.detail || ''].map(esc).join(','))];
  try {
    await S.caps.downloads.save({ filename: 'radar-audit-log.csv', data: lines.join('\n') + '\n' });
    if (canWrite()) await audit('audit_exported', null, `${S.audit.length} entries (.csv)`);
  } catch (e) { if (e && e.code !== 'declined') banner('dl', 'warn', 'The file could not be saved from this view.'); }
}

/* ============================================================== track record */
function drawTrack() {
  const v = $('#view-track');
  const cost = (m) => S.D.cost.find((c) => c.measure === m) || {};
  const pl = (p) => S.D.placebo.find((x) => x.period === p) || {};
  const c1 = cost('Cases with a lead before the first public action'), c2 = cost('Primary tests shown, with a lead before the first public action');
  const c3 = cost('Sensitivity tests shown, with a lead before the first public action'), c4 = cost('Tests listed with no route or result, under the display rule');
  const peace = pl('Peacetime, 2019-21'), war = pl('War-time, 2022-24');
  const out = (x) => x === 'hit' ? 'Hit' : x === 'miss' ? 'Miss' : x === 'watch only' ? 'Watch only' : 'Not shown';
  swap(v, 
    h('div', { class: 'head' }, h('h1', { class: 'h1' }, 'Track record'),
      h('p', { class: 'lede' }, 'Would the radar have made the routes in published enforcement cases a lead before the first public action? The tests were fixed before either run and are rerun on today’s figures.'),
      h('p', { class: 'note' }, 'The full charts are on the radar dashboard. The research log in the repository keeps every result, including those not shown here.')),
    h('div', { class: 'kpis' },
      kpi('Cases with a lead before the first public action', `${c1.run2} of ${c1.of}`, `with the monthly check; ${c1.run1} with the annual check alone`),
      kpi('Primary tests with a lead before the action', `${c2.run2} of ${c2.of} shown`, `${c2.run1} with the annual check alone. ${c4.run2} tests are not shown, by route or result, under the display rule. Sensitivity tests with the monthly check: ${c3.run2} of ${c3.of}`),
      kpi('Series a lead in peacetime, 2019-21', `${peace.series_ever_lead} of ${peace.series}`, `against ${war.series_ever_lead} in the first 36 war-time runs; annual check alone, as the monthly check was not tested on peacetime years`)),
    h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'The eight tests'),
      h('p', { class: 'note' }, 'Routes and goods as the case sources describe them (official records for the US cases, published reports for the European ones), mapped to the radar’s codes; the mapping column says how close the match is. A test is shown only when its UK flow passes the display rule; the two that are not keep their place in the list, with no route and no result.'),
      h('div', { class: 'scroll' }, h('table', null,
        h('thead', null, h('tr', null, ['Test', 'Case', 'Role', 'Corridor', 'Codes', 'Code mapping', 'First public action', 'Annual check', 'Months', 'With monthly', 'Months', 'Lead on the day, with monthly'].map((x, i) => h('th', { class: [8, 10].includes(i) ? 'num' : '' }, x)))),
        h('tbody', null, S.D.tests.map((t) => h('tr', null, h('td', { class: 'mono' }, t.test_id), h('td', { class: 'mono' }, t.shown ? t.case_id : 'Not shown'), h('td', null, t.shown ? t.role : 'Not shown'), h('td', null, t.corridor || 'Not shown'), h('td', null, t.shown ? t.codes : 'Not shown'), h('td', null, t.shown ? t.mapping : 'Not shown'), h('td', null, t.shown ? t.first_public_action : 'Not shown'),
          h('td', null, out(t.run1_outcome)), h('td', { class: 'num' }, isNum(t.run1_lead_time_months) ? String(t.run1_lead_time_months) : 'n/a'),
          h('td', null, out(t.run2_outcome)), h('td', { class: 'num' }, isNum(t.run2_lead_time_months) ? String(t.run2_lead_time_months) : 'n/a'), h('td', null, t.run2_on_the_day))))))),
    caseLessonsCard(), outcomesCard('track-outcomes'),
    h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'The cases'),
      h('p', { class: 'note' }, 'Cases with pleas or convictions, two of them at first instance, by reference. The US cases rest on official records; the European ones on published reports, with no official judgment seen. None names UK goods or a UK party.'),
      h('div', { class: 'scroll' }, h('table', null,
        h('thead', null, h('tr', null, ['Case', 'Jurisdiction', 'Body', 'Reference', 'Outcome', 'Basis', 'First public action'].map((x) => h('th', null, x)))),
        h('tbody', null, S.D.cases.map((c) => h('tr', null, h('td', { class: 'mono' }, c.case_id), h('td', null, c.jurisdiction), h('td', null, c.enforcing_body), h('td', null, c.reference), h('td', null, c.outcome), h('td', null, c.basis), h('td', null, c.first_public_action))))))),
    h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'What the monthly check costs'),
      h('p', { class: 'note' }, 'Earlier leads on the case routes come with more leads elsewhere. The case and test rows count the tests shown; the series and run rows count every series on the backtest’s nine corridors and every monthly run from January 2022 to August 2026, with today’s rule rerun on today’s figures.'),
      h('div', { class: 'scroll' }, h('table', null, h('thead', null, h('tr', null, h('th', null, 'Measure'), h('th', { class: 'num' }, 'Annual check'), h('th', { class: 'num' }, 'With monthly'), h('th', { class: 'num' }, 'Out of'))),
        h('tbody', null, S.D.cost.map((c) => h('tr', null, h('td', null, c.measure), h('td', { class: 'num' }, intGB(c.run1)), h('td', { class: 'num' }, intGB(c.run2)), h('td', { class: 'num' }, intGB(c.of)))))))),
    h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'What the track record does not show'), h('ul', { class: 'plain' },
      h('li', null, 'Four cases are an illustration, not a validation [Certain]. The cases, corridors and codes come from the same public reporting, so the test is not blind [Likely].'),
      h('li', null, 'The extra case and the two extra hits with the monthly check are US-02’s, and that gain was foreseen: run 1’s report pointed to Armenia’s monthly data before run 2 was designed. It shows the mechanism works; it is not fresh evidence [Certain]. The monthly check also moved EU-05’s first lead earlier, from 12 to 17 months before the action [Certain].'),
      h('li', null, 'Of the hits shown, two had stopped being leads before the action, by 5 and 9 months [Certain].'),
      h('li', null, 'Tests whose UK flow is under the display rule are listed with no route and no result, whatever the result was; the counts above cover the tests shown, and the research log in the repository keeps every result [Certain].'),
      h('li', null, 'The figures are today’s, after revisions, not what the radar would have seen at the time [Certain].'),
      h('li', null, 'Integrated circuits rise on many corridors at once: the same codes were a lead at some run before the US-01 and EU-05 dates on 4 of the 8 other corridors in the backtest, so a lead on them says little about one route [Certain].'),
      h('li', null, 'The backtest covers the nine corridors of runs 1 and 2. Run 3 added nine corridors to the live radar on the same rule and did not rerun or extend the backtest, so the track record says nothing about them [Certain].'),
      h('li', null, 'The European dates are known only to the month: EU-05’s charges as reported, and the earliest dated step found for EU-01. EU-01 had earlier public steps that the sources do not date, so its lead times may be too long [Likely]; for EU-05 an earlier step is possible [Guessing]. Dating both to the first of the month can make lead times, and how long before the action a hit had stopped, up to a month too short [Certain].'),
      h('li', null, 'Codes are mapped from the cases’ descriptions of the goods, not stated in them. EU-01 concerned mainly computers, outside the radar’s codes, so its tests check the route on a weak match; US-02’s avionics could fall under several codes [Certain].'),
      h('li', null, 'The peacetime years held the pandemic’s swings in trade, and sanctions on Russia from 2014 were already in force. The peacetime count used the annual check alone and is an indication, not a measured false alarm rate [Certain].'))));
}

/* ============================================================== method */
/* ============================================================== how it works */
// A plain-English guide for someone new: what the tool is for, who uses it, a typical month,
// what is demo data in this copy, and what a deployment adds.
function drawGuide() {
  const v = $('#view-guide');
  const s = S.D.summary[0];
  const sec = (title, ...kids) => h('section', { class: 'card' }, h('h2', { class: 'h2' }, title), ...kids);
  const li = (b, ...rest) => h('li', null, b ? h('b', null, b + ' ') : null, ...rest);
  const copy = isDemo()
    ? [li('Nothing is kept.', 'Changes stay in this tab and go when you reload or close it.'),
       li('Briefs start from the template,', 'as drafting with Claude needs the page inside Claude.'),
       li('The people are made up.', 'Sign in as one, and use “Switch user” at the foot of the sidebar to become another and see four-eyes at work: the person who saved a brief cannot approve it.')]
    : HOSTED
      ? [li('Records are kept in the project’s database,', 'which sets every author and time itself and writes the audit log.'),
         li('Briefs are drafted by the project’s drafting function,', 'with the same screens and the owner’s private deny list of names.')]
      : [li('Records are kept in this artifact’s shared store,', 'so the people it is shared with see the same files, briefs and audit log.'),
         li('Briefs are drafted by Claude', 'on the viewer’s own Claude usage, from the file’s facts only.')];
  swap(v,
    h('div', { class: 'head' }, h('h1', { class: 'h1' }, 'How it works'),
      h('p', { class: 'lede' }, 'What Diversion Radar is for, who uses it, a typical month with it, and what is demo data in this copy.')),
    sec('What it does',
      h('p', { class: 'body' }, `Each month, once HMRC publishes its trade figures, the radar checks every pairing of a corridor country and a goods code from the high-priority list: ${s.corridors} corridors by ${s.codes} codes here. A lead is a pairing where UK exports to the corridor rose well above their 2019-21 level and the corridor’s own exports of the same goods to Russia rose too. A UK rise alone is a watch item.`),
      h('p', { class: 'body' }, 'A rise in exports is a lead, not evidence of a breach. A lead is a question for an analyst to check, and it never means a UK party was involved.')),
    h('div', { class: 'grid2' },
      sec('Who uses it', h('ul', { class: 'plain' },
        li('An analyst', 'works each lead: reads its figures, drafts a brief, answers the checklist and submits the file.'),
        li('A second person', '(an Editor or the owner) approves the brief, returns it with a note or rejects it. With four-eyes on, the default, nobody approves their own.'),
        li('A team lead', 'reads the dashboard and the track record: what the method flagged before published enforcement cases, and how many leads it makes to do so.'))),
      sec('In this copy', h('ul', { class: 'plain' },
        li('Published figures:', 'HMRC overseas trade statistics and UN Comtrade, as aggregates; the Common High Priority List of goods codes; the enforcement cases in the track record, by official reference only.'),
        li('Synthetic:', 'the export declarations, the exporter’s shipments and the reports are made up from a seed, some with patterns placed by hand, so they can be shared.'),
        ...copy))),
    sec('A typical month', h('ol', { class: 'steps' },
      h('li', null, h('b', null, 'The data arrives. '), 'HMRC publishes a month. The pull checks each file against its checksum, logs the release and reruns the leads; the dashboard and this inbox update.'),
      h('li', null, h('b', null, 'Start on the overview. '), 'What changed since the last run, what is waiting for a decision and for how long, who holds what, and how fresh the data is. The corridor map shows where the files sit, route by route.'),
      h('li', null, h('b', null, 'Work from the inbox. '), 'Files are grouped by the job they need: Needs my review and Returned to me first, then the rest by stage, down to leads and watch items with no brief yet. j and k move through a list, Enter opens a row, and Ctrl or Cmd + K finds a country, a goods code or a page.'),
      h('li', null, h('b', null, 'Open a lead. '), 'Its file shows the UK and onward figures behind it, its past runs and the questions official guidance asks of a route like it.'),
      h('li', null, h('b', null, 'Draft the brief. '), 'Every draft and every edit passes a screen before it can be saved: no firm names, no figures the facts do not hold, no accusing words, and every claim tied to a fact. The screen is a net, not a guarantee, so the analyst reads every brief.'),
      h('li', null, h('b', null, 'Submit it for approval. '), 'A second person approves it, returns it with a note or rejects it. An approval counts only while the text still matches what they approved.'),
      h('li', null, h('b', null, 'Use the tools where they help. '), 'The exporter check reads an exporter’s own shipments against the corridor signals in your browser, without uploading them. A reviewer’s note can become a lesson for the next draft, once a second person approves it' + (HOSTED ? ' (not yet in the hosted version).' : '.')),
      h('li', null, h('b', null, 'Keep the record. '), 'Every step is in the audit log, which exports with each file’s evidence.'))),
    sec('What a lead is worth',
      h('p', { class: 'body' }, 'A lead is a question, ranked: worth an analyst’s look before anything else, not a conclusion. The overview sets out what the backtest says leads bought (earlier warning in the published cases) and what they cost (many more leads than cases), and works out what briefing a run would take on the hours and cost you enter. It never puts a value on a case.'),
      h('p', { class: 'body' }, 'Each lead file lists the factors behind it, present or not: both checks passing, the annual and monthly onward checks agreeing, how many runs it has been a lead, how steady the UK flow is, how recent the onward data is, and whether the route appears in a published case. They are factors, not a score.')),
    h('div', { class: 'grid2' },
      sec('What a deployment could add', h('ul', { class: 'plain' },
        li('Data on release day:', 'the pull run on a schedule when HMRC and UN Comtrade publish, rather than when someone starts it.'),
        li('Sign-in and roles:', 'named accounts, the owner setting who may approve, and an audit log the database writes.' + (HOSTED ? '' : ' A hosted version (Supabase and Netlify) is built and tested, not deployed.')),
        li('The drafting service:', 'drafting on the server with the same screens and the owner’s private deny list of names.'),
        li('The owner’s own rules:', 'the display threshold, the corridors and goods codes and the checklist.'),
        li('The team’s own data:', 'declarations or shipments it holds under its own powers, in place of the synthetic layer.'))),
      sec('Improving it',
        h('p', { class: 'body' }, 'This is demo data and a first set of rules, and both can be improved further: more corridors and goods codes, monthly onward data where publishers release it, a longer backtest as more cases are published (four cases is a small test), and lessons from the team’s own reviews.'),
        h('p', { class: 'body' }, 'Run 4 was registered before its data were released: what the radar expects the November and December runs to show was written down first, so they test it on figures the project had not seen [Certain]. Method has the rules in full; Track record has the backtest.'))));
}

function drawMethod() {
  const v = $('#view-method');
  const s = S.D.summary[0];
  const m = S.D.manifest[0];
  const fourEyes = S.workflow.four_eyes !== false;
  const wfCard = h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'How the workspace works'),
    h('ul', { class: 'plain' },
      h('li', null, h('b', null, 'Roles. '), 'Contributors draft briefs, tick checks and submit files. Editors and the owner approve, return or reject them. Viewers read. ' + (HOSTED ? 'The owner sets each person’s role in the members table.' : 'Roles follow the artifact’s sharing levels.')),
      h('li', null, h('b', null, 'Four-eyes. '), fourEyes ? 'On: the person who saved a brief version cannot approve it, and an approval by that person does not count.' : 'Off: one person may draft and approve. Each approval records that four-eyes was off, and the file, the inbox and the evidence pack mark it. Turning four-eyes back on stops those approvals counting.'),
      h('li', null, h('b', null, 'Briefs. '), 'Claude is asked to draft from the file\u2019s facts only, with any reviewers\u2019 notes and approved lessons as data, ' + (HOSTED ? 'through the drafting function on the owner’s key, which also screens every draft with the private deny list of names.' : 'on the viewer\u2019s own Claude usage.') + ' Every draft and every edit passes a screen before it can be saved: no firm names with a legal-form ending, no capitalised words that may be names unless the file\u2019s own facts hold them, no emails or postcodes, no accusing words outside a hedged clause, no figure the facts do not hold, every claim tied to the facts it rests on, and the house line word for word. A draft that fails is never shown. The screen cannot catch a name in lower case or at the start of a sentence, so the analyst reads every brief.'),
      h('li', null, h('b', null, 'Records. '), HOSTED ? 'Briefs, decisions and the audit log are rows the database writes: it sets every author and time from the signed-in person and the clock, checks each approval (the brief, its SHA-256 and four-eyes) and writes the audit log itself. An approval counts only when the brief text still matches the SHA-256 the approver saw and someone else saved it, unless four-eyes is off at the time it is read. No member can change or delete a brief, a decision or the audit log; the status pointer and the checks are shared records any Contributor can change, with every change audited; whoever holds the database password can still change those and could drop the triggers [Certain].' : 'Briefs, decisions and the audit log are stored under each person\u2019s own path, which only they can write, and decisions only at Editor level, so the path says who saved and who approved. An approval counts only when the brief text still matches the SHA-256 the approver saw and someone else saved it, unless four-eyes is off at the time it is read; the evidence pack carries the check. The owner can still write anywhere, and a person can change or delete their own records [Certain]. That the store enforces this for people other than the owner is [Likely] until checked with a second account.'),
      h('li', null, h('b', null, 'Your exporter file. '), 'Read in the browser and never uploaded, stored or sent to Claude.')),
    canApprove() && S.store ? h('div', { class: 'row' }, h('button', { class: 'btn small', onclick: () => setFourEyes(!fourEyes), disabled: S.storeState === 'connecting' }, fourEyes ? 'Turn four-eyes off' : 'Turn four-eyes on'), h('span', { class: 'note' }, 'Editors and the owner only; recorded in the audit log.')) : null);
  swap(v, 
    h('div', { class: 'head' }, h('h1', { class: 'h1' }, 'Method'), h('p', { class: 'lede' }, 'The rules behind each lead, what may be shown, and how the workspace keeps its records.')),
    h('div', { class: 'grid2' },
      h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'The rules'), h('ul', { class: 'plain' },
        h('li', null, h('b', null, 'UK signal. '), 'UK exports to the corridor over the trailing 12 published months at least 2x the 2019-21 annual average and at least £20,000 above it, for 3 published months running. HMRC month M counts from the end of month M + 2.'),
        h('li', null, h('b', null, 'Onward signal. '), `The corridor’s own exports of the code to Russia: the latest year released (2022 or later), or, for the ${isNum(s.monthly_corridors) ? `${inWords(s.monthly_corridors)} of the ${inWords(s.corridors)} ` : ''}corridors with monthly UN Comtrade data after 2019, the 12 months to the latest month released. At least 2x the 2019-21 level and at least $100,000.`),
        h('li', null, h('b', null, 'Lead. '), 'Both signals at one monthly run. A UK signal alone is a watch item.'),
        h('li', null, h('b', null, 'Release dates. '), 'Each year or month of onward data counts only from the release date UN Comtrade records for it; where a dataset was replaced, that may be the replacement’s date, so a signal can come late but not early [Likely]. The exception is the 2019-21 baselines, used at every run though some were released later [Certain].'),
        h('li', null, 'The rules were fixed and committed before each backtest ran [Certain].'))),
      h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'The display rule'),
        h('p', { style: 'margin:0;max-width:78ch' }, `A flagged series is shown only when UK exports over the 12 published months reach £${intGB(s.display_min_gbp)} and came in at least ${s.display_min_months} separate months, and a past run is drawn only when its own 12 months pass the same test. A series or run whose 12 months are smaller is counted, never shown by corridor or code, and a backtest test whose UK flow is smaller is listed with no route and no result, whatever the result was. The 2019-21 average is shown however small, as pre-war context. This makes it less likely that a small flow points at one exporter; it cannot rule that out [Likely]. The months test screens out flows that came in fewer than 6 months, but one large consignment with small sales in other months can still pass [Certain]. The levels are judgement calls, not taken from HMRC’s disclosure rules. On a corridor and goods heading that appear in the enforcement cases, only 12-month windows that start after the cases’ first public actions are drawn.`),
        h('p', { class: 'note' }, 'In the exporter screen, the UK-wide column follows the same rule: a status only where the series passes it at this run, and figures only for series that are flagged and shown.'))),
    h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'Limits of a lead'), h('ul', { class: 'plain' },
      h('li', null, 'Ordinary trade can pass both tests: a corridor’s own demand can rise with its exports to Russia [Certain].'),
      h('li', null, 'A lead can rest on onward trade that has since stopped. The United Arab Emirates and Tajikistan have released no annual data for years after 2023; the UAE has no monthly data after 2019 and Tajikistan none, so their onward check rests on 2023, as both UAE leads shown do [Certain]. Vietnam\u2019s annual and monthly data also end in 2023, and China\u2019s monthly data end in December 2024 [Certain].'),
      h('li', null, 'A 2019-21 year counts in a corridor\u2019s annual onward baseline only when its figures hold exports of one of the nine codes to Russia that year. Macao\u2019s hold none for 2019-21, so its annual check cannot pass, and its monthly baseline is zero, so its monthly check rests on the $100,000 floor alone. Azerbaijan\u2019s hold none for 2019 and Georgia\u2019s none for 2020, so their baselines are the average of the other two years [Certain].'),
      h('li', null, 'Hong Kong\u2019s reported exports include re-exports, so its onward figures also count goods that only passed through it [Likely].'),
      h('li', null, 'One month can carry the monthly onward check. The rule itself does not test how spread out the exports are on either side; only the display rule’s months test does, on the UK side [Certain].'),
      h('li', null, 'The codes are broad, and most of what they cover is in ordinary use [Certain].'),
      h('li', null, 'The onward check rests on what each corridor reports to UN Comtrade as its exports to Russia [Certain].'),
      h('li', null, 'HMRC and UN Comtrade revise published figures, so later releases may change these [Likely].'))),
    wfCard,
    h('div', { class: 'grid2' },
      h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'Sources'), h('ul', { class: 'plain' },
        h('li', null, 'HMRC overseas trade statistics (uktradeinfo), UK exports by goods code, country and month.'),
        h('li', null, 'UN Comtrade, corridor exports to Russia by goods code, annual and monthly, with the release date UN Comtrade records for each dataset.'),
        h('li', null, 'Common High Priority List (US, EU, UK and Japan), the goods codes.'),
        h('li', null, 'Enforcement cases: official records for the two US cases and published reports for the two European cases, by reference.'),
        S.spec.redflags ? h('li', null, 'Questions to check: official guidance only, each cited by publisher, title and date.') : null)),
      h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'This build'), h('ul', { class: 'plain' },
        h('li', null, `Run ${m.run_label}${s.variant ? ` (${s.variant.replace(/^run/, 'run ')}: ${inWords(s.corridors)} corridors)` : ''}, HMRC data to ${m.uk_data_to}. Built from commit ${m.source_commit}; ${Object.keys(m.files).length} data files, each with a SHA-256 in the manifest.`),
        h('li', null, HOSTED ? 'This is the hosted version, on Supabase in London and Netlify, with drafting through a server function on the owner’s key. The page loads one script from another site, the Supabase client, at a pinned version checked by its SHA-384, and nothing else: no fonts. The hosted version has no lessons yet.' : 'Inside Claude for the pilot: the shared store, sign-in and drafting come from the artifact. The hosted version, on Supabase (London region) and Netlify with the same page and three adapters (store, drafter and sign-in), is built and tested here (the database on a local Postgres, the page and the drafting function against fakes) and not deployed (hosted/README.md). The page loads nothing from other sites: no fonts, no scripts.'),
        h('li', null, S.spec.rules ? `Screen rules: ${S.spec.rules.schema}.` : 'Screen rules: loading with the brief engine.')))));
}
async function setFourEyes(on) {
  if (!canApprove()) return;
  try {
    await upsert('config', 'workflow', { four_eyes: on, updated_by: myId(), updated_at: nowIso() });
    await audit('workflow_changed', null, `four-eyes ${on ? 'on' : 'off'}`);
  } catch (e) { writeFailed(e, 'the workflow setting'); }
}

/* ============================================================== Brief: drafting, screen, review
   Filled in from the brief engine's spec (spec/prompt.md, brief.schema.json,
   screen_rules.json, redflags.json) and the per-lead contexts. */
const Screen = window.RadarScreen;
const Brief = (() => {
  // The brief is radar-brief/1 (spec/brief.schema.json). Every check comes from the shared
  // screen (window.RadarScreen, app/src/screen.js), the same code the hosted function runs.
  const RS = window.RadarScreen;
  const SECTIONS = [
    ['uk', 'What rose in the UK figures', (d) => d.what_rose.uk],
    ['onward', 'What the onward figures show', (d) => d.what_rose.onward],
    ['ordinary', 'Why it may be ordinary trade', (d) => d.why_it_may_be_ordinary],
  ];
  const REJECT_REASONS = [
    ['ordinary_trade', 'Ordinary trade explains the rise'],
    ['data', 'A data problem or revision'],
    ['duplicate', 'Already covered by another file'],
    ['other', 'Other (see the note)'],
  ];
  const order = () => (S.spec.rules && S.spec.rules.confidence_order) || ['Guessing', 'Likely', 'Certain'];

  function screen(draft, ctx, review) {
    if (!RS || !S.spec.C || !S.spec.schema || !ctx) return { ok: false, problems: [{ code: 'not_ready', path: '', detail: '' }] };
    let problems;
    try { problems = RS.screenShared(draft, ctx, S.spec.C, S.spec.schema, review || []); } catch { problems = [{ code: 'not_ready', path: 'responds_to_review', detail: '' }]; }
    return { ok: problems.length === 0, problems };
  }

  // Reviewer notes for the next draft (screen_rules.json, review): what editors wrote when they
  // returned or rejected a version since the file's last approval, oldest first, as review-1 to
  // review-5. A note that fails the note checks is held back from Claude and not required.
  const rejectLabel = (k) => ((REJECT_REASONS.find((r) => r[0] === k) || [])[1] || '');
  function reviewNotes(f) {
    const ds = decisionsFor(f);
    let from = 0;
    for (let i = ds.length - 1; i >= 0; i--) if (ds[i].decision === 'approved' && approvalCheck(ds[i]).ok === true) { from = i + 1; break; }
    const max = (S.spec.rules && S.spec.rules.review && S.spec.rules.review.max_notes) || 5;
    const picked = ds.slice(from).filter((d) => (d.decision === 'returned' && String(d.note || '').trim()) || d.decision === 'rejected').slice(-max);
    return picked.map((d, i) => ({
      id: `review-${i + 1}`, kind: d.decision, at: String(d.decided_at || '').slice(0, 10),
      text: d.decision === 'rejected' ? [rejectLabel(d.reason) || 'Rejected', String(d.note || '').trim()].filter(Boolean).join(': ') : String(d.note).trim(),
    }));
  }
  function notesFor(f, ctx) {
    if (!RS || !RS.usableNotes || !S.spec.C || !S.spec.C.raw.review || !ctx) return { usable: [], held: [] };
    try { return RS.usableNotes(reviewNotes(f), ctx, S.spec.C); } catch { return { usable: [], held: [] }; }
  }
  // A copy of a draft with one answer per usable note: answers kept for notes still given, the
  // template's placeholder for the rest, and none for notes no longer given.
  function withAnswers(d, review) {
    const ph = S.spec.C.raw.review.placeholder;
    const have = new Map((d.responds_to_review || []).map((a) => [a.note, a]));
    const answers = (review || []).map((n) => have.get(n.id) || { note: n.id, change: { text: ph, confidence: 'Certain', cites: [n.id] } });
    if (answers.length) d.responds_to_review = answers; else delete d.responds_to_review;
    return d;
  }

  // The template: radar/brief/fake_llm.py's fake_draft, built only from the context, so it
  // passes the screen by construction. A person edits it from there.
  const RANK = { Guessing: 0, Likely: 1, Certain: 2 };
  const QUESTION_TAGS = ['chpl', 'corridor', 'volume_rise', 'end_use', 'end_user', 'payment', 'routing'];
  const WHY_HERE = { chpl: 'series.chpl_tier', corridor: 'corridor.uk_guidance', volume_rise: 'uk.ratio' };
  const ORDINARY = ['limit.code_breadth', 'limit.corridor_totals', 'limit.single_month', 'limit.revisions', 'limit.onward_age'];
  function template(ctx, review) {
    const items = new Map([...ctx.facts, ...ctx.limits, ...ctx.cases].map((x) => [x.id, x]));
    const claim = (text, cites) => ({ text, confidence: cites.map((c) => items.get(c).confidence).reduce((a, b) => (RANK[b] < RANK[a] ? b : a)), cites: cites.slice() });
    const say = (ids, lead) => claim(((lead || '') + ids.map((i) => items.get(i).text).join(' ')).trim(), ids);
    const ratioText = items.get('uk.ratio').display;
    const head = ctx.status === 'lead'
      ? `${ctx.series}: UK exports ${ratioText} the 2019-21 average and the onward check passed; a lead to check, not a finding`
      : `${ctx.series}: UK exports ${ratioText} the 2019-21 average; the onward check has not passed; a watch item to check, not a finding`;
    const onward = [say(['onward.check'])].concat(['onward.annual', 'onward.monthly'].filter((i) => items.has(i)).map((i) => say([i])));
    const ordinary = ORDINARY.filter((i) => items.has(i)).map((i) => say([i], i === 'limit.code_breadth' ? 'The rise may be ordinary trade. ' : ''));
    const questions = [], picked = new Set();
    for (const tag of QUESTION_TAGS) {
      const flag = ctx.red_flags.find((x) => x.tags.includes(tag) && !picked.has(x.id));
      if (!flag) continue;
      picked.add(flag.id);
      const q = { red_flag: flag.id, question: flag.question };
      if (items.has(WHY_HERE[tag])) q.why_here = say([WHY_HERE[tag]]);
      questions.push(q);
    }
    return withAnswers({
      schema: 'radar-brief/1', series: ctx.series, run: ctx.run,
      headline: claim(head, ['uk.ratio', 'onward.check']),
      what_rose: { uk: [say(['uk.trailing12', 'uk.ratio']), say(['uk.months', 'display.rule']), say(['history.summary'])], onward },
      why_it_may_be_ordinary: ordinary,
      linked_cases: { case_ids: ctx.cases.map((c) => c.case_id), note: claim(items.get('cases.summary').text, ['cases.summary'].concat(ctx.cases.map((c) => c.id))) },
      questions_to_check: questions,
      limits: ctx.limits.map((x) => x.id),
      house_line: ctx.house_line, ogl_line: ctx.ogl_line,
    }, review);
  }

  /* ---------- drafting with Claude ---------- */
  function promptTurns(ctx, review, lessons) {
    const p = RS.buildPrompt(S.spec.prompt, S.spec.rules, S.spec.schema, ctx, review || [], lessons || []);
    // sample() has no system prompt the page controls: the rules go in a leading user turn.
    return [{ role: 'user', content: p.system }, { role: 'user', content: p.user }];
  }
  const UNAVAILABLE = ['not_granted', 'sampling_disabled', 'not_declared', 'capability_disabled', 'capability_removed'];
  async function draftWithClaude(f, ctx, fresh) {
    const u = uiFor(f.docId);
    if (u.busy || !S.caps.sample) return;
    u.busy = true; u.problems = null; u.msg = ''; u.ctl = new AbortController();
    refresh();
    const opts = { signal: u.ctl.signal, modelTier: 'default', onText: ({ text }) => { const el = document.getElementById('draft-progress'); if (el) el.textContent = `Writing, ${text.length.toLocaleString('en-GB')} characters so far`; } };
    if (fresh) opts.cache = false;
    const review = notesFor(f, ctx).usable;
    const lessons = Lessons.snapshot(f);
    try {
      const { text } = await S.caps.sample(promptTurns(ctx, review, Lessons.forPrompt(lessons)), opts);
      const parsed = RS.parseReply(text);
      const res = parsed.ok ? screen(parsed.draft, ctx, review) : { ok: false, problems: [parsed.problem] };
      if (res.ok) {
        u.working = { draft: parsed.draft, source: 'claude', review, lessons }; u.mode = 'view';
        await keepPrivate(f, u.working);
        await audit('draft_created', f, `by Claude, passed the screen${lessons.length ? `, with ${lessons.length} lesson${lessons.length === 1 ? '' : 's'}` : ''}`);
      } else {
        u.problems = res.problems; u.working = null;
        await audit('draft_failed_screen', f, `${res.problems.length} problem${res.problems.length === 1 ? '' : 's'}`);
      }
    } catch (e) {
      const code = e && e.code;
      u.msg = code === 'cancelled' ? 'Stopped.'
        : UNAVAILABLE.includes(code) ? 'Claude drafting is not available in this view. Start from the template instead.'
        : code === 'rate_limited' ? 'Claude is busy or a usage limit was reached. Try again in a few minutes.'
        : code === 'refused' ? 'Claude declined to draft this. Start from the template instead.'
        : code === 'session_expired' ? 'Sign in to Claude again, then retry.'
        : code === 'prompt_too_large' ? 'The facts for this file are too long to send. Start from the template instead.'
        : 'The draft did not arrive. Try again.';
      if (UNAVAILABLE.includes(code)) S.caps.sample = null;
    } finally { u.busy = false; u.ctl = null; refresh(); }
  }

  // An unsaved, screened draft is kept in the viewer's own private space, so leaving the
  // page does not lose it.
  const privKey = (f) => 'draft_' + f.docId;
  async function keepPrivate(f, working) {
    if (!S.store || S.store.kind !== 'db' || !S.me.id) return;
    try { await S.store.set('data/users/' + S.me.id, privKey(f), { lead: f.docId, working, at: nowIso() }); } catch { /* a convenience */ }
  }
  async function loadPrivate(f) {
    if (!S.store || S.store.kind !== 'db' || !S.me.id) return null;
    try { const d = await S.store.get('data/users/' + S.me.id, privKey(f)); return d && d.working ? d.working : null; } catch { return null; }
  }
  async function dropPrivate(f) {
    if (!S.store || S.store.kind !== 'db' || !S.me.id) return;
    try { await S.store.set('data/users/' + S.me.id, privKey(f), { lead: f.docId, working: null, at: nowIso() }); } catch { /* ignore */ }
  }

  /* ---------- workflow ---------- */
  const stale = (f, text) => {
    const u = uiFor(f.docId);
    u.msg = text || 'The file changed while you were looking at it. Check it again.'; u.confirm = null; u.note = ''; u.reason = '';
    refresh();
  };
  async function saveDraft(f, ctx) {
    const u = uiFor(f.docId);
    if (!u.working || !canWrite()) return;
    if (['submitted', 'approved', 'rejected'].includes(workflowOf(f).state)) return stale(f, 'The brief is awaiting approval or decided, so a new version cannot be saved now. Ask an editor to return or reopen the file.');
    const review = u.working.review || [];
    const res = screen(u.working.draft, ctx, review);
    if (!res.ok) { u.problems = res.problems; refresh(); return; }
    const id = newId(f.docId);
    const version = briefsFor(f).length + 1;
    const hash = await sha256(canon(u.working.draft));
    const lessons = u.working.lessons || [];
    const doc = { lead: f.docId, run: f.run, series: f.series, version, source: u.working.source, draft: u.working.draft, review, lessons,
      screen: { ok: true, rules: S.spec.rules.schema, checked_at: nowIso() }, sha256: hash, created_at: nowIso() };
    try {
      await ensureMember();
      await S.store.set(ownColl('briefs', myId()), id, doc);
      await upsert('leads', f.docId, { run: f.run, series: f.series, status: 'drafting', brief_id: `${myId()}/${id}`, updated_at: nowIso(), updated_by: myId() });
      await audit('brief_saved', f, `version ${version}, ${u.working.source === 'claude' ? 'drafted by Claude' : u.working.source === 'template' ? 'from the template' : 'edited'}${lessons.length ? `, ${lessons.length} lesson${lessons.length === 1 ? '' : 's'} recalled` : ''}`);
      u.working = null; u.problems = null; u.mode = 'view'; u.msg = '';
      await dropPrivate(f);
    } catch (e) { writeFailed(e, 'the brief'); }
    refresh();
  }
  async function submit(f, b, ctx) {
    if (!canWrite() || !b) return;
    const w = workflowOf(f);
    if (!['new', 'drafting', 'returned'].includes(w.state)) return stale(f);
    if (!screen(b.draft, ctx, b.review || []).ok || S.verified.get(b.key) !== true) return stale(f, 'This version no longer passes the screen or its fingerprint. Draft a new version.');
    if (w.decision && w.decision.decision === 'returned' && !(String(b.created_at || '') > String(w.decision.decided_at || ''))) return stale(f, 'This version was saved before the brief was returned. Save a new version that answers the reviewer’s note, then submit it.');
    try {
      await upsert('leads', f.docId, { run: f.run, series: f.series, status: 'submitted', brief_id: b.key, updated_at: nowIso(), updated_by: myId() });
      await audit('brief_submitted', f, '');
      say('Submitted for approval. Someone else decides.');
    } catch (e) { writeFailed(e, 'the submission'); }
  }
  async function decide(f, b, decision, extra) {
    if (!canApprove()) return;
    const w = workflowOf(f), L = S.leads.get(f.docId);
    if (!(decision === 'reopened' ? ['approved', 'rejected'] : ['submitted']).includes(w.state)) return stale(f);
    if (decision !== 'reopened' && (!b || !L || L.brief_id !== b.key)) return stale(f);
    const fourEyes = S.workflow.four_eyes !== false;
    if (decision === 'approved') {
      if (fourEyes && b.author === myId()) return;
      if ((await sha256(canon(b.draft))) !== b.sha256 || !screen(b.draft, S.contexts[f.key], b.review || []).ok) return stale(f, 'This version does not match its saved fingerprint or no longer passes the screen, so it cannot be approved.');
    }
    const doc = Object.assign({ lead: f.docId, run: f.run, series: f.series, decision, brief_id: b ? b.key : null, brief_sha256: b ? b.sha256 : null, four_eyes: fourEyes, decided_at: nowIso() }, extra || {});
    // A return can keep its note as a lesson for later drafts, if the memory core admits it.
    let refused = null;
    if (decision === 'returned' && doc.keep_lesson && doc.note) {
      const scope = Lessons.scopeOf(doc.keep_lesson, f);
      const adm = Lessons.admission(scope, doc.note, S.contexts[f.key]);
      if (adm.status === 'rejected') refused = adm.why;
      else doc.lesson = { scope, sha256: await Lessons.sha(scope, doc.note), memory_rules: S.spec.memRules.version };
    }
    delete doc.keep_lesson;
    try {
      await ensureMember();
      await S.store.set(ownColl('decisions', myId()), newId(f.docId), doc);
      const action = { approved: 'brief_approved', returned: 'brief_returned', rejected: 'brief_rejected', reopened: 'reopened' }[decision];
      const detail = decision === 'approved' ? (fourEyes ? 'four-eyes on' : 'four-eyes off')
        : decision === 'rejected' ? ((REJECT_REASONS.find((r) => r[0] === doc.reason) || [])[1] || '')
        : decision === 'returned' ? 'with a note' : '';
      await audit(action, f, detail);
      say(DECIDED[decision] || 'Saved.');
      if (doc.lesson) await audit('lesson_proposed', f, `for ${Lessons.scopeWords(doc.lesson.scope)}; waits for a second person`);
      if (refused) { await audit('lesson_not_kept', f, refused.join('; ')); banner('lesson', 'warn', `The brief was returned, but the note was not kept as a lesson: ${refused.join('; ')}.`); }
    } catch (e) { writeFailed(e, 'the decision'); }
    const u = uiFor(f.docId); u.confirm = null; u.note = ''; u.reason = ''; u.keepLesson = false; refresh();
  }

  // Free text a person types (a note on a return or rejection): the same text checks, and a
  // guard against names that only the server's deny list would catch.
  const NAME_ALLOW = ['United Arab Emirates', 'Kyrgyz Republic', 'United Kingdom', 'United States', 'Russian Federation', 'Hong Kong', 'UN Comtrade', 'Common High Priority List', 'Common High Priority Items List', 'High Priority List', 'Open Government Licence', 'Department for Business and Trade', 'Office of Trade Sanctions Implementation', 'Office of Financial Sanctions Implementation'];
  function screenNote(text, ctx) {
    const out = S.spec.C ? RS.textProblems(text, 'note', S.spec.C) : [];
    if (S.spec.C && RS.noteProblems && S.spec.C.raw.review) {
      try { out.push(...RS.noteProblems(text, ctx || {}, 'note', S.spec.C).filter((x) => x.code === 'planted_instruction')); } catch { /* older rules */ }
    }
    if (S.spec.C && RS.nameProblems && RS.namesAllowed) {
      try { out.push(...RS.nameProblems(text, 'note', RS.namesAllowed(ctx || {}, S.spec.C), S.spec.C)); } catch { /* older rules: the guard below still runs */ }
    }
    const month = new RegExp('^(?:' + MONTH_FULL.join('|') + ')\\b');
    for (const n of String(text).match(/\b[A-Z][a-z]+(?:[ '\-][A-Z][a-z]+)+\b/g) || []) {
      if (NAME_ALLOW.some((a) => a.includes(n)) || month.test(n)) continue;
      out.push({ code: 'possible_name', path: 'note', detail: n });
    }
    const seen = new Set();
    return out.filter((x) => { const k = x.code + '|' + x.path; if (x.code !== 'possible_name') return true; if (seen.has(k)) return false; seen.add(k); return true; });
  }
  const EXTRA_CODES = { possible_name: 'Words that may be a name of a person or firm. Notes must not name anyone.', not_ready: 'The facts or the screen rules have not loaded.' };
  // Show what matched only where it cannot itself be a name or personal data.
  const SAFE_DETAIL = new Set(['invented_figure', 'uncited_figure', 'accusing_language', 'unknown_fact', 'unknown_case', 'cases_missing', 'unknown_red_flag', 'confidence_above_source', 'series_mismatch', 'run_mismatch',
    'review_unanswered', 'review_unknown', 'review_duplicate', 'review_not_cited', 'review_placeholder']);
  function problemText(p) {
    const codes = (S.spec.rules && S.spec.rules.problem_codes) || {};
    return (codes[p.code] || EXTRA_CODES[p.code] || p.code) + (p.path ? ` (${p.path})` : '') + (SAFE_DETAIL.has(p.code) && p.detail ? `: ${p.detail}` : '');
  }
  const problemsBox = (title, problems) => h('div', { class: 'problems', role: 'alert' }, h('b', null, title),
    h('ul', null, problems.slice(0, 20).map((p) => h('li', null, problemText(p)))), problems.length > 20 ? h('span', null, `and ${problems.length - 20} more`) : null);

  /* ---------- evidence pack ---------- */
  function citeText(ctx, id) {
    const x = [...ctx.facts, ...ctx.limits, ...ctx.cases].find((i) => i.id === id);
    return x ? x.text : '';
  }
  async function evidencePack(f, b, ctx, kind) {
    if (!S.caps.downloads || !b) return;
    const s = S.D.summary[0], m = S.D.manifest[0];
    const Dn = workflowOf(f).decision || {};
    const st = (S.checks.get(f.docId) || {}).items || {};
    const items = checkItemsFor(f, ctx);
    const evs = S.audit.filter((e) => e.lead === f.docId).slice().sort(byTime('at'));
    const cut = S.auditCapped ? 'The audit trail below may be incomplete: the workspace holds the latest 1,000 entries per person.' : '';
    await resolvePeople([Dn.author, b.author, ...evs.map((e) => e.author), ...Object.values(st).map((c) => c.by)].filter(Boolean));
    const verified = (await sha256(canon(b.draft))) === b.sha256 && b.sha256 === Dn.brief_sha256;
    const d = b.draft;
    let out, name;
    if (kind === 'json') {
      out = JSON.stringify({
        reference: f.ref, run: s.run, run_label: s.run_label, uk_data_to: s.uk_data_to, series: f.series, signal: f.status,
        decision: { decision: Dn.decision || null, at: Dn.decided_at || null, by: Dn.author ? nameFor(Dn.author) : null, four_eyes: Dn.four_eyes !== false, approved_by_author: !!(Dn.author && Dn.author === b.author), brief_sha256: Dn.brief_sha256 || null, hash_verified: verified },
        brief: { id: b.key, source: b.source, saved_at: b.created_at, saved_by: nameFor(b.author), sha256: b.sha256, draft: d, review_notes: b.review || [] },
        context: ctx,
        checks: items.map((it) => ({ red_flag: it.id, question: it.q, state: (st[it.id] || {}).state || 'open', by: (st[it.id] || {}).by ? nameFor(st[it.id].by) : null, at: (st[it.id] || {}).at || null })),
        audit: evs.map((e) => ({ at: e.at, by: nameFor(e.author), action: ACTION_LABEL[e.action] || e.action, detail: e.detail })),
        audit_note: cut || null,
        provenance: { source_commit: m.source_commit, source_dirty: !!m.source_dirty, data_files: m.files, screen_rules: S.spec.rules.schema },
        house_line: ctx.house_line, ogl_line: ctx.ogl_line,
        licence: 'https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/',
      }, null, 1) + '\n';
      name = `${f.ref}-evidence.json`;
    } else {
      const claimLine = (c) => `- ${c.text} [${c.confidence}] (${c.cites.join(', ')})`;
      const L = [`# Evidence pack: ${f.ref}`, '',
        `Diversion Radar, ${s.run_label} run, HMRC data to ${s.uk_data_to}. ${f.country}, code ${fmtCode(f.code)} (${f.description}). Signal: ${f.status === 'lead' ? 'lead' : 'watch item'}.`, '',
        `**Decision:** ${Dn.decision || 'none'}${Dn.decided_at ? ` on ${stamp(Dn.decided_at)} by ${nameFor(Dn.author)}` : ''}. Four-eyes: ${Dn.four_eyes === false ? 'off' : 'on'}${Dn.author && Dn.author === b.author ? '; approved by the person who saved the brief' : ''}.`,
        `**Brief:** saved ${stamp(b.created_at)} by ${nameFor(b.author)}, ${b.source === 'claude' ? 'drafted by Claude and screened' : b.source === 'template' ? 'from the template, screened' : 'edited and screened'}. SHA-256 ${b.sha256}: ${verified ? 'matches the approval record' : 'does not match the approval record'}.`, '',
        `> ${ctx.house_line}`, '',
        '## Analyst brief', '', `### ${d.headline.text}`, '', `[${d.headline.confidence}] (${d.headline.cites.join(', ')})`, ''];
      for (const [, label, get] of SECTIONS) { const cs = get(d); if (cs.length) { L.push(`**${label}**`, '', ...cs.map(claimLine), ''); } }
      L.push('**Linked enforcement cases**', '', `${d.linked_cases.case_ids.length ? d.linked_cases.case_ids.join(', ') + ': ' : ''}${d.linked_cases.note.text} [${d.linked_cases.note.confidence}]`, '');
      L.push('**Questions to check**', '');
      d.questions_to_check.forEach((q, i) => { L.push(`${i + 1}. ${q.question}${q.why_here ? ` Why here: ${q.why_here.text} [${q.why_here.confidence}]` : ''}`); });
      L.push('', '**Limits that apply**', '', ...d.limits.map((id) => `- ${citeText(ctx, id)} (${id})`), '');
      if ((d.responds_to_review || []).length) {
        L.push('**Reviewer notes and answers**', '');
        for (const a of d.responds_to_review) {
          const n = (b.review || []).find((x) => x.id === a.note);
          L.push(`- ${a.note}${n ? ` (${n.kind}, ${n.at}): ${n.text}` : ''}`, `  Answer: ${a.change.text} [${a.change.confidence}]`);
        }
        L.push('');
      }
      if ((b.lessons || []).length) {
        L.push('**Lessons in front of the drafter**', '', 'Data from earlier reviews, each approved by a second person; never a fact or a rule.', '');
        for (const l of b.lessons) L.push(`- ${l.id}, for ${Lessons.scopeWords(l.scope)}: ${l.text}`, `  Kept by ${nameFor(l.proposed_by)} from a returned brief${l.from_ref ? ` (${l.from_ref})` : ''}; approved by ${nameFor(l.approved_by)}, ${stamp(l.approved_at)}: ${l.reason}. SHA-256 ${String(l.sha256 || '').slice(0, 16)}`);
        L.push('');
      }
      L.push('## The facts behind it', '', ...ctx.facts.map((x) => `- ${x.id}: ${x.text} [${x.confidence}] (${x.source.dataset}, ${x.source.field})`), '');
      L.push('## Checks', '');
      for (const it of items) { const c = st[it.id] || {}; L.push(`- [${c.state === 'done' ? 'x' : c.state === 'na' ? '-' : ' '}] ${it.q}${c.by ? ` (${c.state === 'done' ? 'checked' : c.state === 'na' ? 'not applicable' : 'open'}, ${nameFor(c.by)}, ${stamp(c.at)})` : ''}`); }
      L.push('', '## Audit trail', '', ...(cut ? [cut, ''] : []), '| When | Who | Action | Detail |', '|---|---|---|---|');
      for (const e of evs) L.push(`| ${stamp(e.at)} | ${String(nameFor(e.author)).replace(/\|/g, '/')} | ${ACTION_LABEL[e.action] || e.action} | ${String(e.detail || '').replace(/\|/g, '/')} |`);
      L.push('', '## Provenance', '', `Built from commit ${m.source_commit}${m.source_dirty ? ', with uncommitted changes' : ''}. Screen rules ${S.spec.rules.schema}. Data files and their SHA-256:`, '', ...Object.entries(m.files).map(([k, v]) => `- ${k}: ${v}`));
      L.push('', '---', '', `${ctx.ogl_line} https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/`, ctx.sources_line, ctx.house_line);
      out = L.join('\n') + '\n'; name = `${f.ref}-evidence.md`;
    }
    try {
      await S.caps.downloads.save({ filename: name, data: out });
      await audit('pack_exported', f, kind === 'json' ? 'data (.json)' : 'evidence pack (.md)');
    } catch (e) { if (e && e.code !== 'declined') banner('dl', 'warn', 'The file could not be saved from this view.'); }
  }

  /* ---------- rendering ---------- */
  const confTag = (c) => h('span', { class: 'tag ' + c }, c);
  function cites(ctx, ids) { return ids.map((id) => h('span', { class: 'cite', title: citeText(ctx, id) }, id)); }
  function claimView(ctx, c) { return h('li', null, h('span', null, c.text), h('span', { class: 'meta' }, confTag(c.confidence), cites(ctx, c.cites))); }
  function renderDoc(d, ctx, review) {
    return h('div', { class: 'brief' },
      h('div', null, h('p', { class: 'headline' }, d.headline.text), h('div', { class: 'claims' }, h('span', { class: 'meta' }, confTag(d.headline.confidence), cites(ctx, d.headline.cites)))),
      SECTIONS.map(([, label, get]) => get(d).length ? h('section', null, h('h3', { class: 'h3' }, label), h('ul', { class: 'claims' }, get(d).map((c) => claimView(ctx, c)))) : null),
      h('section', null, h('h3', { class: 'h3' }, 'Linked enforcement cases'), h('ul', { class: 'claims' }, claimView(ctx, d.linked_cases.note)),
        d.linked_cases.case_ids.length ? h('div', { class: 'row' }, d.linked_cases.case_ids.map((id) => h('span', { class: 'cite' }, id))) : null),
      h('section', null, h('h3', { class: 'h3' }, 'Questions to check'), h('ol', { class: 'plain' }, d.questions_to_check.map((q) => h('li', null, q.question,
        q.why_here ? h('div', { class: 'note' }, 'Why here: ', q.why_here.text, ' ', confTag(q.why_here.confidence), ' ', cites(ctx, q.why_here.cites)) : null)))),
      h('section', null, h('h3', { class: 'h3' }, 'Limits that apply'), h('ul', { class: 'plain' }, d.limits.map((id) => h('li', null, citeText(ctx, id), ' ', h('span', { class: 'cite' }, id))))),
      (d.responds_to_review || []).length ? h('section', null, h('h3', { class: 'h3' }, 'Reviewer notes answered'),
        h('ul', { class: 'claims' }, d.responds_to_review.map((a) => {
          const n = (review || []).find((x) => x.id === a.note);
          return h('li', null, h('div', { class: 'note' }, `${a.note}${n ? `, ${n.kind === 'rejected' ? 'rejected' : 'returned'} ${n.at}: ${n.text}` : ''}`), h('span', null, a.change.text), h('span', { class: 'meta' }, confTag(a.change.confidence), cites(ctx, a.change.cites)));
        }))) : null,
      h('p', { class: 'house-line' }, d.house_line), h('p', { class: 'note' }, d.ogl_line));
  }
  function editor(f, ctx) {
    const u = uiFor(f.docId);
    const d = clone(u.working.draft);
    const lessons = u.working.lessons || [];
    const status = h('div');
    const done = h('button', { class: 'btn primary' }, 'Done editing');
    const review = u.working.review || [];
    const check = () => {
      const r = screen(d, ctx, review);
      swap(status, r.ok ? h('div', { class: 'passed' }, 'Passes the screen.') : problemsBox('Not yet: fix these before saving.', r.problems));
      done.disabled = !r.ok;
      return r;
    };
    let timer = null;
    const later = () => { clearTimeout(timer); timer = setTimeout(check, 250); };
    const claimEdit = (c, label, remove) => {
      const ta = h('textarea', { rows: 3, 'aria-label': label, oninput: (e) => { c.text = e.target.value; later(); } });
      ta.value = c.text;
      const sel = h('select', { 'aria-label': `${label}: confidence`, onchange: (e) => { c.confidence = e.target.value; later(); } }, order().slice().reverse().map((o) => h('option', { value: o, selected: c.confidence === o }, o)));
      const row = h('div', { class: 'claim-edit' }, ta, h('div', { class: 'row' }, sel, remove ? h('button', { class: 'btn quiet small', onclick: () => { remove(); row.remove(); later(); } }, 'Remove') : null),
        h('div', { class: 'row', style: 'grid-column:1/-1' }, cites(ctx, c.cites)));
      return row;
    };
    const list = (arr, label) => arr.map((c, i) => claimEdit(c, `${label}, claim ${i + 1}`, () => { const k = arr.indexOf(c); if (k >= 0) arr.splice(k, 1); }));
    done.addEventListener('click', () => { if (!check().ok) return; u.working = { draft: d, source: 'edited', from: u.working.from || u.working.source, review, lessons }; u.mode = 'view'; keepPrivate(f, u.working); refresh(); });
    const box = h('div', { class: 'editor' },
      h('p', { class: 'note' }, 'Edit the wording and the confidence of each claim, or remove claims. Each claim keeps the facts it cites, and its figures must come from them; the screen checks every change. No names of people or firms.'),
      h('section', { class: 'editor' }, h('h3', { class: 'h3' }, 'Headline'), claimEdit(d.headline, 'Headline')),
      SECTIONS.map(([key, label, get]) => h('section', { class: 'editor' }, h('h3', { class: 'h3' }, label), list(get(d), label))),
      h('section', { class: 'editor' }, h('h3', { class: 'h3' }, 'Linked enforcement cases'), claimEdit(d.linked_cases.note, 'Case note')),
      h('section', { class: 'editor' }, h('h3', { class: 'h3' }, 'Questions to check'),
        d.questions_to_check.map((q, i) => h('div', { class: 'editor' }, h('div', null, `${i + 1}. ${q.question}`),
          q.why_here ? claimEdit(q.why_here, `Why question ${i + 1} fits`, () => { delete q.why_here; }) : null)),
        h('p', { class: 'note' }, 'Questions come from the red-flag list, each citing official guidance; they cannot be reworded here.')),
      (d.responds_to_review || []).length ? h('section', { class: 'editor' }, h('h3', { class: 'h3' }, 'Reviewer notes'),
        d.responds_to_review.map((a) => { const n = review.find((x) => x.id === a.note); return h('div', { class: 'editor' }, h('div', { class: 'note' }, `${a.note}: ${n ? n.text : ''}`), claimEdit(a.change, `Answer to ${a.note}`)); }),
        h('p', { class: 'note' }, 'Say what this version changed because of each note, or why it could not change. Each answer cites its note; a figure in it must come from a fact it cites.')) : null,
      status, h('div', { class: 'row' }, done, h('button', { class: 'btn', onclick: () => { u.mode = 'view'; refresh(); } }, 'Cancel')));
    setTimeout(check, 0);
    return box;
  }

  // The brief panel is being typed in: an editor open on an unlocked file, or a return or reject note.
  function editing(u, w) {
    const locked = ['approved', 'rejected', 'submitted'].includes(w.state);
    return (!!u.working && u.mode === 'edit' && !u.busy && !locked) || (!!u.confirm && w.state === 'submitted' && canApprove());
  }
  function panel(f, w) {
    const u = uiFor(f.docId);
    const decided = ['approved', 'rejected'].includes(w.state), locked = decided || w.state === 'submitted', Dn = w.decision || null;
    const card = h('div', { class: 'card', id: 'brief-panel', dataset: { mode: editing(u, w) ? 'edit' : 'view', doc: f.docId } });
    add(card, h('div', { class: 'card-head' }, h('h2', { class: 'h2' }, 'Analyst brief')));
    const ctx = S.contexts[f.key];
    if (ctx === undefined) { contextFor(f).then(() => refresh()); add(card, h('p', { class: 'note' }, 'Loading the facts for this file…')); return card; }
    if (!ctx || !S.spec.C || !S.spec.schema || !RS) { add(card, h('p', { class: 'note' }, 'The brief engine’s facts or rules for this file are not in this build, so briefs cannot be drafted here.')); return card; }
    if (!u.privateChecked && S.store && S.store.kind === 'db' && S.me.id) {
      u.privateChecked = true;
      loadPrivate(f).then((wk) => { if (wk && !u.working && screen(wk.draft, ctx, wk.review || []).ok) { u.working = wk; u.msg = 'Your unsaved draft was kept. Save it or discard it.'; refresh(); } });
    }
    const nt = notesFor(f, ctx);
    // A decided file shows the version its decision names, never a later save.
    const b = currentBrief(f), all = briefsFor(f);
    const given = h('details', { class: 'given' }, h('summary', null, 'What Claude is given'),
      h('p', { class: 'note' }, 'The drafting rules (spec/prompt.md), the output schema and these facts; after a return or rejection, the reviewers’ notes on this file; and any lessons in force for this route, goods code or corridor, each approved by a second person. Notes and lessons are marked as data. Nothing else: no web and no other files; the lessons are the only text from earlier reviews, and they can come from reviews of other files’ briefs.'),
      h('pre', null, JSON.stringify(ctx, null, 1)),
      nt.usable.length ? h('pre', null, JSON.stringify(nt.usable, null, 1)) : null,
      Lessons.ready() && Lessons.snapshot(f).length ? h('pre', null, JSON.stringify(Lessons.forPrompt(Lessons.snapshot(f)), null, 1)) : null);
    if (u.msg) add(card, h('div', { class: 'banner' }, u.msg));
    if (nt.held.length && !decided) add(card, h('div', { class: 'banner warn' }, `${nt.held.length === 1 ? 'One reviewer’s note was' : `${inWords(nt.held.length)} reviewer notes were`} held back from drafting (${[...new Set(nt.held.flatMap((n) => n.problems.map((p) => problemText(Object.assign({}, p, { path: '' })))))].join('; ')}). Claude is not sent ${nt.held.length === 1 ? 'it' : 'them'}, and the draft does not have to answer ${nt.held.length === 1 ? 'it' : 'them'}.`));
    const bad = badApprovals(f);
    if (bad.length) resolvePeople(bad.map(([d]) => d.author));
    for (const [d, c] of bad) add(card, h('div', { class: 'banner bad' }, `An approval recorded ${stamp(d.decided_at)} by ${person(d.author).name} does not count: ${c.why}.`));
    if (u.busy) {
      add(card, h('div', { class: 'thinking' }, h('span', { class: 'pulse' }), h('span', { id: 'draft-progress' }, 'Claude is drafting from the facts. This can take a minute.')),
        h('div', { class: 'row' }, h('button', { class: 'btn', onclick: () => u.ctl && u.ctl.abort() }, 'Stop')));
      return card;
    }
    if (u.problems && !u.working) add(card, problemsBox('The draft was stopped by the screen and is not shown.', u.problems));
    if (!decided && (u.working || !currentBrief(f) || !Lessons.sameAs(f, currentBrief(f).lessons))) add(card, Lessons.box(f, u.working ? u.working.lessons : null, false, !!currentBrief(f) && !u.working));
    if (u.working) {
      if (u.mode === 'edit' && !locked) { add(card, editor(f, ctx)); return card; }
      const r = screen(u.working.draft, ctx, u.working.review || []);
      add(card, h('div', { class: 'panel-status' }, h('span', { class: 'st st-drafting' }, 'Unsaved draft'), h('span', null, u.working.source === 'claude' ? 'Drafted by Claude' : u.working.source === 'template' ? 'From the template' : 'Edited'), r.ok ? h('span', { class: 'tag Certain' }, 'Screen passed') : null),
        locked ? h('p', { class: 'note' }, decided ? 'This file is decided, so the draft cannot be saved. An editor can reopen the file to work on it; until then you can only discard the draft.'
          : 'This brief is awaiting approval, so the draft cannot be saved. An editor can return it to drafting; until then you can only discard the draft.') : null,
        r.ok ? renderDoc(u.working.draft, ctx, u.working.review) : problemsBox('This draft no longer passes the screen.', r.problems),
        h('div', { class: 'row' },
          locked ? null : h('button', { class: 'btn primary', disabled: !r.ok || !canWrite(), onclick: () => saveDraft(f, ctx) }, 'Save draft'),
          locked ? null : h('button', { class: 'btn', disabled: !canWrite(), onclick: () => { u.mode = 'edit'; refresh(); } }, 'Edit'),
          h('button', { class: 'btn quiet danger', onclick: () => { u.working = null; u.problems = null; u.msg = ''; u.mode = 'view'; dropPrivate(f); refresh(); } }, 'Discard')), given);
      return card;
    }
    const startButtons = () => h('div', { class: 'row' },
      S.caps.sample ? h('button', { class: b ? 'btn' : 'btn primary', disabled: !canWrite(), onclick: () => draftWithClaude(f, ctx, !!b || !!u.problems) }, b || u.problems ? 'Draft again with Claude' : 'Draft with Claude') : null,
      h('button', { class: 'btn', disabled: !canWrite(), onclick: () => { u.working = { draft: template(ctx, nt.usable), source: 'template', review: nt.usable, lessons: Lessons.snapshot(f) }; u.mode = nt.usable.length ? 'edit' : 'view'; u.problems = null; u.msg = ''; refresh(); } }, 'Start from the template'),
      b ? h('button', { class: 'btn', disabled: !canWrite(), onclick: () => { u.working = { draft: withAnswers(clone(b.draft), nt.usable), source: 'edited', from: b.source, review: nt.usable, lessons: Lessons.snapshot(f) }; u.mode = 'edit'; refresh(); } }, 'Edit this version') : null);
    if (!b) {
      if (decided) { add(card, h('p', { class: 'note' }, 'The version this decision names has not loaded, so it is not shown.')); return card; }
      add(card, h('p', { class: 'note' }, S.caps.sample ? (HOSTED ? 'Claude is asked to draft from this file’s facts only, with any reviewers’ notes and approved lessons as data, through the drafting function on the owner’s key. The draft is screened before you see it.' : 'Claude is asked to draft from this file’s facts only, with any reviewers’ notes and approved lessons as data, on your own Claude usage; the first use asks you to allow it. The draft is screened before you see it.')
        : S.caps.sample === null ? 'Claude drafting is not available in this view. The template builds a brief from the facts, word for word, for you to edit.' : 'Checking whether Claude drafting is available…'),
        canWrite() ? startButtons() : h('p', { class: 'note' }, 'You can read this file. Drafting needs Contributor access.'), given);
      return card;
    }
    const r = screen(b.draft, ctx, b.review || []), intact = S.verified.get(b.key);
    const ver = all.findIndex((x) => x.key === b.key) + 1;
    resolvePeople([b.author, Dn && Dn.author].filter(Boolean));
    add(card, h('div', { class: 'panel-status' }, stChip(w.state), h('span', null, `Version ${ver} of ${all.length}, saved ${stamp(b.created_at)} by ${person(b.author).name}`), r.ok && intact === true ? h('span', { class: 'tag Certain' }, 'Screen passed') : null));
    if (intact === false) { add(card, problemsBox('This version does not match the fingerprint saved with it, so it is not shown.', [])); if (canWrite() && !locked) add(card, startButtons()); return card; }
    if (!r.ok) { add(card, problemsBox('This saved brief fails the screen when loaded, so it is not shown. Draft a new version.', r.problems)); if (canWrite() && !locked) add(card, startButtons()); return card; }
    if (Dn && Dn.decision === 'returned' && ['returned', 'drafting'].includes(w.state)) add(card, h('div', { class: 'decision' }, h('b', null, `Returned by ${person(Dn.author).name}, ${stamp(Dn.decided_at)}`), Dn.note ? h('span', null, Dn.note) : null));
    add(card, renderDoc(b.draft, ctx, b.review));
    if ((b.lessons || []).length && !u.working) add(card, Lessons.box(f, b.lessons, true));
    const fourEyes = S.workflow.four_eyes !== false;
    const answered = (b.draft.responds_to_review || []).length;
    const pendingNotes = Dn && Dn.decision === 'returned' && ['returned', 'drafting'].includes(w.state) && !(String(b.created_at || '') > String(Dn.decided_at || ''));
    if (['drafting', 'returned', 'new'].includes(w.state)) {
      if (pendingNotes) add(card, h('p', { class: 'note' }, `This version was saved before the brief was returned. Draft a new version${nt.usable.length ? `: it must answer the reviewer’s note${nt.usable.length === 1 ? '' : 's'}` : ''}, then submit it.`));
      else if (answered) add(card, h('p', { class: 'note' }, `This version answers ${answered === 1 ? 'one reviewer’s note' : `${inWords(answered)} reviewer notes`}.`));
      add(card, h('div', { class: 'row' }, h('button', { class: 'btn primary', disabled: !canWrite() || pendingNotes, onclick: () => submit(f, b, ctx) }, 'Submit for approval')), canWrite() ? startButtons() : null);
    } else if (w.state === 'submitted') {
      const own = b.author === myId();
      if (!canApprove()) add(card, h('p', { class: 'note' }, 'Awaiting approval by an editor.'));
      else if (u.confirm === 'return' || u.confirm === 'reject') {
        const isReject = u.confirm === 'reject';
        const msg = h('div', { 'aria-live': 'polite' });
        const go2 = h('button', { class: 'btn primary' }, isReject ? 'Reject the lead' : 'Return with this note');
        const check = () => {
          const probs = screenNote(u.note || '', ctx);
          const need = isReject ? !u.reason : !(u.note || '').trim();
          swap(msg, probs.length ? problemsBox('Fix the note first.', probs) : h('span'));
          go2.disabled = need || probs.length > 0 || (u.note || '').length > 400;
          return !go2.disabled;
        };
        go2.addEventListener('click', () => { if (check()) decide(f, b, isReject ? 'rejected' : 'returned', isReject ? { reason: u.reason, note: (u.note || '').trim() } : { note: (u.note || '').trim(), keep_lesson: u.keepLesson && Lessons.ready() ? (u.lessonScope || 'route') : null }); });
        const ta = h('textarea', { rows: 3, 'aria-label': 'Note', placeholder: isReject ? 'Optional: what decided it. No names of people or firms.' : 'What needs to change. No names of people or firms.', oninput: (e) => { u.note = e.target.value; check(); } });
        ta.value = u.note || '';
        const sel = isReject ? h('select', { 'aria-label': 'Reason', onchange: (e) => { u.reason = e.target.value; check(); } }, h('option', { value: '' }, 'Choose a reason'), REJECT_REASONS.map(([k, l]) => h('option', { value: k, selected: u.reason === k }, l))) : null;
        // The panel is not redrawn while a note is being typed, so the tick box shows and hides
        // its own options.
        const keepOpts = h('div', { class: 'keep-lesson', hidden: !u.keepLesson },
          h('label', { class: 'field' }, 'Where it applies', h('select', { 'aria-label': 'Where the lesson applies', onchange: (e) => { u.lessonScope = e.target.value; } },
            Lessons.SCOPES.map(([k, label]) => h('option', { value: k, selected: (u.lessonScope || 'route') === k }, label)))),
          h('p', { class: 'note' }, 'A second person must approve a lesson, with a reason, before any draft uses it (Lessons).'));
        const keep = !isReject && Lessons.ready() ? h('div', { class: 'keep-lesson' },
          h('label', { class: 'check' }, h('input', { type: 'checkbox', checked: !!u.keepLesson, onchange: (e) => { u.keepLesson = e.target.checked; keepOpts.hidden = !u.keepLesson; } }), ' Keep this note as a lesson for later drafts'),
          keepOpts) : null;
        add(card, h('div', { class: 'inline-confirm' }, h('b', null, isReject ? 'Reject this lead' : 'Return the brief to its author'), sel ? h('label', { class: 'field' }, 'Reason', sel) : null,
          h('label', { class: 'field' }, isReject ? 'Note (optional, 400 characters at most)' : 'Note (400 characters at most)', ta), keep, msg,
          h('div', { class: 'row' }, go2, h('button', { class: 'btn', onclick: () => { u.confirm = null; u.note = ''; u.reason = ''; refresh(); } }, 'Cancel'))));
        setTimeout(check, 0);
      } else {
        add(card, own && fourEyes ? h('p', { class: 'note' }, 'You saved this version, so with four-eyes on someone else must approve it. You can still return or reject it.') : null,
          h('div', { class: 'row' },
            h('button', { class: 'btn primary', disabled: own && fourEyes, onclick: () => decide(f, b, 'approved') }, 'Approve'),
            h('button', { class: 'btn', onclick: () => { u.confirm = 'return'; refresh(); } }, 'Return with a note'),
            h('button', { class: 'btn quiet danger', onclick: () => { u.confirm = 'reject'; refresh(); } }, 'Reject')));
      }
    } else if (decided) {
      const self = w.state === 'approved' && b.author === Dn.author;
      add(card, h('div', { class: 'decision' },
        h('b', null, `${w.state === 'approved' ? 'Approved' : 'Rejected'} by ${person(Dn.author).name}, ${stamp(Dn.decided_at)}`),
        w.state === 'approved' ? h('span', null, `Four-eyes ${Dn.four_eyes === false ? 'off' : 'on'}${self ? ', and the person who saved it approved it' : ''}. Approved brief SHA-256 ${String(Dn.brief_sha256 || '').slice(0, 16)}…, which matches this text.`)
          : h('span', null, ((REJECT_REASONS.find((x) => x[0] === Dn.reason) || [])[1] || 'No reason given') + (Dn.note ? `: ${Dn.note}` : ''))),
        h('div', { class: 'row' },
          w.state === 'approved' ? h('button', { class: 'btn primary', disabled: !S.caps.downloads, onclick: () => evidencePack(f, b, ctx, 'md') }, 'Evidence pack (.md)') : null,
          w.state === 'approved' ? h('button', { class: 'btn', disabled: !S.caps.downloads, onclick: () => evidencePack(f, b, ctx, 'json') }, 'Data (.json)') : null,
          canApprove() ? h('button', { class: 'btn quiet', onclick: () => decide(f, b, 'reopened') }, 'Reopen the file') : null));
    }
    add(card, given);
    return card;
  }

  return { panel, screen, screenNote, template, promptTurns };
})();

/* ============================================================== lessons
   fd-core's memory core (fdcore/memory.mjs, inlined as window.FdMemory) on the workspace's own
   records. A reviewer who returns a brief can keep the note as a lesson: for the route, for
   the goods code on every corridor, or for the corridor and every code. The lesson is a field
   on the return decision, under the reviewer's own decisions path, so the path says who kept
   it, with the SHA-256 of its scope and text. The memory core admits a person's own reviewed
   note at once, but a note can carry text pasted from elsewhere (fd-core's
   research/POISONING_LOG.md, P1.1), so here every lesson waits for a second person, who is not
   its author, to approve it with a reason, under their own path, for that SHA-256. A lesson in
   force is recalled into later drafts on its route, code or corridor, after the memory core's
   recall screen (planted instructions) and a check of its text against its SHA-256: it is shown
   with its provenance, sent to Claude as data in its own block, never as a fact or a rule, and
   recorded with each version saved. */
const Lessons = (() => {
  const FM = window.FdMemory;
  const Cap = (n) => { const w = inWords(n); return w.charAt(0).toUpperCase() + w.slice(1); };
  const SCOPES = [
    ['route', 'This route only', (f) => ({ route: f.key })],
    ['code', 'This goods code, on every corridor', (f) => ({ code: f.code })],
    ['corridor', 'This corridor, for every code', (f) => ({ corridor: f.iso2 })],
  ];
  const ready = () => !!(FM && S.spec.memRules);
  const scopeOf = (choice, f) => (SCOPES.find((x) => x[0] === choice) || SCOPES[0])[2](f);
  const sha = (scope, text) => sha256(canon({ scope, text }));
  const corridorName = (iso) => { const c = ((S.D.corridors || [])[0] || { corridors: [] }).corridors.find((x) => x.iso2 === iso); return c ? c.name : iso; };
  function scopeWords(sc, f) {
    if (!sc) return 'no scope';
    if (sc.route) { if (f && f.key === sc.route) return 'this route'; const [iso, code] = sc.route.split('-'); return `${corridorName(iso)}, ${fmtCode(code)}`; }
    if (sc.code) return `${fmtCode(sc.code)} on every corridor`;
    if (sc.corridor) return `${corridorName(sc.corridor)}, every code`;
    return 'no scope';
  }
  const where = (f) => ({ route: f.key, code: f.code, corridor: f.iso2 });
  const applies = (sc, f) => { const w = where(f), ks = Object.keys(sc || {}); return ks.length > 0 && ks.every((k) => w[k] === sc[k]); };
  const fileOf = (L) => S.files.find((x) => x.docId === L.lead) || null;
  // The memory core's admission check: kind, scope, source, length, the page's text screen
  // and the planted-instruction patterns. A person's own reviewed note is what it admits.
  function admission(scope, text, ctx) {
    if (!ready()) return { status: 'rejected', why: ['the memory core is not in this build'] };
    const guard = (t) => Brief.screenNote(t, ctx).map((x) => x.code);
    return FM.memoryAdmission({ kind: 'lesson', scope, text, source: 'review:returned-brief', author: myId() || 'unknown', author_kind: 'person', trust: 'high' }, S.spec.memRules, guard);
  }
  // A lesson is in force from the latest decision on it that counts: an approval by someone
  // else, with a reason, for the SHA-256 saved with the lesson; or a decision not to keep it.
  function status(L) {
    const ds = (S.lessonDecisions.get(L.key) || []).slice().sort(byTime('decided_at'));
    let wasApproved = false;
    for (const d of ds) if (d.decision === 'lesson_approved' && d.author !== L.author) wasApproved = true;
    for (let i = ds.length - 1; i >= 0; i--) {
      const d = ds[i];
      if (d.decision === 'lesson_rejected') return { state: 'rejected', d, retired: wasApproved };
      if (d.decision === 'lesson_approved' && d.author !== L.author && String(d.reason || '').trim() && d.lesson_sha256 === L.sha256) return { state: 'approved', d };
    }
    return { state: 'waiting', d: null };
  }
  function asMemory(L) {
    const st = status(L);
    return { id: L.key, kind: 'lesson', scope: L.scope, text: L.text, status: st.state === 'approved' ? 'admitted' : st.state, superseded_by: null,
      valid_from: st.d ? String(st.d.decided_at || '').slice(0, 10) : '', decided_at: st.d ? st.d.decided_at : L.proposed_at,
      provenance: { proposed_by: L.author, proposed_at: L.proposed_at, from_ref: L.ref, approved_by: st.d ? st.d.author : null, approved_at: st.d ? st.d.decided_at : null, reason: st.d ? st.d.reason : '' } };
  }
  // The memory core's recall: lessons in force whose scope fits the file, valid on the day,
  // whose text still matches its SHA-256 and passes the instruction screen again.
  function recall(f) {
    if (!ready()) return { recalled: [], withheld: [] };
    return FM.recallMemories([...S.lessons.values()].map(asMemory), where(f), S.spec.memRules, { limit: 5, verify: (m) => S.lessonVerified.get(m.id) === true });
  }
  // What is kept with a draft and a version: enough to show the lesson and check it later.
  function snapshot(f) {
    return recall(f).recalled.map((m, i) => {
      const L = S.lessons.get(m.id) || {};
      return { key: m.id, id: `lesson-${i + 1}`, scope: m.scope, text: m.text, sha256: L.sha256 || '', proposed_by: m.provenance.proposed_by,
        from_ref: m.provenance.from_ref, approved_by: m.provenance.approved_by, approved_at: m.provenance.approved_at, reason: m.provenance.reason };
    });
  }
  // What goes to Claude: the lesson's words and where it applies, never who or when.
  const forPrompt = (list) => (list || []).map((l) => ({ id: l.id, applies_to: scopeWords(l.scope), text: l.text }));

  function provenanceLine(l, f) {
    return `For ${scopeWords(l.scope, f)}. Kept by ${person(l.proposed_by).name} from a returned brief${l.from_ref ? ` (${l.from_ref})` : ''}; approved by ${person(l.approved_by).name}, ${stamp(l.approved_at)}: ${l.reason}`;
  }
  // The lessons beside a draft: recorded with a draft or a version, or recalled now.
  // Whether the next draft would be given the same lessons as a saved version was.
  const sameAs = (f, recorded) => { const a = snapshot(f).map((l) => l.key + l.sha256).sort().join('|'), b = (recorded || []).map((l) => l.key + l.sha256).sort().join('|'); return a === b; };
  function box(f, recorded, isVersion, forNext) {
    if (!ready()) return null;
    const list = recorded || snapshot(f);
    const rec = recorded ? null : recall(f);
    const withheld = rec ? rec.withheld.filter((w) => S.lessonVerified.has(w.id)) : [];
    const waiting = recorded ? 0 : [...S.lessons.values()].filter((L) => status(L).state === 'waiting' && applies(L.scope, f)).length;
    if (!list.length && !withheld.length && !waiting) return null;
    resolvePeople(list.flatMap((l) => [l.proposed_by, l.approved_by]).filter(Boolean));
    return h('div', { class: 'lessons' },
      h('h3', { class: 'h3' }, isVersion ? 'Lessons in front of the drafter of this version' : recorded ? 'Lessons in front of the drafter' : forNext ? 'Lessons for the next draft' : 'Lessons for this file'),
      list.length ? h('ul', { class: 'plain' }, list.map((l) => h('li', null,
        h('div', null, h('span', { class: 'cite' }, l.id), ' ', l.text), h('div', { class: 'note' }, provenanceLine(l, f))))) : null,
      list.length && !isVersion ? h('p', { class: 'note' }, 'Claude is sent these as data, in their own block, with no names or dates: they never add a figure, a source or a rule, and the screen checks the draft as it always does. Saving a version records them with it.') : null,
      waiting ? h('p', { class: 'note' }, `${waiting === 1 ? 'One more lesson' : `${Cap(waiting)} more lessons`} for this file ${waiting === 1 ? 'is' : 'are'} waiting for a second person, in Lessons.`) : null,
      withheld.length ? h('div', { class: 'banner warn' }, `${withheld.length === 1 ? 'One lesson is' : `${Cap(withheld.length)} lessons are`} held back from drafting: ${[...new Set(withheld.flatMap((w) => w.why))].join('; ')}.`) : null);
  }

  async function decideLesson(L, decision, reason) {
    const why = String(reason || '').trim();
    if (!canApprove() || !why) return;
    if (decision === 'lesson_approved' && L.author === myId()) return;
    const probs = Brief.screenNote(why, null);
    if (probs.length) { banner('lesson', 'warn', 'The reason cannot be saved as it is: no names of people or firms, and no instructions to a model.'); return; }
    if (decision === 'lesson_approved') {
      if ((await sha(L.scope, L.text)) !== L.sha256) { banner('lesson', 'bad', 'This lesson’s text does not match the fingerprint saved with it, so it cannot be approved.'); return; }
      const adm = admission(L.scope, L.text, null);
      if (adm.status === 'rejected') { banner('lesson', 'bad', `The memory core does not admit this lesson: ${adm.why.join('; ')}.`); return; }
    }
    const doc = { lead: L.lead, decision, lesson_id: L.key, lesson_sha256: L.sha256, reason: why.slice(0, 400), decided_at: nowIso() };
    try {
      await ensureMember();
      await S.store.set(ownColl('decisions', myId()), newId('lesson'), doc);
      await audit(decision, fileOf(L), `for ${scopeWords(L.scope)}`);
      const u = uiFor('lesson:' + L.key); u.reason = '';
    } catch (e) { writeFailed(e, 'the decision on the lesson'); }
    refresh();
  }
  function card(L, st) {
    const u = uiFor('lesson:' + L.key);
    const f = fileOf(L), own = L.author === myId(), ok = S.lessonVerified.get(L.key);
    resolvePeople([L.author, st.d && st.d.author].filter(Boolean));
    const head = h('div', null, h('div', { class: 'lesson-text' }, L.text),
      h('div', { class: 'note' }, `For ${scopeWords(L.scope)}. Kept by ${person(L.author).name}, ${stamp(L.proposed_at)}, from a returned brief on `,
        f ? h('a', { href: '#file-' + f.key, class: 'mono' }, L.ref) : h('span', { class: 'mono' }, L.ref), '.'),
      st.d ? h('div', { class: 'note' }, `${st.state === 'approved' ? 'Approved' : st.retired ? 'Retired' : 'Not kept'} by ${person(st.d.author).name}, ${stamp(st.d.decided_at)}: ${st.d.reason || ''}`) : null,
      ok === false ? h('div', { class: 'banner bad' }, 'Its text no longer matches the fingerprint saved with it, so no draft uses it.') : null);
    const reasonBox = (label, decision, primary) => {
      const ta = h('textarea', { rows: 2, 'aria-label': 'Reason', placeholder: 'Why. No names of people or firms.', oninput: (e) => { u.reason = e.target.value; btn.disabled = !u.reason.trim(); } });
      ta.value = u.reason || '';
      const btn = h('button', { class: primary ? 'btn primary' : 'btn', disabled: !(u.reason || '').trim(), onclick: () => decideLesson(L, decision, u.reason) }, label);
      return [ta, btn];
    };
    let actions = null;
    if (st.state === 'waiting' && canApprove() && !own) {
      const [ta, a] = reasonBox('Approve the lesson', 'lesson_approved', true);
      const [, r] = reasonBox('Do not keep it', 'lesson_rejected', false);
      r.disabled = a.disabled; ta.addEventListener('input', () => { r.disabled = a.disabled; });
      actions = h('div', { class: 'inline-confirm' }, h('label', { class: 'field' }, 'Reason (required, 400 characters at most)', ta), h('div', { class: 'row' }, a, r));
    } else if (st.state === 'waiting' && own) {
      const [ta, r] = reasonBox('Withdraw it', 'lesson_rejected', false);
      actions = h('div', { class: 'inline-confirm' }, h('p', { class: 'note' }, 'You kept this note, so someone else must approve it. You can withdraw it.'), canApprove() ? h('label', { class: 'field' }, 'Reason', ta) : null, canApprove() ? r : null);
    } else if (st.state === 'waiting') {
      actions = h('p', { class: 'note' }, 'Waiting for an editor who did not write it.');
    } else if (st.state === 'approved' && canApprove()) {
      const [ta, r] = reasonBox('Retire it', 'lesson_rejected', false);
      actions = h('details', { class: 'given' }, h('summary', null, 'Retire this lesson'), h('label', { class: 'field' }, 'Reason', ta), r);
    }
    return h('li', { class: 'lesson-card' }, head, actions);
  }
  function draw() {
    const v = $('#view-lessons');
    const all = [...S.lessons.values()].sort(byTime('proposed_at')).reverse();
    const g = { waiting: [], approved: [], rejected: [] };
    for (const L of all) { const st = status(L); g[st.state].push(card(L, st)); }
    const section = (title, items, empty) => h('div', { class: 'card' }, h('div', { class: 'card-head' }, h('h2', { class: 'h2' }, title), h('span', { class: 'note' }, String(items.length))),
      items.length ? h('ul', { class: 'plain lesson-list' }, items) : h('p', { class: 'note' }, empty));
    swap(v,
      h('div', { class: 'head' }, h('h1', { class: 'h1' }, 'Lessons'),
        h('p', { class: 'lede' }, 'Notes a reviewer kept from a returned brief, for later drafts on the same route, goods code or corridor. A lesson is used only once a second person approves it, with a reason.'),
        h('p', { class: 'note' }, 'Each lesson is checked by fd-core’s memory core: when it is kept (no names, no instructions to a model, a scope and a source), and every time a draft recalls it (its text against the fingerprint saved with it, and the instruction screen again). Claude is sent lessons as data, never as facts or rules, and the screen checks every draft as usual. A screen is a net, not a guarantee: the second person reads each lesson [Certain].')),
      ready() ? null : h('div', { class: 'banner warn' }, HOSTED ? 'The hosted version has no lessons yet: they run in the artifact and demo builds.' : 'The memory core is not in this build, so lessons cannot be kept or used.'),
      section('Waiting for a second person', g.waiting, 'None. Return a brief with a note and tick “Keep this note as a lesson”.'),
      section('In force', g.approved, 'None yet.'),
      section('Not kept, withdrawn or retired', g.rejected, 'None.'));
  }
  const waitingCount = () => [...S.lessons.values()].filter((L) => status(L).state === 'waiting').length;
  return { SCOPES, ready, scopeOf, sha, scopeWords, admission, status, recall, snapshot, sameAs, forPrompt, box, draw, waitingCount };
})();

/* ============================================================== restricted layer
   What a deployment inside government would run on export declarations, here on synthetic
   records only (radar/declarations): seven detectors, each implementing red flags from the
   official guidance, group their signals into cases. Every line is a question for a person.
   A case goes through the same four-eyes workflow as a lead: an analyst proposes an outcome,
   an editor approves, returns or rejects it, under author-bound records. */
const Decl = (() => {
  const D = { loaded: false, loading: null, error: false, cases: null, evaluation: null, spec: null, graph: null, byId: new Map(), det: new Map(), nodes: new Map(), truth: new Map(), reveal: false, filter: { kind: 'all', order: 'all', det: 'all', state: 'all' } };
  const OUTCOMES = [
    ['refer', 'Refer for investigation'],
    ['more_information', 'Ask the exporter or its agent for more information'],
    ['no_further_action', 'No further action: an ordinary explanation was found'],
  ];
  const OUTCOME_LABEL = Object.fromEntries(OUTCOMES);
  function load() {
    if (D.loaded || D.error) return Promise.resolve(D.loaded);
    if (!D.loading) D.loading = Promise.all(['cases', 'evaluation', 'signals_spec', 'graph'].map((n) => getJSON(`data/declarations/${n}.json`)))
      .then(([c, e, sp, g]) => {
        D.cases = c; D.evaluation = e; D.spec = sp; D.graph = g;
        D.byId = new Map(c.cases.map((x) => [x.id, x]));
        D.det = new Map(sp.detectors.map((d) => [d.id, d]));
        D.nodes = new Map(g.nodes.map((n) => [n.id, n]));
        for (const inj of e.injections || []) for (const cid of inj.cases || []) {
          const was = D.truth.get(cid);
          D.truth.set(cid, was === 'injected' || inj.kind === 'injected' ? 'injected' : 'look-alike');
        }
        D.loaded = true; refresh(); return true;
      })
      .catch((err) => { console.warn('the restricted layer did not load', err); D.error = true; refresh(); return false; });
    return D.loading;
  }
  const fileFor = (c) => ({ docId: 'case_' + c.id, key: 'case-' + c.id, ref: c.id, run: S.D.summary[0].run, series: c.title });
  const casesOnRoute = (key) => (D.loaded ? D.cases.cases.filter((c) => (c.parties.routes || []).includes(key)) : []);
  const routeLink = (key) => (S.byKey.has(key) ? h('button', { class: 'btn quiet small', onclick: () => go('file', key) }, `Public lead file ${key}`) : h('span', { class: 'cite' }, key));
  const kindTag = (k) => h('span', { class: 'sig' }, k);
  const orderTag = (o) => h('span', { class: 'order ' + (o === 'check first' ? 'first' : 'check') }, o === 'check first' ? 'Check first' : 'Check');
  const box = (title, problems) => h('div', { class: 'problems', role: 'alert' }, h('b', null, title), h('ul', null, problems.map((x) => h('li', null, x))));
  const notice = () => h('div', { class: 'banner warn' }, D.cases.notice);
  // A proposed outcome is valid only with a known outcome and a screened note.
  function outcomeProblems(dr, fc) {
    const out = [];
    if (!dr || dr.schema !== 'radar-case-outcome/1' || dr.case_id !== fc.ref) out.push('The record is not an outcome for this case.');
    if (!dr || !OUTCOME_LABEL[dr.outcome]) out.push('Choose an outcome.');
    const note = dr && typeof dr.note === 'string' ? dr.note : '';
    if (note.trim().length < 10) out.push('Give the reason in the note, in a sentence or two.');
    if (note.length > 600) out.push('Keep the note to 600 characters.');
    for (const pr of Brief.screenNote(note, D.byId.get(fc.ref))) out.push(pr.code === 'possible_name' ? 'The note may name a person or firm. Use the ids only.' : ((S.spec.rules && S.spec.rules.problem_codes && S.spec.rules.problem_codes[pr.code]) || pr.code));
    return out;
  }
  async function propose(fc, outcome, note) {
    if (!canWrite()) return;
    const u = uiFor(fc.docId);
    if (['submitted', 'approved', 'rejected'].includes(workflowOf(fc).state)) { u.msg = 'The case is awaiting a decision or decided, so a new outcome cannot be proposed now.'; refresh(); return; }
    const draft = { schema: 'radar-case-outcome/1', case_id: fc.ref, outcome, note: String(note || '').trim() };
    const probs = outcomeProblems(draft, fc);
    if (probs.length) { u.problems = probs; refresh(); return; }
    const id = newId(fc.docId);
    const doc = { lead: fc.docId, run: fc.run, series: fc.series, kind: 'case_outcome', source: 'analyst', draft, sha256: await sha256(canon(draft)), created_at: nowIso() };
    try {
      await ensureMember();
      await S.store.set(ownColl('briefs', myId()), id, doc);
      await upsert('leads', fc.docId, { run: fc.run, series: fc.series, status: 'submitted', brief_id: `${myId()}/${id}`, updated_at: nowIso(), updated_by: myId() });
      await audit('case_outcome_proposed', fc, OUTCOME_LABEL[outcome]);
      u.confirm = null; u.note = ''; u.reason = ''; u.problems = null; u.msg = '';
    } catch (e) { writeFailed(e, 'the outcome'); }
    refresh();
  }
  async function decide(fc, b, decision, extra) {
    if (!canApprove()) return;
    const u = uiFor(fc.docId), w = workflowOf(fc), L = S.leads.get(fc.docId);
    const stale = () => { u.msg = 'The case changed while you were looking at it. Check it again.'; u.confirm = null; refresh(); };
    if (!(decision === 'reopened' ? ['approved', 'rejected'] : ['submitted']).includes(w.state)) return stale();
    if (decision !== 'reopened' && (!b || !L || L.brief_id !== b.key)) return stale();
    const fourEyes = S.workflow.four_eyes !== false;
    if (decision === 'approved') {
      if (fourEyes && b.author === myId()) return;
      if ((await sha256(canon(b.draft))) !== b.sha256 || outcomeProblems(b.draft, fc).length) return stale();
    }
    const doc = Object.assign({ lead: fc.docId, run: fc.run, series: fc.series, decision, brief_id: b ? b.key : null, brief_sha256: b ? b.sha256 : null, four_eyes: fourEyes, decided_at: nowIso() }, extra || {});
    try {
      await ensureMember();
      await S.store.set(ownColl('decisions', myId()), newId(fc.docId), doc);
      await audit({ approved: 'case_outcome_approved', returned: 'case_outcome_returned', rejected: 'case_outcome_rejected', reopened: 'case_reopened' }[decision], fc,
        decision === 'approved' ? `${OUTCOME_LABEL[b.draft.outcome]}, four-eyes ${fourEyes ? 'on' : 'off'}` : decision === 'returned' || decision === 'rejected' ? 'with a note' : '');
    } catch (e) { writeFailed(e, 'the decision'); }
    u.confirm = null; u.note = ''; refresh();
  }
  /* ---------- the list ---------- */
  // The cases the list shows, with its filters, in its order: what a case's place in the list and
  // j and k go by.
  function visible() {
    if (!D.loaded) return [];
    const f = D.filter;
    return D.cases.cases.filter((c) => (f.kind === 'all' || c.kind === f.kind) && (f.order === 'all' || c.check_order === f.order)
      && (f.det === 'all' || c.detectors.includes(f.det)) && (f.state === 'all' || workflowOf(fileFor(c)).state === f.state));
  }
  function drawList() {
    const v = $('#view-declarations');
    if (!D.loaded) { load(); swap(v, h('p', { class: 'note' }, D.error ? 'The restricted layer’s files are not in this build.' : 'Loading the synthetic declarations…')); return; }
    const f = D.filter, all = D.cases.cases, ev = D.evaluation;
    const states = {};
    for (const c of all) { const st = workflowOf(fileFor(c)).state; states[st] = (states[st] || 0) + 1; }
    const rows = visible();
    const select = (label, key, opts) => h('label', { class: 'field inline' }, label, h('select', { onchange: (e) => { D.filter[key] = e.target.value; refresh(); } }, opts.map(([val, text]) => h('option', { value: val, selected: f[key] === val }, text))));
    const kinds = [...new Set(all.map((c) => c.kind))];
    swap(v, 
      h('div', { class: 'head' }, h('h1', { class: 'h1' }, 'Declarations: the restricted layer'),
        h('p', { class: 'lede' }, 'What the radar would do inside government with export declarations, which show who sent what to whom. Here it runs on synthetic records only: seven detectors, each implementing red flags from official guidance, group their signals into cases. Every line is a question for a person to check; none is a finding.'),
        h('p', { class: 'note' }, 'The synthetic world covers the radar\u2019s original nine corridors, not the nine run 3 added [Certain]. Some of its patterns are placed by hand on routes the public radar shows, or on chosen corridors and goods codes; the exporters, consignees, dates and values in each case are drawn at random. A synthetic case says nothing about real exporters, or about the radar\u2019s view of its route [Likely].'),
        h('p', { class: 'house' }, D.cases.house_line)),
      notice(),
      h('div', { class: 'kpis' },
        kpi('Cases', intGB(all.length), `${all.filter((c) => c.check_order === 'check first').length} to check first`),
        kpi('Signals', intGB(ev.overall.signals), 'questions raised by the detectors'),
        kpi('Outcomes approved', intGB(states.approved || 0), `${states.submitted || 0} awaiting a decision`),
        kpi('Detectors', String(D.spec.detectors.length), 'one per pattern, each citing its red flags')),
      h('div', { class: 'row filters-row' },
        select('Kind', 'kind', [['all', 'All kinds'], ...kinds.map((k) => [k, k])]),
        select('Order', 'order', [['all', 'Any'], ['check first', 'Check first'], ['check', 'Check']]),
        select('Detector', 'det', [['all', 'Any'], ...D.spec.detectors.map((d) => [d.id, `${d.id} ${d.title}`])]),
        select('Outcome', 'state', [['all', 'Any'], ['new', 'No outcome'], ['submitted', 'Awaiting a decision'], ['returned', 'Returned'], ['approved', 'Approved'], ['rejected', 'Rejected']])),
      h('div', { class: 'queue' },
        h('div', { class: 'qrow qhead', role: 'presentation' }, h('span', null, 'Case'), h('span', null, 'Kind and order'), h('span', null, 'Detectors'), h('span', null, 'Routes'), h('span', null, 'Outcome')),
        rows.length ? rows.map((c) => {
          const w = workflowOf(fileFor(c));
          return h('button', { class: 'qrow', onclick: () => go('case', c.id), 'aria-label': `Open ${c.id}` },
            h('div', { class: 'q-cell q-main' }, h('span', { class: 'q-ref' }, c.id), h('span', { class: 'q-title' }, c.title), h('span', { class: 'q-desc' }, `${c.questions.length} ${c.questions.length === 1 ? 'question' : 'questions'}`)),
            h('div', { class: 'q-cell' }, h('div', { class: 'q-st' }, kindTag(c.kind), orderTag(c.check_order))),
            h('div', { class: 'q-cell' }, h('span', null, c.detectors.join(', '))),
            h('div', { class: 'q-cell' }, h('span', { class: 'muted' }, (c.parties.routes || []).join(', ') || 'none')),
            h('div', { class: 'q-cell' }, stChip(w.state), selfChip(w)));
        }) : h('p', { class: 'note', style: 'padding:12px 16px' }, 'No case matches these filters.')),
      evaluationCard(),
      h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'What declarations cannot show'), h('p', { class: 'body' }, D.cases.data_cannot_show)));
  }
  /* ---------- evaluation ---------- */
  function evaluationCard() {
    const ev = D.evaluation;
    const out = h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'How the detectors do on the synthetic world'),
      h('p', { class: 'note' }, ev.label),
      h('div', { class: 'scroll' }, h('table', null,
        h('thead', null, h('tr', null, h('th', null, 'Detector'), h('th', { class: 'num' }, 'Fired'), h('th', { class: 'num' }, 'Right'), h('th', { class: 'num' }, 'Look-alikes and ordinary trade'), h('th', { class: 'num' }, 'Missed'), h('th', { class: 'num' }, 'Precision'), h('th', { class: 'num' }, 'Recall'))),
        h('tbody', null, ev.detectors.map((d) => h('tr', null, h('td', null, `${d.detector} ${(D.det.get(d.detector) || {}).title || d.name}`), h('td', { class: 'num' }, d.fired), h('td', { class: 'num' }, d.true_positives),
          h('td', { class: 'num' }, d.false_positives), h('td', { class: 'num' }, d.misses), h('td', { class: 'num' }, d.precision.toFixed(2)), h('td', { class: 'num' }, d.recall.toFixed(2)))),
          h('tr', { class: 'sub' }, h('td', null, 'All seven'), h('td', { class: 'num' }, ev.overall.signals), h('td', { class: 'num' }, ev.overall.true_positives), h('td', { class: 'num' }, ev.overall.false_positives),
            h('td', { class: 'num' }, ev.overall.misses), h('td', { class: 'num' }, ev.overall.precision.toFixed(2)), h('td', { class: 'num' }, ev.overall.recall.toFixed(2)))))),
      h('p', { class: 'note' }, 'Every miss is one of the near misses built to sit just outside a threshold. The thresholds were set on the synthetic data; whether they suit real declarations is a guess [Guessing].'));
    // The analysts' approved outcomes against what was injected: the loop of detector and person,
    // shown only on request so it does not steer anyone working the cases.
    const decided = D.cases.cases.map((c) => [c, workflowOf(fileFor(c))]).filter(([, w]) => w.state === 'approved');
    add(out, h('div', { class: 'row' }, h('button', { class: 'btn small', onclick: () => { D.reveal = !D.reveal; refresh(); } }, D.reveal ? 'Hide the answers' : 'Show the answers'),
      h('span', { class: 'note' }, 'Compares each approved outcome with what the generator put in. Open it once the cases are worked, so it does not steer anyone.')));
    if (D.reveal) {
      const rows = decided.map(([c, w]) => { const b = S.briefs.get(w.decision.brief_id); return [c, b ? b.draft.outcome : null, D.truth.get(c.id) || 'ordinary trade']; });
      const count = (o, t) => rows.filter(([, oo, tt]) => oo === o && tt === t).length;
      add(out, rows.length ? h('div', { class: 'scroll' }, h('table', null,
        h('thead', null, h('tr', null, h('th', null, 'Approved outcome'), h('th', { class: 'num' }, 'Injected pattern'), h('th', { class: 'num' }, 'Look-alike'), h('th', { class: 'num' }, 'Ordinary trade'))),
        h('tbody', null, OUTCOMES.map(([k, l]) => h('tr', null, h('td', null, l), h('td', { class: 'num' }, count(k, 'injected')), h('td', { class: 'num' }, count(k, 'look-alike')), h('td', { class: 'num' }, count(k, 'ordinary trade')))))))
        : h('p', { class: 'note' }, 'No outcome has been approved yet.'),
      h('p', { class: 'note' }, `Of the ${D.cases.cases.length} cases, ${[...D.truth.values()].filter((t) => t === 'injected').length} hold an injected pattern, ${[...D.truth.values()].filter((t) => t === 'look-alike').length} only look-alikes, and the rest ordinary trade [Certain: synthetic ground truth].`));
    }
    return out;
  }
  /* ---------- one case ---------- */
  function graph(c) {
    const cg = D.graph.cases[c.id];
    if (!cg) return null;
    const ids = new Set(cg.nodes), focus = new Set(cg.focus);
    const COL = { exporter: 0, forwarder: 1, consignee: 2, route: 3 }, TITLE = ['Exporters', 'Forwarders', 'Consignees', 'Routes'];
    const cols = [[], [], [], []];
    for (const id of cg.nodes) { const n = D.nodes.get(id); if (n && n.type in COL) cols[COL[n.type]].push(n); }
    cols.forEach((col) => col.sort((a, b) => (focus.has(b.id) - focus.has(a.id)) || (a.id < b.id ? -1 : 1)));
    const W = 760, rowH = 22, top = 34, X = [60, 235, 410, 585];
    const H = top + Math.max(1, ...cols.map((col) => col.length)) * rowH + 10;
    const pos = new Map();
    cols.forEach((col, i) => col.forEach((n, j) => pos.set(n.id, [X[i], top + j * rowH + 8])));
    const edges = D.graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target) && pos.has(e.source) && pos.has(e.target));
    const svg = sv('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `Link graph for ${c.id}: ${cg.nodes.length} parties and routes, ${edges.length} links` },
      TITLE.map((t, i) => sv('text', { x: X[i], y: 14, 'text-anchor': 'middle', class: 'g-lab' }, t)),
      edges.map((e) => { const [x1, y1] = pos.get(e.source), [x2, y2] = pos.get(e.target); const hot = focus.has(e.source) && focus.has(e.target);
        return sv('line', { x1, y1, x2, y2, class: hot ? 'g-edge hot' : 'g-edge' }, sv('title', null, `${e.source.slice(2)} to ${e.target.slice(2)}: ${e.type.replace(/_/g, ' ')}, ${e.items} ${e.items === 1 ? 'item' : 'items'}, ${e.first} to ${e.last}`)); }),
      [...pos.entries()].map(([id, [x, y]]) => sv('g', null, sv('circle', { cx: x, cy: y, r: focus.has(id) ? 5 : 3.5, class: focus.has(id) ? 'g-node hot' : 'g-node' }),
        sv('text', { x: x + 8, y: y + 4, class: focus.has(id) ? 'g-lab hot' : 'g-lab' }, id.slice(2)))));
    return h('div', { class: 'card' }, h('div', { class: 'card-head' }, h('h2', { class: 'h2' }, 'Who is linked'), h('span', { class: 'note' }, 'The case’s parties in bold, with one hop around them. Hover a line for its totals.')),
      h('div', { class: 'scroll' }, h('div', { class: 'graph' }, svg)));
  }
  function questionItems(c) {
    const items = [];
    for (const sg of c.signals) {
      items.push({ id: sg.id, q: sg.question, why: sg.basis, flags: sg.implements, det: sg.detector });
      const det = D.det.get(sg.detector);
      for (const id of sg.then_check || []) {
        if (items.some((x) => x.id === id)) continue;
        const t = det && (det.then_check || []).find((x) => x.id === id);
        items.push({ id, q: t ? t.question : id, why: `Follow-up from ${sg.detector}.`, flags: [id], det: sg.detector });
      }
    }
    return items;
  }
  function checksCard(c, fc, w) {
    const st = (S.checks.get(fc.docId) || {}).items || {};
    const locked = ['approved', 'rejected'].includes(w.state) || !canWrite();
    const items = questionItems(c), who = [];
    const card = h('div', { class: 'card' }, h('div', { class: 'card-head' }, h('h2', { class: 'h2' }, 'Questions to check'),
      h('span', { class: 'note' }, `${items.filter((x) => (st[x.id] || {}).state && st[x.id].state !== 'open').length} of ${items.length} worked through`)));
    add(card, h('div', { class: 'checks' }, items.map((it) => {
      const cur = st[it.id] || {};
      if (cur.by) who.push(cur.by);
      const btn = (state, label) => h('button', { 'aria-pressed': String((cur.state || 'open') === state), disabled: locked, onclick: () => setCheck(fc, it.id, state) }, label);
      return h('div', { class: 'check' },
        h('div', null, h('div', { class: 'q' }, it.q), h('div', { class: 'why' }, it.why),
          h('div', { class: 'why' }, `Red flags: ${it.flags.join(', ')}${cur.by ? ` · ${cur.state === 'done' ? 'Checked' : cur.state === 'na' ? 'Marked not applicable' : 'Reopened'} by ${person(cur.by).name}, ${stamp(cur.at)}` : ''}`)),
        h('div', { class: 'seg', role: 'group', 'aria-label': 'Check state' }, btn('open', 'Open'), btn('done', 'Checked'), btn('na', 'N/A')));
    })));
    resolvePeople(who);
    return card;
  }
  function outcomeCard(c, fc, w) {
    const u = uiFor(fc.docId), Dn = w.decision || null;
    const decided = ['approved', 'rejected'].includes(w.state);
    const b = currentBrief(fc);
    const card = h('div', { class: 'card', id: 'case-panel', dataset: { mode: (u.confirm && (w.state === 'submitted' ? canApprove() : canWrite())) ? 'edit' : 'view', doc: fc.docId } },
      h('div', { class: 'card-head' }, h('h2', { class: 'h2' }, 'Outcome'), stChip(w.state), selfChip(w)));
    if (u.msg) add(card, h('div', { class: 'banner' }, u.msg));
    for (const [d, chk] of badApprovals(fc)) add(card, h('div', { class: 'banner bad' }, `An approval recorded ${stamp(d.decided_at)} by ${person(d.author).name} does not count: ${chk.why}.`));
    if (b) resolvePeople([b.author, Dn && Dn.author].filter(Boolean));
    const intact = b ? S.verified.get(b.key) : null;
    if (b && intact === false) { add(card, box('This outcome does not match the fingerprint saved with it, so it is not shown.', [])); return card; }
    if (b && (w.state !== 'new')) {
      add(card, h('div', { class: 'decision' }, h('b', null, OUTCOME_LABEL[b.draft.outcome] || b.draft.outcome),
        h('span', null, b.draft.note), h('span', { class: 'muted' }, `Proposed ${stamp(b.created_at)} by ${person(b.author).name}.`)));
    }
    if (Dn && Dn.decision === 'returned' && w.state === 'returned') add(card, h('div', { class: 'decision' }, h('b', null, `Returned by ${person(Dn.author).name}, ${stamp(Dn.decided_at)}`), Dn.note ? h('span', null, Dn.note) : null));
    const form = (title, outcomes) => {
      const msg = h('div', { 'aria-live': 'polite' });
      const sel = h('select', { 'aria-label': 'Outcome', onchange: (e) => { u.reason = e.target.value; check(); } }, h('option', { value: '' }, 'Choose an outcome'), outcomes.map(([k, l]) => h('option', { value: k, selected: u.reason === k }, l)));
      const ta = h('textarea', { rows: 3, 'aria-label': 'Reason', placeholder: 'Why, in a sentence or two. Use the ids only: no names of people or firms.', oninput: (e) => { u.note = e.target.value; check(); } });
      ta.value = u.note || '';
      const goBtn = h('button', { class: 'btn primary' }, 'Propose this outcome');
      function check() {
        const probs = u.reason ? outcomeProblems({ schema: 'radar-case-outcome/1', case_id: fc.ref, outcome: u.reason, note: (u.note || '').trim() }, fc) : ['Choose an outcome.'];
        swap(msg, probs.length && (u.note || '').length ? box('Not yet:', probs) : h('span'));
        goBtn.disabled = probs.length > 0;
      }
      goBtn.addEventListener('click', () => { if (!goBtn.disabled) propose(fc, u.reason, u.note); });
      setTimeout(check, 0);
      return h('div', { class: 'inline-confirm' }, h('b', null, title), h('label', { class: 'field' }, 'Outcome', sel), h('label', { class: 'field' }, 'Reason (600 characters at most)', ta), msg,
        h('div', { class: 'row' }, goBtn, h('button', { class: 'btn', onclick: () => { u.confirm = null; refresh(); } }, 'Cancel')));
    };
    if (['new', 'returned', 'drafting'].includes(w.state)) {
      if (!canWrite()) add(card, h('p', { class: 'note' }, 'You can read this case. Proposing an outcome needs Contributor access.'));
      else if (u.confirm === 'propose') add(card, form('Propose an outcome for a second person to approve', OUTCOMES));
      else add(card, h('p', { class: 'note' }, 'Work through the questions, then propose an outcome. An editor approves, returns or rejects it; with four-eyes on, not the person who proposed it.'),
        h('div', { class: 'row' }, h('button', { class: 'btn primary', onclick: () => { u.confirm = 'propose'; u.reason = ''; u.note = ''; refresh(); } }, 'Propose an outcome')));
    } else if (w.state === 'submitted') {
      const own = b && b.author === myId(), fourEyes = S.workflow.four_eyes !== false;
      if (!canApprove()) add(card, h('p', { class: 'note' }, 'Awaiting a decision by an editor.'));
      else if (u.confirm === 'return' || u.confirm === 'reject') {
        const isReject = u.confirm === 'reject', msg = h('div', { 'aria-live': 'polite' });
        const go2 = h('button', { class: 'btn primary' }, isReject ? 'Reject the outcome' : 'Return with this note');
        const check = () => { const probs = Brief.screenNote(u.note || '', c); swap(msg, probs.length ? box('Fix the note first.', probs.map((x) => (x.code === 'possible_name' ? 'The note may name a person or firm.' : x.code))) : h('span')); go2.disabled = probs.length > 0 || !(u.note || '').trim() || (u.note || '').length > 400; };
        go2.addEventListener('click', () => { if (!go2.disabled) decide(fc, b, isReject ? 'rejected' : 'returned', { note: (u.note || '').trim() }); });
        const ta = h('textarea', { rows: 3, 'aria-label': 'Note', placeholder: 'What needs to change. No names of people or firms.', oninput: (e) => { u.note = e.target.value; check(); } });
        ta.value = u.note || '';
        add(card, h('div', { class: 'inline-confirm' }, h('b', null, isReject ? 'Reject this outcome' : 'Return the outcome to its author'), h('label', { class: 'field' }, 'Note (400 characters at most)', ta), msg,
          h('div', { class: 'row' }, go2, h('button', { class: 'btn', onclick: () => { u.confirm = null; u.note = ''; refresh(); } }, 'Cancel'))));
        setTimeout(check, 0);
      } else {
        add(card, own && fourEyes ? h('p', { class: 'note' }, 'You proposed this outcome, so with four-eyes on someone else must approve it.') : null,
          h('div', { class: 'row' },
            h('button', { class: 'btn primary', disabled: own && fourEyes, onclick: () => decide(fc, b, 'approved') }, 'Approve'),
            h('button', { class: 'btn', onclick: () => { u.confirm = 'return'; u.note = ''; refresh(); } }, 'Return with a note'),
            h('button', { class: 'btn quiet danger', onclick: () => { u.confirm = 'reject'; u.note = ''; refresh(); } }, 'Reject')));
      }
    } else if (decided) {
      add(card, h('div', { class: 'decision' }, h('b', null, `${w.state === 'approved' ? 'Approved' : 'Rejected'} by ${person(Dn.author).name}, ${stamp(Dn.decided_at)}`),
        h('span', null, w.state === 'approved' ? `Four-eyes ${Dn.four_eyes === false ? 'off' : 'on'}. Outcome SHA-256 ${String(Dn.brief_sha256 || '').slice(0, 16)}…, which matches this text.` : (Dn.note || 'No note.'))),
      canApprove() ? h('div', { class: 'row' }, h('button', { class: 'btn quiet', onclick: () => decide(fc, b, 'reopened') }, 'Reopen the case')) : null);
    }
    return card;
  }
  function drawCase() {
    const v = $('#view-case');
    if (!D.loaded) { load(); swap(v, h('p', { class: 'note' }, D.error ? 'The restricted layer’s files are not in this build.' : 'Loading the case…')); return; }
    const c = D.byId.get(S.caseId);
    if (!c) { swap(v, h('p', { class: 'note' }, 'There is no such case.')); return; }
    const fc = fileFor(c), w = workflowOf(fc), u = uiFor(fc.docId);
    if (v.dataset.doc !== c.id) {
      v.dataset.doc = c.id;
      const routes = c.parties.routes || [];
      swap(v, recordNav('Declarations', visible().map((x) => x.id), c.id),
        h('div', { class: 'file-head' }, h('div', { class: 'file-meta' }, h('span', { class: 'q-ref' }, c.id), kindTag(c.kind), orderTag(c.check_order), h('span', { class: 'syn-mini' }, 'synthetic')),
          h('h1', { class: 'h1' }, c.title), h('p', { class: 'lede' }, `${c.questions.length} ${c.questions.length === 1 ? 'question' : 'questions'} from ${c.detectors.map((d) => `${d} (${(D.det.get(d) || {}).title || ''})`).join(', ')}.`)),
        notice(),
        h('div', { class: 'file-grid' },
          h('div', { class: 'col' },
            h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'What raised it'), h('ul', { class: 'claims' }, c.signals.map((sg) => h('li', null, h('b', null, `${sg.detector}: ${(D.det.get(sg.detector) || {}).title || sg.name}`), h('span', null, sg.basis),
              h('span', { class: 'meta' }, h('span', { class: 'note' }, 'Implements red flags: '), sg.implements.map((x) => h('span', { class: 'cite' }, x))))))),
            h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'Parties'), h('ul', { class: 'plain' },
              ['exporters', 'consignees', 'forwarders'].map((k) => (c.parties[k] || []).length ? h('li', null, h('b', null, k.charAt(0).toUpperCase() + k.slice(1) + ': '), c.parties[k].join(', ')) : null),
              routes.length ? h('li', null, h('b', null, 'Routes: '), routes.map(routeLink)) : null),
              h('p', { class: 'note' }, 'Ids are made up and look nothing like EORI numbers. A route links to the public radar’s file when the public radar shows it.')),
            graph(c)),
          h('div', { class: 'col' }, h('div', { id: 'slot-case' }), h('div', { id: 'slot-case-checks' }), h('div', { id: 'slot-case-activity' }))));
    }
    const slot = $('#slot-case'), cur = slot.firstElementChild;
    const open = !!u.confirm && cur && cur.dataset.mode === 'edit' && cur.dataset.doc === fc.docId;
    if (!open) swap(slot, outcomeCard(c, fc, w));
    swap($('#slot-case-checks'), checksCard(c, fc, w));
    swap($('#slot-case-activity'), drawActivity(fc));
  }
  const searchItems = () => (D.loaded ? D.cases.cases.map((c) => ({ label: `${c.id} \u00b7 ${c.title}`, sub: `${c.kind} \u00b7 ${c.check_order === 'check first' ? 'Check first' : 'Check'}`, hint: 'Case',
    keywords: [...(c.parties.exporters || []), ...(c.parties.consignees || []), ...(c.parties.forwarders || []), ...(c.parties.routes || [])].join(' '), run: () => go('case', c.id) })) : []);
  return { load, drawList, drawCase, casesOnRoute, isLoaded: () => D.loaded, count: () => (D.loaded ? D.cases.cases.length : null), ids: () => visible().map((c) => c.id), searchItems };
})();

/* ============================================================== triage of incoming reports (synthetic) */
const Triage = (() => {
  // The hosted version records no triage outcomes or checks yet (its database takes lead and case
  // files only), so there the view reads and proposes nothing; the artifact and demo builds do.
  const writable = () => canWrite() && !HOSTED;
  const approvable = () => canApprove() && !HOSTED;
  const T = { loaded: false, loading: null, error: false, reports: null, list: null, spec: null, byId: new Map(), entries: new Map(), filter: { body: 'all', band: 'all', state: 'all', touches: 'all' }, open: new Set() };
  const BAND_LABEL = { 1: 'Listed number', 2: 'Case or near match', 3: 'Radar goods', 4: 'Other' };
  const BAND_CLASS = { 1: 'first', 2: 'first', 3: 'check', 4: 'none' };
  function load() {
    if (T.loaded || T.error) return Promise.resolve(T.loaded);
    if (!T.loading) T.loading = Promise.all(['reports', 'list', 'spec'].map((n) => getJSON(`data/triage/${n}.json`)))
      .then(([r, l, sp]) => {
        T.reports = r; T.list = l; T.spec = sp;
        T.byId = new Map(r.reports.map((x) => [x.id, x]));
        T.entries = new Map(l.entries.map((e) => [e['Unique ID'], e]));
        T.loaded = true; refresh(); return true;
      })
      .catch((err) => { console.warn('the triage files did not load', err); T.error = true; refresh(); return false; });
    return T.loading;
  }
  const OUTCOME_LABEL = () => Object.fromEntries(T.spec.outcomes);
  const fileFor = (x) => ({ docId: 'report_' + x.id, key: 'report-' + x.id, ref: x.id, run: S.D.summary[0].run, series: x.id });
  const country = (iso) => (T.spec.countries && T.spec.countries[iso]) || iso;
  const bandTag = (b) => h('span', { class: 'order ' + BAND_CLASS[b] }, `${b} · ${BAND_LABEL[b]}`);
  const box = (title, problems) => h('div', { class: 'problems', role: 'alert' }, h('b', null, title), h('ul', null, problems.map((x) => h('li', null, x))));
  const notice = () => h('div', { class: 'banner warn' }, T.reports.notice);
  const day = (iso) => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso)); return m ? `${+m[3]} ${MON[+m[2] - 1]} ${m[1]}` : String(iso); };
  const cite = (s) => `${s.publisher}, ${s.title} (${s.date}; read ${s.read}).`;
  // The radar's status for a route, looked up against the run the workspace shows, never stored.
  function routeStatus(key) {
    const [iso, code] = key.split('-');
    if (S.byKey.has(key)) { const f = S.byKey.get(key); return { label: f.status === 'lead' ? 'Lead' : 'Watch', file: f }; }
    const sg = (S.D.signals || []).find((x) => x.iso2 === iso && x.code === code);
    if (!sg) return { label: 'Not a radar corridor', file: null };
    if (sg.uk && sg.uk.shown === false) return { label: 'Not shown (display rule)', file: null };
    return { label: 'Shown: not flagged', file: null };
  }
  // The text a note is screened against: the report and the bodies, so its ids and the bodies' names count as known words.
  const noteCtx = (x) => ({ report: x, bodies: T.spec.bodies });
  function outcomeProblems(dr, fc, x) {
    const out = [];
    if (!dr || dr.schema !== 'radar-triage-outcome/1' || dr.report_id !== fc.ref) out.push('The record is not an outcome for this report.');
    if (!dr || !OUTCOME_LABEL()[dr.outcome]) out.push('Choose an outcome.');
    if (dr && dr.outcome === 'ask' && x && x.anonymous) out.push('This report is anonymous, so the reporter cannot be asked.');
    const note = dr && typeof dr.note === 'string' ? dr.note : '';
    if (note.trim().length < 10) out.push('Give the reason in the note, in a sentence or two.');
    if (note.length > 600) out.push('Keep the note to 600 characters.');
    for (const pr of Brief.screenNote(note, noteCtx(x))) out.push(pr.code === 'possible_name' ? 'The note may name a person or firm. Use the ids only.' : ((S.spec.rules && S.spec.rules.problem_codes && S.spec.rules.problem_codes[pr.code]) || pr.code));
    return out;
  }
  async function propose(x, fc, outcome, note) {
    if (!writable()) return;
    const u = uiFor(fc.docId);
    if (['submitted', 'approved', 'rejected'].includes(workflowOf(fc).state)) { u.msg = 'The report is awaiting a decision or decided, so a new outcome cannot be proposed now.'; refresh(); return; }
    const draft = { schema: 'radar-triage-outcome/1', report_id: fc.ref, outcome, note: String(note || '').trim() };
    const probs = outcomeProblems(draft, fc, x);
    if (probs.length) { u.problems = probs; refresh(); return; }
    const id = newId(fc.docId);
    const doc = { lead: fc.docId, run: fc.run, series: fc.series, kind: 'triage_outcome', source: 'analyst', draft, sha256: await sha256(canon(draft)), created_at: nowIso() };
    try {
      await ensureMember();
      await S.store.set(ownColl('briefs', myId()), id, doc);
      await upsert('leads', fc.docId, { run: fc.run, series: fc.series, status: 'submitted', brief_id: `${myId()}/${id}`, updated_at: nowIso(), updated_by: myId() });
      await audit('triage_outcome_proposed', fc, OUTCOME_LABEL()[outcome]);
      u.confirm = null; u.note = ''; u.reason = ''; u.problems = null; u.msg = '';
    } catch (e) { writeFailed(e, 'the outcome'); }
    refresh();
  }
  async function decide(x, fc, b, decision, extra) {
    if (!approvable()) return;
    const u = uiFor(fc.docId), w = workflowOf(fc), L = S.leads.get(fc.docId);
    const stale = () => { u.msg = 'The report changed while you were looking at it. Check it again.'; u.confirm = null; refresh(); };
    if (!(decision === 'reopened' ? ['approved', 'rejected'] : ['submitted']).includes(w.state)) return stale();
    if (decision !== 'reopened' && (!b || !L || L.brief_id !== b.key)) return stale();
    const fourEyes = S.workflow.four_eyes !== false;
    if (decision === 'approved') {
      if (fourEyes && b.author === myId()) return;
      if ((await sha256(canon(b.draft))) !== b.sha256 || outcomeProblems(b.draft, fc, x).length) return stale();
    }
    const doc = Object.assign({ lead: fc.docId, run: fc.run, series: fc.series, decision, brief_id: b ? b.key : null, brief_sha256: b ? b.sha256 : null, four_eyes: fourEyes, decided_at: nowIso() }, extra || {});
    try {
      await ensureMember();
      await S.store.set(ownColl('decisions', myId()), newId(fc.docId), doc);
      await audit({ approved: 'triage_outcome_approved', returned: 'triage_outcome_returned', rejected: 'triage_outcome_rejected', reopened: 'triage_reopened' }[decision], fc,
        decision === 'approved' ? `${OUTCOME_LABEL()[b.draft.outcome]}, four-eyes ${fourEyes ? 'on' : 'off'}` : decision === 'returned' || decision === 'rejected' ? 'with a note' : '');
    } catch (e) { writeFailed(e, 'the decision'); }
    u.confirm = null; u.note = ''; refresh();
  }
  /* ---------- the list ---------- */
  const cap = (t) => String(t).charAt(0).toUpperCase() + String(t).slice(1);
  const low = (t) => String(t).charAt(0).toLowerCase() + String(t).slice(1);
  function about(x) {
    const g = x.goods;
    const goods = g ? (g.hs_given ? `${g.words} (HS ${fmtCode(g.hs_given)})` : g.words) : null;
    const what = x.service && goods ? `${x.service}: ${goods}` : goods || (T.spec.nexus[x.nexus] || x.nexus);
    return cap(`${what} to ${inText(country(x.destination))}${(x.transit || []).length ? ` via ${x.transit.map((i) => inText(country(i))).join(', ')}` : ''}`);
  }
  // The reports the list shows, with its filters, in reading order and then oldest first: what a
  // report's place in the list and j and k go by.
  function visible() {
    if (!T.loaded) return [];
    const f = T.filter;
    return T.reports.reports.filter((x) => {
      const st = workflowOf(fileFor(x)).state, body = x.matched.body.name;
      return (f.body === 'all' || (f.body === 'other' ? !['HMRC', 'OTSI'].includes(body) : body === f.body))
        && (f.band === 'all' || String(x.matched.order) === f.band) && (f.state === 'all' || st === f.state)
        && (f.touches === 'all' || (f.touches === 'yes') === x.matched.touches_radar);
    }).sort((a, b) => (a.matched.order - b.matched.order) || (a.received < b.received ? -1 : a.received > b.received ? 1 : 0));
  }
  function drawList() {
    const v = $('#view-reports');
    if (!T.loaded) { load(); swap(v, h('p', { class: 'note' }, T.error ? 'The triage files are not in this build.' : 'Loading the synthetic reports…')); return; }
    const f = T.filter, all = T.reports.reports;
    const states = {};
    const bodyOf = (x) => x.matched.body.name;
    for (const x of all) { const st = workflowOf(fileFor(x)).state; states[st] = (states[st] || 0) + 1; }
    const rows = visible();
    const select = (label, key, opts) => h('label', { class: 'field inline' }, label, h('select', { onchange: (e) => { T.filter[key] = e.target.value; refresh(); } }, opts.map(([val, text]) => h('option', { value: val, selected: f[key] === val }, text))));
    const n = (b) => all.filter((x) => x.matched.order === b).length;
    swap(v,
      h('div', { class: 'head' }, h('h1', { class: 'h1' }, 'Reports: triage'),
        h('p', { class: 'lede' }, 'Where reports of a suspected breach of trade sanctions arrive, the radar reads each one against its goods codes, its corridor signals, the synthetic declarations and a synthetic list in the UK Sanctions List’s format. Each report shows the body that handles that kind of report, the factors OTSI’s guidance weighs that it states, and the questions it raises. A person decides what happens to it; a second person approves.'),
        h('p', { class: 'note' }, 'The reports are synthetic, with their routes and goods drawn from the synthetic declarations and at random, so a report on a route says nothing about that route or about any series the display rule holds back [Likely].'),
        h('p', { class: 'house' }, T.spec.house_line)),
      notice(),
      h('div', { class: 'kpis' },
        kpi('Reports', intGB(all.length), `received ${day(all[0].received)} to ${day(all[all.length - 1].received)}`),
        kpi('Read first', intGB(n(1) + n(2)), `${n(1)} with a listed number, ${n(2)} with a case or near match`),
        kpi('For HMRC', intGB(all.filter((x) => bodyOf(x) === 'HMRC').length), 'UK customs, by what each report says'),
        kpi('Outcomes approved', intGB(states.approved || 0), `${states.submitted || 0} awaiting a decision`)),
      h('div', { class: 'row filters-row' },
        select('Body', 'body', [['all', 'Any body'], ['HMRC', 'HMRC'], ['OTSI', 'OTSI'], ['other', 'Another body']]),
        select('Order', 'band', [['all', 'Any'], ...[1, 2, 3, 4].map((b) => [String(b), `${b}: ${BAND_LABEL[b]}`])]),
        select('Touches the radar', 'touches', [['all', 'Either'], ['yes', 'Yes'], ['no', 'No']]),
        select('Outcome', 'state', [['all', 'Any'], ['new', 'No outcome'], ['submitted', 'Awaiting a decision'], ['returned', 'Returned'], ['approved', 'Approved'], ['rejected', 'Rejected']])),
      h('div', { class: 'queue' },
        h('div', { class: 'qrow qhead', role: 'presentation' }, h('span', null, 'Report'), h('span', null, 'Order'), h('span', null, 'Body'), h('span', null, 'What it touches'), h('span', null, 'Outcome')),
        rows.length ? rows.map((x) => {
          const w = workflowOf(fileFor(x)), m = x.matched;
          const touch = [m.list.some((hh) => hh.strength === 'same number') ? 'listed number' : m.list.length ? 'near a listed number' : null,
            m.declaration_cases.length ? `${m.declaration_cases.length} ${m.declaration_cases.length === 1 ? 'case' : 'cases'}` : null,
            m.codes.length ? `${m.codes.length === 1 ? 'HS ' + fmtCode(m.codes[0].code) : m.codes.length + ' possible codes'}` : null].filter(Boolean);
          return h('button', { class: 'qrow', onclick: () => go('report', x.id), 'aria-label': `Open ${x.id}` },
            h('div', { class: 'q-cell q-main' }, h('span', { class: 'q-ref' }, x.id), h('span', { class: 'q-title' }, about(x)), h('span', { class: 'q-desc' }, `${T.spec.channels[x.channel]} · received ${day(x.received)}`)),
            h('div', { class: 'q-cell' }, bandTag(m.order)),
            h('div', { class: 'q-cell' }, h('span', null, m.body.name)),
            h('div', { class: 'q-cell' }, h('span', { class: 'muted' }, touch.join(', ') || 'nothing the radar holds')),
            h('div', { class: 'q-cell' }, stChip(w.state), selfChip(w)));
        }) : h('p', { class: 'note', style: 'padding:12px 16px' }, 'No report matches these filters.')),
      h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'How the order is set'),
        h('ol', null, T.spec.order_rule.map((r) => h('li', null, r.rule))), h('p', { class: 'note' }, T.spec.order_note)),
      h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'What this view cannot do'), h('ul', null, T.spec.limits.map((l) => h('li', null, l)))));
  }
  /* ---------- one report ---------- */
  function saysCard(x) {
    const g = x.goods;
    const li = (label, value) => (value ? h('li', null, h('b', null, label + ': '), value) : null);
    return h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'What the report says'),
      h('ul', { class: 'plain' },
        li('About', T.spec.nexus[x.nexus]),
        li('Goods', g ? `${g.words}${g.hs_given ? `, HS ${fmtCode(g.hs_given)} given` : ', no code given'}` : null),
        li('Service', x.service ? cap(x.service) : null),
        li('Destination', inText(country(x.destination), true)), li('Through', (x.transit || []).map((i) => inText(country(i), true)).join(', ')),
        li('Value', x.value_band), li('When', x.period),
        li('Reporter', `${T.spec.channels[x.channel]}; ${low(T.spec.relationships[x.relationship])}`),
        li('Documents', x.anonymous ? 'None: whistleblowers are told not to send supporting information' : (x.documents || []).join(', '))),
      h('h3', { class: 'h3' }, 'Parties'),
      h('ul', { class: 'plain' }, x.parties.map((p) => h('li', null, h('b', null, p.role.charAt(0).toUpperCase() + p.role.slice(1) + ': '), h('span', { class: 'mono' }, p.id), p.registration ? h('span', { class: 'muted' }, ` · registration ${p.registration}`) : null))),
      x.says.length ? h('h3', { class: 'h3' }, 'It also says') : null,
      x.says.length ? h('ul', { class: 'claims' }, x.says.map((s) => h('li', null, h('span', null, T.spec.statements[s]), h('span', { class: 'meta' }, h('span', { class: 'note' }, 'As the report states it.'))))) : null,
      h('p', { class: 'note' }, 'Ids are made up. EXP-, CON- and FWD- ids are parties in the synthetic declarations; PTY- ids are parties outside UK customs.'));
  }
  function entryCard(e) {
    const filled = T.list.headings.filter((k) => String(e[k] || '').trim());
    return h('div', { class: 'list-entry' },
      h('dl', { class: 'kv' }, filled.map((k) => [h('dt', null, k), h('dd', null, e[k])])),
      h('p', { class: 'note' }, `${T.list.headings.length - filled.length} of the list’s ${T.list.headings.length} headings are blank for this entry.`));
  }
  function touchesCard(x) {
    const m = x.matched;
    const card = h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'What it touches in the radar'));
    if (!m.touches_radar) add(card, h('p', null, 'Nothing: its goods are not among the radar’s codes, its destination is not a radar corridor, and no party is in the synthetic declarations or near the list [Certain on the rules].'));
    if (m.codes.length) add(card, h('h3', { class: 'h3' }, 'Goods'), h('ul', { class: 'plain' }, m.codes.map((c) => h('li', null, h('b', null, `HS ${fmtCode(c.code)}`), ` ${c.description}. CHPL tier ${c.tier}. From ${c.how} `, h('span', { class: 'tag ' + c.confidence }, `[${c.confidence}]`)))));
    else if (x.goods) add(card, h('p', { class: 'note' }, `The words “${x.goods.words}” point to none of the radar’s codes. A person reads the description [Certain].`));
    if (m.routes.length) add(card, h('h3', { class: 'h3' }, 'Routes'), h('ul', { class: 'plain' }, m.routes.map((k) => {
      const st = routeStatus(k);
      return h('li', null, h('span', { class: 'mono' }, k), ' ', st.file ? h('button', { class: 'btn quiet small', onclick: () => go('file', st.file.key) }, `${st.label}: open ${st.file.ref}`) : h('span', { class: 'muted' }, st.label));
    })));
    if (m.declaration_cases.length) add(card, h('h3', { class: 'h3' }, 'Synthetic declaration cases'), h('ul', { class: 'plain' }, m.declaration_cases.map((c) =>
      h('li', null, h('button', { class: 'btn quiet small', onclick: () => go('case', c.case) }, c.case), ` ${c.check_order === 'check first' ? 'Check first' : 'Check'}; holds ${c.parties.join(', ')}.`))));
    if (m.list.length) {
      add(card, h('h3', { class: 'h3' }, 'Synthetic list'));
      for (const hit of m.list) {
        const e = T.entries.get(hit.unique_id), k = x.id + '|' + hit.unique_id, open = T.open.has(k);
        add(card, h('div', { class: 'decision' },
          h('b', null, hit.strength === 'same number' ? `${hit.party}’s registration number is on the list: ${hit.unique_id}` : `${hit.party}’s registration number is one character from ${hit.unique_id}’s`),
          h('span', null, hit.strength === 'same number' ? 'The same number. A person checks the full entry before anything else [Certain on the match].' : `${hit.registration} against ${hit.listed_number}. It may be a typing slip or another business: a person checks [Certain on the match].`),
          h('div', { class: 'row' }, h('button', { class: 'btn quiet small', 'aria-expanded': String(open), onclick: () => { if (open) T.open.delete(k); else T.open.add(k); $('#view-report').dataset.doc = ''; refresh(); } }, open ? 'Hide the entry' : 'Show the entry'))),
          open && e ? entryCard(e) : null);
      }
      add(card, h('p', { class: 'note' }, T.list.notice));
    }
    return card;
  }
  function bodyCard(x) {
    const b = x.matched.body;
    return h('div', { class: 'card' }, h('h2', { class: 'h2' }, `Which body: ${b.name}`), h('p', null, b.why),
      h('p', { class: 'note' }, `By what the report says it is about. A report can touch more than one body, and OTSI passes on what is outside its powers. Source: ${cite(T.spec.body_source)}`));
  }
  function factorsCard(x) {
    const fs = x.matched.factors, F = T.spec.factors;
    const group = (g, title) => { const ids = fs.filter((f) => f.group === g).map((f) => f.id); return ids.length ? [h('h3', { class: 'h3' }, title), h('ul', { class: 'plain' }, ids.map((id) => h('li', null, F[g][id] + (g === 'severity' && id === 'value' ? `: ${x.value_band}, as stated. OTSI publishes no thresholds [Certain].` : '.'))))] : []; };
    const parts = [...group('severity', 'Severity'), ...group('mitigating', 'Mitigating'), ...group('aggravating', 'Aggravating')];
    return h('div', { class: 'card' }, h('h2', { class: 'h2' }, 'Factors it touches, in OTSI’s terms'),
      parts.length ? parts : h('p', { class: 'note' }, 'The report states none of them.'),
      h('p', { class: 'note' }, `Our reading of what the report states [Likely]. OTSI weighs these only once it has assessed a report. Source: ${cite(T.spec.factor_source)}`));
  }
  function questionsCard(x, fc, w) {
    const st = (S.checks.get(fc.docId) || {}).items || {};
    const locked = ['approved', 'rejected'].includes(w.state) || !writable();
    const items = ((S.spec.redflags && S.spec.redflags.items) || []).filter((it) => x.matched.red_flags.includes(it.id));
    items.sort((a, b) => x.matched.red_flags.indexOf(a.id) - x.matched.red_flags.indexOf(b.id));
    const who = [];
    const card = h('div', { class: 'card' }, h('div', { class: 'card-head' }, h('h2', { class: 'h2' }, 'Questions it raises'),
      h('span', { class: 'note' }, `${items.filter((it) => (st[it.id] || {}).state && st[it.id].state !== 'open').length} of ${items.length} worked through`)));
    if (!items.length) { add(card, h('p', { class: 'note' }, 'None from the radar’s red flag list.')); return card; }
    add(card, h('div', { class: 'checks' }, items.map((it) => {
      const cur = st[it.id] || {};
      if (cur.by) who.push(cur.by);
      const btn = (state, label) => h('button', { 'aria-pressed': String((cur.state || 'open') === state), disabled: locked, onclick: () => setCheck(fc, it.id, state) }, label);
      return h('div', { class: 'check' },
        h('div', null, h('div', { class: 'q' }, it.question), h('div', { class: 'why' }, it.why),
          cur.by ? h('div', { class: 'why' }, `${cur.state === 'done' ? 'Checked' : cur.state === 'na' ? 'Marked not applicable' : 'Reopened'} by ${person(cur.by).name}, ${stamp(cur.at)}`) : null),
        h('div', { class: 'seg', role: 'group', 'aria-label': 'Check state' }, btn('open', 'Open'), btn('done', 'Checked'), btn('na', 'N/A')));
    })));
    resolvePeople(who);
    return card;
  }
  function outcomeCard(x, fc, w) {
    const u = uiFor(fc.docId), Dn = w.decision || null, LBL = OUTCOME_LABEL();
    const decided = ['approved', 'rejected'].includes(w.state);
    const b = currentBrief(fc);
    const card = h('div', { class: 'card', id: 'report-panel', dataset: { mode: (u.confirm && (w.state === 'submitted' ? approvable() : writable())) ? 'edit' : 'view', doc: fc.docId } },
      h('div', { class: 'card-head' }, h('h2', { class: 'h2' }, 'Outcome'), stChip(w.state), selfChip(w)));
    if (u.msg) add(card, h('div', { class: 'banner' }, u.msg));
    if (u.problems && u.problems.length) add(card, box('Not saved:', u.problems));
    for (const [d, chk] of badApprovals(fc)) add(card, h('div', { class: 'banner bad' }, `An approval recorded ${stamp(d.decided_at)} by ${person(d.author).name} does not count: ${chk.why}.`));
    if (b) resolvePeople([b.author, Dn && Dn.author].filter(Boolean));
    const intact = b ? S.verified.get(b.key) : null;
    if (b && intact === false) { add(card, box('This outcome does not match the fingerprint saved with it, so it is not shown.', [])); return card; }
    if (b && w.state !== 'new') add(card, h('div', { class: 'decision' }, h('b', null, LBL[b.draft.outcome] || b.draft.outcome), h('span', null, b.draft.note), h('span', { class: 'muted' }, `Proposed ${stamp(b.created_at)} by ${person(b.author).name}.`)));
    if (Dn && Dn.decision === 'returned' && w.state === 'returned') add(card, h('div', { class: 'decision' }, h('b', null, `Returned by ${person(Dn.author).name}, ${stamp(Dn.decided_at)}`), Dn.note ? h('span', null, Dn.note) : null));
    if (['new', 'returned', 'drafting'].includes(w.state)) {
      if (!writable()) add(card, h('p', { class: 'note' }, HOSTED ? 'The hosted version records no triage outcomes yet: they run in the artifact and demo builds.' : 'You can read this report. Proposing an outcome needs Contributor access.'));
      else if (u.confirm === 'propose') {
        const msg = h('div', { 'aria-live': 'polite' });
        const opts = T.spec.outcomes.filter(([k]) => !(k === 'ask' && x.anonymous));
        const sel = h('select', { 'aria-label': 'Outcome', onchange: (e) => { u.reason = e.target.value; check(); } }, h('option', { value: '' }, 'Choose an outcome'), opts.map(([k, l]) => h('option', { value: k, selected: u.reason === k }, l)));
        const ta = h('textarea', { rows: 3, 'aria-label': 'Reason', placeholder: 'Why, in a sentence or two. Use the ids only: no names of people or firms.', oninput: (e) => { u.note = e.target.value; check(); } });
        ta.value = u.note || '';
        const goBtn = h('button', { class: 'btn primary' }, 'Propose this outcome');
        function check() {
          const probs = u.reason ? outcomeProblems({ schema: 'radar-triage-outcome/1', report_id: fc.ref, outcome: u.reason, note: (u.note || '').trim() }, fc, x) : ['Choose an outcome.'];
          swap(msg, probs.length && (u.note || '').length ? box('Not yet:', probs) : h('span'));
          goBtn.disabled = probs.length > 0;
        }
        goBtn.addEventListener('click', () => { if (!goBtn.disabled) propose(x, fc, u.reason, u.note); });
        setTimeout(check, 0);
        add(card, h('div', { class: 'inline-confirm' }, h('b', null, 'Propose an outcome for a second person to approve'), h('label', { class: 'field' }, 'Outcome', sel), h('label', { class: 'field' }, 'Reason (600 characters at most)', ta), msg,
          h('div', { class: 'row' }, goBtn, h('button', { class: 'btn', onclick: () => { u.confirm = null; refresh(); } }, 'Cancel'))));
      } else add(card, h('p', { class: 'note' }, `Suggested by what the report says: ${x.matched.body.name === 'HMRC' ? 'pass to HMRC' : x.matched.body.name === 'OTSI' ? 'assess further' : 'pass to another body'}. You decide; an editor approves, returns or rejects it, and with four-eyes on not the person who proposed it.`),
        h('div', { class: 'row' }, h('button', { class: 'btn primary', onclick: () => { u.confirm = 'propose'; u.reason = ''; u.note = ''; u.problems = null; refresh(); } }, 'Propose an outcome')));
    } else if (w.state === 'submitted') {
      const own = b && b.author === myId(), fourEyes = S.workflow.four_eyes !== false;
      if (!approvable()) add(card, h('p', { class: 'note' }, 'Awaiting a decision by an editor.'));
      else if (u.confirm === 'return' || u.confirm === 'reject') {
        const isReject = u.confirm === 'reject', msg = h('div', { 'aria-live': 'polite' });
        const go2 = h('button', { class: 'btn primary' }, isReject ? 'Reject the outcome' : 'Return with this note');
        const check = () => { const probs = Brief.screenNote(u.note || '', noteCtx(x)); swap(msg, probs.length ? box('Fix the note first.', probs.map((p) => (p.code === 'possible_name' ? 'The note may name a person or firm.' : p.code))) : h('span')); go2.disabled = probs.length > 0 || !(u.note || '').trim() || (u.note || '').length > 400; };
        go2.addEventListener('click', () => { if (!go2.disabled) decide(x, fc, b, isReject ? 'rejected' : 'returned', { note: (u.note || '').trim() }); });
        const ta = h('textarea', { rows: 3, 'aria-label': 'Note', placeholder: 'What needs to change. No names of people or firms.', oninput: (e) => { u.note = e.target.value; check(); } });
        ta.value = u.note || '';
        add(card, h('div', { class: 'inline-confirm' }, h('b', null, isReject ? 'Reject this outcome' : 'Return the outcome to its author'), h('label', { class: 'field' }, 'Note (400 characters at most)', ta), msg,
          h('div', { class: 'row' }, go2, h('button', { class: 'btn', onclick: () => { u.confirm = null; u.note = ''; refresh(); } }, 'Cancel'))));
        setTimeout(check, 0);
      } else {
        add(card, own && fourEyes ? h('p', { class: 'note' }, 'You proposed this outcome, so with four-eyes on someone else must approve it.') : null,
          h('div', { class: 'row' },
            h('button', { class: 'btn primary', disabled: own && fourEyes, onclick: () => decide(x, fc, b, 'approved') }, 'Approve'),
            h('button', { class: 'btn', onclick: () => { u.confirm = 'return'; u.note = ''; refresh(); } }, 'Return with a note'),
            h('button', { class: 'btn quiet danger', onclick: () => { u.confirm = 'reject'; u.note = ''; refresh(); } }, 'Reject')));
      }
    } else if (decided) {
      add(card, h('div', { class: 'decision' }, h('b', null, `${w.state === 'approved' ? 'Approved' : 'Rejected'} by ${person(Dn.author).name}, ${stamp(Dn.decided_at)}`),
        h('span', null, w.state === 'approved' ? `Four-eyes ${Dn.four_eyes === false ? 'off' : 'on'}. Outcome SHA-256 ${String(Dn.brief_sha256 || '').slice(0, 16)}…, which matches this text.` : (Dn.note || 'No note.'))),
      approvable() ? h('div', { class: 'row' }, h('button', { class: 'btn quiet', onclick: () => decide(x, fc, b, 'reopened') }, 'Reopen the report')) : null);
    }
    return card;
  }
  function drawReport() {
    const v = $('#view-report');
    if (!T.loaded) { load(); swap(v, h('p', { class: 'note' }, T.error ? 'The triage files are not in this build.' : 'Loading the report…')); return; }
    const x = T.byId.get(S.reportId);
    if (!x) { swap(v, h('p', { class: 'note' }, 'There is no such report.')); return; }
    const fc = fileFor(x), w = workflowOf(fc), u = uiFor(fc.docId);
    if (v.dataset.doc !== x.id) {
      v.dataset.doc = x.id;
      swap(v, recordNav('Reports', visible().map((y) => y.id), x.id),
        h('div', { class: 'file-head' }, h('div', { class: 'file-meta' }, h('span', { class: 'q-ref' }, x.id), bandTag(x.matched.order), h('span', { class: 'syn-mini' }, 'synthetic')),
          h('h1', { class: 'h1' }, about(x)), h('p', { class: 'lede' }, `${T.spec.channels[x.channel]}, received ${day(x.received)}. A report is an allegation until a person has assessed it.`)),
        notice(),
        h('div', { class: 'file-grid' },
          h('div', { class: 'col' }, saysCard(x), touchesCard(x), bodyCard(x), factorsCard(x)),
          h('div', { class: 'col' }, h('div', { id: 'slot-report' }), h('div', { id: 'slot-report-checks' }), h('div', { id: 'slot-report-activity' }))));
    }
    const slot = $('#slot-report'), cur = slot.firstElementChild;
    const open = !!u.confirm && cur && cur.dataset.mode === 'edit' && cur.dataset.doc === fc.docId;
    if (!open) swap(slot, outcomeCard(x, fc, w));
    swap($('#slot-report-checks'), questionsCard(x, fc, w));
    swap($('#slot-report-activity'), drawActivity(fc));
  }
  // In the order the list shows them: reading order, then oldest first.
  const ordered = () => (T.loaded ? T.reports.reports.slice().sort((a, b) => (a.matched.order - b.matched.order) || (a.received < b.received ? -1 : a.received > b.received ? 1 : 0)) : []);
  const searchItems = () => ordered().map((x) => ({ label: `${x.id} \u00b7 ${about(x)}`, sub: `${x.matched.body.name} \u00b7 ${BAND_LABEL[x.matched.order]}`, hint: 'Report',
    keywords: x.parties.map((p) => p.id + ' ' + (p.registration || '')).join(' '), run: () => go('report', x.id) }));
  const onRoute = (key) => (T.loaded ? T.reports.reports.filter((x) => ((x.matched && x.matched.routes) || []).includes(key)) : []);
  return { load, drawList, drawReport, onRoute, isLoaded: () => T.loaded, has: (id) => T.byId.has(id), count: () => (T.loaded ? T.reports.reports.length : null), ids: () => visible().map((x) => x.id), searchItems };
})();

/* ============================================================== boot */
async function boot() {
  try { await loadStatic(); } catch (e) {
    swap($('#view-inbox'), h('div', { class: 'banner bad' }, 'The run’s data could not be loaded. Reload the page; if it still does not load, the data files are missing from this build.'));
    return;
  }
  buildFiles();
  const m = S.D.manifest[0];
  $('#provenance').textContent = `Data: ${m.run_label} run, commit ${m.source_commit}.`;
  mountShell();
  routeFromHash();
  Decl.load();
  Triage.load();
  // Capabilities light up as they arrive; the page works without each of them.
  useCap('user').then(async (user) => {
    S.caps.user = user;
    if (user) {
      try {
        const me = await user.me();
        S.me.id = me.id; S.me.name = me.name || ''; S.me.avatar = me.avatarUrl || ''; S.me.isOwner = !!me.isOwner; S.me.canEdit = !!me.canEdit;
        S.me.canData = await user.can('data.write');
      } catch { /* reads never reject; keep defaults */ }
      S.me.role = S.me.isOwner ? 'Owner' : S.me.canEdit ? 'Editor' : S.me.canData === true ? 'Contributor' : S.me.canData === false ? 'Viewer' : '';
      if (S.store && S.store.kind === 'db' && S.me.id) addMember(S.me.id);
    }
    refresh();
  });
  useCap('sample').then((sample) => { S.caps.sample = sample; refresh(); });
  useCap('downloads').then((dl) => { S.caps.downloads = dl; refresh(); });
  const db = await useCap('db');
  S.caps.db = db;
  if (db) { S.store = dbStore(db); S.storeState = 'live'; }
  else {
    S.store = memoryStore(); S.storeState = 'demo';
    banner('demo', 'warn', 'Demo mode: this view has no shared store, so changes stay in this tab and go when it closes.');
  }
  subscribeAll();
  refresh();
  if (isDemo() && !HOSTED && !DEMO_PEOPLE[session.get()]) showPortal(!location.hash || location.hash === '#overview');
}
const AUDIT_LIMIT = 1000, MAX_MEMBERS = 18;
let unsubs = [];
const memberUnsubs = new Map(), seq = new Map();
const onErr = (what) => (e) => {
  if (e && e.code === 'revoked') banner('revoked', 'warn', 'This view no longer has access to the shared store.');
  else if (e && e.code === 'resource_exhausted') banner('subs', 'warn', 'This view reached the store\u2019s limit on live updates, so some records may not show. Tell the owner.');
  else banner('sub-' + what, 'warn', `Live updates for ${what} stopped. Reload the page to reconnect.`);
};
// Each person's briefs are checked against the SHA-256 saved with them as they arrive.
async function onBriefs(uid, rows) {
  const n = (seq.get(uid) || 0) + 1;
  seq.set(uid, n);
  const list = rows.map((r) => Object.assign({}, r.data, { id: r.id, author: uid, key: `${uid}/${r.id}` })).filter((b) => b.draft && typeof b.lead === 'string');
  const ok = await Promise.all(list.map(async (b) => (await sha256(canon(b.draft))) === b.sha256));
  if (seq.get(uid) !== n) return;   // a newer snapshot arrived meanwhile
  list.forEach((b, i) => S.verified.set(b.key, ok[i]));
  S.byMember.briefs.set(uid, list);
  S.briefs = new Map([...S.byMember.briefs.values()].flat().map((b) => [b.key, b]));
  refresh();
}
function onDecisions(uid, rows) {
  S.byMember.decisions.set(uid, rows.map((r) => Object.assign({}, r.data, { id: r.id, author: uid })));
  const m = new Map(), lessons = new Map(), ld = new Map();
  for (const d of [...S.byMember.decisions.values()].flat()) {
    // A return that keeps its note as a lesson; the lesson's key is the decision's own path.
    if (d.decision === 'returned' && d.lesson && d.lesson.scope && typeof d.note === 'string' && d.note.trim() && typeof d.lead === 'string') {
      const key = `${d.author}/${d.id}`;
      lessons.set(key, { key, author: d.author, lead: d.lead, ref: 'DR-' + d.lead.replace('_', '-'), scope: d.lesson.scope, text: d.note.trim(), sha256: d.lesson.sha256, proposed_at: d.decided_at });
    }
    if (['lesson_approved', 'lesson_rejected'].includes(d.decision) && typeof d.lesson_id === 'string') {
      if (!ld.has(d.lesson_id)) ld.set(d.lesson_id, []);
      ld.get(d.lesson_id).push(d);
      continue;
    }
    if (typeof d.lead !== 'string' || !['approved', 'returned', 'rejected', 'reopened'].includes(d.decision)) continue;
    if (!m.has(d.lead)) m.set(d.lead, []);
    m.get(d.lead).push(d);
  }
  S.decisions = m; S.lessons = lessons; S.lessonDecisions = ld;
  verifyLessons();
  refresh();
}
// Each lesson's text is checked against the SHA-256 saved with it as it arrives.
let lessonSeq = 0;
async function verifyLessons() {
  const n = ++lessonSeq, list = [...S.lessons.values()];
  const ok = await Promise.all(list.map(async (L) => (await sha256(canon({ scope: L.scope, text: L.text }))) === L.sha256));
  if (n !== lessonSeq) return;
  S.lessonVerified = new Map(list.map((L, i) => [L.key, ok[i]]));
  refresh();
}
function onAudit(uid, rows) {
  S.byMember.audit.set(uid, rows.map((r) => Object.assign({}, r.data, { id: r.id, author: uid })));
  if (rows.length >= AUDIT_LIMIT) S.auditCapped = true;
  S.audit = [...S.byMember.audit.values()].flat().sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0));
  refresh();
}
function addMember(uid) {
  if (!uid || S.members.has(uid) || !S.store) return;
  if (S.members.size >= MAX_MEMBERS) { banner('members', 'warn', `More than ${MAX_MEMBERS} people have worked in this workspace, and this view reads the records of the first ${MAX_MEMBERS} only. Tell the owner.`); return; }
  S.members.add(uid);
  memberUnsubs.set(uid, [
    S.store.watch(ownColl('briefs', uid), null, (rows) => { onBriefs(uid, rows); }, onErr('briefs')),
    S.store.watch(ownColl('decisions', uid), null, (rows) => onDecisions(uid, rows), onErr('decisions')),
    S.store.watch(ownColl('audit', uid), { orderBy: 'at', dir: 'desc', limit: AUDIT_LIMIT }, (rows) => onAudit(uid, rows), onErr('the audit log')),
  ]);
}
function subscribeAll() {
  unsubs.forEach((u) => { try { u(); } catch { /* already closed */ } });
  unsubs = [];
  const asMap = (rows) => new Map(rows.map((r) => [r.id, r.data]));
  unsubs.push(S.store.watch('leads', null, (rows) => { S.leads = asMap(rows); refresh(); }, onErr('files')));
  unsubs.push(S.store.watch('checks', null, (rows) => { S.checks = asMap(rows); refresh(); }, onErr('checks')));
  unsubs.push(S.store.watch('tasks', null, (rows) => { S.tasks = asMap(rows); refresh(); }, onErr('follow-ups')));
  unsubs.push(S.store.watch('outcomes', null, (rows) => { S.outcomes = asMap(rows); refresh(); }, onErr('outcomes')));
  unsubs.push(S.store.watch('enduse', null, (rows) => { S.enduse = asMap(rows); refresh(); }, onErr('decision records')));
  unsubs.push(S.store.watch('monitor', null, (rows) => { S.monitorDec = asMap(rows); refresh(); }, onErr('monitoring decisions')));
  unsubs.push(S.store.watchDoc('config', 'workflow', (doc) => { S.workflow = Object.assign({ four_eyes: true }, doc || {}); refresh(); }, onErr('settings')));
  unsubs.push(S.store.watch('members', null, (rows) => { S.memberIds = new Set(rows.map((r) => r.id)); S.memberInfo = new Map(rows.map((r) => [r.id, r.data || {}])); rows.forEach((r) => addMember(r.id)); refresh(); }, onErr('people')));
  if (S.store.kind === 'memory') Object.keys(DEMO_PEOPLE).forEach(addMember);
  else if (S.me.id) addMember(S.me.id);
}
window.addEventListener('hashchange', () => { if (S.files.length) routeFromHash(); });
boot();
})();
