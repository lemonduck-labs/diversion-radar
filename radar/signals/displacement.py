"""S3. Displacement of UK exports from Russia to a corridor.

Pre-registered in radar/signals/RESEARCH.md (S0, commit cd74780). For corridor c and code k,
with R the UK's exports of k to Russia, all over the run's own 12-month window W:

- Russia fall: R's 2019-21 annual average is at least GBP 100,000 and R over W is at most half
  of it.
- Corridor rise: the backtest's UK signal for (c, k) at the run (backtest/asof.py, uk_series).
- Magnitude: the corridor's excess over its 2019-21 average is at least FACTOR times the
  shortfall in UK exports to Russia (0.10; 0.05 and 0.25 as sensitivity).
- The signal is on at run p when all three hold at p.

The peacetime placebo cannot be run: it needs a 2016-18 baseline for Russia, and the repo has
UK exports to Russia from 2019 only [Certain].

A rise in exports is a lead, not evidence of a breach.
Contains public sector information licensed under the Open Government Licence v3.0.
"""
from __future__ import annotations

import pandas as pd

from backtest import asof
from radar.signals import common

R_MIN_BASE, R_FALL = 100_000, 0.5
FACTOR = 0.10
SENSITIVITY = (0.05, 0.25)


def timeline(panel: common.Panel, monthly: pd.DataFrame, country_id: int, code: str,
             run_index: pd.PeriodIndex, factors=(FACTOR,) + SENSITIVITY,
             base_years: tuple = common.WAR_BASE, lag: int = common.LAG) -> pd.DataFrame:
    n = len(base_years)
    r = panel.series("value_gbp", common.RUSSIA_ID, code)
    r_base = common.base_sum(r, base_years) / n
    r_w = common.roll(r)
    fall = (r_w <= R_FALL * r_base) & (r_base >= R_MIN_BASE)

    v = panel.series("value_gbp", country_id, code)
    base_ck = common.base_sum(v, base_years) / n
    excess = common.roll(v) - base_ck
    shortfall = r_base - r_w

    uk = asof.uk_series(monthly, country_id, code, panel.end, lag, base_years)
    uk_signal = uk.uk_signal.reindex(run_index).fillna(False).astype(bool)

    out = pd.DataFrame(index=run_index)
    out["russia_fall"] = common.at_runs(fall, run_index, lag)
    out["uk_signal"] = uk_signal
    out["excess"] = common.at_runs(excess, run_index, lag)
    out["russia_shortfall"] = common.at_runs(shortfall, run_index, lag)
    out["russia_base"] = r_base
    for f in factors:
        mag = common.at_runs(excess >= f * shortfall, run_index, lag)
        out[f"s3_{f:.2f}"] = out.russia_fall & out.uk_signal & mag
    out["shown"] = common.at_runs(common.display_window(v), run_index, lag)
    return out
