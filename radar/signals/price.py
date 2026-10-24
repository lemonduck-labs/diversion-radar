"""S1. Price per kilogram of UK exports to a corridor, against the other eight corridors.

Pre-registered in radar/signals/RESEARCH.md (S0, commit cd74780). For corridor c and code k,
over priced rows only (value above zero and net mass above zero):

- UV = value / net mass over the 12-month window W; B = the same for the other eight
  corridors pooled; RUV = UV / B.
- D = RUV(W) / RUV(baseline years).
- The rule holds at a window when D >= 2 or D <= 0.5, the series passes the display rule over
  W (at least GBP 250,000, exports in at least 6 months) and its priced value over the three
  baseline years is at least GBP 60,000.
- The signal is on at run p when the rule held at 3 published windows running, in the same
  direction.

There is no total for all destinations in the repo, so the benchmark is made of the other
transit routes: a shift common to all corridors does not show [Certain].

A rise in exports is a lead, not evidence of a breach.
Contains public sector information licensed under the Open Government Licence v3.0.
"""
from __future__ import annotations

import pandas as pd

from backtest import asof
from radar.signals import common

HIGH, LOW = 2.0, 0.5
MIN_BASE_PRICED_GBP = 60_000


def drift(panel: common.Panel, corridor_ids, country_id: int, code: str,
          base_years: tuple, base_until: int | None = None) -> pd.DataFrame:
    """D and the rule for one series, dated by data month (the window's last month).

    base_until (YYYYMM) drops later baseline months; it is used only to check the first run of
    each period, which sees the baseline years before their last month is published."""
    others = [c for c in corridor_ids if int(c) != int(country_id)]
    pv = panel.series("priced_value", country_id, code)
    pm = panel.series("priced_mass", country_id, code)
    pv_o = panel.total("priced_value", others, code)
    pm_o = panel.total("priced_mass", others, code)
    uv = common.ratio(common.roll(pv), common.roll(pm))
    bench = common.ratio(common.roll(pv_o), common.roll(pm_o))
    ruv = common.ratio(uv, bench)

    def bs(s: pd.Series) -> float:
        if base_until is None:
            return common.base_sum(s, base_years)
        b = s[common.base_slice(base_years)]
        return float(b[b.index <= asof.to_period(base_until)].sum())

    uv_b = bs(pv) / bs(pm) if bs(pm) > 0 else float("nan")
    bench_b = bs(pv_o) / bs(pm_o) if bs(pm_o) > 0 else float("nan")
    ruv_b = uv_b / bench_b if bench_b > 0 else float("nan")
    d = ruv / ruv_b if ruv_b > 0 else pd.Series(float("nan"), index=panel.index)

    value = panel.series("value_gbp", country_id, code)
    shown = common.display_window(value)
    base_ok = bs(pv) >= MIN_BASE_PRICED_GBP
    up = shown & base_ok & (d >= HIGH)
    down = shown & base_ok & (d <= LOW)
    return pd.DataFrame({"uv": uv, "bench": bench, "ruv": ruv, "ruv_base": ruv_b, "d": d,
                         "shown": shown, "base_priced_gbp": bs(pv), "rule_up": up, "rule_down": down,
                         "run_up": common.persist(up), "run_down": common.persist(down)})


def timeline(panel: common.Panel, corridor_ids, country_id: int, code: str, base_years: tuple,
             run_index: pd.PeriodIndex, lag: int = common.LAG,
             base_until: int | None = None) -> pd.DataFrame:
    """One row per run: D on the run's own window, the direction of a run of three, the signal
    and whether the run's window passes the display rule."""
    x = drift(panel, corridor_ids, country_id, code, base_years, base_until)
    up = common.at_runs(x.run_up, run_index, lag)
    down = common.at_runs(x.run_down, run_index, lag)
    out = pd.DataFrame(index=run_index)
    out["d"] = common.at_runs(x.d, run_index, lag)
    out["s1_up"], out["s1_down"] = up, down
    out["s1"] = up | down
    out["s1_direction"] = ["up" if u else ("down" if dn else "") for u, dn in zip(up, down)]
    out["shown"] = common.at_runs(x.shown, run_index, lag)
    out["base_priced_gbp"] = x.base_priced_gbp.iloc[0]
    return out
