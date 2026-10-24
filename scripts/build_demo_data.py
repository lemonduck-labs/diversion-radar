"""Datasets for the radar demo: the October 2026 run and the backtest's track record.

What leaves the repo through these files:
- Series flagged now are shown only when they pass the display rule (radar/display.py); the
  rest are counts.
- History: a past run of a shown series is drawn only when its own 12 published months pass
  the same rule (display.screen_runs). On a route the backtest tests, only 12-month windows
  that start after the case's first public action are drawn, so no UK figure shown covers
  the period of a case. The cases named no UK goods or UK party.
- Backtest: a test is shown only when its UK flow at the last run before the action passes
  the display rule for at least one of its codes, whatever its result. A test not shown keeps
  only its id, so the eight pre-registered tests stay visible as a count, but not its case,
  route (corridor), codes, mapping or result. A test shown gives its first lead whose 12
  months pass the rule. No UK figure is given for any backtest route.
- Summary: counts only. No count that splits the leads by which onward check carries them,
  since with the display rule's counts that can single out a held-back lead.
- Cases: case-level outcomes only (no sentences or other per-person detail), what each
  reference rests on, and the first public action to the month where the day is not known.

Writes one JSON file of row objects per dataset to demo/radar/:
summary, leads, history, onward_years, tests, cases, placebo, cost.
cases.json holds the official outcome of each tested case and is screened under the policy
line for official outcomes (config/guardrails_policy.txt).

The live datasets (summary, leads, history, onward_years) come from one variant of the run:
- run3 (the default, the workspace's current run): 18 corridors on run 2's rule
  (scripts/run_live_run3.py), read from data/processed/live_<run>_run3.csv with run 3's
  tables, the monthly check for every corridor with monthly UN Comtrade data after 2019, and
  run 3's case routes (config/case_routes_run3.csv with the routes run 2 uses);
- run2: the nine corridors of run 2 (scripts/run_live.py), from data/processed/live_<run>.csv.
The display rule, the case windows and every screening step are the same for both. The
backtest's datasets (tests, cases, placebo, cost) do not depend on the variant: the
backtest covers the original nine corridors and reads its own tables.

Usage:  python scripts/build_demo_data.py [--run 2026-10] [--rule run2] [--variant run3]
(run scripts/run_live_run3.py, or scripts/run_live.py with the same --run and --rule for
run2, first)

A rise in exports is a lead, not evidence of a breach.
Contains public sector information licensed under the Open Government Licence v3.0.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest import asof  # noqa: E402
from radar import display, onward as onward_rule  # noqa: E402

DATA, BT, OUT = ROOT / "data" / "processed", ROOT / "backtest" / "data", ROOT / "demo" / "radar"
NOT_SHOWN = "not shown (display rule)"
VARIANTS = ("run2", "run3")
#: The workspace's current run: demo/radar, the brief contexts and app/data are built from it.
CURRENT = "run3"

# How well the goods in each case map to the radar's codes (backtest/data/cases.csv,
# mapping_confidence). EU-01's goods were mainly computers (8471, outside the radar's nine
# codes); its tests use 8517.62, which the register rates low. Sensitivity tests use
# alternative codes: US-02's register rating is low overall; EU-05's alternatives are only
# called possible.
MAPPING = {"T1": "medium", "T2": "low", "T2s": "low (alternative code)", "T3": "medium",
           "T3s": "possible (alternative codes)", "T4a": "low", "T4b": NOT_SHOWN, "T4c": NOT_SHOWN}


def _module(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ROUTE_FILES = ("backtest/data/test_plan.csv", "config/case_routes_extra.csv")


def variant(name: str) -> SimpleNamespace:
    """What one variant of the run reads: its input tables (for scripts/run_live.load), the
    corridors with the monthly onward check (None keeps run 2's seven in
    scripts/run_backtest2.MONTHLY_REPORTERS) and where they are set, the display rule's case
    routes and the files they come from, and the suffix of its live table in data/processed.
    Run 3's come from scripts/run_live_run3.py, which checks that they leave the original nine
    as run 2 had them."""
    live_mod = _module("run_live")
    if name == "run2":
        return SimpleNamespace(name=name, inputs=dict(live_mod.RUN2_INPUTS), monthly_reporters=None,
                               monthly_source=("scripts/run_backtest2.py", "MONTHLY_REPORTERS"),
                               routes=display.load_case_routes(ROOT), route_files=ROUTE_FILES, suffix="")
    if name == "run3":
        r3 = _module("run_live_run3")
        monthly_all, _ = r3.monthly_reporters(_module("run_backtest2").MONTHLY_REPORTERS)
        return SimpleNamespace(name=name, inputs={**live_mod.RUN2_INPUTS, **r3.INPUTS}, monthly_reporters=monthly_all,
                               monthly_source=("scripts/run_live_run3.py", "monthly_reporters()"),
                               routes=r3.case_routes(), route_files=ROUTE_FILES + ("config/case_routes_run3.csv",),
                               suffix=f"_{r3.LABEL}")
    raise ValueError(f"variant must be one of {', '.join(VARIANTS)}, not {name!r}")


def live_table(run: int, name: str = CURRENT) -> Path:
    """The live table a variant's datasets are built from."""
    return DATA / f"live_{asof.to_period(run).strftime('%Y-%m')}{variant(name).suffix}.csv"


