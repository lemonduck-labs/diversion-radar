"""Backtest run 1: the radar as it stood before each case's first public action.

Follows backtest/preregistration.md and the pre-registered backtest/data/test_plan.csv.
Writes:
- backtest/data/run1_series.csv   every corridor and code series under each availability
                                  rule: first watch and first lead, with the values behind them
- backtest/data/run1_results.csv  one row per test and rule: outcome, lead time, conduct
                                  window, placebos
and prints a summary. Usage:  python scripts/run_backtest.py

A rise in exports is a lead, not evidence of a breach.
Contains public sector information licensed under the Open Government Licence v3.0.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest import asof  # noqa: E402

DATA, BT = ROOT / "data" / "processed", ROOT / "backtest" / "data"
START, END = 202201, 202608
RULES = ("release dates", "July rule")


def load():
    monthly = pd.read_csv(DATA / "hmrc_monthly_phase1.csv", dtype={"code": str})
    ct = pd.read_csv(DATA / "comtrade_annual_phase1.csv", dtype={"code": str})
    release = pd.read_csv(BT / "comtrade_release_dates.csv")
    release["first_released"] = pd.to_datetime(release.first_released, format="ISO8601")
    countries = pd.read_csv(ROOT / "config" / "countries.csv")
    corridors = countries[countries.role == "corridor"].astype({"hmrc_country_id": int, "comtrade_code": int})
    codes = pd.read_csv(ROOT / "config" / "codes.csv", dtype={"code": str}).code.tolist()
    plan = pd.read_csv(BT / "test_plan.csv", dtype={"codes": str, "conduct_end": str})
    return monthly, ct, release, corridors, codes, plan


def first(index) -> pd.Period | None:
    return index[0] if len(index) else None


def earliest(*ps):
    ps = [p for p in ps if p is not None]
    return min(ps) if ps else None


def months_to(p: pd.Period | None, ref: pd.Timestamp) -> int | None:
    """Whole months from the radar run at the end of month p to the reference date."""
    if p is None:
        return None
    end = p.end_time.normalize()
    m = (ref.year - end.year) * 12 + (ref.month - end.month)
    return m - 1 if ref.day < end.day else m


def before(t: pd.DataFrame, ref: pd.Timestamp) -> pd.DataFrame:
    return t[[p.end_time < ref for p in t.index]]


def series_table(timelines: dict, names: dict) -> pd.DataFrame:
    """First watch and first lead for every series, with the values behind the first lead."""
    series_rows = []
    for (rule, cid, code), t in timelines.items():
        fw, fl = first(t.index[t.uk_signal]), first(t.index[t.lead])
        row = {"rule": rule, "country": names[cid], "hmrc_country_id": cid, "code": code,
               "first_watch": str(fw) if fw is not None else "", "first_lead": str(fl) if fl is not None else ""}
        if fl is not None:
            r = t.loc[fl]
            row.update({"lead_trailing12_gbp": round(r.trailing12_published), "lead_baseline_gbp": round(r.baseline),
                        "lead_onward_year": r.onward_year,
                        "lead_onward_usd": round(r.onward_value) if pd.notna(r.onward_value) else None,
                        "lead_onward_base_usd": round(r.onward_base) if pd.notna(r.onward_base) else None})
        series_rows.append(row)
    return pd.DataFrame(series_rows)


def evaluate(timelines: dict, plan: pd.DataFrame, corridors: pd.DataFrame, codes: list, rule: str) -> list:
    """Outcome, lead time, conduct window and placebos for every test under one rule."""
    def lead_before(cid, code, ref) -> bool:
        return bool(before(timelines[(rule, cid, code)], ref).lead.any())

    results = []
    for _, tst in plan.iterrows():
        ref = pd.Timestamp(tst.reference_date)
        tcodes = tst.codes.split(";")
        case_rows = plan[plan.case_id == tst.case_id]
        case_corridors = set(case_rows.hmrc_country_id)
        case_codes = {c for cs in case_rows.codes for c in cs.split(";")}
        cid = int(tst.hmrc_country_id)
        c_start = pd.Period(tst.conduct_start, freq="M")
        c_end = pd.Period(tst.conduct_end, freq="M") if isinstance(tst.conduct_end, str) and tst.conduct_end else None

        fw_before = fl_before = fl_any = None
        lead_in_conduct = watch_in_conduct = lead_at_ref = False
        last_lead = None
        detail = []
        for code in tcodes:
            t = timelines[(rule, cid, code)]
            b = before(t, ref)
            w, l, la = first(b.index[b.uk_signal]), first(b.index[b.lead]), first(t.index[t.lead])
            fw_before, fl_before, fl_any = earliest(fw_before, w), earliest(fl_before, l), earliest(fl_any, la)
            if len(b):
                lead_at_ref |= bool(b.lead.iloc[-1])
                ll = b.index[b.lead]
                if len(ll):
                    last_lead = ll[-1] if last_lead is None else max(last_lead, ll[-1])
            in_c = b[[p >= c_start and (c_end is None or p <= c_end) for p in b.index]]
            lead_in_conduct |= bool(in_c.lead.any())
            watch_in_conduct |= bool(in_c.uk_signal.any())
            detail.append(f"{code}: watch {w or '-'}, lead {l or '-'}, any-time lead {la or '-'}")
        outcome = "hit" if fl_before is not None else ("watch only" if fw_before is not None else "miss")

        p1 = [c for c in corridors.hmrc_country_id if c not in case_corridors]
        p1_hits = sum(any(lead_before(c, code, ref) for code in tcodes) for c in p1)
        p2 = [c for c in codes if c not in case_codes]
        p2_hits = sum(lead_before(cid, c, ref) for c in p2)
        case_code_hits = sum(lead_before(cid, c, ref) for c in tcodes)
        all_hits = sum(lead_before(c, code, ref) for c in corridors.hmrc_country_id for code in codes)

        results.append({
            "rule": rule, "test_id": tst.test_id, "case_id": tst.case_id, "role": tst.role,
            "country": tst.country, "codes": tst.codes, "reference_date": tst.reference_date,
            "outcome": outcome,
            "first_watch_before": str(fw_before) if fw_before is not None else "",
            "first_lead_before": str(fl_before) if fl_before is not None else "",
            "lead_time_months": months_to(fl_before, ref),
            "first_lead_any_time": str(fl_any) if fl_any is not None else "",
            "lead_at_reference": lead_at_ref,
            "last_lead_before": str(last_lead) if last_lead is not None else "",
            "lapsed_months_before_reference": (months_to(last_lead, ref)
                                               if last_lead is not None and not lead_at_ref else None),
            "watch_in_conduct": watch_in_conduct, "lead_in_conduct": lead_in_conduct,
            "case_codes_leading": f"{case_code_hits}/{len(tcodes)}",
            "p1_other_corridors_hit": f"{p1_hits}/{len(p1)}",
            "p2_other_codes_leading": f"{p2_hits}/{len(p2)}",
            "p3_all_series_leading": f"{all_hits}/{len(corridors) * len(codes)}",
            "detail": "; ".join(detail),
        })
    return results


def main() -> int:
    monthly, ct, release, corridors, codes, plan = load()
    names = dict(zip(corridors.hmrc_country_id, corridors.name))
    reporter_of = dict(zip(corridors.hmrc_country_id, corridors.comtrade_code))

    # Every series, every month-end run, under both availability rules.
    timelines = {}
    for rule in RULES:
        rel = release if rule == "release dates" else None
        for cid in corridors.hmrc_country_id:
            for code in codes:
                timelines[(rule, cid, code)] = asof.timeline(
                    monthly, ct, cid, reporter_of[cid], code, START, END, asof.UK_LAG_MONTHS, rel)

    series = series_table(timelines, names)
    series.to_csv(BT / "run1_series.csv", index=False)

    results = []
    for rule in RULES:
        results.extend(evaluate(timelines, plan, corridors, codes, rule))
    res = pd.DataFrame(results)
    res.to_csv(BT / "run1_results.csv", index=False)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 120)
    for rule in RULES:
        print(f"\n=== {rule} ===")
        r = res[res.rule == rule]
        print(r[["test_id", "country", "codes", "reference_date", "outcome", "first_watch_before",
                 "first_lead_before", "lead_time_months", "first_lead_any_time", "lead_in_conduct",
                 "case_codes_leading", "p1_other_corridors_hit", "p2_other_codes_leading",
                 "p3_all_series_leading"]].to_string(index=False))
        for _, x in r.iterrows():
            print(f"  {x.test_id}: {x.detail}")
    print("\nA rise in exports is a lead, not evidence of a breach. "
          "Contains public sector information licensed under the Open Government Licence v3.0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
