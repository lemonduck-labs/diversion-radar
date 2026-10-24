"""Run 4: the prediction register (pre-registered in backtest/RESEARCH_LOG.md, entry R4).

Before the next HMRC releases, writes down what the radar's own history says each of run 3's
162 series should do at the next two runs, so the November and December runs can be scored
against predictions made before their data existed.

Method, fixed in R4 before any later data is pulled:
- Each series' status at every month end from January 2022 to October 2026 comes from the same
  engine and tables as run 3 (scripts/run_live_run3.py): "lead" (UK signal and an onward
  signal), "watch" (UK signal only) or "none".
- Primary rates: the empirical transitions between consecutive month ends over the last 12
  transitions (October 2025 to October 2026), pooled over all 162 series, by status. The
  two-run rates (for December) come from pairs two month ends apart over the same span.
- Secondary rates, reported and never tested: the same over every transition since January 2022.
- Each series gets the probability of each status at run 4 (November 2026 run, HMRC data to
  September 2026) and run 5 (December 2026 run, data to October 2026) from its run 3 status.

Writes (stops if run 3's statuses are not reproduced exactly):
- backtest/data/r4_register.csv           every series: run 3 status, whether it may be shown,
                                           and its predicted probabilities (internal; it names
                                           series the display rule holds back)
- backtest/data/r4_register_summary.json  the rates, the expected counts and their 90% intervals

Usage:  python scripts/prediction_register.py

A rise in exports is a lead, not evidence of a breach.
Contains public sector information licensed under the Open Government Licence v3.0.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest import asof  # noqa: E402

BT = ROOT / "backtest" / "data"
RUN3_OUT = ROOT / "data" / "processed" / "live_2026-10_run3.csv"
OUT = BT / "r4_register.csv"
SUMMARY = BT / "r4_register_summary.json"
STATUSES = ("lead", "watch", "none")
RECENT_FROM = 202510  # first month end of the primary window's transitions (Oct 2025 -> Nov 2025)


def _load(name: str, alias: str):
    spec = importlib.util.spec_from_file_location(alias, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def histories() -> pd.DataFrame:
    """Status at every month end since January 2022, for all 162 series, as run 3 builds them."""
    run3 = _load("run_live_run3", "run_live_run3_for_r4")
    live = run3._module("run_live")
    rb2 = run3._module("run_backtest2")
    monthly_all, _ = run3.monthly_reporters(rb2.MONTHLY_REPORTERS)
    rb2.MONTHLY_REPORTERS = set(int(r) for r in monthly_all)
    p = {**live.RUN2_INPUTS, **run3.INPUTS}
    monthly, ct, release, corridors, codes = live.load(p)
    ctm = pd.read_csv(p["comtrade_monthly"], dtype={"code": str})
    rel_m = pd.read_csv(p["monthly_release_dates"])
    rel_m["first_released"] = pd.to_datetime(rel_m.first_released, format="ISO8601")
    rows = []
    for _, c in corridors.iterrows():
        for _, k in codes.iterrows():
            t = rb2.part_a_timeline(monthly, ct, release, ctm, rel_m, int(c.hmrc_country_id),
                                    int(c.comtrade_code), k.code, live.START, run3.RUN)
            for per, r in t.iterrows():
                rows.append({"hmrc_country_id": int(c.hmrc_country_id), "code": k.code,
                             "month": int(per.strftime("%Y%m")),
                             "status": "lead" if r.lead else ("watch" if r.uk_signal else "none")})
    return pd.DataFrame(rows)


def rates(h: pd.DataFrame, step: int, since: int | None) -> dict:
    """Empirical P(status after `step` month ends | status now), pooled over series."""
    w = h.pivot_table(index=["hmrc_country_id", "code"], columns="month", values="status", aggfunc="first")
    months = sorted(w.columns)
    counts = {a: {b: 0 for b in STATUSES} for a in STATUSES}
    for i in range(len(months) - step):
        m0, m1 = months[i], months[i + step]
        if since is not None and m0 < since:
            continue
        for a, b in zip(w[m0], w[m1]):
            counts[a][b] += 1
    out = {}
    for a in STATUSES:
        n = sum(counts[a].values())
        out[a] = {"n": n, **{b: (counts[a][b] / n if n else None) for b in STATUSES},
                  "counts": counts[a]}
    return out


def binom_interval(n: int, p: float, level: float = 0.90) -> tuple[int, int]:
    """Central interval of a Binomial(n, p): the smallest k_lo, k_hi with tail mass at most
    (1 - level) / 2 on each side."""
    if n == 0:
        return 0, 0
    pmf = [math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(n + 1)]
    tail = (1 - level) / 2
    lo, acc = 0, 0.0
    for k in range(n + 1):
        acc += pmf[k]
        if acc > tail:
            lo = k
            break
    hi, acc = n, 0.0
    for k in range(n, -1, -1):
        acc += pmf[k]
        if acc > tail:
            hi = k
            break
    return lo, hi


def main() -> int:
    h = histories()
    run3 = pd.read_csv(RUN3_OUT, dtype={"code": str})
    last = h[h.month == int(h.month.max())][["hmrc_country_id", "code", "status"]]
    chk = run3[["hmrc_country_id", "code", "status", "display", "country", "description"]].merge(
        last, on=["hmrc_country_id", "code"], suffixes=("", "_rebuilt"))
    if len(chk) != 162 or not (chk.status == chk.status_rebuilt).all():
        raise SystemExit("the rebuilt histories do not reproduce run 3's statuses")
    one = rates(h, 1, RECENT_FROM)
    two = rates(h, 2, RECENT_FROM)
    one_all, two_all = rates(h, 1, None), rates(h, 2, None)
    reg = chk.drop(columns=["status_rebuilt"]).copy()
    for s in STATUSES:
        reg[f"p_r4_{s}"] = reg.status.map(lambda a, s=s: one[a][s])
        reg[f"p_r5_{s}"] = reg.status.map(lambda a, s=s: two[a][s])
    reg = reg.sort_values(["status", "hmrc_country_id", "code"]).reset_index(drop=True)
    reg.to_csv(OUT, index=False)

    n = {s: int((reg.status == s).sum()) for s in STATUSES}
    expect = {}
    for label, rt in (("r4", one), ("r5", two)):
        e = {}
        for a in STATUSES:
            for b in STATUSES:
                p = rt[a][b] or 0.0
                lo, hi = binom_interval(n[a], p)
                e[f"{a}_to_{b}"] = {"n": n[a], "p": round(p, 4), "expected": round(n[a] * p, 2),
                                    "interval_90": [lo, hi]}
        e["leads_total"] = {"expected": round(sum(n[a] * (rt[a]["lead"] or 0.0) for a in STATUSES), 2)}
        expect[label] = e
    summary = {
        "written": "21 October 2026, before HMRC's 12 November 2026 release (September data)",
        "run3_counts": n,
        "run3_shown": {s: int(((reg.status == s) & reg.display).sum()) for s in ("lead", "watch")},
        "primary_window": "transitions from the October 2025 month end to the October 2026 month end",
        "rates_one_run": one, "rates_two_runs": two,
        "secondary_rates_one_run_since_2022": one_all, "secondary_rates_two_runs_since_2022": two_all,
        "expected": expect,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"run3_counts": n, "one_run": {a: {b: one[a][b] for b in STATUSES} | {"n": one[a]["n"]} for a in STATUSES},
                      "expected_r4": {k: v for k, v in expect["r4"].items() if k.startswith(("lead_to", "watch_to_lead", "none_to_lead")) or k == "leads_total"}},
                     indent=1))
    print("A rise in exports is a lead, not evidence of a breach.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
