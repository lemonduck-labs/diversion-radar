// The draft-brief function's logic. Every outside call (the session check, the database, Claude,
// the clock) is passed in, so node can test it without the network (tests/hosted_js_run.mjs)
// and Deno runs it unchanged (index.ts).
//
// POST {slug, prompt_sha256} with the caller's session token in Authorization. slug names one
// file's facts (app/data/briefs/<slug>.json). The function checks the session and the caller's
// role, reads the file's reviewer notes from the decisions in the database (never from the
// caller), builds the drafting prompt from its own copy of the facts and those notes with the
// page's own code (app/src/screen.js, buildPrompt; no lessons, since the hosted version has
// none yet), refuses if the page built a different prompt, asks Claude through the Messages API
// with the owner's key, reads the reply with parseReply and screens it as the reference screen
// does (radar/brief/screen.py, screen_draft): the shared rules of screen.js, then fd-core's
// guardrails over every string with the private deny list. It records the draft in
// public.drafts and returns {passed, problems, draft}.
//
// A draft that fails is never returned: the caller learns which rules it broke and where, and
// what matched only for rules whose match cannot itself be a name or personal data (the page's
// own list). The reply's text is never logged.
//
// Outputs are leads for a person, never findings. A rise in exports is a lead, not evidence of
// a breach.

export const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
export const ANTHROPIC_VERSION = "2023-06-01";
export const DEFAULT_MODEL = "claude-sonnet-5-5";
export const DEFAULT_MAX_TOKENS = 8000;
export const DEFAULT_DRAFTS_PER_HOUR = 30;
// What matched is returned only for these codes (app/src/page.js, Brief's SAFE_DETAIL).
export const SAFE_DETAIL = new Set(["invented_figure", "uncited_figure", "accusing_language", "unknown_fact", "unknown_case", "cases_missing",
  "unknown_red_flag", "confidence_above_source", "series_mismatch", "run_mismatch", "review_unanswered", "review_unknown", "review_duplicate",
  "review_not_cited", "review_placeholder"]);
// The page's words for a rejection's reason (app/src/page.js, Brief's REJECT_REASONS).
export const REJECT_LABELS = { ordinary_trade: "Ordinary trade explains the rise", data: "A data problem or revision",
  duplicate: "Already covered by another file", other: "Other (see the note)" };
// fd-core finding kinds as problem codes (radar/brief/screen.py, FDCORE_CODES).
export const FDCORE_CODES = { "company name": "company_name", "email address": "email", "UK postcode": "postcode",
  "phone number": "phone", "deny-list name": "deny_list_name", "accusing language": "accusing_language" };
const RANK = { viewer: 1, contributor: 2, editor: 3, owner: 4 };
const SLUG = /^[a-z0-9][a-z0-9-]{0,80}$/;
const HEX64 = /^[0-9a-f]{64}$/;

// The page's canonical JSON (app/src/page.js, canon): keys sorted at every level.
export function canon(v) {
  if (Array.isArray(v)) return "[" + v.map(canon).join(",") + "]";
  if (v && typeof v === "object") return "{" + Object.keys(v).sort().map((k) => JSON.stringify(k) + ":" + canon(v[k])).join(",") + "}";
  return JSON.stringify(v);
}

// The text the page's prompt and the function's are compared by: the system and the user turn.
export const promptKey = (p) => JSON.stringify([String(p.system), String(p.user)]);

// Times as the page holds them (app/src/hosted.js, toIso): milliseconds and Z, so decisions sort
// here exactly as they sort in the page.
export function toIso(v) {
  if (v === null || v === undefined || v === "") return v === undefined ? null : v;
  const s = String(v);
  const m = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.(\d+))?(?:Z|[+-]00(?::?00)?)$/.exec(s);
  if (m) return `${m[1]}T${m[2]}.${(m[3] || "").padEnd(3, "0").slice(0, 3)}Z`;
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toISOString();
}

