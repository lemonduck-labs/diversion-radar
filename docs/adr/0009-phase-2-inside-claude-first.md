# 9. Phase 2 inside Claude first, built to move to Supabase and Netlify

Date: 21 October 2026. Status: Accepted (the owner's decision).

## Context

The analyst workspace needs a shared store, sign-in, drafting with Claude and downloads. None
of these existed for the radar before phase 2.

## Decision

- The workspace (`app/`) runs inside Claude as an artifact page with a shared store, sign-in,
  Claude drafting on the viewer's own usage, and downloads. It is built to move to Supabase and
  Netlify by swapping its store, drafter and sign-in (decision log line 26).
- The page reaches all four through `claude.use(name)` and works without each of them: with no
  store it runs in demo mode, with no drafting it offers the template, with no downloads it hides
  the export buttons.
- The brief engine's contract is language-neutral (`radar/brief/spec/`), so that a page or a
  Deno function loads it unchanged; the Python modules are the reference, and the shared cases
  are what a port must pass.

## Options ruled out

None recorded.

## Consequences

- Drafting runs on the viewer's own Claude usage, with no key held by the project [Certain].
- Until 22 October 2026 no hosted build existed for this workspace. The hosted kit is now built
  and tested here, not deployed (`hosted/README.md`): Supabase Postgres in London, where the
  database sets every author and time, checks approvals and writes the audit log; sign-in by an
  emailed code for invited people; drafting through a function on the owner's key that screens
  every draft with the private deny list; Netlify with a policy that allows only the page's own
  code and the pinned Supabase client. The page is the same, apart from saying which version it
  is; lessons and triage outcomes stay in the artifact and demo builds for now [Certain, from the
  tests]. ta-market made the same move for its planner first (`../ta-market/hosted/README.md`).
- In the pilot, the store's rules for people other than the owner are [Likely] until tested with
  two more accounts (ADR 0008).
- The private deny list cannot run in the page; the hosted drafting function adds it, and with no
  terms bundled it refuses to draft [Certain, from the tests].

## Where recorded

Line numbers are as at commit 1be3729.

- `docs/decision_log.md` line 26 (commit 46af934).
- `app/README.md` lines 10-23, 92-101 and 103-118.
- `radar/brief/README.md` lines 9-24 and 51-70.