def _f(x, nd=0):
    """Rounded halves up; None for missing values."""
    if x is None or pd.isna(x):
        return None
    d = Decimal(str(float(x))).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP)
    return float(d) if nd else int(d)


def _month_date(p) -> str:
    return pd.Period(str(p), freq="M").start_time.strftime("%Y-%m-%d")


def _month(p) -> str:
    return "" if p is None or (isinstance(p, float) and pd.isna(p)) or p == "" else str(p)[:7]


def onward_checks(r) -> tuple[dict, dict | None]:
    """Both onward checks for one series at the run, with the reasons a check did not pass in
    radar/onward.py's words, so a lead that rests on one check shows the other beside it."""
    def check(usd, base, passes):
        return {"usd": _f(usd), "ratio": _f(usd / base, 1) if pd.notna(usd) and pd.notna(base) and base > 0 else None,
                "baseline_zero": bool(pd.notna(base) and base == 0), "passes": bool(passes),
                "no_exports": bool(pd.isna(usd) or usd == 0),
                "why_not": None if passes else onward_rule.why_not_text(usd, base),
                "why_not_short": None if passes else onward_rule.why_not_short(usd, base)}
    annual = {"year": None if pd.isna(r.onward_year) else int(r.onward_year),
              **check(r.onward_usd, r.onward_base_usd, r.onward_annual)}
    if pd.notna(r.onward_usd) and pd.notna(r.onward_ratio) and annual["ratio"] != _f(r.onward_ratio, 1):
        raise SystemExit(f"{r.country} {r.code}: annual ratio differs from the live run")
    monthly = None
    if pd.notna(r.get("monthly_end")) and pd.notna(r.get("monthly_window_usd")):
        monthly = {"to": f"{int(r.monthly_end) // 100:04d}-{int(r.monthly_end) % 100:02d}",
                   **check(r.monthly_window_usd, r.monthly_base_usd, r.onward_monthly)}
    return annual, monthly


def watch_label(annual: dict, monthly: dict | None) -> str:
    """The onward check of a watch item: why neither check passed, in a few words (the full
    reasons are in onward_annual and onward_monthly)."""
    year = f" {annual['year']}" if annual["year"] is not None else ""
    return (f"not passed: annual{year} {annual['why_not_short'] or onward_rule.SHORT[onward_rule.NO_EXPORTS]}"
            + (f"; monthly {monthly['why_not_short']}" if monthly else ""))