// The page's byTime (app/src/page.js): by the field, then by id.
const byTime = (k) => (a, b) => (a[k] < b[k] ? -1 : a[k] > b[k] ? 1 : a.id < b.id ? -1 : a.id > b.id ? 1 : 0);

// Whether an approval counts, as the page's approvalCheck decides it: the brief it names is this
// file's and has the SHA-256 it names, and the person who saved the brief did not approve it
// unless four-eyes is off, both now and in the decision. The database already refuses an approval
// that breaks these when it is made, and keeps each brief's SHA-256 true to its draft; the setting
// can change later, so it is read each time. d.brief is the brief the decision names.
export function approvalCounts(d, fourEyes) {
  const b = d && d.brief;
  if (!b || b.lead !== d.lead) return false;
  if (b.sha256 !== d.brief_sha256) return false;
  if (b.author === d.author && (fourEyes !== false || d.four_eyes !== false)) return false;
  return true;
}

// The file's reviewer notes, as the page's Brief.reviewNotes builds them: what editors wrote when
// they returned or rejected a version since the file's last approval that counts, oldest first,
// at most max_notes, as review-1 to review-5.
export function reviewNotesFrom(decisions, fourEyes, rules) {
  const ds = (Array.isArray(decisions) ? decisions : [])
    .filter((d) => d && typeof d.lead === "string" && ["approved", "returned", "rejected", "reopened"].includes(d.decision))
    .map((d) => Object.assign({}, d, { decided_at: toIso(d.decided_at) }))
    .sort(byTime("decided_at"));
  let from = 0;
  for (let i = ds.length - 1; i >= 0; i--) if (ds[i].decision === "approved" && approvalCounts(ds[i], fourEyes)) { from = i + 1; break; }
  const max = (rules && rules.review && rules.review.max_notes) || 5;
  const picked = ds.slice(from).filter((d) => (d.decision === "returned" && String(d.note || "").trim()) || d.decision === "rejected").slice(-max);
  return picked.map((d, i) => ({
    id: `review-${i + 1}`, kind: d.decision, at: String(d.decided_at || "").slice(0, 10),
    text: d.decision === "rejected" ? [REJECT_LABELS[d.reason] || "Rejected", String(d.note || "").trim()].filter(Boolean).join(": ") : String(d.note).trim(),
  }));
}

/* ------------------------------------------------------------ fd-core's guardrails screen
   A port of fdcore/guardrails.py's scan_text, run on the patterns the build exports from fd-core
   (scripts/build_hosted.py, fdcore_patterns). Python reads \w, \d, \s and \b in these patterns
   as Unicode; JavaScript reads them as ASCII, so they are rewritten to Python's sets with the u
   flag, and positions are counted in code points, as Python counts them. */
const PY_WORD = "\\p{L}\\p{N}_";
const PY_DIGIT = "\\p{Nd}";
const PY_SPACE = "\\t-\\r\\x1c-\\x20\\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000";
const PY_SPACE_RX = new RegExp(`^[${PY_SPACE}]+|[${PY_SPACE}]+$`, "gu");

export function pyRegex(pattern, flags) {
  let out = "", inClass = false;
  for (let i = 0; i < pattern.length; i++) {
    const c = pattern[i];
    if (c === "\\" && i + 1 < pattern.length) {
      const n = pattern[++i];
      const set = { d: PY_DIGIT, w: PY_WORD, s: PY_SPACE }[n.toLowerCase()];
      if (set && n === n.toLowerCase()) out += inClass ? set : `[${set}]`;
      else if (set && !inClass) out += `[^${set}]`;
      else if ((n === "b" || n === "B") && !inClass) {
        const at = `(?<=[${PY_WORD}])(?![${PY_WORD}])|(?<![${PY_WORD}])(?=[${PY_WORD}])`;
        const not = `(?<=[${PY_WORD}])(?=[${PY_WORD}])|(?<![${PY_WORD}])(?![${PY_WORD}])`;
        out += `(?:${n === "b" ? at : not})`;
      } else if (/[A-Za-z0-9]/.test(n)) throw new Error(`fd-core pattern: the escape \\${n} is not ported`);
      // With the u flag only syntax characters may be escaped, and "-" only inside a class.
      else if ("^$\\.*+?()[]{}|/".includes(n) || (n === "-" && inClass)) out += "\\" + n;
      else out += n;
      continue;
    }
    if (c === "[" && !inClass) inClass = true;
    else if (c === "]" && inClass) inClass = false;
    out += c;
  }
  return new RegExp(out, "gu" + (String(flags || "").includes("i") ? "i" : ""));
}

