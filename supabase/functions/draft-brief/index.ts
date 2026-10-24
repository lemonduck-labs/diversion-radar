// The workspace's drafting function, on Supabase Edge Functions (Deno). The logic is in
// core.mjs; this file only wires it to Deno, the project's Auth and REST APIs and the network. It
// imports nothing from outside this folder: the few calls it makes to the project are plain fetches.
//
// Deploy with JWT checking at the gateway off: the function checks the caller's session itself,
// and the gateway's check does not take Supabase's publishable and secret keys:
//   supabase functions deploy draft-brief --no-verify-jwt
//
// Secrets, set by the owner in the dashboard (Edge Functions, Secrets), never in this repo:
//   ANTHROPIC_API_KEY     the key the function drafts with (required)
//   ALLOWED_ORIGINS       the workspace's site, for example https://<site>.netlify.app (comma-separated)
//   DENY_LIST             more deny-list terms, one per line (optional; the bundle holds the private list)
//   ANTHROPIC_MODEL       optional; core.mjs has the default
//   DRAFTS_PER_HOUR       optional cap per person; core.mjs has the default
// Supabase provides SUPABASE_URL and the server key (SUPABASE_SECRET_KEYS, or the legacy
// SUPABASE_SERVICE_ROLE_KEY) to every function.
//
// _bundle/ is written by `python scripts/build_hosted.py` and is not in git: app/src/screen.js
// unchanged, each file's facts, the prompt, the screen rules, fd-core's guardrails patterns and the
// private deny list, of the same build as the hosted page.

import { handleRequest } from "./core.mjs";
import "./_bundle/screen.js";
import { DATA } from "./_bundle/data.mjs";
import { DENY } from "./_bundle/deny.mjs";

// app/src/screen.js sets globalThis.RadarScreen when it is loaded as a module.
const screen = (globalThis as unknown as { RadarScreen?: object }).RadarScreen;
if (!screen) throw new Error("_bundle/screen.js did not load: build with scripts/build_hosted.py");

const env = (name: string): string => Deno.env.get(name) ?? "";
const PROJECT = env("SUPABASE_URL").replace(/\/+$/, "");

function serverKey(): string {
  try {
    const keys = JSON.parse(env("SUPABASE_SECRET_KEYS") || "{}");
    if (keys && typeof keys.default === "string" && keys.default) return keys.default;
  } catch {
    // fall back to the legacy key
  }
  return env("SUPABASE_SERVICE_ROLE_KEY");
}
const KEY = serverKey();
// A secret key (sb_secret_...) goes in the apikey header only; the legacy service-role key is a JWT
// and goes in both, as Supabase's own clients send it.
const serverHeaders = (): Record<string, string> =>
  KEY.startsWith("sb_") ? { apikey: KEY } : { apikey: KEY, authorization: "Bearer " + KEY };

class ProjectError extends Error {}

async function rest(method: string, table: string, query: Record<string, string>, init: { body?: unknown; prefer?: string } = {}): Promise<Response> {
  const url = new URL(`${PROJECT}/rest/v1/${table}`);
  for (const [k, v] of Object.entries(query)) url.searchParams.set(k, v);
  const headers: Record<string, string> = { ...serverHeaders(), accept: "application/json" };
  if (init.body !== undefined) headers["content-type"] = "application/json";
  if (init.prefer) headers.prefer = init.prefer;
  const res = await fetch(url, { method, headers, body: init.body === undefined ? undefined : JSON.stringify(init.body) });
  if (!res.ok) throw new ProjectError(`${method} ${table}: HTTP ${res.status}`);
  return res;
}

const hex = (buf: ArrayBuffer): string => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");

const deps = {
  env,
  data: DATA,
  deny: DENY,
  screen,
  fetch: (url: string, init?: RequestInit): Promise<Response> => fetch(url, init),
  now: (): Date => new Date(),
  log: (msg: string): void => console.log(msg),
  sha256Hex: async (text: string): Promise<string> => hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text))),
  // The caller's session, checked by the project's Auth server.
  async getUser(jwt: string): Promise<{ id: string } | null> {
    const res = await fetch(`${PROJECT}/auth/v1/user`, { headers: { apikey: KEY, authorization: "Bearer " + jwt } });
    if (!res.ok) return null;
    const user = await res.json();
    return user && typeof user.id === "string" ? { id: user.id } : null;
  },
  async memberRole(id: string): Promise<string | null> {
    const rows = await (await rest("GET", "members", { select: "role,active", user_id: "eq." + id })).json();
    const m = Array.isArray(rows) ? rows[0] : null;
    return m && m.active ? String(m.role) : null;
  },
  async recentDrafts(id: string, sinceIso: string): Promise<number> {
    const res = await rest("HEAD", "drafts", { select: "id", requested_by: "eq." + id, at: "gte." + sinceIso }, { prefer: "count=exact" });
    const total = Number((res.headers.get("content-range") || "").split("/")[1]);
    if (!Number.isFinite(total)) throw new ProjectError("drafts: no count");
    return total;
  },
  // The file's decisions, each with the brief it names, and the four-eyes setting: what the
  // page's approval check reads, so both build the same reviewer notes.
  async reviewInputs(lead: string): Promise<{ decisions: unknown[]; four_eyes: boolean }> {
    const decisions = await (await rest("GET", "decisions", {
      select: "id,author,lead,decision,brief_id,brief_sha256,four_eyes,note,reason,decided_at,brief:briefs(author,sha256,lead)",
      lead: "eq." + lead, order: "decided_at.asc,id.asc", limit: "1000",
    })).json();
    if (!Array.isArray(decisions)) throw new ProjectError("decisions: not a list");
    const config = await (await rest("GET", "config", { select: "four_eyes", key: "eq.workflow" })).json();
    const row = Array.isArray(config) ? config[0] : null;
    return { decisions, four_eyes: !(row && row.four_eyes === false) };
  },
  async recordDraft(row: Record<string, unknown>): Promise<void> {
    await rest("POST", "drafts", {}, { body: row, prefer: "return=minimal" });
  },
};

Deno.serve((req: Request) => handleRequest(req, deps));
