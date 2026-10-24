// The hosted workspace in a real browser (Chromium through Playwright), run by tests/test_hosted_js.py
// when Playwright, its Chromium and a copy of the pinned Supabase client are on the machine.
//
//   node tests/hosted_browser_check.mjs <playwright module> <site folder> <supabase.js> <reply drafts.json> [shots folder]
//
// The site folder is a hosted build (scripts/build_hosted.py) for the made-up project
// https://abcdefghijklmnopqrst.supabase.co. The browser fetches the site with the headers its
// _headers file sets (so the Content-Security-Policy applies), the Supabase client from its CDN URL
// (answered with the local copy, so the page's SHA-384 check runs), and the project's Auth, REST and
// function endpoints, answered by a small fake of the project in this file; nothing leaves the
// machine. Two people sign in with an emailed code, a Contributor and an Editor, and take a brief
// through the workflow. Prints {steps, csp, errors, requests} as JSON. A rise in exports is a lead,
// not evidence of a breach.
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";

const [, , playwrightPath, siteDir, umdPath, repliesPath, shotsDir] = process.argv;
// With a shots folder, the check also saves a few screenshots there, for a person to look at.
const shot = async (page, name) => { if (shotsDir) await page.screenshot({ path: path.join(shotsDir, `hosted-${name}.png`) }); };
const { chromium } = await import(playwrightPath);
const SITE = "https://workspace.test";
const PROJECT = "https://abcdefghijklmnopqrst.supabase.co";
const CDN = /^https:\/\/cdn\.jsdelivr\.net\/npm\/@supabase\/supabase-js@[\d.]+\/dist\/umd\/supabase\.js$/;
const replies = JSON.parse(readFileSync(repliesPath, "utf8"));   // {slug: the template brief for that file's facts}
const RUN = "2026-10";
const PEOPLE = {
  contributor: { id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", role: "contributor", name: "Analyst contributor" },
  editor: { id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", role: "editor", name: "Analyst editor" },
};
const emailOf = (who) => [who, "workspace.test"].join("@");

/* ------------------------------------------------------------ the site, with its _headers */
function siteHeaders() {
  const lines = readFileSync(path.join(siteDir, "_headers"), "utf8").split("\n");
  const blocks = [];
  for (const line of lines) {
    if (!line.trim() || line.startsWith("#")) continue;
    if (!/^\s/.test(line)) blocks.push({ path: line.trim(), headers: {} });
    else { const i = line.indexOf(":"); blocks[blocks.length - 1].headers[line.slice(0, i).trim().toLowerCase()] = line.slice(i + 1).trim(); }
  }
  return (p) => Object.assign({}, ...blocks.filter((b) => b.path === "/*" || (b.path.endsWith("/*") && p.startsWith(b.path.slice(0, -1)))).map((b) => b.headers));
}
const headersFor = siteHeaders();
const TYPES = { ".html": "text/html; charset=utf-8", ".json": "application/json", ".md": "text/markdown; charset=utf-8", ".txt": "text/plain", ".csv": "text/csv" };

/* ------------------------------------------------------------ a fake of the project */
const tables = { members: [], briefs: [], decisions: [], files: [], checks: [], tasks: [], outcomes: [], enduse_records: [], monitor_decisions: [], config: [{ key: "workflow", four_eyes: true, updated_at: null, updated_by: null }],
  events: [], audit: [], private_drafts: [] };
for (const p of Object.values(PEOPLE)) tables.members.push({ user_id: p.id, role: p.role, display_name: p.name, active: true, invited_at: "2026-10-01T09:00:00+00:00" });
const requests = [];
const keys = { members: ["user_id"], briefs: ["id"], decisions: ["id"], files: ["lead"], config: ["key"], checks: ["lead", "check_id"], tasks: ["id"], outcomes: ["lead"], enduse_records: ["lead"], monitor_decisions: ["item"], private_drafts: ["user_id", "lead"], events: ["id"] };
const nowIso = () => new Date().toISOString().replace("Z", "000+00:00");
const b64 = (o) => Buffer.from(JSON.stringify(o)).toString("base64url");
const token = (p) => `${b64({ alg: "HS256", typ: "JWT" })}.${b64({ sub: p.id, role: "authenticated", aud: "authenticated", email: emailOf(p.role), exp: Math.floor(Date.now() / 1000) + 3600 })}.sig`;
const callerOf = (headers) => {
  const m = /^Bearer (.+)$/.exec(headers.authorization || "");
  try { return JSON.parse(Buffer.from(m[1].split(".")[1], "base64url").toString()).sub; } catch { return null; }
};
function serverSet(table, row, old, uid) {
  const t = nowIso();
  if (table === "briefs") Object.assign(row, { author: uid, created_at: t, version: tables.briefs.filter((v) => v.lead === row.lead).length + 1, key: uid + "/" + row.id });
  if (table === "decisions") Object.assign(row, { author: uid, decided_at: t, four_eyes: tables.config[0].four_eyes, note: row.note || "" });
  if (table === "files") { if (!old || "status" in row || "brief_id" in row) Object.assign(row, { updated_at: t, updated_by: uid }); if ("assignee" in row) row.assigned_at = row.assignee ? t : null; }
  if (table === "checks" || table === "config") Object.assign(row, { updated_by: uid, updated_at: t });
  if (table === "tasks") { if (!old) Object.assign(row, { created_by: uid, created_at: t }); if ("done" in row) Object.assign(row, { done_by: row.done ? uid : null, done_at: row.done ? t : null }); }
  if (table === "events") Object.assign(row, { id: tables.events.length + 1, actor: uid, at: t });
  if (table === "private_drafts") Object.assign(row, { user_id: uid, at: t });
  return row;
}
function matches(row, params) {
  for (const [k, v] of params) {
    if (["select", "order", "limit", "offset", "on_conflict", "columns"].includes(k)) continue;
    const [op, ...rest] = v.split(".");
    const val = rest.join(".");
    if (op === "eq" && String(row[k]) !== val) return false;
    if (op === "gte" && !(String(row[k]) >= val)) return false;
    if (op === "in" && !val.replace(/^\(|\)$/g, "").split(",").map((s) => s.replace(/^"|"$/g, "")).includes(String(row[k]))) return false;
  }
  return true;
}
function rest(method, table, url, headers, body, uid) {
  const rows = tables[table];
  if (!rows) return [404, { message: "no table " + table }];
  const params = [...url.searchParams.entries()];
  const prefer = headers.prefer || "";
  if (method === "GET" || method === "HEAD") {
    let out = rows.filter((r) => matches(r, params));
    if (table === "private_drafts") out = out.filter((r) => r.user_id === uid);
    const order = url.searchParams.get("order");
    if (order) for (const part of order.split(",").reverse()) { const [c, d] = part.split("."); out = out.slice().sort((x, y) => (x[c] < y[c] ? -1 : x[c] > y[c] ? 1 : 0) * (d === "desc" ? -1 : 1)); }
    const off = Number(url.searchParams.get("offset") || 0), lim = url.searchParams.get("limit");
    out = out.slice(off, lim ? off + Number(lim) : undefined);
    return [200, out];
  }
  const payload = body ? JSON.parse(body) : null;
  if (method === "POST") {
    const list = Array.isArray(payload) ? payload : [payload];
    const conflict = (url.searchParams.get("on_conflict") || "").split(",").filter(Boolean);
    const changed = [];
    for (const r of list) {
      const row = JSON.parse(JSON.stringify(r));
      if (table === "private_drafts") row.user_id = uid;
      const ks = conflict.length ? conflict : keys[table];
      const old = prefer.includes("resolution=merge-duplicates") ? rows.find((x) => ks.every((k) => x[k] === row[k])) : null;
      if (old) { Object.assign(old, serverSet(table, row, old, uid)); changed.push(old); } else { const n = serverSet(table, row, null, uid); rows.push(n); changed.push(n); }
    }
    return [201, prefer.includes("return=representation") ? changed : null];
  }
  if (method === "PATCH") {
    const hit = rows.filter((r) => matches(r, params));
    for (const r of hit) Object.assign(r, serverSet(table, JSON.parse(body), r, uid));
    return [prefer.includes("return=representation") ? 200 : 204, prefer.includes("return=representation") ? hit : null];
  }
  return [405, { message: "method" }];
}
let draftAnswer = "pass";
async function project(route) {
  const req = route.request();
  const url = new URL(req.url());
  const headers = req.headers();
  const body = req.postData();
  const uid = callerOf(headers);
  requests.push({ method: req.method(), path: url.pathname, query: url.search, apikey: headers.apikey || null, caller: uid, body: body ? JSON.parse(body) : null });
  const send = (status, data, extra = {}) => route.fulfill({ status, contentType: "application/json",
    headers: Object.assign({ "access-control-allow-origin": SITE, "access-control-allow-headers": "*", "access-control-allow-methods": "*", "access-control-expose-headers": "content-range" }, extra),
    body: data === null ? "" : JSON.stringify(data) });
  if (req.method() === "OPTIONS") return send(204, null);
  if (url.pathname === "/auth/v1/otp") return send(200, {});
  if (url.pathname === "/auth/v1/verify") {
    const { email } = JSON.parse(body);
    const p = Object.values(PEOPLE).find((x) => emailOf(x.role) === email);
    if (!p) return send(403, { code: 403, error_code: "otp_expired", msg: "Token has expired or is invalid" });
    const exp = Math.floor(Date.now() / 1000) + 3600;
    return send(200, { access_token: token(p), token_type: "bearer", expires_in: 3600, expires_at: exp, refresh_token: "refresh-" + p.role,
      user: { id: p.id, aud: "authenticated", role: "authenticated", email, app_metadata: {}, user_metadata: {}, created_at: "2026-10-01T09:00:00Z" } });
  }
  if (url.pathname === "/auth/v1/logout") return send(204, null);
  if (url.pathname === "/auth/v1/user") { const p = Object.values(PEOPLE).find((x) => x.id === uid); return p ? send(200, { id: p.id, email: emailOf(p.role) }) : send(401, {}); }
  if (url.pathname.startsWith("/rest/v1/")) {
    const [status, data] = rest(req.method(), url.pathname.slice("/rest/v1/".length), url, headers, body, uid);
    return send(status, data, status === 200 && Array.isArray(data) ? { "content-range": `0-${Math.max(0, data.length - 1)}/${data.length}` } : {});
  }
  if (url.pathname === "/functions/v1/draft-brief") {
    const b = JSON.parse(body);
    if (draftAnswer === "fail") return send(200, { passed: false, refused: false, draft: null,
      problems: [{ code: "accusing_language", path: "headline.text", detail: "", text: "Judging or accusing wording outside a hedged clause." }] });
    return send(200, { passed: true, refused: false, problems: [], draft: replies[b.slug], prompt_sha256: b.prompt_sha256, build: {} });
  }
  return send(404, { message: "not in the fake" });
}

/* ------------------------------------------------------------ the browser */
const steps = [], errors = [];
const step = (name, ok, detail) => steps.push({ name, ok: !!ok, detail: detail === undefined ? null : detail });
let browser;
// A Chromium named by DR_CHROMIUM (or the one this workspace keeps at /opt/pw-browsers/chromium)
// when it exists, as tests/browser/flow.mjs does; otherwise Playwright's own.
const executablePath = [process.env.DR_CHROMIUM, "/opt/pw-browsers/chromium"].find((x) => x && existsSync(x));
try { browser = await chromium.launch(executablePath ? { executablePath } : {}); } catch (err) {
  process.stdout.write(JSON.stringify({ steps, csp: [], errors: ["browserType.launch: " + String(err && err.message).slice(0, 300)], requests: 0 }));
  process.exit(0);
}
async function personPage(who) {
  const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1280, height: 900 } });
  await context.routeWebSocket(/\/realtime\/v1\//, (ws) => ws.close());   // live updates down, so the page polls
  await context.route("**/*", async (route) => {
    const u = route.request().url();
    if (u.startsWith(SITE + "/")) {
      let p = new URL(u).pathname;
      if (p === "/") p = "/index.html";
      const f = path.join(siteDir, p);
      if (!existsSync(f)) return route.fulfill({ status: 404, body: "" });
      return route.fulfill({ status: 200, contentType: TYPES[path.extname(f)] || "application/octet-stream", headers: headersFor(p), body: readFileSync(f) });
    }
    if (CDN.test(u)) return route.fulfill({ status: 200, contentType: "application/javascript; charset=utf-8", headers: { "access-control-allow-origin": "*" }, body: readFileSync(umdPath) });
    if (u.startsWith(PROJECT + "/")) return project(route);
    return route.abort();
  });
  const page = await context.newPage();
  await page.addInitScript(() => { window.__csp = []; document.addEventListener("securitypolicyviolation", (e) => window.__csp.push(`${e.violatedDirective} ${e.blockedURI} ${e.sample || ""}`)); });
  page.on("pageerror", (e) => errors.push(`${who}: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") errors.push(`${who} console: ${m.text()}`); });
  await page.goto(SITE + "/");
  return { context, page };
}
async function signIn(page, who) {
  await page.locator(".hs-status", { hasText: "Sign in with your work email" }).waitFor({ timeout: 15000 });
  await page.getByPlaceholder("Work email").fill(emailOf(who));
  await page.getByRole("button", { name: "Email me a code", exact: true }).click();
  await page.getByPlaceholder("Code from the email").fill("123456");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.locator(".hs-status", { hasText: `Signed in as ${PEOPLE[who].name}, ${PEOPLE[who].role}.` }).waitFor({ timeout: 15000 });
  await page.locator("#store-chip", { hasText: "Shared store" }).waitFor({ timeout: 15000 });
}
const openFile = async (page, key) => {
  await page.evaluate((k) => { location.hash = "#file-" + k; }, key);
  await page.locator("#view-file .q-ref", { hasText: `DR-${RUN}-${key}` }).waitFor({ timeout: 10000 });
};
const button = (page, name) => page.getByRole("button", { name, exact: true });

try {
  const c = await personPage("contributor");
  step("the Supabase client loaded past its integrity check", await c.page.evaluate(() => typeof window.supabase === "object" && typeof window.supabase.createClient === "function"));
  step("the page waits for sign-in before it has a store", (await c.page.locator("#store-chip").innerText()).includes("Connecting"));
  await shot(c.page, "1-signed-out");
  await signIn(c.page, "contributor");
  step("a Contributor signs in with an emailed code", true);
  await shot(c.page, "2-inbox");
  const verify = requests.find((r) => r.path === "/auth/v1/verify");
  const otp = requests.find((r) => r.path === "/auth/v1/otp");
  step("sign-in never creates an account", otp && otp.body && otp.body.create_user === false, otp && otp.body);
  step("the code is checked as an email code", verify && verify.body && verify.body.type === "email" && verify.body.token === "123456");

  await openFile(c.page, "KZ-851762");
  await button(c.page, "Start from the template").click();
  await button(c.page, "Save draft").click();
  await button(c.page, "Submit for approval").waitFor({ timeout: 10000 });
  const bIns = requests.find((r) => r.path === "/rest/v1/briefs" && r.method === "POST");
  step("a saved brief goes to briefs with no author, time or number from the page",
    bIns && !("author" in bIns.body) && !("created_at" in bIns.body) && !("version" in bIns.body) && bIns.body.kind === "brief" && bIns.caller === PEOPLE.contributor.id,
    bIns && Object.keys(bIns.body).sort());
  await button(c.page, "Submit for approval").click();
  await c.page.locator("#view-file .st", { hasText: "Awaiting approval" }).first().waitFor({ timeout: 10000 });
  const f = tables.files.find((r) => r.lead === `${RUN}_KZ-851762`);
  step("the pointer says submitted, set by the Contributor", f && f.status === "submitted" && f.updated_by === PEOPLE.contributor.id, f);
  step("the Contributor is not offered Approve", (await button(c.page, "Approve").count()) === 0);

  // Drafting with Claude: through the function, the brief saved as a Claude draft.
  await openFile(c.page, "TH-851762");
  await button(c.page, "Draft with Claude").click();
  await button(c.page, "Save draft").waitFor({ timeout: 15000 });
  const fn = requests.find((r) => r.path === "/functions/v1/draft-brief");
  step("drafting sends the file's slug and the prompt's SHA-256 to the function", fn && fn.body.slug === "thailand-851762" && /^[0-9a-f]{64}$/.test(fn.body.prompt_sha256)
    && Object.keys(fn.body).length === 2 && fn.caller === PEOPLE.contributor.id, fn && fn.body);
  // (Saving a brief clears its private draft, so the first write here can be another file's clearing.)
  const priv = requests.find((r) => r.path === "/rest/v1/private_drafts" && r.method === "POST" && r.body && r.body.working);
  step("the unsaved draft is kept in the person's private drafts, with no person or time from the page",
    priv && priv.body.lead === `${RUN}_TH-851762` && priv.body.working && !("user_id" in priv.body) && !("at" in priv.body), priv && Object.keys(priv.body));
  await button(c.page, "Save draft").click();
  await button(c.page, "Submit for approval").waitFor({ timeout: 10000 });
  const claude = tables.briefs.find((v) => v.lead === `${RUN}_TH-851762`);
  step("a Claude draft is saved as one", claude && claude.source === "claude");
  draftAnswer = "fail";
  await openFile(c.page, "IN-851762");
  await button(c.page, "Draft with Claude").click();
  await c.page.locator(".hs-notice", { hasText: "stopped by the screen" }).waitFor({ timeout: 10000 });
  step("a draft that fails the screen is not shown; the bar says what it found", (await button(c.page, "Save draft").count()) === 0
    && (await c.page.locator(".hs-notice").innerText()).includes("Judging or accusing wording"));
  await c.page.click("#tab-lessons");
  step("the Lessons view says the hosted version has no lessons yet", (await c.page.locator("#view-lessons").innerText()).includes("The hosted version has no lessons yet"));
  await c.page.click("#tab-reports");
  await c.page.locator("#view-reports button.qrow").first().click();
  await c.page.locator("#view-report #report-panel").waitFor({ timeout: 10000 });
  await shot(c.page, "3-report");
  step("the triage view reads a report but records no outcome, as the hosted version has no place for one yet",
    (await c.page.locator("#view-report").innerText()).includes("The hosted version records no triage outcomes yet")
    && (await button(c.page, "Propose an outcome").count()) === 0);

  const e = await personPage("editor");
  await signIn(e.page, "editor");
  step("an Editor signs in", true);
  await openFile(e.page, "KZ-851762");
  await button(e.page, "Approve").click();
  await e.page.locator("#view-file .st", { hasText: "Approved" }).first().waitFor({ timeout: 10000 });
  const dIns = requests.find((r) => r.path === "/rest/v1/decisions" && r.method === "POST");
  step("the approval goes to decisions with no author, time or four-eyes flag from the page",
    dIns && !("author" in dIns.body) && !("decided_at" in dIns.body) && !("four_eyes" in dIns.body) && dIns.body.brief_sha256 === tables.briefs[0].sha256
    && dIns.caller === PEOPLE.editor.id, dIns && dIns.body);
  const [download] = await Promise.all([e.page.waitForEvent("download", { timeout: 10000 }), button(e.page, "Evidence pack (.md)").click()]);
  await e.page.waitForTimeout(500);
  const ev = requests.find((r) => r.path === "/rest/v1/events" && r.method === "POST");
  step("the evidence pack downloads, and the export is recorded as a page event", download.suggestedFilename() === `DR-${RUN}-KZ-851762-evidence.md`
    && ev && ev.body.action === "pack_exported" && ev.body.lead === `${RUN}_KZ-851762` && !("actor" in ev.body) && !("at" in ev.body), ev && ev.body);
  step("the page wrote no audit entry of its own", !requests.some((r) => r.path === "/rest/v1/audit" && r.method !== "GET"));

  await e.page.click("#tab-method");
  const method = await e.page.locator("#view-method").innerText();
  step("the Method view describes the hosted version, not the pilot",
    method.includes("This is the hosted version") && method.includes("checked by its SHA-384") && method.includes("rows the database writes") && !method.includes("Inside Claude for the pilot"));
  await e.page.click("#tab-audit");
  step("the audit log view says the database writes it", (await e.page.locator("#view-audit").innerText()).includes("The database writes this log itself"));

  const csp = [...(await c.page.evaluate(() => window.__csp)), ...(await e.page.evaluate(() => window.__csp))];
  step("the Content-Security-Policy blocked nothing", csp.length === 0, csp);
  await button(c.page, "Sign out").click();
  await c.page.locator(".hs-status", { hasText: "Sign in with your work email" }).waitFor({ timeout: 15000 });
  step("signing out leaves the page signed out", true);
  process.stdout.write(JSON.stringify({ steps, csp, errors, requests: requests.length }));
} catch (err) {
  process.stdout.write(JSON.stringify({ steps, csp: [], errors: [...errors, "check stopped: " + String(err && err.message).slice(0, 500)], requests: requests.length }));
} finally {
  await browser.close();
}
