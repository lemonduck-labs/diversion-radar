"""S2. Code shift within a heading.

Pre-registered in radar/signals/RESEARCH.md (S0, commit cd74780). For corridor c, a heading h
with two or more list codes (from the CN8 ranges in config/codes.csv), focal code a and
siblings S (the other list codes in h):

- Fall: a's baseline annual average is at least GBP 20,000 and its 12-month total is at most
  half of it.
- Siblings' rise: the siblings' 12-month total is at least 2x their summed baseline average
  and at least GBP 20,000 above it.
- Offset: the siblings' excess is at least a quarter of a's shortfall.
- The signal is on at run p when all three held at 3 published windows running. The flag
  belongs to (c, a), and may be named only at runs where the heading's total to c passes the
  display rule.

Only codes on the list can be tested: a shift to a code outside it needs new pulls [Certain].

A rise in exports is a lead, not evidence of a breach.
Contains public sector information licensed under the Open Government Licence v3.0.
"""
from __future__ import annotations

import pandas as pd

from radar.signals import common

FALL, RISE, OFFSET = 0.5, 2.0, 0.25
MIN_FOCAL_BASE, MIN_SIBLING_EXCESS = 20_000, 20_000


def shift(panel: common.Panel, country_id: int, focal: str, siblings: list[str],
          base_years: tuple) -> pd.DataFrame:
    """The three tests for one corridor and focal code, dated by data month."""
    n = len(base_years)
    va = panel.series("value_gbp", country_id, focal)
    vs = pd.Series(0.0, index=panel.index)
    for s in siblings:
        vs = vs + panel.series("value_gbp", country_id, s)
    base_a = common.base_sum(va, base_years) / n
    base_s = common.base_sum(vs, base_years) / n
    ta, ts = common.roll(va), common.roll(vs)
    fall = (ta <= FALL * base_a) & (base_a >= MIN_FOCAL_BASE)
    rise = (ts >= RISE * base_s) & (ts - base_s >= MIN_SIBLING_EXCESS)
    offset = (ts - base_s) >= OFFSET * (base_a - ta)
    rule = fall & rise & offset
    return pd.DataFrame({"focal_12m": ta, "siblings_12m": ts, "focal_base": base_a,
                         "siblings_base": base_s, "fall": fall, "rise": rise, "offset": offset,
                         "rule": rule, "run": common.persist(rule),
                         "heading_shown": common.display_window(va + vs)})


def timeline(panel: common.Panel, country_id: int, focal: str, siblings: list[str],
             base_years: tuple, run_index: pd.PeriodIndex, lag: int = common.LAG) -> pd.DataFrame:
    x = shift(panel, country_id, focal, siblings, base_years)
    out = pd.DataFrame(index=run_index)
    for col in ("fall", "rise", "offset", "rule"):
        out[col] = common.at_runs(x[col], run_index, lag)
    out["s2"] = common.at_runs(x.run, run_index, lag)
    out["heading_shown"] = common.at_runs(x.heading_shown, run_index, lag)
    out["focal_base"] = x.focal_base.iloc[0]
    out["siblings_base"] = x.siblings_base.iloc[0]
    return out