const escapeRx = (s) => s.replace(/[\\^$.*+?()[\]{}|/]/g, "\\$&");
const pyStrip = (s) => String(s).replace(PY_SPACE_RX, "");
const cpLen = (s) => Array.from(s).length;
// Python's str.splitlines boundaries.
const LINES = /\r\n|[\n\r\x0b\x0c\x1c-\x1e\x85\u2028\u2029]/;

export function compileFdcore(fd) {
  const P = fd.patterns;
  return {
    raw: fd,
    company: pyRegex(P.company.pattern, P.company.flags), email: pyRegex(P.email.pattern, P.email.flags),
    phone: pyRegex(P.phone.pattern, P.phone.flags), postcode: pyRegex(P.postcode.pattern, P.postcode.flags),
    accusing: pyRegex(P.accusing.pattern, P.accusing.flags), clause: pyRegex(P.clause_break.pattern, P.clause_break.flags),
    hedges: fd.hedges.map((h) => h.toLowerCase()), before: Number(fd.hedge_before), after: Number(fd.hedge_after),
    emailAllow: new Set(fd.email_allow.map((e) => e.toLowerCase())), kinds: fd.kinds,
  };
}

function* all(re, text) {
  re.lastIndex = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    yield m;
    if (m[0].length === 0) re.lastIndex++;
  }
}

// fdcore.guardrails._inside_number: a digit run inside a longer number or token.
function insideNumber(line, start, end) {
  const before = start > 0 ? line[start - 1] : "";
  const after = Array.from(line.slice(end, end + 4)).slice(0, 2);
  return before === "." || /^[A-Za-z0-9]$/.test(before) || (after[0] === "." && /^\p{Nd}$/u.test(after[1] || "")) || after[0] === "e" || after[0] === "E";
}

// fdcore.guardrails._hedged, in code points: a hedge phrase in the same clause as the match.
function hedged(line, start, end, F) {
  const cps = Array.from(line), s = cpLen(line.slice(0, start)), e = cpLen(line.slice(0, end));
  let lo = Math.max(0, s - F.before);
  const head = cps.slice(lo, s).join("");
  let cut = null;
  for (const b of all(F.clause, head)) cut = b;
  if (cut) lo += cpLen(head.slice(0, cut.index + cut[0].length));
  let hi = Math.min(cps.length, e + F.after);
  const tail = cps.slice(e, hi).join("");
  F.clause.lastIndex = 0;
  const nxt = F.clause.exec(tail);
  if (nxt) hi = e + cpLen(tail.slice(0, nxt.index));
  const window = cps.slice(lo, hi).join("").toLowerCase();
  return F.hedges.some((h) => window.includes(h));
}

