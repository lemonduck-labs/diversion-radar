"""The radar as it would have stood on a past date, with no hindsight on timing.

The radar is treated as run at the end of each month A (YYYYMM), using only data
published by then:

- UK side: HMRC publishes month M about six weeks after it ends (June 2023 data came
  out on 11 August 2023, August 2020 data on 14 October 2020). So at the end of month
  A the latest month available is A - UK_LAG_MONTHS, with UK_LAG_MONTHS = 2.
- Onward side: a corridor's annual UN Comtrade data for year Y count from the date
  UN Comtrade first released them (its data availability service, saved in
  backtest/data/comtrade_release_dates.csv). Where a dataset was later replaced,
  the date shown is the replacement's, so it can only be later than the true first
  release; the test errs towards finding the signal late, never early [Likely].
  Without the release table, year Y counts from July of Y + 1 (the fallback rule).

Signals:

- UK signal: the trailing 12 months of UK exports to the corridor, ending at the
  latest published month, against the 2019-21 annual average. It counts when the
  trailing sum is at least 2x the baseline and at least GBP 20,000 above it, and has
  done so for 3 published months running. The run of three does not screen out one
  large consignment: a trailing 12-month sum stays high for a year after it (see
  backtest/RESEARCH_LOG.md, note N1). The live radar's display rule
  (radar/display.py) asks for exports in several separate months before a flagged
  series is shown.
- Onward signal: the corridor's own reported exports of the code to Russia in the
  latest year available by then (2022 or later). It counts when that year is at
  least 2x the corridor's 2019-21 average and at least USD 100,000.
- A lead needs both; a UK signal alone is a watch item.

What it cannot remove: the values are today's, after revisions. The figures the
radar would have seen at the time may differ [Certain].

A rise in exports is a lead, not evidence of a breach.
"""

from __future__ import annotations

import pandas as pd

UK_RATIO, UK_MIN_EXCESS, RUN_MONTHS = 2.0, 20_000, 3
ONWARD_RATIO, ONWARD_MIN_USD = 2.0, 100_000
UK_LAG_MONTHS = 2   # HMRC month M is published about six weeks after M ends
PUBLISH_MONTH = 7   # fallback: annual Comtrade data for year Y available from July of Y+1
RUSSIA = 643


def month_index(start: int = 201901, end: int = 202608) -> pd.PeriodIndex:
    s, e = f"{start // 100}-{start % 100:02d}", f"{end // 100}-{end % 100:02d}"
    return pd.period_range(s, e, freq="M")


def to_period(yyyymm: int) -> pd.Period:
    return pd.Period(f"{yyyymm // 100}-{yyyymm % 100:02d}", freq="M")


BASE_YEARS = (2019, 2020, 2021)
MIN_ONWARD_YEAR = 2022


def uk_series(monthly: pd.DataFrame, country_id: int, code: str, end: int = 202608,
              lag: int = UK_LAG_MONTHS, base_years: tuple = BASE_YEARS) -> pd.DataFrame:
    """Monthly values, trailing 12-month sums and the UK rule for one series.

    uk_rule and uk_run are dated by the data month. uk_signal is dated by the month
    the radar runs: the run at the end of month A sees data months up to A - lag."""
    s = monthly[(monthly.country_id == country_id) & (monthly.code == code)]
    idx = month_index(min(base_years) * 100 + 1, end)
    v = pd.Series(0.0, index=idx)
    for m, val in zip(s.month, s.value_gbp):
        p = to_period(int(m))
        if p in v.index:
            v[p] += val
    baseline = v[f"{min(base_years)}-01":f"{max(base_years)}-12"].sum() / len(base_years)
    trailing = v.rolling(12).sum()
    rule = (trailing >= UK_RATIO * baseline) & (trailing - baseline >= UK_MIN_EXCESS)
    run = rule.astype(int).rolling(RUN_MONTHS).sum() == RUN_MONTHS
    return pd.DataFrame({"value": v, "trailing12": trailing, "baseline": baseline,
                         "uk_rule": rule, "uk_run": run,
                         "trailing12_published": trailing.shift(lag),
                         "uk_signal": run.shift(lag, fill_value=False).astype(bool)})


