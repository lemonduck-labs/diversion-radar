"""radar/onward.py, the one source for why an onward check did not pass, and the R3.4
corrections that use it: both checks shown, the case window's tag, the small-onward limit.

A rise in exports is a lead, not evidence of a breach.
"""
import json
from pathlib import Path

import pandas as pd
import pytest

from radar import onward
from radar.brief.context import _conduct_ended_by, _end_stated

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo" / "radar"


def test_reasons_follow_the_rule():
    assert onward.why_not(0, 50_000) == [onward.NO_EXPORTS]
    assert onward.why_not(float("nan"), 0) == [onward.NO_EXPORTS]
    assert onward.why_not(99_999, 0) == [onward.FLOOR]                   # a zero baseline: the floor alone
    assert onward.why_not(150_000, 100_000) == [onward.RATIO]
    assert onward.why_not(50_000, 40_000) == [onward.FLOOR, onward.RATIO]
    assert onward.why_not_text(50_000, 40_000) == "under the $100,000 floor and under 2x the 2019-21 average"
    assert onward.why_not_short(50_000, 40_000) == "under $100k and under 2x"
    with pytest.raises(ValueError):
        onward.why_not(200_000, 100_000)                                   # exactly 2x and over the floor passes


def test_conduct_end_counts_only_when_stated():
    p = pd.Period("2024-03", freq="M")
    case = lambda end, stated: pd.Series({"conduct_end": end, "conduct_as_stated": stated})
    assert _conduct_ended_by(case("2023-05", "January 2020 to May 2023"), p)
    assert _conduct_ended_by(case("2023", "2022 and 2023"), p)            # a year counts as its December
    assert not _conduct_ended_by(case("2024", "2023 and 2024"), p)
    assert not _conduct_ended_by(case("not stated", "not stated"), p)
    # an end the register worked out, not one its source states (R3.5)
    assert not _conduct_ended_by(case("2023-02", "period not stated; messages cited run from 15 Sep 2022 to 23 Feb 2023"), p)


def test_which_cases_state_an_end():
    """R3.5: checked by hand against the register's conduct_as_stated, case by case."""
    cases = pd.read_csv(ROOT / "backtest" / "data" / "cases.csv")
    stated = sorted(r.case_id for r in cases.itertuples() if _end_stated(r.conduct_as_stated))
    assert stated == ["EU-03", "EU-05", "UK-07", "US-03", "US-07", "US-08", "US-09"]


def test_leads_carry_both_checks_with_the_shared_reasons():
    leads = json.loads((DEMO / "leads.json").read_text())
    for x in leads:
        a, m = x["onward_annual"], x["onward_monthly"]
        for c in filter(None, (a, m)):
            assert (c["why_not"] is None) == c["passes"]
        if x["status"] == "watch":
            assert not a["passes"] and not (m and m["passes"])
            assert x["onward_check"].startswith("not passed: annual")
            if a["no_exports"]:
                assert "none reported" in x["onward_check"].split(";")[0]
    by = {x["series"]: x for x in leads}
    # A lead on its 2025 figures whose latest 12 months do not pass (R3.4)
    india = by["India 854231"]
    assert india["onward_annual"]["passes"] and not india["onward_monthly"]["passes"]
    assert india["onward_monthly"]["why_not"] == onward.RATIO


def test_brief_contexts_tag_the_case_window_and_flag_small_onward_flows():
    ctx = {p.stem: json.loads(p.read_text()) for p in (DEMO / "briefs").glob("*.json") if p.stem != "index"}
    lim = {k: {l["id"]: l for l in c["limits"]} for k, c in ctx.items()}
    # EU-01 and US-01 state no end to their conduct, and every EU-05 route links US-01 (R3.5)
    windows = {k: v["limit.case_window"] for k, v in lim.items() if "limit.case_window" in v}
    assert windows and all(w["confidence"] == "Likely" for w in windows.values())
    assert "may have run past" not in json.dumps(windows)
    small = sorted(k for k, v in lim.items() if "limit.small_onward" in v)
    assert small == ["india-851762", "india-854231", "thailand-851762", "united-arab-emirates-854232"]
    for k in small:
        assert lim[k]["limit.small_onward"]["confidence"] == "Likely"
        assert "at any exchange rate above $" in lim[k]["limit.small_onward"]["text"]
        assert ctx[k]["status"] == "lead"
    check = {f["id"]: f for f in ctx["india-854231"]["facts"]}["onward.check"]["text"]
    assert "the monthly check did not pass" in check
