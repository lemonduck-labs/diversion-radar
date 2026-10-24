"""Backtest run 2, as pre-registered in backtest/preregistration_run2.md (commit b96c917).

Part A. Run 1's tests, with the onward signal widened to: the annual signal (run 1's rule,
release dates) or the monthly signal (backtest/monthly.py) for the seven corridors with
monthly UN Comtrade data. Everything else is run 1's: UK signal, lead, hit rule, tests,
reference dates, placebos P1 to P3, runs from January 2022 to August 2026.

Part B. Peacetime placebo: run 1's rule moved three years earlier. Baseline 2016-18; radar
runs at the end of each month from January 2019 to December 2021 (36 runs); onward year 2019
or later, counted from its first release date. Compared with the first 36 war-time runs
(January 2022 to December 2024) under run 1's rule, in which 18 of the 81 series were a lead
at least once (known from run 1, and recomputed here as a check).

Writes:
- backtest/data/run2_results.csv   Part A: one row per test, with run 1's result beside it
- backtest/data/run2_series.csv    Part A: every series, first lead under run 1 and run 2
- backtest/data/run2_placebo.csv   Part B: every series, peacetime and war-time leads
and prints a summary. Usage:  python scripts/run_backtest2.py

A rise in exports is a lead, not evidence of a breach.
Contains public sector information licensed under the Open Government Licence v3.0.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest import asof  # noqa: E402
from backtest.monthly import MonthlyOnward  # noqa: E402

DATA, BT = ROOT / "data" / "processed", ROOT / "backtest" / "data"
START, END = 202201, 202608                      # Part A: run 1's runs
PEACE_START, PEACE_END = 201901, 202112          # Part B
WAR_START, WAR_END = 202201, 202412              # Part B comparison
PEACE_BASE, PEACE_MIN_YEAR = (2016, 2017, 2018), 2019
MONTHLY_REPORTERS = {417, 51, 398, 268, 792, 860, 31}   # not the UAE (784) or Tajikistan (762)
RULE = "run 2"
WAR_TIME_FIGURE = 18                              # fixed in the pre-registration


def _run1():
    spec = importlib.util.spec_from_file_location("run_backtest", ROOT / "scripts" / "run_backtest.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_part_a():
    r1 = _run1()
    monthly, ct, release, corridors, codes, plan = r1.load()
    ctm = pd.read_csv(BT / "comtrade_monthly_run2.csv", dtype={"code": str})
    rel_m = pd.read_csv(BT / "comtrade_monthly_release_dates.csv")
    rel_m["first_released"] = pd.to_datetime(rel_m.first_released, format="ISO8601")
    return r1, monthly, ct, release, corridors, codes, plan, ctm, rel_m


def part_a_timeline(monthly, ct, release, ctm, rel_m, cid: int, rep: int, code: str,
                    start: int = START, end: int = END) -> pd.DataFrame:
    """Run 1's timeline with the monthly onward signal added and the lead recomputed."""
    t = asof.timeline(monthly, ct, cid, rep, code, start, end, asof.UK_LAG_MONTHS, release)
    t = t.rename(columns={"onward_signal": "onward_annual", "lead": "lead_run1"})
    if rep in MONTHLY_REPORTERS:
        mo = MonthlyOnward(ctm, rel_m, rep, code)
        sig, info = zip(*(mo.at(p) for p in t.index))
        t["onward_monthly"] = list(sig)
        info = pd.DataFrame(list(info), index=t.index)
        for c in info.columns:
            t[c] = info[c]
    else:
        t["onward_monthly"] = False
    t["onward_signal"] = t.onward_annual | t.onward_monthly
    t["lead"] = t.uk_signal & t.onward_signal
    return t