def onward_available_year(asof: pd.Period, reporter: int | None = None,
                          release: pd.DataFrame | None = None) -> int | None:
    """Latest year of the corridor's annual data available at the end of month asof."""
    if release is None:
        return asof.year - 1 if asof.month >= PUBLISH_MONTH else asof.year - 2
    r = release[(release.reporter == reporter) & (release.first_released <= asof.end_time)]
    return int(r.year.max()) if len(r) else None


def onward_signal(ct: pd.DataFrame, reporter: int, code: str, asof: pd.Period,
                  release: pd.DataFrame | None = None, base_years: tuple = BASE_YEARS,
                  min_year: int = MIN_ONWARD_YEAR) -> tuple[bool, dict]:
    x = ct[(ct.reporter == reporter) & (ct.partner == RUSSIA) & (ct.flow == "X") & (ct.code == code)]
    by_year = x.groupby("year").value_usd.sum()
    reported_years = set(ct[(ct.reporter == reporter) & (ct.partner == RUSSIA) & (ct.flow == "X")].year)
    base_years = [y for y in base_years if y in reported_years]
    if release is None:
        # Fallback rule: the latest year the corridor has reported, 2022 or later (min_year),
        # whose July of the following year has passed.
        due = [y for y in reported_years
               if y >= min_year and asof >= pd.Period(f"{y + 1}-{PUBLISH_MONTH:02d}", freq="M")]
        year = max(due) if due else None
    else:
        year = onward_available_year(asof, reporter, release)
    info = {"onward_year": year, "onward_value": None, "onward_base": None}
    if year is None or year < min_year or year not in reported_years or not base_years:
        return False, info
    base = sum(by_year.get(y, 0.0) for y in base_years) / len(base_years)
    val = float(by_year.get(year, 0.0))
    info.update({"onward_value": val, "onward_base": base})
    ok = bool(val >= ONWARD_MIN_USD and (val >= ONWARD_RATIO * base if base > 0 else True))
    return ok, info


def timeline(monthly: pd.DataFrame, ct: pd.DataFrame, country_id: int, reporter: int, code: str,
             start: int = 202201, end: int = 202608, lag: int = UK_LAG_MONTHS,
             release: pd.DataFrame | None = None, base_years: tuple = BASE_YEARS,
             min_year: int = MIN_ONWARD_YEAR) -> pd.DataFrame:
    """One row per radar run (month end) from start to end: the UK signal, the onward
    year and signal, and whether the series was a lead."""
    s = uk_series(monthly, country_id, code, end, lag, base_years)
    rows = []
    for p in month_index(start, end):
        ok, info = onward_signal(ct, reporter, code, p, release, base_years, min_year)
        uk = bool(s.loc[p, "uk_signal"])
        rows.append({"month": p, "uk_signal": uk, "trailing12_published": s.loc[p, "trailing12_published"],
                     "baseline": s.loc[p, "baseline"], "onward_signal": ok, **info,
                     "lead": uk and ok})
    return pd.DataFrame(rows).set_index("month")


def first_signal(monthly: pd.DataFrame, ct: pd.DataFrame, country_id: int, reporter: int,
                 code: str, start: int = 202201, end: int = 202608, lag: int = UK_LAG_MONTHS,
                 release: pd.DataFrame | None = None) -> dict:
    """First radar run from start to end when the series was a watch item (UK signal)
    and a lead (UK and onward signals together)."""
    t = timeline(monthly, ct, country_id, reporter, code, start, end, lag, release)
    watch = t.index[t.uk_signal]
    lead = t.index[t.lead]
    return {"first_watch": str(watch[0]) if len(watch) else None,
            "first_lead": str(lead[0]) if len(lead) else None}


def months_between(a: str | None, b: pd.Period) -> int | None:
    if a is None:
        return None
    pa = pd.Period(a, freq="M")
    return (b.year - pa.year) * 12 + (b.month - pa.month)
