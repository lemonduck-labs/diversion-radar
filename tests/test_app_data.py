"""Checks on what the radar workspace (app/) publishes.

The workspace ships its data beside the page. These tests hold it to the same rules as the
dashboard: the display rule decides what UK detail is shown, onward checks match the live
run's verdicts, the synthetic exporter file describes no one, and the page carries the OGL
line and the house line.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

pytestmark = pytest.mark.skipif(not (APP / "data" / "signals.json").exists(),
                                reason="run scripts/build_app_data.py first")


def _load(name):
    return json.loads((APP / "data" / f"{name}.json").read_text())


def _live():
    """The live table of the run the workspace shows (run 3 now: 18 corridors, 162 series)."""
    from build_app_data import live_path
    s = _load("summary")[0]
    return pd.read_csv(live_path(s["run"], s["variant"]), dtype={"code": str})


def test_copied_files_match_the_reviewed_demo_data():
    for name in ["summary", "leads", "history", "onward_years", "tests", "cases", "placebo", "cost"]:
        assert (APP / "data" / f"{name}.json").read_bytes() == (ROOT / "demo" / "radar" / f"{name}.json").read_bytes(), name


def test_uk_detail_follows_the_display_rule():
    from radar import display
    summary = _load("summary")[0]
    live = _live()
    rows = {(r["country"], r["code"]): r for r in _load("signals")}
    assert summary["variant"] == "run3"
    assert len(rows) == len(live) == summary["series"] == 162
    for r in live.itertuples():
        s = rows[(r.country, r.code)]["uk"]
        flagged = r.status in ("lead", "watch")
        ok = bool(r.display) if flagged else display.displayable(float(r.uk_trailing12_gbp), int(r.uk_months_with_exports))[0]
        assert s["shown"] == ok, (r.country, r.code)
        if not ok:
            assert s == {"shown": False, "status": "not shown (display rule)"}
        elif flagged:
            assert s["status"] == r.status and s["trailing12_gbp"] >= display.MIN_DISPLAY_GBP
            assert s["months_with_exports"] >= display.MIN_DISPLAY_MONTHS
        else:
            # A series that passes the size test but is not flagged gets a status, no figures.
            assert s == {"shown": True, "status": "not flagged"}


def test_shown_flagged_series_are_the_dashboard_leads():
    leads = {(l["country"], l["code"]) for l in _load("leads")}
    shown = {(s["country"], s["code"]) for s in _load("signals") if s["uk"]["status"] in ("lead", "watch")}
    assert shown == leads


def test_a_series_not_shown_carries_nothing_from_the_radar():
    # N7: with the onward check given for a series not shown, a held-back lead could be told
    # apart from the other series not shown.
    rows = _load("signals")
    hidden = [s for s in rows if not s["uk"]["shown"]]
    assert hidden and all(s["onward"] == {"shown": False, "status": "not shown (display rule)"} for s in hidden)
    assert all(set(s) == {"country", "iso2", "code", "description", "uk_data_to", "uk", "onward"} for s in rows)
    assert all("run1_rule" not in k for k in _load("summary")[0])


def test_onward_checks_match_the_live_run():
    from build_app_data import check_passes
    live = _live().set_index(["country", "code"])
    for s in _load("signals"):
        if not s["uk"]["shown"]:
            continue
        r = live.loc[(s["country"], s["code"])]
        o = s["onward"]
        assert o["shown"] is True
        assert o["signal"] == bool(r.onward_signal)
        assert o["signal"] == (o["annual"]["passes"] or bool(o["monthly"] and o["monthly"]["passes"]))
        for c in [o["annual"]] + ([o["monthly"]] if o["monthly"] else []):
            assert (c["why_not"] is None) == c["passes"]
            if c["usd"] is not None and abs(c["usd"] - 100_000) >= 1:
                # Values are rounded to whole dollars; only a value within a dollar of the
                # floor could flip on rounding.
                assert check_passes(c["usd"], c["base_usd"]) == c["passes"]


def test_corridors_are_the_runs_with_their_spellings():
    from build_app_data import countries_path
    s = _load("summary")[0]
    c = _load("corridors")[0]
    countries = pd.read_csv(countries_path(s["variant"]))
    assert [x["iso2"] for x in c["corridors"]] == list(countries[countries.role == "corridor"].iso2)
    assert len(c["corridors"]) == s["corridors"] == 18
    spellings = {a.lower(): x["iso2"] for x in c["corridors"] for a in x["aliases"]}
    for alias, iso in (("Viet Nam", "VN"), ("Hong Kong SAR", "HK"), ("Hong Kong, China", "HK"), ("Macao SAR", "MO"),
                       ("Macau", "MO"), ("PRC", "CN"), ("China", "CN"), ("Kyrgyzstan", "KG"), ("UAE", "AE")):
        assert spellings[alias.lower()] == iso, alias
    assert "republic of china" not in spellings  # Taiwan's name, not China's
    # No spelling, ISO code included, points at two places.
    every = [a.lower() for x in c["corridors"] for a in x["aliases"]] + [x["iso2"].lower() for x in c["corridors"]]
    stops = [a.lower() for x in c["stop"] for a in x["aliases"]] + [x["iso2"].lower() for x in c["stop"]]
    assert len(every) == len(set(every)) and not set(every) & set(stops)
    assert {x["iso2"] for x in c["stop"]} == {"RU", "BY"}


def test_synthetic_sample_reaches_a_corridor_run3_added():
    text = (APP / "data" / "synthetic_shipments.csv").read_text()
    rows = list(csv.DictReader(text.splitlines()))
    by_dest = {}
    for r in rows:
        by_dest.setdefault(r["destination"], set()).add(r["customer_ref"])
    assert by_dest["India"] == {"SYN-C0123"} and by_dest["Hong Kong SAR"] == {"SYN-C0127"}
    sig = {(x["iso2"], x["code"]): x for x in _load("signals")}
    assert sig[("IN", "851762")]["onward"]["signal"] is True and sig[("HK", "854232")]["onward"]["signal"] is False


def test_synthetic_exporter_file_describes_no_one():
    from fdcore.guardrails import scan_text
    text = (APP / "data" / "synthetic_shipments.csv").read_text()
    rows = list(csv.DictReader(text.splitlines()))
    assert len(rows) > 100
    assert all(r["order_ref"].startswith("SYN-") and r["customer_ref"].startswith("SYN-") for r in rows)
    assert {"order_ref", "customer_ref", "destination", "commodity_code", "month", "value_gbp"} == set(rows[0])
    assert scan_text(text, "synthetic_shipments.csv", skip=["phone"]) == []


def test_synthetic_file_is_reproducible():
    from build_app_data import synthetic_rows
    assert synthetic_rows() == synthetic_rows()


def test_manifest_hashes_every_published_file():
    m = _load("manifest")[0]
    for rel, digest in m["files"].items():
        assert hashlib.sha256((APP / rel).read_bytes()).hexdigest() == digest, rel
    published = {str(p.relative_to(APP)) for p in (APP / "data").rglob("*") if p.is_file() and p.name != "manifest.json"}
    assert published <= set(m["files"])


def test_page_carries_the_licence_and_house_lines_and_no_em_dash():
    page = (APP / "index.html").read_text()
    assert "\u2014" not in page
    assert "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/" in page
    assert "Contains public sector information licensed under the" in page
    assert "A rise in exports is a lead, not evidence of a breach." in page
    head = page[:8192]
    assert re.search(r"<title>[^<]{3,60}</title>", head)
    assert '<meta name="claude:viewport-fit-sides" content="cover">' in head
    assert "padding-left: max(16px, env(safe-area-inset-left, 0px))" in page
    assert "padding-right: max(16px, env(safe-area-inset-right, 0px))" in page
    # The viewer never shows browser dialogs or prints, and the platform adds the skeleton.
    for bad in (r"(?<![\w.])alert\(", r"(?<![\w.])confirm\(", r"(?<![\w.])prompt\(", r"window\.print", r"<!doctype", r"<html", r"<body"):
        assert not re.search(bad, page, re.I), bad


def test_data_files_hold_no_names_or_personal_data():
    from fdcore.guardrails import scan_text
    for p in (APP / "data").glob("*.json"):
        if p.name == "cases.json":
            continue  # official outcomes, screened under the policy line for official outcomes
        assert scan_text(p.read_text(), p.name, skip=["phone"]) == [], p.name
