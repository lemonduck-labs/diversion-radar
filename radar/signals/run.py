"""Runs the three research signals as pre-registered (radar/signals/RESEARCH.md, S0) and writes
radar/signals/results/:

- runs.csv      every corridor and code at every war-time run (January 2022 to August 2026):
                the UK signal, run 2's lead, S1 (D and direction), S2, S3, and whether the
                series passes the display rule and may be named at that run
- tests.csv     one row per signal and test: outcome, first flag, lead time, run 2 beside it
- placebo.csv   every series: runs flagged in the 36 peacetime runs and the first 36 war-time runs
- summary.json  cost, placebo, the success criteria and the checks

Usage:  python3 -m radar.signals.run

A rise in exports is a lead, not evidence of a breach.
Contains public sector information licensed under the Open Government Licence v3.0.
"""
from __future__ import annotations

import json
import sys

import pandas as pd

from backtest import asof
from radar import display
from radar.signals import codeshift, common, displacement, evaluate, price

BT = common.ROOT / "backtest" / "data"
OUT = common.ROOT / "radar" / "signals" / "results"
RUN2_SERIES_EVER, RUN2_LEAD_RUNS = 20, 300     # backtest/RESEARCH_LOG.md, B2.1


def compute():
    """Every timeline the evaluation needs. Returns a dict of dicts keyed by (country id, code)."""
    war_m = common.load_monthly(common.WAR_FILE)
    peace_m = common.load_monthly(common.PEACE_FILE)
    codes = common.load_codes()
    corridors = common.load_corridors()
    cids = corridors.hmrc_country_id.tolist()
    code_list = codes.code.tolist()
    sib = common.sibling_map(codes)

    war = common.Panel(war_m, 201901, 202608)
    peace = common.Panel(peace_m, 201601, 202608)
    war_runs = common.runs(*common.WAR_RUNS)
    peace_runs = common.runs(*common.PEACE_RUNS)

    keys = [(c, k) for c in cids for k in code_list]
    s2_keys = [(c, a) for c in cids for a in code_list if a in sib]
    t = {
        "s1": {k: price.timeline(war, cids, *k, common.WAR_BASE, war_runs) for k in keys},
        "s1_peace": {k: price.timeline(peace, cids, *k, common.PEACE_BASE, peace_runs) for k in keys},
        "uk": {k: asof.uk_series(war_m, *k, 202608).uk_signal.reindex(war_runs).astype(bool) for k in keys},
        "uk_peace": {k: asof.uk_series(peace_m, *k, 202608, base_years=common.PEACE_BASE)
                     .uk_signal.reindex(peace_runs).astype(bool) for k in keys},
        "s2": {k: codeshift.timeline(war, k[0], k[1], sib[k[1]], common.WAR_BASE, war_runs) for k in s2_keys},
        "s2_peace": {k: codeshift.timeline(peace, k[0], k[1], sib[k[1]], common.PEACE_BASE, peace_runs)
                     for k in s2_keys},
        "s3": {k: displacement.timeline(war, war_m, *k, war_runs) for k in keys},
    }

    # Run 2's lead at every run, recomputed with run 2's own code.
    rb2 = evaluate.script("run_backtest2")
    _, monthly, ct, release, corr2, _, _, ctm, rel_m = rb2.load_part_a()
    rep = dict(zip(corr2.hmrc_country_id, corr2.comtrade_code))
    t["lead"] = {k: rb2.part_a_timeline(monthly, ct, release, ctm, rel_m, k[0], rep[k[0]], k[1])
                 .lead.reindex(war_runs).astype(bool) for k in keys}
    ctx = {"war_m": war_m, "peace_m": peace_m, "corridors": corridors, "codes": codes, "sib": sib,
           "war_runs": war_runs, "peace_runs": peace_runs, "keys": keys, "s2_keys": s2_keys}
    return t, ctx


