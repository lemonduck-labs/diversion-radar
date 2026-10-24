"""Evaluation of the research signals, as pre-registered in radar/signals/RESEARCH.md (S0).

- Cases: the eight tests in backtest/data/test_plan.csv. A test is hit when the signal is on for
  its corridor and any of its codes at a run whose end falls before the reference date. Lead
  times use run 1's months_to (scripts/run_backtest.py), so they compare with runs 1 and 2.
- Cost: series ever flagged and runs flagged, beside run 2's 20 series ever a lead and 300 lead
  runs, and the same counted only at runs whose window passes the display rule.
- Placebo: series ever flagged in the 36 peacetime runs against the first 36 war-time runs.
- Verdicts: the success criteria in S0, as written.

A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

import importlib.util
from functools import lru_cache

import pandas as pd

from radar import display
from radar.signals import common

NEW_FLAG_MAX_SERIES = 30          # of 81 (1.5x run 2's 20)
NEW_FLAG_MAX_SERIES_S2 = 20       # of 54
FILTER_MAX_SERIES = 13            # run 2's 20, cut to 13 or fewer
EARLIER_BY = 3                    # months earlier than run 2's first lead
PLACEBO_SHARE = 0.5


@lru_cache(maxsize=None)
def script(name: str):
    """A module from scripts/, loaded as run 2 loads run 1 (the scripts are not a package)."""
    spec = importlib.util.spec_from_file_location(f"signals_{name}", common.ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _period(x) -> pd.Period | None:
    return pd.Period(x, freq="M") if isinstance(x, str) and x else None


def test_shown_outside(monthly: pd.DataFrame, plan: pd.DataFrame, run_index: pd.PeriodIndex,
                       lag: int = common.LAG) -> dict[str, bool]:
    """Whether a test may be shown outside the repo at all (backtest/RESEARCH_LOG.md, N6): its UK
    flow at the last run before the reference date passes the display rule for at least one of
    its codes."""
    out = {}
    for t in plan.itertuples():
        ref = pd.Timestamp(t.reference_date)
        last = [p for p in run_index if p.end_time < ref][-1]
        end = last - lag
        ok = False
        for code in str(t.codes).split(";"):
            total, months = display.window_stats(monthly, int(t.hmrc_country_id), code,
                                                 end.year * 100 + end.month)
            ok |= display.displayable(total, months)[0]
        out[t.test_id] = bool(ok)
    return out


def evaluate_tests(flags: dict, plan: pd.DataFrame, run2: pd.DataFrame, label: str,
                   applicable: set[str] | None = None, shown_outside: dict | None = None,
                   shown: dict | None = None, run2_first_shown: dict | None = None) -> pd.DataFrame:
    """One row per test. flags maps (HMRC country id, code) to a boolean series by run.

    With shown (the display rule at each run) the first flag before the reference date at a run
    that passes it is reported too, against run 2's first lead that passes it (run2_first_shown,
    test id to period). That comparison is not one of S0's criteria: it says what could be shown."""
    r1 = script("run_backtest")
    run2 = run2.set_index("test_id")
    rows = []
    for t in plan.itertuples():
        cid = int(t.hmrc_country_id)
        ref = pd.Timestamp(t.reference_date)
        codes = [c for c in str(t.codes).split(";") if applicable is None or c in applicable]
        r2 = run2.loc[t.test_id]
        r2_first = _period(r2.first_lead_before)
        row = {"signal": label, "test_id": t.test_id, "case_id": t.case_id, "role": t.role,
               "country": t.country, "codes": t.codes, "reference_date": t.reference_date,
               "run2_outcome": r2.outcome, "run2_first_lead": str(r2_first) if r2_first is not None else "",
               "run2_lead_time_months": r2.lead_time_months,
               "shown_outside": None if shown_outside is None else shown_outside[t.test_id]}
        if not codes:
            rows.append({**row, "applicable": False, "outcome": "not applicable"})
            continue
        first_before = first_any = None
        on_last, codes_hit = False, []
        for code in codes:
            s = flags[(cid, code)]
            b = s[[p.end_time < ref for p in s.index]]
            fb, fa = r1.first(b.index[b.values]), r1.first(s.index[s.values])
            first_before, first_any = r1.earliest(first_before, fb), r1.earliest(first_any, fa)
            if len(b):
                on_last |= bool(b.iloc[-1])
            if fb is not None:
                codes_hit.append(code)
        hit = first_before is not None
        earlier = (r2_first - first_before).n if hit and r2_first is not None else None
        beats = bool(t.role == "primary" and hit and (r2_first is None or earlier >= EARLIER_BY))
        out = {**row, "applicable": True, "outcome": "hit" if hit else "miss",
               "first_flag_before": str(first_before) if hit else "",
               "lead_time_months": r1.months_to(first_before, ref),
               "on_at_last_run_before": bool(on_last),
               "first_flag_any_time": str(first_any) if first_any is not None else "",
               "months_earlier_than_run2": earlier, "beats_run2": beats,
               "codes_flagged_before": ";".join(codes_hit)}
        if shown is not None:
            fs = None
            for code in codes:
                s = flags[(cid, code)] & shown[(cid, code)]
                b = s[[p.end_time < ref for p in s.index]]
                fs = r1.earliest(fs, r1.first(b.index[b.values]))
            r2s = (run2_first_shown or {}).get(t.test_id)
            out.update({"first_shown_before": str(fs) if fs is not None else "",
                        "lead_time_shown_months": r1.months_to(fs, ref),
                        "run2_first_shown": str(r2s) if r2s is not None else "",
                        "months_earlier_shown": (r2s - fs).n if fs is not None and r2s is not None else None})
        rows.append(out)
    return pd.DataFrame(rows)


