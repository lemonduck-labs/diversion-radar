# 3. The display rule: a floor on size and spread, at every run, with the rest counted

Date: 21 October 2026. Status: Accepted (a default, open to the owner; the two levels wait for
the owner's view before the first public showing).

## Context

CLAUDE.md requires, before anything is public, a minimum size for any series shown as a lead,
so that a small flow cannot point at an identifiable exporter. While setting that minimum,
Claude found that the three-months-running test does not screen out one large consignment: the
UK signal uses a trailing 12-month sum, which stays high for a year after one shipment
(research log N1). There is no disclosure rule to borrow: HMRC suppresses a figure only when a
trader asks (`radar/display.py`).

A rise in exports is a lead, not evidence of a breach.

## Decision

- A flagged series (a lead or a watch item) is shown by corridor, code and figures only when
  its UK exports over the 12 published months behind the flag total at least £250,000 and were
  recorded in at least 6 of those months. A series that fails is counted, never shown by
  corridor or code.
- The rule applies at every run shown or counted, not only the latest: a past run whose 12
  months fail it is blank and counted.
- On a route the backtest tests, or a code in the same four-digit heading on that corridor,
  only 12-month windows that start after the case's first public action are drawn. Routes the
  case register links to cases beyond the test plan limit what is drawn in the same way.
- A backtest test is shown only when its UK flow at the last run before the action passes the
  rule for at least one of its codes, whatever its result; the counts shown cover the tests
  shown. Since N7 (commit dba4c51, 22 October 2026), a test under the rule has no route and no
  result, in the data and on both pages; since 24 October 2026 it keeps only its id, so all
  eight pre-registered tests stay visible as a count, and the shared case register shows the
  case it is on without the corridors that case documents.
- A series not shown carries nothing from the radar in the exporter screen's data, and the
  summary does not split the leads by onward check, so a held-back lead looks like any other
  series not shown (N7).
- The shared copies of the research files count a held-back series and never name it, with no
  UK figure for a run under the rule. They are written and checked by `scripts/build_share.py`.

## Options ruled out

- Holding back every series on a tested case route, instead of cutting its windows: "Holding
  these series back instead would leave no leads on the Now tab" (decision log line 18).
- A rule for showing tests that depends on the result (a hit shown only when one of its lead
  runs passes): dropped the same day, because it made the rule depend on the result (N6, its
  amendment; commit 9a01c96).
- A hand-edited shared copy of the research log: ruled out because it would drift from the log
  (decision log line 43).

## Consequences

- At the October 2026 run (run 3), 12 of the 162 series are held back, 2 leads and 10 watch
  items, and counted only (decision log line 39; research log R3.1) [Certain].
- The rule hides some routes that a case later documented as well as small flows (N2) [Certain].
- It tests size and spread, not how many exporters make up a flow, so a large flow shown can
  still come mostly from one exporter (R3.1, problems) [Certain on the mechanism].
- Both levels are judgement calls, not taken from HMRC's disclosure rules. The owner was asked
  on 21 October 2026, and the item stays open until the first public showing (decision log,
  deferred).
- The reviews of the evening of 21 October 2026 found outputs that, read together, still let a
  reader recover held-back results, and share and site checks that read one line at a time
  (`../fd-core/docs/where_claude_was_wrong.md`). N7 changed those outputs and added four share
  checks; it recorded that the two held-back tests' routes could still be worked out from the
  case register, so the protection was that no output gives their results or UK figures. The
  24 October change narrows that: the tests keep only their id and the case register shows that
  case without its corridors, but their case can still be read from the ids and its published
  reports name its corridors. What the public copies and the demo site hold back is each test's
  result and any UK figure on its route in the case's window: they leave out the research log,
  its shared copy and fd-core's record of review findings, which give them. Anyone can still rerun the radar on the public data: the rule
  limits what this project says, not what the public data hold [Certain, as N7 states].
- The decision log rows on the two tests under the rule (lines 22 and 45) still described them,
  after N7, as not shown at all and as listed with their routes; both were brought into line with
  N7 on 22 October 2026 [Certain].

## Where recorded

Line numbers are as at commit 1be3729.

- `CLAUDE.md` lines 23-24: the requirement.
- `radar/display.py` lines 1-32 (the rule, its levels and why) and 114-120 (`screen_runs`,
  every run).
- `docs/decision_log.md` lines 14, 17, 18, 22, 23, 39, 43 and 45; deferred line 59.
- `backtest/RESEARCH_LOG.md` N1 (lines 210-223), N2 (225-236), N5 (272-304), N6 (306-352) and
  N7 (714-757).
- `README.md` lines 38-41.
- Commits 0d15b29 (the rule), fe90ade (every run, case windows), 15525c3 and 9a01c96 (backtest
  tests), f3c5331 (shared copies), dba4c51 (N7).
- Tests: `tests/test_display.py`, `tests/test_demo_data.py`, `tests/test_demo_run3.py`,
  `tests/test_share.py`.