def part_a():
    r1, monthly, ct, release, corridors, codes, plan, ctm, rel_m = load_part_a()
    names = dict(zip(corridors.hmrc_country_id, corridors.name))
    reporter_of = dict(zip(corridors.hmrc_country_id, corridors.comtrade_code))
    timelines, rows = {}, []
    for cid in corridors.hmrc_country_id:
        for code in codes:
            t = part_a_timeline(monthly, ct, release, ctm, rel_m, cid, reporter_of[cid], code)
            timelines[(RULE, cid, code)] = t
            f1, f2 = r1.first(t.index[t.lead_run1]), r1.first(t.index[t.lead])
            fm = r1.first(t.index[t.onward_monthly])
            rows.append({"country": names[cid], "hmrc_country_id": cid, "code": code,
                         "monthly_data": reporter_of[cid] in MONTHLY_REPORTERS,
                         "first_lead_run1": str(f1) if f1 is not None else "",
                         "first_lead_run2": str(f2) if f2 is not None else "",
                         "months_earlier": (f1 - f2).n if f1 is not None and f2 is not None else None,
                         "first_monthly_onward": str(fm) if fm is not None else "",
                         "runs_as_lead_run1": int(t.lead_run1.sum()), "runs_as_lead_run2": int(t.lead.sum())})
    series = pd.DataFrame(rows)
    results = pd.DataFrame(r1.evaluate(timelines, plan, corridors, codes, RULE))
    run1 = pd.read_csv(BT / "run1_results.csv")
    run1 = run1[run1.rule == "release dates"].set_index("test_id")
    for col in ("outcome", "first_lead_before", "lead_time_months", "lead_at_reference",
                "p1_other_corridors_hit", "p2_other_codes_leading", "p3_all_series_leading"):
        results[f"{col}_run1"] = results.test_id.map(run1[col])
    return series, results


def part_b():
    monthly = pd.read_csv(DATA / "hmrc_monthly_2016_2026.csv", dtype={"code": str})
    ct = pd.read_csv(DATA / "comtrade_annual_2016_2025.csv", dtype={"code": str})
    rel = pd.read_csv(BT / "comtrade_release_dates_2015_2025.csv")
    rel["first_released"] = pd.to_datetime(rel.first_released, format="ISO8601")
    r1 = _run1()
    _, ct1, rel1, corridors, codes, _ = r1.load()
    monthly1 = pd.read_csv(DATA / "hmrc_monthly_phase1.csv", dtype={"code": str})
    names = dict(zip(corridors.hmrc_country_id, corridors.name))
    reporter_of = dict(zip(corridors.hmrc_country_id, corridors.comtrade_code))
    rows = []
    for cid in corridors.hmrc_country_id:
        for code in codes:
            rep = reporter_of[cid]
            p = asof.timeline(monthly, ct, cid, rep, code, PEACE_START, PEACE_END, asof.UK_LAG_MONTHS,
                              rel, PEACE_BASE, PEACE_MIN_YEAR)
            w = asof.timeline(monthly1, ct1, cid, rep, code, WAR_START, WAR_END, asof.UK_LAG_MONTHS, rel1)
            rows.append({"country": names[cid], "hmrc_country_id": cid, "code": code,
                         "peace_lead_runs": int(p.lead.sum()), "peace_watch_runs": int(p.uk_signal.sum()),
                         "peace_onward_runs": int(p.onward_signal.sum()),
                         "peace_first_lead": str(p.index[p.lead][0]) if p.lead.any() else "",
                         "war_lead_runs": int(w.lead.sum()), "war_watch_runs": int(w.uk_signal.sum()),
                         "war_first_lead": str(w.index[w.lead][0]) if w.lead.any() else ""})
    return pd.DataFrame(rows)


def main() -> int:
    series, results = part_a()
    series.to_csv(BT / "run2_series.csv", index=False)
    results.to_csv(BT / "run2_results.csv", index=False)
    placebo = part_b()
    placebo.to_csv(BT / "run2_placebo.csv", index=False)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 80)
    print("=== Part A: run 2 against run 1 ===")
    print(results[["test_id", "country", "codes", "outcome", "outcome_run1", "first_lead_before",
                   "first_lead_before_run1", "lead_time_months", "lead_time_months_run1",
                   "p1_other_corridors_hit", "p1_other_corridors_hit_run1",
                   "p3_all_series_leading", "p3_all_series_leading_run1"]].to_string(index=False))
    n1 = int((series.first_lead_run1 != "").sum())
    n2 = int((series.first_lead_run2 != "").sum())
    print(f"series ever a lead, January 2022 to August 2026: run 1 {n1} of {len(series)}, run 2 {n2}")
    earlier = series[series.months_earlier.fillna(0) > 0]
    print(f"series whose first lead comes earlier under run 2: {len(earlier)}")
    print("\n=== Part B: peacetime placebo ===")
    peace = int((placebo.peace_lead_runs > 0).sum())
    war = int((placebo.war_lead_runs > 0).sum())
    print(f"series a lead at least once: peacetime (36 runs, 2019-21) {peace} of {len(placebo)}; "
          f"war-time (36 runs, 2022-24) {war} (pre-registered figure {WAR_TIME_FIGURE})")
    print("\nA rise in exports is a lead, not evidence of a breach. "
          "Contains public sector information licensed under the Open Government Licence v3.0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