def action_label(text: str) -> str:
    """The first public action as the register gives it: to the day where the day is known,
    otherwise to the month."""
    date = str(text).split(" ")[0]
    if len(date) == 10:
        return pd.Timestamp(date).strftime("%-d %b %Y")
    label = pd.Period(date, freq="M").strftime("%b %Y")
    return label + (" (earliest dated step found)" if "not dated" in str(text) else " (as reported)")


def screened_test(tl_by_code: dict, monthly, cid: int, ref: pd.Timestamp, col: str, months_to) -> dict:
    """A test's result as it may be shown: its first lead before the reference date whose 12
    published months pass the display rule, the months from it to the reference date, and
    whether the last run before the reference date was such a lead."""
    passing, any_lead, last_before = [], False, None
    for code, tl in tl_by_code.items():
        before = tl[[p.end_time < ref for p in tl.index]]
        last_before = before.index[-1]
        leads = before.index[before[col]]
        any_lead |= len(leads) > 0
        if len(leads):
            scr = display.screen_runs(monthly, cid, code, leads, asof.UK_LAG_MONTHS)
            passing += list(scr.index[scr.shown])
    first = min(passing) if passing else None
    on_day = last_before in passing
    last = max(passing) if passing else None
    return {"any_lead": any_lead, "first": first, "lead_time": months_to(first, ref) if first else None,
            "on_day": on_day, "lapsed": months_to(last, ref) if last is not None and not on_day else None}


