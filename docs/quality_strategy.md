# Quality strategy

How quality is assured in this repo as it stands. Written on 22 October 2026 against commit
1be3729, which added lessons to the workspace, and brought up to date at 8ddadc8, after f63245d
changed the brief screen; line numbers below refer to 1be3729 and hold at 8ddadc8 for every file
cited [Certain, from `git diff 1be3729 8ddadc8`]. Three later commits, dd77dfd, f50065a and
9c91283 (01:54 and 01:55 on 22 October 2026), add a triage view and are not described here. At
9c91283 pytest collects 297 tests, adding `tests/test_triage.py` and a fourth browser flow
(`tests/browser/triage_flow.mjs`), and the repo's screen still finds nothing, in 323 files
[Certain]. 69e40c1 replaces the workspace's tabs with fd-core's shared navigation, which the four
browser flows run through (fd-core tests its matching and that it can be inlined); at 33ca4fb
pytest still collects 297 tests, all pass, and the screen finds nothing in 323 files [Certain,
from the runs]. 1b4cbf2 adds the workspace's hosted kit and its 67 tests (two rows at the foot of
the table below): 364 tests, all passing with Postgres, Deno and the pinned Supabase client on the
machine [Certain, from the run].

A rise in exports is a lead, not evidence of a breach.

## 1. The rules every output is held to

From `CLAUDE.md`: no names of people or firms anywhere, official case references only; source
links only in the private register, never per-person detail, no URLs in anything public; the
deny list outside git; a minimum size for any series shown (the display rule, ADR 0003); the
licence checks in `data/SOURCES.md`; aggregates only; leads for a person, never findings; every
number traced to a row in `data/processed` and an entry in `data/ingest_log.jsonl`; data from a
side route used only after its checksums match; every inference tagged [Certain], [Likely] or
[Guessing]; the Open Government Licence line on every screen and report with HMRC data; nothing
leaves the repo until the fact-checker and guardrails-reviewer agents pass it; British English,
no em dashes.

## 2. Tests

Run from the repo root, with fd-core and ta-market beside it:

```bash
pip install -e ".[dev]" && pip install -e ../fd-core
pytest                                   # 286 tests at 1be3729 and at 8ddadc8
```

Some tests skip without their inputs or tools [Certain, from the skip markers]: the workspace
data tests need `app/data` built; the dashboard data tests need `demo/radar` built; the run 3
demo tests need `scripts/run_live_run3.py` run first; the JavaScript screen and prompt tests need
node; the browser flows need node and Playwright in `tests/browser/node_modules`; the site tests
need ta-market and fd-core beside this repo, and the site's browser test also needs Playwright;
the eval tests need Inspect (`inspect-ai`), which `pyproject.toml` does not list. Since 1b4cbf2
the hosted database tests need Postgres (initdb, pg_ctl and psql), the function's run needs Deno,
and the hosted browser check needs Playwright and the pinned Supabase client (`DR_SUPABASE_UMD`).

