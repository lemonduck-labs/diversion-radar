# Backtest run 1: pre-registration

Written 21 October 2026, before `scripts/run_backtest.py` existed or ran. The cases,
pairs, dates and rules below are fixed in `backtest/data/test_plan.csv` and committed
before the run. Any later change gets a new run number and a note of why.

## The question

For closed, published enforcement cases that name a corridor country and goods that map
to the radar's codes: would the radar have made the route a lead before the first public
enforcement action, using only data published by then?

A hit says the radar points at routes that diversion networks were using. It does not
say any UK exporter was involved: none of the four cases names UK goods or a UK
party [Certain, from the case register]. A rise in exports is a lead, not evidence of a
breach, and a backtest hit does not change that.

## Cases and pairs

From the case register (`backtest/data/cases.csv`), the four cases the case researcher
recommended. US-03 is not run: it needs code 8807.30, which the radar does not pull.

| Test | Case | Corridor | Codes | Conduct window | Reference date |
|---|---|---|---|---|---|
| T1 | US-01 | UAE | 8542.31, .32, .33, .39 | 2022-09 to 2023-02 | 2023-10-31 |
| T2 | US-02 | Armenia | 8526.91 | 2022-02 to 2022-07 | 2023-03-02 |
| T2s | US-02 (sensitivity) | Armenia | 8517.62 | as T2 | as T2 |
| T3 | EU-05 | Turkey | 8542.31, 8542.39 | 2022-03 to 2023-05 | 2024-03-01 |
| T3s | EU-05 (sensitivity) | Turkey | 8532.24, 8548 | as T3 | as T3 |
| T4a | EU-01 | Kazakhstan | 8517.62 | from 2022-03 | 2024-10-01 |
| T4b, T4c | [held back] | [held back] | [held back] | [held back] | [held back] |

The reference date is the first public action found (charge, complaint or arrest), not the
conclusion. The T1 date was confirmed from the USAO press release of 31 October 2023. The
T3 and T4 dates come from secondary sources and are known only to the month. For EU-01,
earlier public actions (pre-trial detention) are not dated in the sources read, so the true
reference date may be earlier and any lead time is an upper bound [Likely].

## How the radar is rerun

`backtest/asof.py`, run at the end of each month from January 2022 to the last month end
before the reference date:

- **UK signal:** trailing 12 months of UK exports at least 2x the 2019-21 annual average
  and at least £20,000 above it, for 3 months running. HMRC month M counts from the end
  of month M + 2 (HMRC publishes about six weeks after month end: June 2023 data on
  11 August 2023, August 2020 data on 14 October 2020).
- **Onward signal:** the corridor's exports of the code to Russia in the latest year
  available, 2022 or later, at least 2x its 2019-21 average and at least USD 100,000.
- **Availability of onward data, primary rule:** each corridor-year counts from the date UN
  Comtrade first released it (its data availability service, pulled 21 October 2026 and
  saved in `backtest/data/comtrade_release_dates.csv`). Where a dataset was replaced, the
  date is the replacement's, so the test can only find a signal late, never early [Likely].
- **Availability, sensitivity rule:** year Y counts from July of Y + 1.
- **Lead:** both signals at the same run. Watch: the UK signal alone.

## Hit rule

- **Hit:** at least one of the test's code and corridor series is a lead at a run before
  the reference date.
- **Watch only:** a UK signal but no lead before the reference date.
- **Miss:** neither.
- Also reported, never counted as hits: the first lead at any run up to August 2026 (a late
  hit), whether the series was a lead during the conduct window, and the lead time in
  months from the first lead to the reference date.

## Placebos

Each test is repeated with the same reference date on pairs with no case behind them:

- **P1, other corridors:** the same codes on each of the corridors not in the test.
- **P2, other codes:** the same corridor with each of the nine codes not in the test.
- **P3, base rate:** the share of all 81 corridor and code series that were leads before
  the reference date.

A hit is read as informative only if the case series fire more often than the placebo
series on the same date. With four cases no statistical test is run, and nothing is
generalised [Certain].

Not run in this round: a peacetime placebo (the same rule in pre-2022 years). The data
start in 2019, so it needs a 2016 to 2018 pull first.

## What was already known before this was written

Disclosed so the reader can judge the selection risk:

1. The phase 0 and phase 1 leads (including Kazakhstan, Armenia and UAE routes) were known
   before the cases were picked, and the case researcher saw them.
2. An earlier version of the as-of engine (no publication lag, July rule only) was smoke
   tested on several of the routes here before this was written [held back: which routes, and the
   results]. T2s, T4a and one held-back test use those series.
3. Values are today's, after revisions, not the figures published at the time [Certain].

Contains public sector information licensed under the Open Government Licence v3.0.