def build(run: int, rule: str, variant_name: str = CURRENT) -> dict[str, list[dict]]:
    live_mod = _module("run_live")
    v = variant(variant_name)
    if v.name == "run3" and rule != "run2":
        raise SystemExit("run 3 is on run 2's rule; use --rule run2")
    tag = asof.to_period(run).strftime("%Y-%m")
    live_name = f"live_{tag}{v.suffix}.csv"
    script = "run_live_run3.py" if v.name == "run3" else f"run_live.py --rule {rule}"
    live = pd.read_csv(DATA / live_name, dtype={"code": str})
    if live.rule.iloc[0] != rule:
        raise SystemExit(f"{live_name} was built with rule {live.rule.iloc[0]}; rerun {script}")
    if v.name == "run3" and set(live["run"]) != {"run3"}:
        raise SystemExit(f"{live_name} is not run 3's live table; rerun {script}")
    flagged = live[live.status != "none"]
    shown = flagged[flagged.display]

    summary = [{
        "run": tag, "run_label": asof.to_period(run).strftime("%B %Y"),
        "uk_data_to": asof.to_period(int(live.uk_data_to.iloc[0])).strftime("%B %Y"), "rule": rule,
        "variant": v.name,
        "series": int(len(live)), "corridors": int(live.country.nunique()), "codes": int(live.code.nunique()),
        "leads": int((live.status == "lead").sum()), "leads_shown": int((shown.status == "lead").sum()),
        "leads_held": int(((flagged.status == "lead") & ~flagged.display).sum()),
        "watch": int((live.status == "watch").sum()), "watch_shown": int((shown.status == "watch").sum()),
        "watch_held": int(((flagged.status == "watch") & ~flagged.display).sum()),
        "ever_lead": int((live.runs_as_lead > 0).sum()),
        "display_min_gbp": display.MIN_DISPLAY_GBP, "display_min_months": display.MIN_DISPLAY_MONTHS,
    }]

    plan = pd.read_csv(BT / "test_plan.csv", dtype={"codes": str})
    routes = v.routes
    leads, history, onward_years = [], [], []
    monthly, ct, release, corridors, codes = live_mod.load(v.inputs)
    if rule == "run2":
        rb2 = _module("run_backtest2")
        if v.monthly_reporters is not None:
            rb2.MONTHLY_REPORTERS = set(int(x) for x in v.monthly_reporters)
        ctm = pd.read_csv(v.inputs["comtrade_monthly"], dtype={"code": str})
        rel_m = pd.read_csv(v.inputs["monthly_release_dates"])
        rel_m["first_released"] = pd.to_datetime(rel_m.first_released, format="ISO8601")
    # Corridors with the monthly onward check: none under run 1's rule.
    summary[0]["monthly_corridors"] = int(corridors.comtrade_code.isin(rb2.MONTHLY_REPORTERS).sum()) if rule == "run2" else 0
    if summary[0]["corridors"] != len(corridors):
        raise SystemExit(f"{live_name} has {summary[0]['corridors']} corridors, the variant's tables {len(corridors)}")
    for r in shown.sort_values(["status", "uk_trailing12_gbp"], ascending=[True, False]).itertuples():
        key = f"{r.country} {r.code}"
        cid = int(r.hmrc_country_id)
        label, val, rat = live_mod.onward_desc(r)
        o_annual, o_monthly = onward_checks(pd.Series(r._asdict()))
        if r.status == "watch" and (o_annual["passes"] or (o_monthly and o_monthly["passes"])):
            raise SystemExit(f"{key}: a watch item with an onward check passed")
        route = display.route_for(routes, cid, r.code)
        leads.append({"series": key, "country": r.country, "code": r.code, "description": r.description,
                      "status": r.status, "uk_trailing12_gbp": _f(r.uk_trailing12_gbp),
                      "uk_baseline_gbp": _f(r.uk_baseline_gbp), "uk_ratio": _f(r.uk_ratio, 1),
                      "uk_months_with_exports": int(r.uk_months_with_exports),
                      "onward_check": label if r.status == "lead" else watch_label(o_annual, o_monthly),
                      "onward_usd": _f(val) if r.status == "lead" else _f(r.onward_usd),
                      "onward_ratio": _f(rat, 1) if r.status == "lead" else _f(r.onward_ratio, 1),
                      "onward_baseline_zero": bool((r.monthly_base_usd if r.status == "lead" and not r.onward_annual
                                                    else r.onward_base_usd) == 0),
                      "onward_year": None if pd.isna(r.onward_year) else int(r.onward_year),
                      "onward_annual": o_annual, "onward_monthly": o_monthly,
                      "case_route": route[0] if route else "",
                      "case_match": route[2] if route else "",
                      "history_from": _month(r.history_from),
                      "runs_shown": int(r.runs_shown),
                      "first_lead_shown": _month(r.first_lead_shown),
                      "runs_shown_as_lead": int(r.runs_shown_as_lead)})
        if rule == "run2":
            t = rb2.part_a_timeline(monthly, ct, release, ctm, rel_m, cid, int(r.comtrade_code), r.code, 202201, run)
        else:
            t = asof.timeline(monthly, ct, cid, int(r.comtrade_code), r.code, 202201, run, asof.UK_LAG_MONTHS, release)
        scr = display.screen_runs(monthly, cid, r.code, t.index, asof.UK_LAG_MONTHS, route[1] if route else None)
        if int(scr.shown.sum()) != int(r.runs_shown):
            raise SystemExit(f"{key}: screened runs differ from {live_name}; rerun {script}")
        base = float(t.baseline.iloc[0])
        thr = max(asof.UK_RATIO * base, base + asof.UK_MIN_EXCESS)
        for p, v in t.iterrows():
            ok = bool(scr.loc[p, "shown"])
            history.append({"series": key, "run": _month_date(p), "shown": ok,
                            "not_shown_because": scr.loc[p, "not_shown_because"],
                            "uk_trailing12_gbp": _f(v.trailing12_published) if ok else None,
                            "uk_threshold_gbp": _f(thr),
                            "uk_signal": bool(v.uk_signal) if ok else None,
                            "onward_signal": bool(v.onward_signal) if ok else None,
                            "lead": bool(v.lead) if ok else None})
        x = ct[(ct.reporter == r.comtrade_code) & (ct.partner == asof.RUSSIA) & (ct.flow == "X") & (ct.code == r.code)]
        by_year = x.groupby("year").value_usd.sum()
        years = sorted(set(ct[(ct.reporter == r.comtrade_code) & (ct.partner == asof.RUSSIA) & (ct.flow == "X")].year))
        base_years = [y for y in asof.BASE_YEARS if y in years]
        ob = sum(float(by_year.get(y, 0.0)) for y in base_years) / len(base_years) if base_years else None
        rel = release[release.reporter == r.comtrade_code].set_index("year").first_released
        for y in years:
            onward_years.append({"series": key, "year": str(int(y)), "usd": _f(by_year.get(y, 0.0)),
                                 "threshold_usd": _f(max(asof.ONWARD_RATIO * ob, asof.ONWARD_MIN_USD)) if ob is not None else None,
                                 "first_released": str(rel.get(y).date()) if y in rel.index else ""})

    # Backtest tests, screened the same way as the live radar, on the backtest's own tables
    # and a copy of run 2's module as committed (its seven monthly corridors), whatever the
    # variant.
    rb2 = _module("run_backtest2")
    r1mod, bmonthly, bct, brelease, bcorr, _, _, bctm, brel_m = rb2.load_part_a()
    rep = dict(zip(bcorr.hmrc_country_id, bcorr.comtrade_code))
    r1 = pd.read_csv(BT / "run1_results.csv", dtype={"codes": str})
    r1 = r1[r1.rule == "release dates"].set_index("test_id")
    r2 = pd.read_csv(BT / "run2_results.csv", dtype={"codes": str}).set_index("test_id")
    cases_df = pd.read_csv(BT / "cases.csv").set_index("case_id")
    tests = []
    for p in plan.itertuples():
        ref = pd.Timestamp(p.reference_date)
        cid = int(p.hmrc_country_id)
        tl = {code: rb2.part_a_timeline(bmonthly, bct, brelease, bctm, brel_m, cid, rep[cid], code)
              for code in p.codes.split(";")}
        # A test is shown only when its UK flow at the last run before the action passes the
        # display rule for at least one of its codes. The rule does not look at the result, so
        # "not shown" says nothing about it. A test shown that is a hit with no lead run passing
        # the rule stops the build, for a person to decide.
        last_ok = False
        for code, t_ in tl.items():
            last = t_.index[[q.end_time < ref for q in t_.index]][-1:]
            last_ok |= bool(display.screen_runs(bmonthly, cid, code, last, asof.UK_LAG_MONTHS).shown.iloc[0])
        res = {}
        for tag_, col, rr in (("run1", "lead_run1", r1), ("run2", "lead", r2)):
            s_ = screened_test(tl, bmonthly, cid, ref, col, r1mod.months_to)
            outcome = rr.loc[p.test_id].outcome
            if (outcome == "hit") != s_["any_lead"]:
                raise SystemExit(f"{p.test_id} {tag_}: timelines disagree with the results file")
            res[tag_] = (outcome, s_)
        shown = last_ok
        if shown and any(o == "hit" and s_["first"] is None for o, s_ in res.values()):
            raise SystemExit(f"{p.test_id}: a hit shown with no lead run passing the display rule; decide before showing")
        # A test not shown keeps no route: with the result withheld, the route alone still told a
        # reader about a small UK flow on a case route (N6, N7). Nor its codes, mapping or case:
        # with the case and the case's own documented corridors, the route could be worked out
        # (review of the public copy, 24 Oct 2026). Only its id stays, so the count of tests holds.
        row = {"test_id": p.test_id, "case_id": p.case_id if shown else "", "role": p.role if shown else "", "corridor": p.country if shown else "",
               "codes": p.codes.replace(";", ", ") if shown else "", "mapping": MAPPING[p.test_id] if shown else NOT_SHOWN,
               "first_public_action": action_label(cases_df.loc[p.case_id].first_public_action) if shown else "",
               "shown": shown}
        for tag_, (outcome, s_) in res.items():
            row[f"{tag_}_outcome"] = outcome if shown else NOT_SHOWN
            row[f"{tag_}_first_lead"] = str(s_["first"]) if shown and s_["first"] is not None else ""
            row[f"{tag_}_lead_time_months"] = s_["lead_time"] if shown else None
            if tag_ == "run2":
                row["run2_on_the_day"] = ("n/a" if not shown or outcome != "hit" else "yes" if s_["on_day"]
                                          else f"no, stopped {s_['lapsed']} months before")
        tests.append(row)

    cases = []
    for cid in plan.case_id.unique():
        c = cases_df.loc[cid]
        cases.append({"case_id": cid, "jurisdiction": c.jurisdiction, "enforcing_body": c.enforcing_body,
                      "reference": c.official_reference, "outcome": c.outcome,
                      "basis": ("published reports only; no official judgment seen"
                                if "secondary source" in str(c.verification_notes) else "official records"),
                      "first_public_action": action_label(c.first_public_action)})

    pl = pd.read_csv(BT / "run2_placebo.csv", dtype={"code": str})
    placebo = [{"period": "Peacetime, 2019-21", "baseline": "2016-18", "runs": 36, "rule": "annual check alone",
                "series_ever_lead": int((pl.peace_lead_runs > 0).sum()), "series": int(len(pl))},
               {"period": "War-time, 2022-24", "baseline": "2019-21", "runs": 36, "rule": "annual check alone",
                "series_ever_lead": int((pl.war_lead_runs > 0).sum()), "series": int(len(pl))}]
    s2 = pd.read_csv(BT / "run2_series.csv", dtype={"code": str})
    # Counts from the tests shown only, so that no count gives away a test that is not shown.
    hit = lambda col, role: sum(1 for t in tests if t["shown"] and t["role"] == role and t[col] == "hit")
    n_role = lambda role: sum(1 for t in tests if t["shown"] and t["role"] == role)
    cases_hit = lambda col: len({t["case_id"] for t in tests if t["shown"] and t[col] == "hit"})
    not_shown = sum(1 for t in tests if not t["shown"])
    cost = [{"measure": "Cases with a lead before the first public action", "run1": cases_hit("run1_outcome"),
             "run2": cases_hit("run2_outcome"), "of": len(cases)},
            {"measure": "Primary tests shown, with a lead before the first public action",
             "run1": hit("run1_outcome", "primary"), "run2": hit("run2_outcome", "primary"), "of": n_role("primary")},
            {"measure": "Sensitivity tests shown, with a lead before the first public action",
             "run1": hit("run1_outcome", "sensitivity"), "run2": hit("run2_outcome", "sensitivity"),
             "of": n_role("sensitivity")},
            {"measure": "Tests listed with no route or result, under the display rule", "run1": not_shown, "run2": not_shown,
             "of": len(tests)},
            {"measure": "Series a lead at some run, Jan 2022 to Aug 2026", "run1": int((s2.first_lead_run1.notna()).sum()),
             "run2": int((s2.first_lead_run2.notna()).sum()), "of": int(len(s2))},
            {"measure": "Monthly runs as a lead, all series", "run1": int(s2.runs_as_lead_run1.sum()),
             "run2": int(s2.runs_as_lead_run2.sum()), "of": int(len(s2)) * 56}]
    return {"summary": summary, "leads": leads, "history": history, "onward_years": onward_years,
            "tests": tests, "cases": cases, "placebo": placebo, "cost": cost}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="2026-10")
    ap.add_argument("--rule", default="run2", choices=["run1", "run2"])
    ap.add_argument("--variant", default=CURRENT, choices=list(VARIANTS),
                    help=f"which live run the datasets show (default {CURRENT}, the workspace's current run)")
    a = ap.parse_args(argv)
    data = build(int(a.run.replace("-", "")), a.rule, a.variant)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in data.items():
        (OUT / f"{name}.json").write_text(json.dumps(rows, indent=1))
        print(f"demo/radar/{name}.json: {len(rows)} rows")
    print(f"live datasets from {a.variant}: {data['summary'][0]['corridors']} corridors")
    print("A rise in exports is a lead, not evidence of a breach.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