def cost(flags: dict, shown: dict | None = None, named: dict | None = None) -> dict:
    """Series ever flagged and runs flagged; with shown, the same at runs whose window passes
    the display rule; with named, at runs where the series may be named outside the repo."""
    out = {"series": len(flags), "series_ever": sum(bool(s.any()) for s in flags.values()),
           "runs_flagged": sum(int(s.sum()) for s in flags.values())}
    if shown is not None:
        both = {k: s & shown[k] for k, s in flags.items()}
        out["series_ever_shown"] = sum(bool(s.any()) for s in both.values())
        out["runs_shown"] = sum(int(s.sum()) for s in both.values())
    if named is not None:
        out["series_ever_named"] = sum(bool(s.any()) for s in named.values())
        out["runs_named"] = sum(int(s.sum()) for s in named.values())
    return out


def placebo(peace: dict, war: dict) -> dict:
    p = sum(bool(s.any()) for s in peace.values())
    w = sum(bool(s.any()) for s in war.values())
    return {"peace_series_ever": p, "war_series_ever": w,
            "peace_runs": sum(int(s.sum()) for s in peace.values()),
            "war_runs": sum(int(s.sum()) for s in war.values()),
            "passes": bool(p <= PLACEBO_SHARE * w)}


def verdict_new_flag(tests: pd.DataFrame, cost_: dict, placebo_: dict | None, max_series: int) -> dict:
    c1 = bool(tests.get("beats_run2", pd.Series(dtype=bool)).fillna(False).astype(bool).any())
    c2 = bool(cost_["series_ever"] <= max_series)
    c3 = None if placebo_ is None else bool(placebo_["passes"])
    return {"c1_beats_run2_on_a_primary_test": c1, "c2_series_at_most": max_series,
            "c2_series_flagged": cost_["series_ever"], "c2": c2,
            "c3_placebo": "not computable" if c3 is None else c3,
            "recommended": bool(c1 and c2 and (c3 is None or c3))}


def verdict_filter(tests: pd.DataFrame, run2_tests: pd.DataFrame, cost_: dict) -> dict:
    kept = []
    for t in run2_tests.itertuples():
        if t.role == "primary" and t.outcome == "hit":
            kept.append((t.test_id, bool((tests[tests.test_id == t.test_id].outcome == "hit").any())))
    keeps = all(k for _, k in kept)
    cuts = bool(cost_["series_ever"] <= FILTER_MAX_SERIES)
    return {"primary_hits_kept": {k: v for k, v in kept}, "keeps_every_primary_hit": keeps,
            "series_ever_a_lead": cost_["series_ever"], "at_most": FILTER_MAX_SERIES, "cuts": cuts,
            "recommended": bool(keeps and cuts)}
