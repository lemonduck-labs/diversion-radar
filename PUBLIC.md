# This public copy

The working repository is private. This copy holds the code, the agent team, the docs, the
demo data the published dashboard and workspace load, the processed HMRC and UN Comtrade tables,
and the shared case register (`share/cases.csv`). It leaves out, on purpose:

- **The research record behind the runs**: the research log, the backtest's results, series,
  placebo and test plan (`backtest/data/run*_*.csv`, `test_plan.csv`) and reports, the live runs'
  lead tables (`data/processed/leads*.csv`, `live_*.csv`, `mirror_phase1.csv`), the phase 0
  comparison table (`hmrc_compare.csv`), the prediction register (`r4_register*`), the early
  reports and their charts (`reports/`), the signals research and its results, and the research
  notes. They name series the display rule holds back or give the results of tests it holds back,
  or link to pages that name parties. The results the radar shows are in the README, the
  dashboard and the workspace.
- **The case register's source links**: `backtest/data/cases.csv` keeps every case with its
  official reference; its `source_url` and `other_sources` columns are empty here, and, as in
  `share/cases.csv`, the case that a held-back test is on keeps its record but not the corridors
  it documents.
- **Raw downloads** (`data/raw/`); the processed tables built from them are kept.
- **Two held-back tests' details in `backtest/preregistration.md`**, in the T4 row and in the
  passage on the smoke test run before it was written, marked `[held back]`. Nothing else in the
  pre-registration is changed.
- **Two monitoring items** whose sources reserve their rights or forbid commercial use, as on
  the demo site; their sources stay in `monitor/sources.json`.
- **The continuous-integration workflow**, which needs the private record.
- **The deny list** of names the screen blocks, which never goes into git anywhere.

The processed HMRC and UN Comtrade tables hold every series as the publishers give them; nothing
in them marks a series as held back. Anyone can rerun the radar on the public data: the display
rule limits what this project says, not what the public data hold.

Paths in the docs to the files above point to the private repository. Tests that need them are
skipped here with that reason (`tests/public_skip.txt`); the rest run as they do in the private
repository.

## How this copy was checked

- A scan of every file and the commit for anything that identifies the publisher.
- fd-core's guardrails screen with the private deny list of the parties named in the case
  sources (the list itself is never published): no name found.
- A scan for every series and test route the display rule holds back.
- Three independent reviews by agents that did not build the copy, against the rules in
  `CLAUDE.md`; their blocking findings were fixed before it was published.

A rise in exports is a lead, not evidence of a breach.