| Suite | Tests | What it covers |
|---|---|---|
| `test_rules.py` | 20 | Phase 1 lead rules: thresholds, persistence, the onward floor, baseline years, missing data |
| `test_baseline.py` | 3 | Baseline maths, missing years as zero |
| `test_leads.py` | 6 | The leads table, and that the phase 0 rules reproduce the phase 0 table |
| `test_mirror.py` | 15 | The mirror check and the exchange rates it uses |
| `test_config.py` | 5 | Goods codes, corridors, exchange rates and their sources |
| `test_pull.py` | 7 | Pull jobs, processed layouts, refusal to replace existing tables |
| `test_analyse.py` | 4 | Phase 1 analysis inputs |
| `test_asof.py` | 6 | The as-of engine: publication lag, release dates, three months running, the fallback rule, lead times |
| `test_backtest2.py` | 4 | The monthly onward signal, the peacetime rule, the run 2 snapshot reader |
| `test_run3.py` | 16 | Run 3: snapshot checksums, tables that extend run 2's byte for byte, reporter codes, outputs |
| `test_display.py` | 9 | The display rule at every run and the case-route windows |
| `test_onward.py` | 5 | Reasons an onward check did not pass, stated conduct ends, the small-onward limit |
| `test_demo_data.py` | 6 | Dashboard data: every run drawn passes the rule, no UK figure where a run is not shown, no per-person detail |
| `test_demo_run3.py` | 6 | Run 3 dashboard data: held-back series counted, never shown; counts as R3.1 and R3.2 |
| `test_brief.py` | 58 | The brief engine: contexts (no URL, no per-person detail, a source and a tag on every fact), the screen's rules and shared cases, the prompt, the stand-in drafter end to end, the red flags |
| `test_app_data.py` | 12 | Workspace data: copies match the reviewed dashboard files, manifest hashes, the display rule, the synthetic exporter file |
| `test_app_page.py` | 3 | The page holds the current shared screen; the JavaScript screen passes the shared cases; the page builds the same drafting prompt as Python, with and without notes and lessons (node) |
| `test_browser_flows.py` | 3 | Runs the three browser flows below in Chromium against the mock (since 1be3729) |
| `test_declarations.py` | 30 | The synthetic restricted layer: the seven detectors, schema, synthetic markers, evaluation |
| `test_signals.py` | 18 | The three public signals and the pre-registered criteria; committed results match a recomputation |
| `test_prediction_register.py` | 6 | Run 4's register |
| `test_share.py` | 22 | The shared copies' checks: held-back series and hidden tests, lead times by subtraction, first leads at runs the rule holds back, UK figures beside a case period, URLs, edits that must match the log, the README |
| `test_site.py` | 19 | The demo site's build checks, its Content-Security-Policy, and a browser test |
| `test_evals.py` | 3 | The offline evals reach their bar, and every planted note passes the note checks |
| `test_hosted_db.py` | 23 | Since 1b4cbf2: the hosted database on a scratch Postgres, acting as each person: roles, authors and times set by the server, four-eyes and SHA-256 on approvals, reviewer notes, refused lessons, the workflow locks, synthetic case outcomes only, insert-only tables and the audit rows |
| `test_hosted_js.py` | 44 | Since 1b4cbf2: the hosted build (the page unchanged, the reviewed data, the policy's hashes), the drafting function with a faked model, its port of fd-core's screen, `hosted.js` against a fake client, Deno, and Chromium under the site's policy (22 steps) |

Browser flows and the site's checks:

- `tests/browser/`: Playwright flows for the workspace (`flow.mjs`), the restricted layer
  (`decl_flow.mjs`) and lessons (`lessons_flow.mjs`: a note kept as a lesson, its author unable
  to approve it, a second person approving it, recall into a later draft with its provenance, a
  changed text stopping its use, retiring it), run against a mock of the platform that applies
  the page's own path rules. `tests/test_browser_flows.py` runs all three under pytest. They test
  the page against the rules, not the platform's enforcement [Certain, as
  `tests/browser/README.md` states]. At 8ddadc8 that README's steps for running them by hand
  list only the first two flows; dd77dfd lists all four, the triage flow included [Certain].
- `tests/site/smoke.mjs`: opens every page of a built site in Chromium at desktop and phone width
  and fails on console errors, blocked loads, requests to other sites, stray "null" text and
  sideways scroll. `tests/test_site.py` runs it on a fresh build when node and Playwright are
  installed, and it can be run by hand on `site/dist`. `tests/site/walkthrough.mjs` records the
  videos and stops if a count typed into a caption no longer matches the data.

## 3. CI

`.github/workflows/ci.yml` (commit b6ec1af) is set up to run, on every push and pull request,
the tests and the two evals that need no model, keeping the eval logs as artefacts; the live eval
would run only when started by hand with an API key set as a secret. It installs node and
Playwright's Chromium, so since 1be3729 its tests include the three browser flows [Certain, from
the workflow and `tests/test_browser_flows.py`]. It checks out fd-core and ta-market with a
read-only token the owner adds (`FD_CORE_TOKEN`). It has not yet run: the repo has no remote
[Certain, from the workflow and `git remote`]. It does not run fd-core's screen over the
tracked files and commit messages [Certain, from the workflow].

## 4. Screens and build checks

- **fd-core's screen** over every tracked file and every commit message:
  `python -m fdcore.guardrails --deny config/deny_list.txt --git . --policy config/guardrails_policy.txt`.
  The policy switches off only the accusing or phone check, for named paths, with the reasons
  in comments; names, company names, emails and postcodes are always checked (fd-core ADR 0004).
  Run on the committed trees of 1be3729 and 8ddadc8 on 22 October 2026, it found nothing in 310
  files (309 text files, four binary files skipped, and the commit messages) [Certain].
- **The brief screen** (`radar/brief/spec/screen_rules.json`): the Python reference and the
  page's port (`app/src/screen.js`) are held to the same 69 shared cases (56 drafts, 9 reviewer
  notes, 4 raw replies; 64 at 1be3729, before f63245d added five drafts). A draft that fails is
  never shown or saved. Since f63245d a multiple or fraction in words (doubled, tripled, twice,
  halved, threefold, three times) is refused as `figure_in_words`, and a count from two to twelve
  in words is read as its digits and must be backed like any other figure [Certain, from the
  rules and the shared cases].
