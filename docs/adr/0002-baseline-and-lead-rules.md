# 2. Baseline and lead rules for phase 0

Date: 21 October 2026. Status: accepted for the spike. Phase 1 (commit 9529aa8, 21 October 2026)
kept these windows and thresholds in `radar/rules.py` and added a persistence test: a UK rise
counts only when at least two of 2023, 2024 and 2025 also pass on their own. This record was not
updated then. The live radar no longer uses these rules: since commit 0d15b29 it runs the
backtest's as-of rule at each month end (a trailing 12-month UK signal), with run 2's onward
check since 40c10a8 (ADR 0005). The phase 0
code also held an onward rise to an average of at least USD 100,000 a year after 2022
(`scripts/analyse_spike.py` in commit 8a05b13), which the list below leaves out [Certain, from
the code].

## Decision

- Baseline: the average of calendar years 2019, 2020 and 2021, before the invasion
  in February 2022 and the export bans that followed. 2020 stays in because removing
  it changes few results; the report shows where it matters.
- Comparison window: the average of 2023, 2024 and 2025. 2022 is a transition year
  and is left out of both windows. 2026 is shown year to date (January to August)
  against the same months of the baseline years.
- A series is one goods code to one country. Years with no HMRC record count as zero,
  because HMRC returns no row when nothing was recorded.
- A UK rise: exports at least double the baseline and at least £20,000 a year above it.
- An onward rise: the corridor country's reported exports of the same code to Russia
  at least double their own 2019-21 average.
- A lead needs both. Everything else stays visible in the table, unflagged.

## Why simple rules

An analyst has to be able to check every flag by hand in a couple of minutes. Model
scores can come later, once there are labelled decisions to test them against.

## Known weaknesses

- Values are nominal; inflation alone lifts 2023-25 above 2019-21. Net mass is shown
  as a rough volume check.
- Broad codes such as 8517.62 cover a great deal of ordinary trade, so large hubs
  (the UAE) can rise for normal reasons.
- The onward check depends on what corridor countries report to Comtrade.
