# 4. As-of reruns: each figure counts only from when it was published

Date: 21 October 2026. Status: Accepted.

## Context

The backtest asks whether the radar would have made a route a lead before the first public
enforcement action "using only data published by then" (`backtest/preregistration.md`). The
first smoke test of the engine (B0) counted HMRC month M from the end of month M and each year
of onward data from July of the following year, with no record of when the data were in fact
released.

A rise in exports is a lead, not evidence of a breach.

## Decision

- HMRC month M counts from the end of month M + 2, since HMRC publishes about six weeks after a
  month ends.
- Each corridor-year of UN Comtrade onward data counts from the date UN Comtrade first released
  it, as its data availability service records it (the primary rule). Counting year Y from July
  of Y + 1 is kept as a sensitivity rule.
- Run 2's monthly onward data count the same way, month by month, from their first release
  dates.
- The 2019-21 baseline years are treated as available at every run.
- Values are today's, after revisions, not the figures as first published; every run states
  this as a limit.

These rules were committed before the runner existed: the pre-registration in commit 3b77d39 at
10:51 on 21 October 2026, `scripts/run_backtest.py` first in commit 0690667 at 10:56.

## Options ruled out

- B0's engine (no publication lag, the July rule only): replaced by the pre-registered engine.
  The July rule survives only as the sensitivity rule, and B0's numbers are not cited as
  evidence (research log B0).
- No other option is recorded as ruled out. A rerun on figures as first published is not
  recorded as considered; the records list today's revised values as a limit instead.

## Consequences

- Where UN Comtrade replaced a dataset, the date recorded is the replacement's, so the test can
  find a signal late, never early [Likely] (`backtest/preregistration.md`).
- Two corridors' 2022 and 2023 monthly release dates look like later replacements, so their
  monthly signals can only come late (`backtest/preregistration_run2.md`).
- Some baseline years show first release dates after the runs that use them. They are treated
  as available, and N6 records that this changes no lead [Certain that N6 says so].
- The README's sentence that the backtest "has no hindsight on when data arrived" was found
  overstated by the fact-check of 21 October 2026 (item 9), because of the replacement dates.
  Since commit dba4c51 the README says the date UN Comtrade records may be the replacement's,
  so a signal can come late but not early [Likely].
- Every result is worded as "rerun on today's figures" (research log N6).

## Where recorded

Line numbers are as at commit 1be3729.

- `backtest/preregistration.md` lines 3-5, 40-54 and 82-92.
- `backtest/preregistration_run2.md` lines 19-23, 27-29, 45-47 and 71-74.
- `backtest/RESEARCH_LOG.md` B0 (lines 35-50), B1 (52-78), N6 (323-337).
- `README.md` lines 31-35.
- `backtest/asof.py` and `backtest/monthly.py`; `tests/test_asof.py`
  (`test_publication_lag_delays_the_uk_signal`, `test_release_dates_replace_the_july_rule`,
  `test_onward_uses_only_published_years`) and `tests/test_backtest2.py`.
- Commits 3b77d39, 0690667, b96c917, 3b8a0d5 and dba4c51.