def flag_sets(t: dict) -> dict:
    """Every variant evaluated, as boolean series by war-time run."""
    f = {"S1": {k: x.s1 for k, x in t["s1"].items()}}
    f["S1 with the UK signal"] = {k: f["S1"][k] & t["uk"][k] for k in f["S1"]}
    f["S2"] = {k: x.s2 for k, x in t["s2"].items()}
    for fac in (displacement.FACTOR,) + displacement.SENSITIVITY:
        f[f"S3 at {fac:.2f}"] = {k: x[f"s3_{fac:.2f}"] for k, x in t["s3"].items()}
    f["Run 2 lead"] = t["lead"]
    f["Run 2 lead filtered by S1"] = {k: t["lead"][k] & f["S1"][k] for k in t["lead"]}
    for fac in (displacement.FACTOR,) + displacement.SENSITIVITY:
        f[f"Run 2 lead filtered by S3 at {fac:.2f}"] = {k: t["lead"][k] & f[f"S3 at {fac:.2f}"][k]
                                                       for k in t["lead"]}
    f["UK signal (watch)"] = t["uk"]
    return f


def shown_sets(t: dict) -> dict:
    """The display rule at every war-time run: on the series' own window, and for S2 on the
    heading's total to the corridor."""
    own = {k: x.shown for k, x in t["s1"].items()}
    return {"own": own, "heading": {k: x.heading_shown for k, x in t["s2"].items()}}


