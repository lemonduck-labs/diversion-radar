# Handover

For someone taking this repo over. Written on 22 October 2026 against commit 1be3729 and brought
up to date at 8ddadc8. Three later commits, dd77dfd, f50065a and 9c91283 (01:54 and 01:55 on
22 October 2026), add a triage view of synthetic reports to the workspace, and 69e40c1 gives the
workspace fd-core's shared navigation; neither is described here (see `app/README.md`, "Getting
around" and "Reports: triage") [Certain]. 1b4cbf2 adds the workspace's hosted kit, under "How
hosting would work" below. Phase 4 (69e40c1 to cc1d786, 22 October 2026) is the look and the
wayfinding: the shared navigation, record pages that keep their place in a list, phone layouts,
cues on wide tables, an amber lead marker on the dashboard, the landing page's tiles and
re-recorded walkthroughs (decision log, 22 October 2026). The brand step that followed, later on
22 October 2026, gives the dashboard and the workspace the Diversion Radar brand (`brand/`, written
into both pages by `scripts/build_app_page.py`; the lead marker is now violet, not amber, at the
owner's request) and a How it works guide in each [Certain].
Phase 5, the same day, adds the workspace's overview, corridor map, lead factors, Connected panel
and the lead-worth card, and HMRC's next release date (12 November 2026, from the uktradeinfo
release calendar, read 22 Oct 2026), which with the calendar's 11 December 2026 entry (October 2026 data) sources both of R4's release
dates [Certain].
Phase 6, later the same day, adds a sign-in screen, the record layout for files, follow-ups (hosted:
`public.tasks`, migration `20261022130000_radar_followups.sql`), a Follow-ups page, corridor and
goods-code pages, a Team and access page, a References panel from `radar/brief/spec/references.json`
and add-ons that send nothing; `docs/phase6_platform.md` has the research behind it and the
proposed phase 7 monitoring layer, which waits for the owner's sign-off [Certain].

## What it is

- A monthly radar of leads from published trade statistics alone: the corridor countries where
  UK exports of high-priority goods and that country's own exports of the same goods to Russia
  rose together (162 series, 18 corridors by 9 goods codes).
