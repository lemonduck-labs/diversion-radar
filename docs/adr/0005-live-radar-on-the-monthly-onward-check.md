# 5. The live radar on run 2's rule: an annual or a monthly onward check

Date: 21 October 2026. Status: Accepted (a default, open to the owner).

## Context

Run 1 found the annual onward check to be the bottleneck: no lead could appear before a
corridor's 2022 data were released (research log B1.1). Run 2 was pre-registered to test a
monthly onward check and to measure what it costs in leads elsewhere, before any monthly values
were pulled (commit b96c917). The live radar's first October 2026 run used run 1's rule (N2,
commit 0d15b29).

A rise in exports is a lead, not evidence of a breach.

## Decision

- The live radar uses run 2's onward rule: the onward signal is on when either the annual check
  (run 1's) or the monthly check passes.
- The monthly check takes the 12 months ending at the latest month released, at least twice the
  average reported 2019-21 month times 12 and at least USD 100,000, for corridors with monthly
  UN Comtrade data after 2019.
- Run 3 kept the rule unchanged when it added nine corridors; 16 of the 18 corridors get the
  monthly check.
- Run 4 freezes the rule, as run in run 3, for a prediction register scored on HMRC's November
  and December 2026 releases (R4).

## Options ruled out

- Run 1's annual check alone, the live rule in N2: replaced, since run 2 supports the monthly
  check, with all four cases a lead before the first public action against three (decision log
  line 16).
- Adding any of three further public signals (price per kilogram, code shift within a heading,
  displacement from Russia) to the live rule: not done. The pre-registered tests found price per
  kilogram a negative result, and code shift and displacement go to a new pre-registered run
  first (`radar/signals/RESEARCH.md` S0.1; decision log, deferred line 66).

## Consequences

- Over the 81 original series and the 56 monthly runs from January 2022 to August 2026, series
  ever a lead went from 19 to 20 and lead runs from 257 to 300 (B2.1) [Certain].
- US-02's gain was foreseen in run 1's report, so it confirms the mechanism rather than adding
  fresh evidence (B2.1, problems).
- Two corridors' monthly release dates look like replacements, so their signals come late
  (B2, B2.1).
- Four cases is an illustration, not a validation (B2.1).

## Where recorded

Line numbers are as at commit 1be3729.

- `docs/decision_log.md` line 16; deferred line 66.
- `backtest/preregistration_run2.md` (all of it).
- `backtest/RESEARCH_LOG.md` B1.1 (lines 107-110), B2.1 (150-208), N2 (225-236), N3 (238-247),
  R3 (384-399) and R4 (655-712).
- `radar/signals/RESEARCH.md` lines 217-284.
- `backtest/monthly.py`, `scripts/run_live.py --rule`, `scripts/run_live_run3.py`.
- Commits b96c917, 40c10a8, 5447f08 and 06f25ca.
