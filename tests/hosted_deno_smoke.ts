// A smoke test of supabase/functions/draft-brief/index.ts under Deno, run by tests/test_hosted_js.py
// when Deno is installed. It loads the function as Supabase would, with fetch replaced so that
// nothing leaves the machine: calls to the project go to a fake (Auth, members, drafts, the file's
// decisions and the setting) and the call to Claude returns the reply given in the first argument.
// The page's prompt is built with the bundle's own screen.js, with the reviewer note given in the
// third argument. It prints what happened as JSON. A rise in exports is a lead, not evidence of a breach.
//   deno run --allow-read --allow-env --allow-net=127.0.0.1 tests/hosted_deno_smoke.ts <reply.txt> <function dir> <note.json>

const [replyPath, fnDir, noteJson] = Deno.args;
const reply = await Deno.readTextFile(replyPath);
const NOTE = JSON.parse(noteJson);
const UID = "eeeeeeee-aaaa-4bbb-8ccc-dddddddddddd";
const PROJECT = "https://project.invalid";
const SECRET = "sb_secret_" + "x".repeat(20);
const SLUG = "kazakhstan-851762";
const LEAD = "2026-10_KZ-851762";
const seen: string[] = [];
const keys: { path: string; apikey: string; authorization: string }[] = [];
const recorded: unknown[] = [];
const sentToClaude: { headers: Record<string, string>; body: { model: string; system: string; messages: { content: string }[] } }[] = [];

const json = (v: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(v === null ? null : JSON.stringify(v), { status, headers: { "content-type": "application/json", ...headers } });

globalThis.fetch = async (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
  const req = new Request(input, init);
  const url = new URL(req.url);
  seen.push(`${req.method} ${url.host}${url.pathname}${url.search}`);
  if (url.host === "api.anthropic.com") {
    sentToClaude.push({ headers: Object.fromEntries(req.headers), body: await req.json() });
    return json({ id: "msg", type: "message", model: "claude-sonnet-5-5", content: [{ type: "text", text: reply }], stop_reason: "end_turn", usage: { input_tokens: 10, output_tokens: 20 } });
  }
  if (url.origin !== PROJECT) return json({ error: "unexpected host " + url.host }, 599);
  const auth = req.headers.get("authorization") || "";
  const apikey = req.headers.get("apikey") || "";
  keys.push({ path: url.pathname, apikey: apikey === SECRET ? "secret" : apikey ? "other" : "none",
    authorization: auth === "Bearer good-token" || auth === "Bearer stale-token" ? "user" : auth ? "other" : "none" });
  if (url.pathname === "/auth/v1/user") return auth === "Bearer good-token" ? json({ id: UID, aud: "authenticated", role: "authenticated", email: ["analyst", "workspace.test"].join("@") }) : json({ msg: "invalid JWT" }, 401);
  if (url.pathname === "/rest/v1/members") return json([{ role: "contributor", active: true }]);
  if (url.pathname === "/rest/v1/drafts" && (req.method === "HEAD" || req.method === "GET")) return json(null, 200, { "content-range": "*/0" });
  if (url.pathname === "/rest/v1/drafts" && req.method === "POST") { recorded.push(await req.json()); return json(null, 201); }
  if (url.pathname === "/rest/v1/decisions") {
    return json([{ id: "d1", author: UID, lead: LEAD, decision: "returned", brief_id: null, brief_sha256: null, four_eyes: true,
      note: NOTE.text, reason: null, decided_at: "2026-10-21T09:00:00.123456+00:00", brief: null }]);
  }
  if (url.pathname === "/rest/v1/config") return json([{ four_eyes: true }]);
  return json({ message: "not in the fake" }, 404);
};

Deno.env.set("SUPABASE_URL", PROJECT);
Deno.env.set("SUPABASE_SECRET_KEYS", JSON.stringify({ default: SECRET }));
Deno.env.set("ANTHROPIC_API_KEY", "test-key-not-real");

let handler: ((req: Request) => Response | Promise<Response>) | null = null;
const serve = (h: (req: Request) => Response | Promise<Response>) => { handler = h; return { finished: Promise.resolve(), shutdown: async () => {} }; };
Object.defineProperty(Deno, "serve", { value: serve, configurable: true, writable: true });

const base = "file://" + fnDir.replace(/\/?$/, "/");
await import(new URL("index.ts", base).href);
if (!handler) throw new Error("index.ts did not call Deno.serve");

// The page's prompt, built as the page builds it: the same screen.js, facts and note.
// deno-lint-ignore no-explicit-any
const RS = (globalThis as any).RadarScreen;
const { DATA } = await import(new URL("_bundle/data.mjs", base).href);
const prompt = RS.buildPrompt(DATA.prompt, DATA.spec.rules, DATA.spec.schema, DATA.contexts[SLUG], [NOTE], []);
const hex = (buf: ArrayBuffer) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
const pageSha = hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify([prompt.system, prompt.user]))));

const call = async (body: unknown, token = "good-token") => {
  const res = await handler!(new Request(PROJECT + "/functions/v1/draft-brief", {
    method: "POST", headers: { authorization: "Bearer " + token, "content-type": "application/json" }, body: JSON.stringify(body) }));
  return { status: res.status, body: await res.json() };
};
const ok = await call({ slug: SLUG, prompt_sha256: pageSha });
const stale = await call({ slug: SLUG, prompt_sha256: pageSha }, "stale-token");
const mismatch = await call({ slug: SLUG, prompt_sha256: "0".repeat(64) });
const notesIn = (user: string) => JSON.parse(user.split("<review_notes>\n")[1].split("\n</review_notes>")[0]);
console.log(JSON.stringify({ ok, stale, mismatch, seen, keys, recorded, sentToClaude: sentToClaude.map((c) => ({ key: c.headers["x-api-key"],
  version: c.headers["anthropic-version"], model: c.body.model, system: c.body.system === prompt.system, notes: notesIn(c.body.messages[0].content) })) }));