- **fd-core's memory core on lessons** (since 1be3729): the page runs fd-core's `memory.mjs`,
  with rules exported from fd-core into `app/spec/memory_rules.json` and fd-core's commit in the
  manifest. A lesson passes the core's admission check when it is kept, and the core's recall
  screen and a check against its SHA-256 each time it is recalled; one that fails is held back
  and the file says why. It counts only once someone other than its author approves it with a
  reason (ADR 0008; `app/README.md` lines 120-141).
- **Build checks**: `scripts/build_share.py` checks the shared copies against the live tables and
  stops on a held-back series or hidden test named in one sentence, table row or list item, a
  list of lead times from which a held-back test's result could be worked out, a first lead at a run the rule holds back, a
  UK figure beside a tested case's period, a URL other than a data publisher's, a small UK figure
  or a screen finding (N7 added the first four); `scripts/build_site.py` checks the site before
  it writes it, including that a series not shown carries no field but its name and status;
  `scripts/build_app_data.py` writes a manifest that names the commit and lists any input not
  committed as it is (`source_dirty`); the generated spec and brief contexts fail the tests when
  out of date.
- **Data checks**: browser snapshots are verified by SHA-256, row counts and sums on load
  (`radar/snapshots.py`), and every call is in `data/ingest_log.jsonl`.

## 5. Independent review: `/review`, then `/ship`

- `.claude/agents/fact-checker.md` re-derives every number with its own script, marks each one
  MATCHES, WRONG, UNSOURCED or OVERSTATED, and checks confidence tags, dropped caveats, British
  English and dashes. It reports and never edits.
- `.claude/agents/guardrails-reviewer.md` runs fd-core's screen, then reads every file for names,
  personal data, accusations, licences, sensitive locations and anything linking the builder to
  investigating named parties. It returns PASS or BLOCK and never edits.
- `/review` runs both on the files to be shared. `/ship` requires: `pytest` passes, the review
  passes on every file shared, the licence line on every screen and report with HMRC data, no
  raw UN Comtrade responses unless its terms are checked, and a README that opens with the
  problem, the outcome and a video link.
- The record so far: independent rebuilds matched all 192 result fields of run 1 (B1.1), all
  1,310 output fields of run 2 (B2.1) and every field of run 3's 162 series (R3.2). The
  guardrails review blocked the demo three times on the display rule (N5, N6, N7). The reviews of
  the evening of 21 October 2026 returned 20 fact-check problems and a guardrails BLOCK; the fixes
  are in commit dba4c51 and research log N7, and no review of those fixes, of the lessons added
  in 1be3729 or of the screen change in f63245d is recorded yet [Certain, from the records]. Each
  error the reviews found is logged in `../fd-core/docs/where_claude_was_wrong.md`.

## 6. Pre-registration

Every backtest and every new rule is fixed in writing and committed before the code that runs
it or the data it reads:

| Run | Pre-registration | Committed before |
|---|---|---|
| Run 1 | `backtest/preregistration.md`, `backtest/data/test_plan.csv` (3b77d39) | `scripts/run_backtest.py` existed |
| Run 2 | `backtest/preregistration_run2.md` (b96c917) | any monthly UN Comtrade values or 2016-18 data were pulled |
| Signals S1 to S3 | `radar/signals/RESEARCH.md`, S0 (cd74780) | any signal was computed |
| Run 3 | research log R3 (5447f08) | any figure for the nine new corridors was pulled |
| Run 4 | research log R4 (06f25ca) | HMRC's 12 November 2026 release |

Each pre-registration says what was known before it was written (for example B0's smoke test,
disclosed in `backtest/preregistration.md`). Anything added after a run is labelled as not
pre-registered (B1.1), and any further analysis gets a new run number.

## 7. The research logs

- `backtest/RESEARCH_LOG.md` and `radar/signals/RESEARCH.md`: entries are added, never
  rewritten; a correction is a new entry that points back (N4 to N7, R3.2 to R3.5). The index
  changes only an entry's status: when R3.5 edited R3.4's index headline, the fact-checker's
  second pass had it restored (commit 6d80ad7). One exception since: R3.5's own headline still
  said a stray "null" was fixed on both pages after its amendment had narrowed that to the
  workspace page, and on 22 October 2026 it was made to match the amendment. Until
  `scripts/build_share.py` is run again, `share/RESEARCH_LOG.md` keeps the old headline and
  `tests/test_share.py` (`test_share_folder_is_current`) fails [Certain, from `--check`].
- Superseded runs stay in the log (B0, B1, N2).
- `share/RESEARCH_LOG.md` is written by `scripts/build_share.py` from the internal log, with each
  edit in `config/share_log_edits.json` required to match the log exactly once; it is never
  edited by hand.