def main() -> int:
    t, ctx = compute()
    plan = pd.read_csv(BT / "test_plan.csv", dtype={"codes": str, "conduct_end": str})
    run2 = pd.read_csv(BT / "run2_results.csv")
    routes = display.load_case_routes(common.ROOT)
    flags = flag_sets(t)
    shown = shown_sets(t)
    war_runs, sib = ctx["war_runs"], ctx["sib"]
    shown_out = evaluate.test_shown_outside(ctx["war_m"], plan, war_runs)

    # Checks: run 2 recomputed as published.
    lead_cost = evaluate.cost(flags["Run 2 lead"])
    checks = {"run2_series_ever_a_lead": lead_cost["series_ever"], "run2_lead_runs": lead_cost["runs_flagged"],
              "run2_matches_B2.1": lead_cost["series_ever"] == RUN2_SERIES_EVER
              and lead_cost["runs_flagged"] == RUN2_LEAD_RUNS}
    run2_check = evaluate.evaluate_tests(flags["Run 2 lead"], plan, run2, "Run 2 lead").set_index("test_id")
    published = run2.set_index("test_id")
    checks["run2_tests_match"] = bool(
        (run2_check.first_flag_before.fillna("") == published.first_lead_before.fillna("")).all()
        and (run2_check.lead_time_months.fillna(-1) == published.lead_time_months.fillna(-1)).all())

    # Run 2's first lead before each reference date at a run that passes the display rule.
    r2s = evaluate.evaluate_tests({k: s & shown["own"][k] for k, s in flags["Run 2 lead"].items()},
                                  plan, run2, "Run 2 lead, display rule")
    run2_first_shown = {x.test_id: pd.Period(x.first_flag_before, freq="M")
                        for x in r2s.itertuples() if isinstance(x.first_flag_before, str) and x.first_flag_before}

    tests, costs = [], {}
    for label, fl in flags.items():
        applicable = set(sib) if label == "S2" else None
        sh = shown["heading"] if label == "S2" else shown["own"]
        tests.append(evaluate.evaluate_tests(fl, plan, run2, label, applicable, shown_out,
                                             {k: sh[k] for k in fl}, run2_first_shown))
        named = {k: common.nameable(s, sh[k], routes, *k) for k, s in fl.items()}
        costs[label] = evaluate.cost(fl, {k: sh[k] for k in fl}, named)
    tests = pd.concat(tests, ignore_index=True)

    # Placebo: S1, S1 with the UK signal and S2, peacetime against the first 36 war-time runs.
    first36 = common.runs(*common.WAR_PLACEBO_RUNS)
    pl = {
        "S1": ({k: x.s1 for k, x in t["s1_peace"].items()}, {k: x.s1.reindex(first36) for k, x in t["s1"].items()}),
        "S1 with the UK signal": ({k: x.s1 & t["uk_peace"][k] for k, x in t["s1_peace"].items()},
                                  {k: (x.s1 & t["uk"][k]).reindex(first36) for k, x in t["s1"].items()}),
        "S2": ({k: x.s2 for k, x in t["s2_peace"].items()}, {k: x.s2.reindex(first36) for k, x in t["s2"].items()}),
    }
    placebo = {label: evaluate.placebo(p, w) for label, (p, w) in pl.items()}

    verdicts = {
        "S1": evaluate.verdict_new_flag(tests[tests.signal == "S1"], costs["S1"], placebo["S1"],
                                        evaluate.NEW_FLAG_MAX_SERIES),
        "S2": evaluate.verdict_new_flag(tests[tests.signal == "S2"], costs["S2"], placebo["S2"],
                                        evaluate.NEW_FLAG_MAX_SERIES_S2),
        "S3 at 0.10 as a new flag": evaluate.verdict_new_flag(tests[tests.signal == "S3 at 0.10"],
                                                              costs["S3 at 0.10"], None,
                                                              evaluate.NEW_FLAG_MAX_SERIES),
        "S1 with the UK signal as a filter": evaluate.verdict_filter(
            tests[tests.signal == "Run 2 lead filtered by S1"], run2, costs["Run 2 lead filtered by S1"]),
        "S3 at 0.10 as a filter": evaluate.verdict_filter(
            tests[tests.signal == "Run 2 lead filtered by S3 at 0.10"], run2,
            costs["Run 2 lead filtered by S3 at 0.10"]),
    }

    # The baselines use all three baseline years, as the backtest's do, so the first run of each
    # period (January 2022; January 2019) counts one baseline month not yet published (December
    # 2021; December 2018). Flags at those runs, and S1 there with that month left out.
    first_war, first_peace = common.runs(202201, 202201), common.runs(201901, 201901)
    early = {label: sorted(f"{k[0]}:{k[1]}" for k, s in flags[label].items() if s.reindex(first_war).any())
             for label in ("S1", "S2", "S3 at 0.10", "S3 at 0.05", "S3 at 0.25")}
    early["S1 peacetime"] = sorted(f"{k[0]}:{k[1]}" for k, x in t["s1_peace"].items() if x.s1.reindex(first_peace).any())
    early["S2 peacetime"] = sorted(f"{k[0]}:{k[1]}" for k, x in t["s2_peace"].items() if x.s2.reindex(first_peace).any())
    war_p, peace_p = common.Panel(ctx["war_m"], 201901, 202608), common.Panel(ctx["peace_m"], 201601, 202608)
    cids = ctx["corridors"].hmrc_country_id.tolist()
    strict_war = sorted(f"{k[0]}:{k[1]}" for k in ctx["keys"]
                        if price.timeline(war_p, cids, *k, common.WAR_BASE, first_war, base_until=202111).s1.any())
    strict_peace = sorted(f"{k[0]}:{k[1]}" for k in ctx["keys"]
                          if price.timeline(peace_p, cids, *k, common.PEACE_BASE, first_peace, base_until=201811).s1.any())
    checks["first_run_flags"] = early
    checks["first_run_s1_unchanged_without_the_unpublished_month"] = (
        strict_war == early["S1"] and strict_peace == early["S1 peacetime"])

    write(t, ctx, flags, shown, routes, tests, costs, placebo, verdicts, checks)
    report(tests, costs, placebo, verdicts, checks)
    return 0


