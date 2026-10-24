"""R3.4: does the onward baseline's year rule change any result?

backtest/asof.py counts a 2019-21 year in a corridor's annual onward baseline only when the
corridor's UN Comtrade figures hold exports of one of the nine codes to Russia in that year
(onward_signal, reported_years). The pre-registrations (B1, B2, R3) say "its 2019-21 average"
and do not state the rule. This script reruns, in memory only, run 3's live table and backtest
run 2 (parts A and B, which carry run 1's columns) with every base year counted and a year with
no records counted as zero, and compares them with the engine's own results. It writes nothing.

Usage:  python scripts/check_baseline_years.py      (about five minutes)

A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest import asof  # noqa: E402

ENGINE = asof.onward_signal


def every_base_year(ct, reporter, code, p, release=None, base_years=asof.BASE_YEARS,
                    min_year=asof.MIN_ONWARD_YEAR):
    """asof.onward_signal with every base year counted, a year with no records as zero."""
    x = ct[(ct.reporter == reporter) & (ct.partner == asof.RUSSIA) & (ct.flow == "X") & (ct.code == code)]
    by_year = x.groupby("year").value_usd.sum()
    reported_years = set(ct[(ct.reporter == reporter) & (ct.partner == asof.RUSSIA) & (ct.flow == "X")].year)
    if release is None:
        due = [y for y in reported_years
               if y >= min_year and p >= pd.Period(f"{y + 1}-{asof.PUBLISH_MONTH:02d}", freq="M")]
        year = max(due) if due else None
    else:
        year = asof.onward_available_year(p, reporter, release)
    info = {"onward_year": year, "onward_value": None, "onward_base": None}
    if year is None or year < min_year or year not in reported_years:
        return False, info
    base = sum(by_year.get(y, 0.0) for y in base_years) / len(base_years)
    val = float(by_year.get(year, 0.0))
    info.update({"onward_value": val, "onward_base": base})
    ok = bool(val >= asof.ONWARD_MIN_USD and (val >= asof.ONWARD_RATIO * base if base > 0 else True))
    return ok, info


def _module(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _with(fn, job):
    asof.onward_signal = fn
    try:
        return job()
    finally:
        asof.onward_signal = ENGINE


def live_run3() -> pd.DataFrame:
    live, rb2, r3 = _module("run_live"), _module("run_backtest2"), _module("run_live_run3")
    monthly_all, _ = r3.monthly_reporters(rb2.MONTHLY_REPORTERS)
    return live.build(r3.RUN, "run2", inputs=r3.INPUTS, monthly_reporters=monthly_all, routes=r3.case_routes())


def backtest_run2():
    rb2 = _module("run_backtest2")
    series, results = rb2.part_a()
    return {"series": series, "results": results, "placebo": rb2.part_b()}


def main() -> int:
    a, b = _with(ENGINE, live_run3), _with(every_base_year, live_run3)
    cols = ["status", "display", "runs_as_lead", "runs_shown", "runs_shown_as_lead", "first_lead_shown",
            "lead_under_run1_rule", "onward_annual", "onward_monthly", "onward_signal"]
    m = a.merge(b, on=["country", "code"], suffixes=("_engine", "_every"))
    changed = m[[any(str(r[c + "_engine"]) != str(r[c + "_every"]) for c in cols) for _, r in m.iterrows()]]
    print(f"run 3 live table: {len(a)} series; {len(changed)} with a status, display verdict or run count changed")
    base = m[m.onward_base_usd_engine.fillna(-1) != m.onward_base_usd_every.fillna(-1)]
    print(f"series whose annual baseline at the October 2026 run differs: {len(base)}")
    for r in base.itertuples():
        print(f"  {r.country} {r.code}: USD {r.onward_base_usd_engine:,.2f} (engine) against "
              f"USD {r.onward_base_usd_every:,.2f} (every year)")
    x, y = _with(ENGINE, backtest_run2), _with(every_base_year, backtest_run2)
    same = True
    for name in x:
        ok = x[name].reset_index(drop=True).astype(str).equals(y[name].reset_index(drop=True).astype(str))
        same &= ok
        print(f"backtest run 2, {name}: {len(x[name])} rows, {'identical' if ok else 'DIFFERENT'}")
    print("A rise in exports is a lead, not evidence of a breach.")
    return 0 if same and not len(changed) else 1


if __name__ == "__main__":
    sys.exit(main())