- The decision log (`docs/decision_log.md`) is a table of current decisions, deferred items and
  their dates; it is not append-only, and git history keeps its earlier wording [Certain].

## 8. Evals (Inspect)

`evals/brief_evals.py`, `evals/run.py` and `evals/fake_drafter.py`, committed in b6ec1af:

- `brief_screen`: the brief screen on the 69 shared cases (64 before f63245d), with no model;
  each case must give exactly the problems it was written to show. Bar 1.0.
- `brief_live`: the workspace's drafting prompt on each of the 23 series the workspace shows, and
  on 6 of them again with a planted reviewer note taken from the poisoning test's held-out set,
  29 prompts per epoch. Scored on what a user would see: the reply parses as one brief and passes
  the screen, and the draft does not say what a planted note asks. A case passes only if every
  epoch passes. It needs a model and an API key, and costs money; it reports scores and has no
  bar.
- `pipeline`: `brief_live` on the stand-in drafter, one epoch, bar 1.0. It shows the scorers can
  pass; it says nothing about a model. The commit records that a stand-in that obeys the notes
  scores 0 of 6 (checked outside the repo).
- Run with `python evals/run.py screen`, `python evals/run.py pipeline` or
  `python evals/run.py live --model <provider>/<model> [--epochs 3]`; logs go to `evals/logs`,
  which git ignores. This machine has Inspect 0.3.283, the version CI pins [Certain].
- No live eval has been run. `evals/logs` does not exist; the only Inspect logs on this machine
  are in the build session's scratchpad, and every one is a run on `mockllm`, the stand-in
  drafter or a stand-in that obeys the notes [Certain, from the logs' headers].
- The evals leave the prompt's lessons block empty: `evals/brief_evals.py` builds the prompt with
  reviewer notes only; 1be3729 did not change it, and f63245d changed only its docstring's count
  of drafts [Certain, from the code].

## 9. What is not covered or checked

- **CI has not run.** The workflow is set up but the repo has no remote, so the tests and evals
  run only when someone runs them, and fd-core's screen over the repo is not part of CI at all
  [Certain].
- **The platform's own enforcement** of the workspace's store rules for people other than the
  owner is untested: it needs one account at Contributor and one at Editor (decision log,
  deferred line 65). The browser flows use a mock [Certain].
- **Names.** The deny list holds no names, so the screen's name check matches nothing; people's
  names are caught only through it and firm names only by their legal-form endings. The brief
  screen's possible-name check misses a name in lower case or at the start of a sentence; a
  person reads every brief [Certain, from the code and `radar/brief/README.md`].
- **Meaning.** The screens check wording and figures, not meaning: a claim can cite the right
  facts and read them wrongly (`radar/brief/README.md` lines 102-108). Since f63245d a multiple
  in words such as "doubled" is refused rather than passed, but that README still says the
  figure rule cannot test such words [Certain]. The eval's planted-note scorer looks for
  phrases, so it sees a draft that says what a note asks, not one that leaves something out
  [Certain, from the scorer's code].
- **Disclosure by combination.** The display rule tests size and spread, not how many exporters
  make up a flow. The share and site checks catch the forms of leak found so far, not every
  inference; the reviews stay the main defence, and anyone can rerun the radar on the public
  data (N7, limits).
- **Backtest limits.** Four cases; the tests are not blind (B0 touched three series before the
  rules were fixed); goods are mapped to codes, some loosely; values are today's, after
  revisions; some release dates are replacements; the European reference dates are the earliest
  dated steps found, known only to the month; the integrated circuit codes are unspecific.
- **The three signals** were checked by a second implementation by the same author, not
  re-derived by the fact-checker (S0.1).
- **Terms and sources.** The raw UN Comtrade snapshots are within its limited-amount exemption
  [Likely]; the Bank of England series' republishing terms were read through a summary [Likely];
  R4's release dates are unsourced, as no copy of the calendar page was kept (fact-check of
  21 October 2026, item 20).
- **Known bias.** The 2019-21 baseline for heading 8548 holds goods the later series does not,
  which leans towards fewer flags [Likely] (decision log, deferred line 64).
- **A model in the loop.** No brief drafted by a model has been scored by an eval yet. Whether
  a model follows an instruction hidden in an approved lesson is fd-core's poisoning test P2, not
  yet run (`app/README.md` lines 120-141). A second person on every lesson is one of the two
  defences P1.1 named for a separate pre-registered test. fd-core's P1.2 (commit 1077d94)
  records both tools' adoption of the two defences as unmeasured and says any measurement is to
  be registered, with predictions, before it runs; none is written yet, so what they add is not
  measured (fd-core `research/POISONING_LOG.md` lines 94-132) [Certain].
- **Deployment.** Nothing is deployed; the site's checks run on the build, not on a deployed
  site.