def write(t, ctx, flags, shown, routes, tests, costs, placebo, verdicts, checks) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    names = dict(zip(ctx["corridors"].hmrc_country_id, ctx["corridors"].name))
    rows = []
    for k in ctx["keys"]:
        s1, s3 = t["s1"][k], t["s3"][k]
        s2 = t["s2"].get(k)
        own = shown["own"][k]
        n1 = common.nameable(s1.s1, own, routes, *k)
        n3 = common.nameable(s3["s3_0.10"], own, routes, *k)
        n2 = common.nameable(s2.s2, s2.heading_shown, routes, *k) if s2 is not None else None
        for p in ctx["war_runs"]:
            rows.append({
                "country": names[k[0]], "hmrc_country_id": k[0], "code": k[1], "run": str(p),
                "uk_signal": bool(t["uk"][k][p]), "run2_lead": bool(t["lead"][k][p]),
                "shown": bool(own[p]),
                "s1_d": round(float(s1.d[p]), 3) if pd.notna(s1.d[p]) else None,
                "s1": bool(s1.s1[p]), "s1_direction": s1.s1_direction[p], "s1_named": bool(n1[p]),
                "s2": None if s2 is None else bool(s2.s2[p]),
                "s2_heading_shown": None if s2 is None else bool(s2.heading_shown[p]),
                "s2_named": None if s2 is None else bool(n2[p]),
                "s3_0.10": bool(s3["s3_0.10"][p]), "s3_0.05": bool(s3["s3_0.05"][p]),
                "s3_0.25": bool(s3["s3_0.25"][p]), "s3_russia_fall": bool(s3.russia_fall[p]),
                "s3_named": bool(n3[p])})
    pd.DataFrame(rows).to_csv(OUT / "runs.csv", index=False)
    tests.to_csv(OUT / "tests.csv", index=False)

    first36 = common.runs(*common.WAR_PLACEBO_RUNS)
    prow = []
    for k in ctx["keys"]:
        r = {"country": names[k[0]], "hmrc_country_id": k[0], "code": k[1],
             "s1_peace_runs": int(t["s1_peace"][k].s1.sum()),
             "s1_war_runs": int(t["s1"][k].s1.reindex(first36).sum()),
             "s1_uk_peace_runs": int((t["s1_peace"][k].s1 & t["uk_peace"][k]).sum()),
             "s1_uk_war_runs": int((t["s1"][k].s1 & t["uk"][k]).reindex(first36).sum())}
        if k in t["s2"]:
            r["s2_peace_runs"] = int(t["s2_peace"][k].s2.sum())
            r["s2_war_runs"] = int(t["s2"][k].s2.reindex(first36).sum())
        prow.append(r)
    pd.DataFrame(prow).to_csv(OUT / "placebo.csv", index=False)

    summary = {"pre_registration": "radar/signals/RESEARCH.md, S0 (commit cd74780)",
               "runs": "end of each month, January 2022 to August 2026 (56); placebo January 2019 to "
                       "December 2021 (36) against January 2022 to December 2024 (36)",
               "cost": costs, "placebo": placebo, "verdicts": verdicts, "checks": checks,
               "house_line": "A rise in exports is a lead, not evidence of a breach.",
               "licence": "Contains public sector information licensed under the Open Government Licence v3.0."}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")


def report(tests, costs, placebo, verdicts, checks) -> None:
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 40)
    print("checks:", json.dumps(checks, default=str))
    cols = ["signal", "test_id", "role", "outcome", "first_flag_before", "lead_time_months",
            "on_at_last_run_before", "first_flag_any_time", "run2_first_lead", "months_earlier_than_run2",
            "beats_run2", "first_shown_before", "run2_first_shown", "months_earlier_shown"]
    print(tests[cols].to_string(index=False))
    print("\ncost:")
    for label, c in costs.items():
        print(f"  {label}: {c}")
    print("\nplacebo:")
    for label, p in placebo.items():
        print(f"  {label}: {p}")
    print("\nverdicts:")
    for label, v in verdicts.items():
        print(f"  {label}: {v}")
    print("\nA rise in exports is a lead, not evidence of a breach. "
          "Contains public sector information licensed under the Open Government Licence v3.0.")


if __name__ == "__main__":
    sys.exit(main())