// fdcore.guardrails.scan_text: [{kind, text}] in fd-core's order. For accusing language the text
// is the word only, never the line, which could hold a name.
export function fdcoreScan(text, F, deny) {
  const out = [];
  const denyRx = (deny || []).map(pyStrip).filter((d) => d && !d.startsWith("#")).map((d) => new RegExp(escapeRx(d), "giu"));
  for (const line of String(text).split(LINES)) {
    for (const m of all(F.company, line)) out.push({ kind: F.kinds.company, text: m[0] });
    for (const m of all(F.email, line)) if (!F.emailAllow.has(m[0].toLowerCase())) out.push({ kind: F.kinds.email, text: m[0] });
    for (const m of all(F.postcode, line)) { if (m.index > 0 && line[m.index - 1] === "#") continue; out.push({ kind: F.kinds.postcode, text: m[0] }); }
    for (const m of all(F.phone, line)) {
      const digits = Array.from(m[0].replace(/\P{Nd}/gu, ""));
      if (digits.length >= 10 && !/^(?:19|20)\p{Nd}{2}/u.test(digits.join("")) && !insideNumber(line, m.index, m.index + m[0].length)) {
        out.push({ kind: F.kinds.phone, text: pyStrip(m[0]) });
      }
    }
    for (const rx of denyRx) for (const m of all(rx, line)) out.push({ kind: F.kinds.deny, text: m[0] });
    for (const m of all(F.accusing, line)) if (!hedged(line, m.index, m.index + m[0].length, F)) out.push({ kind: F.kinds.accusing, text: m[0] });
  }
  return out;
}

function dedupe(list) {
  const seen = new Set(), out = [];
  for (const p of list) { const k = p.code + "\u0000" + p.path; if (!seen.has(k)) { seen.add(k); out.push(p); } }
  return out;
}

// radar/brief/screen.py's screen_draft: the shared rules (screen.js), then, unless the draft is
// not a JSON object of the brief schema, fd-core over every string with the deny list.
export function screenDraft(draft, ctx, lib, deny, review) {
  const out = lib.RS.screenShared(draft, ctx, lib.C, lib.schema, review || []);
  if (out.length && (out[0].code === "not_json" || out[0].code === "schema")) return out;
  const fd = [];
  lib.RS.walkStrings(draft, (path, s) => {
    for (const f of fdcoreScan(s, lib.F, deny)) fd.push({ code: FDCORE_CODES[f.kind] || f.kind, path, detail: f.text });
  });
  return dedupe(out.concat(fd));
}

export function safeProblems(problems, rules) {
  const words = (rules && rules.problem_codes) || {};
  return problems.slice(0, 50).map((p) => {
    const code = String((p && p.code) || "");
    return { code, path: String((p && p.path) || ""), detail: SAFE_DETAIL.has(code) ? String(p.detail || "").slice(0, 200) : "", text: String(words[code] || "") };
  });
}

// Deny-list lines from a secret: one term per line, blank lines and # comments ignored.
export function denyLines(text) {
  return String(text || "").split(/\r?\n/).map((s) => s.trim()).filter((s) => s && !s.startsWith("#"));
}

const posInt = (v, d) => { const n = Number.parseInt(String(v || ""), 10); return Number.isFinite(n) && n > 0 ? n : d; };
const intOrNull = (v) => (Number.isInteger(v) ? v : null);

// The screen rules and fd-core patterns, compiled once per bundle.
const compiled = new WeakMap();
function libFor(data, RS) {
  if (!compiled.has(data)) compiled.set(data, { RS, C: RS.compile(data.spec.rules), schema: data.spec.schema, F: compileFdcore(data.fdcore) });
  return compiled.get(data);
}

function corsHeaders(origin, allowed) {
  const allow = !allowed.length ? "*" : allowed.includes(origin) ? origin : allowed[0];
  return {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    vary: "Origin",
    "access-control-allow-origin": allow,
    "access-control-allow-headers": "authorization, apikey, content-type, x-client-info",
    "access-control-allow-methods": "POST, OPTIONS",
    "access-control-max-age": "600",
  };
}

/**
 * @param {Request} req
 * @param {{env: (name: string) => string, data: object, deny: string[], screen: object,
 *          fetch: Function, now: () => Date, sha256Hex: (text: string) => Promise<string>,
 *          getUser: (jwt: string) => Promise<{id: string}|null>, memberRole: (id: string) => Promise<string|null>,
 *          recentDrafts: (id: string, sinceIso: string) => Promise<number>,
 *          reviewInputs: (lead: string) => Promise<{decisions: unknown[], four_eyes: boolean}>,
 *          recordDraft: (row: Record<string, unknown>) => Promise<void>, log?: (msg: string) => void}} deps
 * @returns {Promise<Response>}
 */
