"""The radar demo's datasets (demo/radar/*.json) follow the display rule and the case rules.

Rebuild them first with scripts/run_live.py and scripts/build_demo_data.py."""
import json
import re
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parent.parent / "demo" / "radar"
pytestmark = pytest.mark.skipif(not (DEMO / "history.json").exists(), reason="demo data not built")


def _load(name):
    return json.loads((DEMO / f"{name}.json").read_text())


def test_no_uk_figure_or_flag_where_a_run_is_not_shown():
    for h in _load("history"):
        if not h["shown"]:
            assert h["uk_trailing12_gbp"] is None and h["lead"] is None and h["uk_signal"] is None
            assert h["not_shown_because"]


def test_every_run_drawn_passes_the_size_rule():
    summary = _load("summary")[0]
    for h in _load("history"):
        if h["shown"]:
            assert h["uk_trailing12_gbp"] >= summary["display_min_gbp"]


def test_lead_counts_come_from_shown_runs_only():
    hist = _load("history")
    for s in _load("leads"):
        shown = [h for h in hist if h["series"] == s["series"] and h["shown"]]
        assert len(shown) == s["runs_shown"]
        assert sum(1 for h in shown if h["lead"]) == s["runs_shown_as_lead"]


def test_held_back_tests_carry_no_month_or_lead_time():
    for t in _load("tests"):
        for run in ("run1", "run2"):
            if t[f"{run}_outcome"] == "hit, held back":
                assert t[f"{run}_first_lead"] == "" and t[f"{run}_lead_time_months"] is None


def test_cases_carry_no_per_person_detail_or_links():
    text = json.dumps(_load("cases")).lower()
    assert not re.search(r"sentenc|custod|defendant|http", text)


def test_no_em_dashes_in_the_page_or_data():
    for f in list(DEMO.glob("*.json")) + [DEMO / "index.html"]:
        assert "\u2014" not in f.read_text(), f.name
