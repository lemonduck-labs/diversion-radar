"""Run 4's prediction register (backtest/RESEARCH_LOG.md, R4): the files written before the
November and December 2026 releases agree with run 3 and with each other."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "backtest" / "data" / "r4_register.csv"
SUMMARY = ROOT / "backtest" / "data" / "r4_register_summary.json"
RUN3 = ROOT / "data" / "processed" / "live_2026-10_run3.csv"
STATUSES = ("lead", "watch", "none")


@pytest.fixture(scope="module")
def reg():
    return pd.read_csv(REG, dtype={"code": str})


@pytest.fixture(scope="module")
def summary():
    return json.loads(SUMMARY.read_text())


def test_every_run3_series_once_with_its_status(reg):
    run3 = pd.read_csv(RUN3, dtype={"code": str})
    m = run3.merge(reg, on=["hmrc_country_id", "code"], suffixes=("", "_reg"))
    assert len(reg) == 162 and len(m) == 162
    assert (m.status == m.status_reg).all()
    assert (m.display == m.display_reg).all()


@pytest.mark.parametrize("run", ["r4", "r5"])
def test_probabilities_sum_to_one(reg, run):
    total = sum(reg[f"p_{run}_{s}"] for s in STATUSES)
    assert (total - 1).abs().max() < 1e-9


def test_rates_come_from_counts(summary):
    for key in ("rates_one_run", "rates_two_runs"):
        for a in STATUSES:
            r = summary[key][a]
            assert sum(r["counts"].values()) == r["n"]
            for b in STATUSES:
                assert r[b] == pytest.approx(r["counts"][b] / r["n"])


def test_expected_counts_sit_inside_their_intervals(summary):
    n = summary["run3_counts"]
    assert n == {"lead": 9, "watch": 26, "none": 127}
    for run in ("r4", "r5"):
        for k, v in summary["expected"][run].items():
            if k == "leads_total":
                continue
            lo, hi = v["interval_90"]
            assert lo <= v["expected"] <= hi or v["n"] == 0
            assert v["n"] == n[k.split("_to_")[0]]


def test_pre_registered_headline(summary):
    e = summary["expected"]["r4"]["lead_to_lead"]
    assert (e["expected"], e["interval_90"]) == (8.25, [7, 9])
