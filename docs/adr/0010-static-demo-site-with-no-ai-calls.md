# 10. A static demo site with no AI calls and no sign-in

Date: 21 October 2026. Status: Accepted (a default, open to the owner; published on 24 October 2026).

## Context

The four demos (the radar dashboard, the analyst workspace, the TA market picture and the
move-on planner) run as artifacts inside Claude. A link that opens on a phone with no sign-in
needed a copy that does not depend on claude.ai (`site/README.md`).

## Decision

- The four demos as static pages for Netlify, built by `scripts/build_site.py` from the
  committed repos and checked before anything is written: fd-core's screen, councils, the
  display rule, other sites, licence lines, links and headers.
- A Content-Security-Policy per page that allows only the site's own files and the page's
  inline scripts by SHA-256.
- No AI calls, no sign-in, noindex, no byline.
- Published on 24 October 2026, after the independent reviews and at the owner's yes (decision
  log, 24 Oct 2026).

## Options ruled out

- A live drafting demo, because it needs a key and has a running cost (decision log line 46).

## Consequences

- With no Claude runtime, the workspace and the planner run in demo mode: changes stay in the
  tab, and briefs and plans start from the template (`site/README.md` lines 31-33).
- Sharing the artifacts by link stays possible, and the site can move to the owner's own domain
  (decision log line 46).
- The checks run in `tests/test_site.py` and in the Chromium smoke test
  (`tests/site/smoke.mjs`), which found a stray "null" on the workspace and the planner
  (commits f4c30e1 and 4b62133) [Certain].
- The reviews of 21 October 2026 found that `--check` is not write-free (it runs ta-market's
  page build, which writes that repo's `app/dist`), that the display-rule check reads one line
  at a time, and that no video caption or transcript carried the licence line (fact-check item
  16; guardrails items 7 and 8). Commit dba4c51 documents the first, adds checks for the fields
  of series not shown, and ends every video with the licence line (`site/README.md` lines 55-57,
  62-65 and 77-92) [Certain, as the file records].
- Open for the owner: a byline, indexing, and whether to show the two backtest tests under the
  display rule at all (`site/README.md` lines 123-130).

## Where recorded

Line numbers are as at commit 1be3729.

- `docs/decision_log.md` line 46 (commit e6b7401).
- `site/README.md` lines 1-8, 35-48, 50-75 and 94-130.
- `scripts/build_site.py`, `tests/test_site.py`, `tests/site/smoke.mjs`, `tests/site/serve.mjs`.
- Commits e6b7401 (the site), 3a557bf (the walkthrough videos) and dba4c51 (the review fixes).