export async function handleRequest(req, deps) {
  const env = (name) => String(deps.env(name) || "");
  const log = deps.log || (() => {});
  const origin = req.headers.get("origin") || "";
  const allowed = env("ALLOWED_ORIGINS").split(",").map((s) => s.trim()).filter(Boolean);
  const headers = corsHeaders(origin, allowed);
  const reply = (status, body) => new Response(body === null ? null : JSON.stringify(body), { status, headers });
  if (allowed.length && origin && !allowed.includes(origin)) return reply(403, { error: "origin_not_allowed" });
  if (req.method === "OPTIONS") return reply(204, null);
  if (req.method !== "POST") return reply(405, { error: "method_not_allowed" });
  try {
    return await draft(req, deps, env, log, reply);
  } catch (e) {
    log("draft-brief: unexpected " + ((e && e.name) || "error"));
    return reply(500, { error: "internal" });
  }
}

async function draft(req, deps, env, log, reply) {
  const raw = await req.text();
  if (raw.length > 4096) return reply(413, { error: "request_too_large" });
  let body;
  try { body = JSON.parse(raw); } catch { return reply(400, { error: "bad_request" }); }
  if (!body || typeof body !== "object" || Array.isArray(body) || typeof body.slug !== "string" || !SLUG.test(body.slug)
      || typeof body.prompt_sha256 !== "string" || !HEX64.test(body.prompt_sha256)) {
    return reply(400, { error: "bad_request" });
  }

  // Who is asking: a signed-in member at Contributor or above.
  const m = /^Bearer\s+(\S+)$/i.exec(req.headers.get("authorization") || "");
  if (!m) return reply(401, { error: "not_signed_in" });
  let user = null;
  try { user = await deps.getUser(m[1]); } catch { user = null; }
  if (!user || typeof user.id !== "string") return reply(401, { error: "not_signed_in" });
  const role = await deps.memberRole(user.id);
  if ((RANK[role] || 0) < RANK.contributor) return reply(403, { error: "not_allowed" });

  // The file and its facts, from the function's own copy of this build.
  const data = deps.data;
  const file = Object.prototype.hasOwnProperty.call(data.files, body.slug) ? data.files[body.slug] : null;
  const ctx = file && Object.prototype.hasOwnProperty.call(data.contexts, body.slug) ? data.contexts[body.slug] : null;
  if (!file || !ctx) return reply(404, { error: "no_such_file" });
  const build = { source_commit: (data.build && data.build.source_commit) || null, rules: data.spec.rules.schema, run: ctx.run };

  const key = env("ANTHROPIC_API_KEY");
  if (!key) return reply(503, { error: "not_configured" });

  const limit = posInt(env("DRAFTS_PER_HOUR"), DEFAULT_DRAFTS_PER_HOUR);
  const since = new Date(deps.now().getTime() - 3600 * 1000).toISOString();
  if ((await deps.recentDrafts(user.id, since)) >= limit) return reply(429, { error: "too_many_drafts", limit });

  // The private deny list: bundled at build time from config/deny_list.txt, plus the DENY_LIST
  // secret. Without any term the screen cannot check names, so no draft is made.
  const deny = [...(Array.isArray(deps.deny) ? deps.deny : []), ...denyLines(env("DENY_LIST"))];
  if (!deny.length) return reply(503, { error: "deny_list_unavailable" });
  const lib = libFor(data, deps.screen);

  // The reviewer notes, from the decisions editors recorded. The page builds them the same way
  // from what it has loaded and without the deny list, which it never sees; a note the deny list
  // would hold back is not sent, and the page is told so instead of being sent a different prompt.
  let review;
  try {
    const inputs = await deps.reviewInputs(file.lead);
    const notes = reviewNotesFrom(inputs && inputs.decisions, inputs && inputs.four_eyes, data.spec.rules);
    review = lib.RS.usableNotes(notes, ctx, lib.C).usable;
  } catch { return reply(503, { error: "notes_unavailable" }); }
  if (review.some((n) => fdcoreScan(n.text, lib.F, deny).some((f) => f.kind === lib.F.kinds.deny))) return reply(422, { error: "note_blocked" });

  const prompt = lib.RS.buildPrompt(data.prompt, data.spec.rules, data.spec.schema, ctx, review, []);
  const promptSha = await deps.sha256Hex(promptKey(prompt));
  if (body.prompt_sha256 !== promptSha) return reply(409, { error: "build_mismatch", build, notes: review.length });

  const model = env("ANTHROPIC_MODEL") || DEFAULT_MODEL;
  let res;
  try {
    res = await deps.fetch(ANTHROPIC_URL, {
      method: "POST",
      headers: { "x-api-key": key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json" },
      // spec/prompt.md: the system section as the system prompt, the user section as the user turn.
      body: JSON.stringify({ model, max_tokens: posInt(env("ANTHROPIC_MAX_TOKENS"), DEFAULT_MAX_TOKENS), system: prompt.system,
        messages: [{ role: "user", content: prompt.user }] }),
      signal: AbortSignal.timeout(posInt(env("ANTHROPIC_TIMEOUT_MS"), 120000)),
    });
  } catch {
    return reply(504, { error: "draft_timed_out" });
  }
  if (res.status === 429 || res.status === 529 || res.status >= 500) return reply(503, { error: "busy" });
  if (res.status === 401 || res.status === 403) { log("draft-brief: the API key was refused"); return reply(503, { error: "not_configured" }); }
  if (!res.ok) { log("draft-brief: the API answered " + res.status); return reply(502, { error: "draft_failed" }); }
  let msg;
  try { msg = await res.json(); } catch { return reply(502, { error: "draft_failed" }); }
  const text = (Array.isArray(msg && msg.content) ? msg.content : []).filter((b) => b && b.type === "text" && typeof b.text === "string").map((b) => b.text).join("");

  let problems, out = null, passed = false;
  const refused = msg.stop_reason === "refusal";
  if (refused) problems = [{ code: "refused", path: "", detail: "Claude declined to draft this brief" }];
  else if (msg.stop_reason === "max_tokens") problems = [{ code: "not_json", path: "", detail: "the reply was cut off" }];
  else {
    const parsed = lib.RS.parseReply(text);
    if (!parsed.ok) problems = [parsed.problem];
    else {
      try { problems = screenDraft(parsed.draft, ctx, lib, deny, review); } catch { problems = [{ code: "not_ready", path: "", detail: "" }]; }
      passed = problems.length === 0;
      if (passed) out = parsed.draft;
    }
  }

  // Every draft is recorded before anyone sees it; a draft that cannot be recorded is not returned.
  const rules = [...new Set(problems.map((p) => String(p.code)))].sort();
  try {
    await deps.recordDraft({
      requested_by: user.id, lead: file.lead, passed, rules, problem_count: problems.length,
      prompt_sha256: promptSha, draft_sha256: passed ? await deps.sha256Hex(canon(out)) : null,
      model: String(msg.model || model).slice(0, 80), stop_reason: msg.stop_reason ? String(msg.stop_reason).slice(0, 40) : null,
      input_tokens: intOrNull(msg.usage && msg.usage.input_tokens), output_tokens: intOrNull(msg.usage && msg.usage.output_tokens),
      rules_version: String(data.spec.rules.schema || "").slice(0, 40),
    });
  } catch {
    log("draft-brief: the draft could not be recorded");
    return reply(500, { error: "not_recorded" });
  }
  log(`draft-brief: ${file.lead} ${passed ? "passed" : "failed: " + rules.join(", ")}`);
  return reply(200, { passed, refused, problems: safeProblems(problems, data.spec.rules), draft: out, prompt_sha256: promptSha, build });
}
