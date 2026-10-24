"""Lead rules for phase 1. Every threshold sits at the top of this module, and the
leads table shows the per-year values behind each test, so an analyst can check
any flag by hand in a couple of minutes.

A series is one goods code to one corridor country. Values are nominal: pounds
on the UK side (HMRC), US dollars on the onward side (UN Comtrade). Baseline and
comparison windows are as in docs/adr/0002: 2019-21 against 2023-25, with 2022
left out of both.

UK rise, averaged (the phase 0 rule): the 2023-25 average is at least
MIN_UK_RATIO times the 2019-21 average and at least MIN_UK_EXCESS_GBP above it.

UK rise, persistent (new in phase 1): at least MIN_PERSIST_YEARS of the post
years 2023, 2024 and 2025 each meet the same test on their own, against the same
2019-21 average. One large year can lift a three-year average over the line; this
asks the rise to hold.

In phase 1 a UK rise counts only when both hold. The onward rise is unchanged
from phase 0. A lead needs a UK rise and an onward rise; a mirror gap
(radar/mirror.py) is shown beside it but does not make or break a lead.

A rise in exports is a lead, not evidence of a breach.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from . import baseline

BASELINE_YEARS = baseline.BASELINE_YEARS  # 2019, 2020, 2021
POST_YEARS = baseline.POST_YEARS          # 2023, 2024, 2025

MIN_UK_RATIO = 2.0           # UK exports at least double the 2019-21 average
MIN_UK_EXCESS_GBP = 20_000   # and at least GBP 20k a year above it
MIN_PERSIST_YEARS = 2        # persistence: post years that must each pass the test alone

MIN_ONWARD_RATIO = 2.0       # corridor exports of the code to Russia at least double
MIN_ONWARD_USD = 100_000     # and average at least USD 100k a year after 2022
RUSSIA = 643                 # Comtrade partner code for the Russian Federation


def meets_rise(value, base, min_ratio: float = MIN_UK_RATIO,
               min_excess: float = MIN_UK_EXCESS_GBP):
    """True where value is at least min_ratio times base and at least min_excess
    above it. Works on numbers or on aligned pandas objects. NaN never passes."""
    return (value >= min_ratio * base) & (value - base >= min_excess)


def uk_rise(w: pd.DataFrame, baseline_years=BASELINE_YEARS, post_years=POST_YEARS,
            min_ratio: float = MIN_UK_RATIO, min_excess: float = MIN_UK_EXCESS_GBP,
            min_years: int = MIN_PERSIST_YEARS) -> pd.DataFrame:
    """Both UK rise rules, side by side.

    w: one row per series, one column per year (GBP). Years with no HMRC record
    must already be zero; a row of NaN (no data for the country) fails every test.

    Returns, per series: uk_rise_avg (the averaged rule), uk_years_met (the post
    years that pass on their own, such as "2023,2025"), uk_n_years_met,
    uk_rise_persistent (at least min_years of them) and uk_rise (both rules).
    """
    base = w[list(baseline_years)].mean(axis=1)
    post = w[list(post_years)].mean(axis=1)
    met = pd.DataFrame({y: meets_rise(w[y], base, min_ratio, min_excess) for y in post_years},
                       index=w.index)
    out = pd.DataFrame(index=w.index)
    out["uk_rise_avg"] = meets_rise(post, base, min_ratio, min_excess).astype(bool)
    out["uk_years_met"] = [",".join(str(y) for y, ok in zip(post_years, row) if ok)
                           for row in met.itertuples(index=False)]
    out["uk_n_years_met"] = met.sum(axis=1).astype(int)
    out["uk_rise_persistent"] = out["uk_n_years_met"] >= min_years
    out["uk_rise"] = out["uk_rise_avg"] & out["uk_rise_persistent"]
    return out


def onward(ct: pd.DataFrame, reporters: Iterable[int], codes: Iterable[str],
           baseline_years=BASELINE_YEARS, post_years=POST_YEARS,
           min_ratio: float = MIN_ONWARD_RATIO, min_usd: float = MIN_ONWARD_USD,
           partner: int = RUSSIA) -> pd.DataFrame:
    """Each corridor's own exports of each code to Russia (Comtrade flow X,
    partner 643): its 2019-21 average against its post-2022 average.

    A year counts as reported when the corridor has any export record to Russia
    for any of the codes that year; within a reported year, a code with no record
    counts as zero. Years not reported are left out of both averages.

    onward_data says whether the test could be run: "ok", "no data" (no records
    at all), "no baseline years" or "no post years". Without baseline years there
    is no ratio and no onward rise. (Phase 0 gave such a series an infinite ratio;
    none of the phase 0 corridors was affected, because all five reported baseline
    years.)

    Returns one row per reporter and code, indexed by (reporter, code).
    """
    codes = list(codes)
    x = ct[(ct["partner"] == partner) & (ct["flow"] == "X")]
    values = x.groupby(["reporter", "code", "year"])["value_usd"].sum()
    reported = {int(r): set(int(y) for y in ys) for r, ys in x.groupby("reporter")["year"]}
    rows = []
    for rep in reporters:
        years = reported.get(int(rep), set())
        base_years = [y for y in baseline_years if y in years]
        post_yrs = [y for y in post_years if y in years]
        if not years:
            status = "no data"
        elif not base_years:
            status = "no baseline years"
        elif not post_yrs:
            status = "no post years"
        else:
            status = "ok"
        for code in codes:
            base = (np.mean([values.get((rep, code, y), 0.0) for y in base_years])
                    if base_years else np.nan)
            post = (np.mean([values.get((rep, code, y), 0.0) for y in post_yrs])
                    if post_yrs else np.nan)
            if status != "ok":
                ratio = np.nan
            elif base > 0:
                ratio = post / base
            else:
                ratio = np.inf if post > 0 else np.nan
            rows.append({
                "reporter": int(rep), "code": code, "onward_data": status,
                "onward_base_years": ",".join(map(str, base_years)),
                "onward_post_years": ",".join(map(str, post_yrs)),
                "onward_base_usd": base, "onward_post_usd": post, "onward_ratio": ratio,
                "onward_rise": bool(status == "ok" and ratio >= min_ratio and post >= min_usd),
            })
    cols = ["reporter", "code", "onward_data", "onward_base_years", "onward_post_years",
            "onward_base_usd", "onward_post_usd", "onward_ratio", "onward_rise"]
    return pd.DataFrame(rows, columns=cols).set_index(["reporter", "code"])
