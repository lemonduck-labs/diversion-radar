"""The workspace's current run, run 3 (backtest/RESEARCH_LOG.md, R3.1 and R3.2), in the radar's
datasets: scripts/build_demo_data.py with --variant run3, against the same build of run 2.

Both variants are built in memory once for the module (about 20 seconds)."""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo" / "radar"
LIVE3 = ROOT / "data" / "processed" / "live_2026-10_run3.csv"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import build_demo_data as bdd  # noqa: E402
from backtest import asof  # noqa: E402
from radar import display  # noqa: E402

pytestmark = pytest.mark.skipif(not LIVE3.exists(), reason="run scripts/run_live_run3.py first")
RUN = 202610
ORIGINAL = set(pd.read_csv(ROOT / "config" / "countries.csv").query("role == 'corridor'").name)
LIVE_DATASETS = ("summary", "leads", "history", "onward_years")
BACKTEST_DATASETS = ("tests", "cases", "placebo", "cost")


@pytest.fixture(scope="module")
def builds():
    return {v: bdd.build(RUN, "run2", v) for v in ("run2", "run3")}


def _country(series: str) -> str:
    return series.rsplit(" ", 1)[0]


def _text(rows) -> str:
    return json.dumps(rows, indent=1)


def test_the_workspace_shows_run3_and_demo_radar_is_its_build(builds):
    assert bdd.CURRENT == "run3"
    assert bdd.live_table(RUN) == LIVE3
    for name, rows in builds["run3"].items():
        assert (DEMO / f"{name}.json").read_text() == _text(rows), f"rebuild demo/radar/{name}.json"


def test_the_backtest_datasets_are_the_same_byte_for_byte(builds):
    for name in BACKTEST_DATASETS:
        assert _text(builds["run3"][name]) == _text(builds["run2"][name]), name


def test_the_original_nine_rows_are_run2s(builds):
    for name in ("leads", "history", "onward_years"):
        run2 = builds["run2"][name]
        assert run2 and all(_country(x["series"]) in ORIGINAL for x in run2), name
        run3 = [x for x in builds["run3"][name] if _country(x["series"]) in ORIGINAL]
        assert run3 == run2, name


def test_the_counts_are_r31s_and_r32s(builds):
    s = builds["run3"]["summary"][0]
    assert (s["variant"], s["rule"], s["series"], s["corridors"], s["codes"]) == ("run3", "run2", 162, 18, 9)
    assert s["monthly_corridors"] == 16 and builds["run2"]["summary"][0]["monthly_corridors"] == 7
    assert (s["leads"], s["leads_shown"], s["leads_held"]) == (9, 7, 2)
    assert (s["watch"], s["watch_shown"], s["watch_held"]) == (26, 16, 10)
    assert s["ever_lead"] == 35
    leads = builds["run3"]["leads"]
    assert sum(x["status"] == "lead" for x in leads) == 7 and sum(x["status"] == "watch" for x in leads) == 16
    new_leads = {x["series"] for x in leads if x["status"] == "lead" and _country(x["series"]) not in ORIGINAL}
    assert new_leads == {"India 851762", "Thailand 851762", "India 854231", "China 853221"}


def test_series_held_back_are_counted_never_shown(builds):
    live = pd.read_csv(LIVE3, dtype={"code": str})
    flagged = live[live.status != "none"]
    held = {f"{r.country} {r.code}" for r in flagged[~flagged.display].itertuples()}
    shown = {f"{r.country} {r.code}" for r in flagged[flagged.display].itertuples()}
    s = builds["run3"]["summary"][0]
    assert len(held) == s["leads_held"] + s["watch_held"] == 12
    for name in ("leads", "history", "onward_years"):
        assert {x["series"] for x in builds["run3"][name]} == shown, name
    text = json.dumps({k: builds["run3"][k] for k in LIVE_DATASETS})
    for series in held:
        assert series not in text, series


def test_no_uk_figure_for_a_run_held_back_or_in_a_case_window(builds):
    routes = bdd.variant("run3").routes
    hist = builds["run3"]["history"]
    for h in hist:
        if not h["shown"]:
            assert h["not_shown_because"]
            assert (h["uk_trailing12_gbp"], h["uk_signal"], h["onward_signal"], h["lead"]) == (None,) * 4
    ids = dict(pd.read_csv(LIVE3)[["country", "hmrc_country_id"]].drop_duplicates().itertuples(index=False))
    on_routes = 0
    for x in builds["run3"]["leads"]:
        route = display.route_for(routes, int(ids[x["country"]]), x["code"])
        assert (route[0] if route else "") == x["case_route"], x["series"]
        if not route:
            continue
        on_routes += 1
        rows = [h for h in hist if h["series"] == x["series"]]
        for h in rows:
            start = display.window_start(pd.Period(h["run"][:7], freq="M"), asof.UK_LAG_MONTHS)
            if not start > route[1]:
                assert not h["shown"] and h["not_shown_because"] == display.CASE_WINDOW_REASON, (x["series"], h["run"])
                assert h["uk_trailing12_gbp"] is None
        assert any(h["not_shown_because"] == display.CASE_WINDOW_REASON for h in rows), x["series"]
    assert on_routes == 12  # six on the original nine, six on the nine added (R3.1)