- An enforcement backtest of that rule against published cases, every run pre-registered and
  logged, and an analyst workspace that drafts a brief from a lead's facts, screens it and puts
  it in front of a second person; a reviewer's note can be kept as a lesson for later drafts once
  a second person approves it (fd-core's memory core, since 1be3729).
- Leads for a person, never findings. A rise in exports is a lead, not evidence of a breach.

## Set up and run

With fd-core and ta-market cloned beside this repo:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" && pip install -e ../fd-core
pytest                                  # 365 tests at cc1d786; 364 at 1b4cbf2; 297 at 9c91283 and 33ca4fb
python evals/run.py screen              # no model, no key (needs inspect-ai; CI pins 0.3.283)
```

The full build order, from pulls to the demo site, is under "Run it" in `README.md`. Also needed:
node 22 and Playwright 1.64.1 (`cd tests/browser && npm install`) for the browser flows and the
site's smoke test; `COMTRADE_KEY` (optional) for faster UN Comtrade pulls. Before anything leaves
the repo: `/review`, then `/ship` (`.claude/commands/`).

## Where things live

| Path | What |
|---|---|
| `CLAUDE.md`, `WORKFLOW.md` | The hard rules and the stages, owners and gates |
| `docs/decision_log.md` | Every decision, default and deferred check, with its record |
| `docs/adr/` | Decision records 0001 to 0010 |
| `docs/quality_strategy.md` | Tests, screens, reviews, pre-registration, evals, and what is not covered |
| `backtest/RESEARCH_LOG.md` | Every backtest and note, superseded ones included (internal: it names held-back series) |
| `backtest/`, `radar/` | The live rule (`backtest/asof.py`, `backtest/monthly.py`), the display rule (`radar/display.py`), the brief engine (`radar/brief/`), the synthetic restricted layer (`radar/declarations/`) |
| `data/` | Raw snapshots, processed tables, `ingest_log.jsonl`, `SOURCES.md` |
| `demo/radar/`, `app/` | The dashboard and the analyst workspace, with their data; `app/spec/memory_rules.json` is generated from fd-core |
| `share/` | The only copies of the research log and case register that may leave the repo, written by `scripts/build_share.py` |
| `site/` | The static demo site's sources; `site/dist` and `site/media` are built, not in git |
| `evals/`, `.github/workflows/ci.yml` | Inspect evals and the CI workflow |
| `config/` | Codes, corridors, exchange rates, the guardrails policy, the deny-list template (the working `deny_list.txt` is local and gitignored) |

## What is open

- **The reviews of 22 October 2026**, on 0993ea2 (reports in the build session's scratchpad,
  `reviews/guardrails_2026-10-22.md` and `reviews/factcheck_radar_2026-10-22.md`): the guardrails
  review passed the demo site, the private tool pages and the shared files, with low fixes, and
  blocked making any repository public as it stands; the fact-check found 20 problems, none a
  wrong figure on the site. Their fixes are in e5b4ddf and research log N8. A verification of
  the fixes the same day (`reviews/verification_2026-10-22.md`) passed the site and the shared
  files for sharing, on two owner decisions (below), and found a few small slips, fixed in the
  commit that adds this sentence [Certain].
- **The private artifacts** inside Claude (the workspace, the planner and the two dashboards)
  were refreshed to match the repositories after each round of fixes on 22 October 2026, the
  last after e5b4ddf and ta-market a243d3b. Each is private; the owner should confirm he has not
  shared any of their links, since until that morning they held earlier copies (decision log,
  22 October 2026) [Certain on the refresh; the sharing is the owner's to confirm].
- **Still open from the reviews**: Move forward's deny list is empty (the radar's was filled on 24 October 2026); [held back in this copy]; invented names in the
  brief screen's shared cases rest on a person reading them (item 10); the memo's byline chip
  (item 9, outside the repo); R4's release dates are unsourced (fact-check item 20) [Certain,
  from the files on 22 October 2026].
- **Lessons** (1be3729) and the screen change of f63245d have no review recorded. Whether a
  model follows an instruction hidden in an approved lesson waits for fd-core's poisoning test
  P2. fd-core's P1.2 (commit 1077d94) records the second person on every lesson as adopted and
  unmeasured; the pre-registered measurement it calls for has not been written [Certain].
- **The workspace manifest** committed in 8ddadc8 names f63245d as its source, with no
  uncommitted inputs; the dirty manifest of 1be3729 is resolved [Certain, from `git show`].
- **The shared research log** was regenerated with `python scripts/build_share.py` in the commit
  that adds this handover, after the R3.5 and N6 index rows were corrected on 22 October 2026 to
  match their amendments; run it again whenever the research log changes, as `--check` and one
  test in `tests/test_share.py` fail until it is [Certain].
- **The site's clean build** was blocked from ta-market c165ef6 until ta-market 98c745a, as
  ta-market's `scripts/build_app.py --clean` counted fd-core's `memory.mjs` as an uncommitted
  input. Since 98c745a it works: `python scripts/build_site.py --clean` wrote `site/dist` at
  02:37 on 22 October 2026 from diversion-radar 33ca4fb, ta-market 98c745a and fd-core 72ead08
  [Certain, from the run].
- **`tests/browser/README.md`** at 8ddadc8 lists two of the three browser flows, leaving out
  `lessons_flow.mjs`; dd77dfd lists all four, the triage flow included [Certain].
- **Run 4**: the first check is due after HMRC's release of 12 November 2026, the second after
  11 December 2026 (research log R4).
- **CI** is set up but has not run: the repo has no remote, and the workflow needs the secret
  `FD_CORE_TOKEN`; the live eval also needs an API key, and the repository screen it runs takes
  the deny list from an optional secret, `DENY_LIST`.
- **Deferred items** (`docs/decision_log.md` lines 52-70): a code licence; the commit author email;
  UN Comtrade's terms for the raw snapshots and for any paid product; the Bank of England series'
  terms; EU-05's finality; US-01's sentencing; the display rule's levels; official URLs in the
  private register whose paths describe defendants; filling the deny list; the phase 0 charts; a
  test of spread in the rule; the heading 8548 baseline; the workspace's rules on a live
  artifact; signals S2 and S3; the git history from e6b7401 to 1392ce7; and, since 1b4cbf2,
  lessons and triage outcomes in the hosted version, the hosted workspace on a live project, and
  staff data on the hosted site.
- **Decision log rows 22, 27 and 45** described the held-back tests and the exporter screen's
  data as they were before N7; they were brought into line with N7 on 22 October 2026.

## Decisions that wait for the owner

- Every row marked "Default, open to the owner" in `docs/decision_log.md`: lines 14, 15, 16, 18,
  19, 20, 23, 24, 27, 28, 30, 31, 41, 42, 43, 44, 45 and 46.
- The display rule's levels, before the first public showing (deferred line 59).
- From `site/README.md` ("Open for the owner"): a byline, indexing, and whether to show the two
  held-back backtest tests at all; N7 adds that the owner may drop their count too, and N8 that
  the site alone places one of them on its route, with a bound on its UK flow.
- Anything that publishes, spends or sends waits for the owner's explicit yes (decision log line
  40): publishing the site, pushing to a public remote, the CI secrets, and paying for live evals.
- This copy is the separate public repository the guardrails review of 22 October 2026
  recommended: fresh history, built from the code, `share/` and `site/` without the private
  research files, a neutral author and plain commit messages (`PUBLIC.md`).

## How hosting would work

- **The demo site** is built and tested here and not deployed. `site/README.md` ("Publishing")
  gives the owner's steps: `/review` and `/ship` on the built site, the owner's own checks,
  `python scripts/build_site.py --clean`, then Netlify
  (drag `site/dist` onto the dashboard, or the CLI at 27.11.2), a check that the headers arrived,
  and a look on a phone. It makes no AI calls and needs no sign-in.
- **The workspace** runs inside Claude as an artifact page (ADR 0009). Its hosted version on
  Supabase and Netlify is built and tested here since 1b4cbf2, and not deployed: `hosted/README.md`
  gives the owner's steps, from creating the project in London to the checks with a second and a
  third account. Nothing exists for it yet: no project, site, secret or key [Certain].
  `python scripts/build_hosted.py` writes the Netlify folder and the drafting function's bundle,
  which holds the private deny list and stays out of git; with no terms in it the function will
  not draft. ta-market's `hosted/README.md` is the same move for the planner, also not deployed.
