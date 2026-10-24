# Diversion Radar

> **Start here.** [Live demo](https://lemonduck-labs.netlify.app/) of the dashboard and the analyst workspace (static
> pages, synthetic people, nothing sent anywhere) · films: [dashboard, 1:53](https://lemonduck-labs.netlify.app/videos/radar.mp4)
> and [workspace, 5:02](https://lemonduck-labs.netlify.app/videos/workspace.mp4) · what this public copy leaves out and why:
> [`PUBLIC.md`](PUBLIC.md) · how it was built and checked: [`docs/how_this_was_built.md`](docs/how_this_was_built.md)
> · the case register as it may leave the repo: [`share/cases.csv`](share/cases.csv) · decisions and what is
> still open: [`docs/decision_log.md`](docs/decision_log.md). Shared for review: [`NOTICE.md`](NOTICE.md).

**The problem.** Goods on the Common High Priority List (integrated circuits, communication and
navigation equipment, capacitors and other electrical parts) reach Russia through third
countries. Who shipped what to whom sits in export declarations: exporters see their own, and
only customs and enforcement bodies see them all.

**The outcome.** Leads from published trade statistics alone: each month, the corridor and goods
code pairs where UK exports to the corridor rose and the corridor's own exports of the same goods
to Russia rose too. Rerun month by month on today's figures, with each onward figure counted from
its recorded release date, the rule with a monthly onward check had a lead before the first
public action in 4 of 4 published enforcement cases (3 with the annual check alone), though in
two of them the lead shown had stopped before the action. The monthly check's price is more
leads: 20 of 81 series on those corridors were a lead at some run since January 2022, against 19
with the annual check alone. Four cases is a small test, and not a blind one [Likely].

**Watch.** Captioned walkthroughs of the dashboard (1:53) and the analyst workspace (5:02), on the
demo site at `/videos/radar.mp4` and `/videos/workspace.mp4`. The site (`site/`, built by
`scripts/build_site.py`) runs both as static pages, with no sign-in and no AI calls, beside the
market picture and the Move forward planner of the Move forward build (ta-market); it is not published yet
(`site/README.md`).

**Brand and guide.** The dashboard and the workspace share one look, kept in `brand/`: navy ink,
an action blue, violet for a lead and the onward signal behind it, Aldrich for the wordmark, titles
and headline figures, IBM Plex Sans and IBM Plex Mono for text and codes (all SIL Open
Font License, `brand/fonts/OFL.txt`) and an original logo mark. `scripts/build_app_page.py`
writes it into both pages with fd-core's `fdcore.brand`, fonts as data: URIs, so neither page
loads anything from elsewhere. The workspace opens on an overview (what changed since the last run, what
waits for a decision and for how long, who holds what, and what a lead is worth: the
backtest's record and its price, and briefing time on the hours you enter, never a value put on a
case), with a corridor map, the factors behind each lead and what each file connects to. Phase 6
adds a sign-in screen (in the demo, synthetic people at each role: analyst, reviewer, partner
liaison, owner), files laid out as one record with folding sections and a rail (properties,
follow-ups with owners and due dates, official references, add-ons that show what they would
send, connected records), a Follow-ups page, corridor and goods-code pages, and a Team and access
page (`docs/phase6_platform.md`). Phase 6.5 closes the loop: the overview opens on a console
with a turning globe (the run's leads and watch items by corridor, routes from the UK and on to
Russia, a sweep that lights each as it passes; the sweep is continuous, the data is the monthly
run's), an outcome on every decided file, a referral pack that follows the headings of OTSI's
reporting guidance where a lead can fill them, an end-use controls decision record that a second editor approves, lessons from
the published cases, and pilot timings kept in the browser. Phase 7 adds the monitor: official
notices, statistics releases and guidance from a register of lawful public sources (in English,
Turkish and Russian so far), each with the original beside an English summary and a proposed
grade, waiting for an analyst to accept or reject (`monitor/RUNBOOK.md`). Each
has a How it works guide (the workspace's sidebar, the dashboard's last tab): who uses it, a typical month (the workspace) or how to read it (the
dashboard), what is demo data in that copy, and what a deployment could add.

A rise in exports is a lead, not evidence of a breach.

## What it does

Each month, for 162 series (18 corridor countries by 9 goods codes):

- **UK signal**: UK exports to the corridor over the trailing 12 published months at least twice
  the 2019-21 annual average and at least £20,000 above it, for 3 published months running
  (HMRC overseas trade statistics).
- **Onward signal**: the corridor's own exports of the code to Russia at least twice its 2019-21
  level and at least $100,000, in the latest year released or, for the 16 corridors with monthly
  UN Comtrade data after 2019, the latest 12 months (UN Comtrade; China's monthly data end in
  December 2024 and Vietnam's in December 2023). Each figure counts only from the release date
  UN Comtrade records for it; where a dataset was replaced, that may be the replacement's date,
  so a signal can come late but not early [Likely]. The 2019-21 baselines are used at every run.
- **Lead**: both signals at one run. A UK signal alone is a watch item.
- **Display rule**: a flagged series is shown only when its UK exports over the 12 months reach
  £250,000 and came in at least 6 of them. Smaller ones are counted, never shown by corridor or
  code, so a small flow is less likely to point at one exporter; it cannot rule that out
  [Likely].

## What it found

- **The October 2026 run**, on HMRC data to August 2026: 9 leads and 26 watch items among the
  162 series, of which 7 leads and 16 watch items are shown (`backtest/reports/run3.md`,
  internal, as it lists the series held back).
- **The backtest** (`backtest/`): four published cases with pleas or convictions, two
  of them at first instance (two US, on official records; two European, on published reports),
  and eight tests fixed before either run. With the monthly check, a lead came before the first
  public action in 4 of 4 cases; with the annual check alone, in 3. In two cases the lead shown
  had stopped before the action. Two tests are held back by the display
  rule, with no route and no result. None of the four cases names UK goods or a UK party, and a
  lead never means a UK party was involved.
- **What it does not show.** Four cases is an illustration, not a validation. The test is not
  blind: the cases, corridors and codes come from the same public reporting, and an early smoke
  test touched three of the tested series before the rules were fixed [Likely]. The monthly check
  was designed after run 1, whose report foresaw one of its gains [Certain]. The goods are mapped
  to the radar's codes, some loosely [Certain]. The integrated-circuit codes were a lead at some
  run before two of the case dates on 4 of 8 other corridors, so a lead on them says little about
  one route [Certain]. EU-01's lead times may be too long [Likely], and dating the European
  actions to the first of the month can make lead times up to a month too short [Certain]. The backtest covers the original nine corridors
  only, and the four cases are the only ones of the 22 in the register that can be tested
  [Certain].
- **What earlier warning costs**: on the backtest's nine corridors, the monthly check made 20 of
  81 series a lead at some monthly run from January 2022 to August 2026, against 19 with the
  annual check alone, and 300 of the 4,536 series-runs (81 series at 56 monthly runs) a lead,
  against 257. In a peacetime
  placebo (2019-21 against 2016-18, annual check alone) 2 of 81 series were ever a lead, against
  18 of 81 in 2022-24: an indication, not a false-alarm rate, as 2019-21 held the pandemic and
  the 2014 sanctions [Certain].
- **The record**: every run, superseded ones included, is in `backtest/RESEARCH_LOG.md`, with a
  shared copy in `share/`. Run 4, a prediction register scored on HMRC's November and December
  releases, was registered before them (R4).

## The analyst workspace (`app/`)

An inbox of the run's leads and watch items; a file for each with its evidence and the case
routes it touches; an analyst brief that Claude is asked to draft from those facts only, with any
reviewers' notes and approved lessons as data (inside Claude), or that starts from a template; a screen that checks every draft and edit before it is shown or saved
(figures not in the evidence, names, judging words: a net, not a guarantee); approval by a second
person while four-eyes is on, as it is by default (with it off, one person may approve and the
file says so), which counts only while the text matches its SHA-256 fingerprint; lessons, where
a reviewer keeps a returned brief's note for later drafts on the same route, goods code or
corridor, used only once a second person approves it and recalled through fd-core's memory
core with its provenance; questions
from official guidance; an exporter screen that checks an exporter's own shipments against the
corridor signals; a restricted layer that runs seven detectors over synthetic export
declarations; a triage view that reads synthetic reports of a suspected breach of trade
sanctions against all of these and a synthetic list in the UK Sanctions List's format, with the
body that handles each kind of report and the factors OTSI's guidance weighs; an audit log and
an evidence pack; follow-ups on each file, with an owner and a due date, audited like the checks. It runs inside Claude as an artifact, and on
the demo site in demo mode. `app/README.md` has the detail.

## Guardrails

- No names of people or firms anywhere, and no personal data: aggregate statistics and
  synthetic declarations only. The workspace's own screen checks every draft and edit. fd-core's
  screen checks the shared copies in `share/` and the demo site as they are built, and every
  tracked file and commit message when it is run on the repository (`--git`), as the CI
  workflow will on each push once the repo has a remote: it catches firm names by their
  legal-form endings and people's names only through a private deny list kept out of git, filled
  on 24 October 2026 with the parties named in the case register's sources. Both screens are nets, not guarantees; the reviews below
  are the main check [Certain].
- The evals (`evals/`, on Inspect) run the brief screen's hand-written cases on every push, and
  the drafting prompt end to end on a stand-in drafter; when the workflow is started by hand with
  an API key set, they run the live model several times a case. The CI workflow is left out of this public copy, since it needs the private research
  record (`PUBLIC.md`).
- Outputs are leads for a person, never findings.
- Every number traces to a row in `data/processed` and an entry in `data/ingest_log.jsonl`, and
  every inference carries [Certain], [Likely] or [Guessing].
- Nothing leaves the repo until the fact-checker and guardrails-reviewer agents pass it (`/review`,
  then `/ship`). This public copy went through the same checks (`PUBLIC.md`).

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" && pip install -e ../fd-core
python scripts/pull.py                  # HMRC and UN Comtrade for the original nine corridors (needs internet)
python scripts/build_run3_tables.py     # run 3's tables, from the browser snapshots in data/raw, checked
python scripts/run_live_run3.py         # the current run: 18 corridors, on run 2's rule
python scripts/run_backtest.py          # backtest run 1, as pre-registered in backtest/preregistration.md
python scripts/run_backtest2.py         # backtest run 2: the monthly onward check and the placebo
python scripts/build_demo_data.py       # the dashboard's datasets (demo/radar)
python scripts/build_brief_contexts.py  # the brief contexts for every series shown
python scripts/build_app_data.py        # the workspace's data files (app/data, app/spec)
python scripts/build_app_page.py        # the workspace page (app/index.html)
python scripts/build_share.py           # the shared copies of the research files (share/)
python scripts/build_site.py --clean    # the demo site (site/dist), with ta-market beside this repo
pytest
python evals/run.py screen              # the brief screen's cases, scored in Inspect (no model, no key)
python evals/run.py pipeline            # the drafting prompt end to end on a stand-in drafter (no key)
```

Set `COMTRADE_KEY` to a free UN Comtrade subscription key for faster, larger pulls. Without it
the scripts use the public preview endpoint (one period per call, rate limited).

## Layout

| Path | What it holds |
|---|---|
| `config/` | The nine goods codes, the corridors (`countries.csv`, the original nine; `countries_run3.csv`, all 18), exchange rates, the guardrails policy and the deny-list template |
| `radar/` | API clients, the ingest log, baselines, phase 1's rules, the display rule, the brief engine (`radar/brief`) and the synthetic declarations (`radar/declarations`) |
| `backtest/` | The live rule (`asof.py` with `monthly.py`, run by `scripts/run_live_run3.py`), the case register, pre-registrations, results, reports and `RESEARCH_LOG.md` |
| `evals/` | Inspect evals of the brief: the screen's cases, and the drafting prompt end to end |
| `data/` | Raw pulls and browser snapshots, processed tables, the ingest log and `SOURCES.md` |
| `demo/radar/` | The dashboard (written for Claude's Dashboard artifact type) and its datasets |
| `app/` | The analyst workspace page, its data and its spec |
| `share/` | The copies of the research log and case register that may leave the repo |
| `site/` | The demo site's landing page, styles and build notes |
| `reports/` | Phase 0 and phase 1 results and the October 2026 run on the original nine corridors |
| `docs/` | Decision records (`docs/adr/`) and the decision log |
| `tests/` | Tests for every part, the browser flows (`tests/browser/`) and the site's smoke test and walkthroughs (`tests/site/`) |

## Data and licences

Contains public sector information licensed under the Open Government Licence v3.0 (HMRC
overseas trade statistics): https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/

Onward figures: UN Comtrade, used under its re-dissemination guidance: limited tables and charts
need no permission, and this public copy leaves the raw UN Comtrade snapshots out until its
terms are confirmed. Details, and the other sources, in `data/SOURCES.md`.
