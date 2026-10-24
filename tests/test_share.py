"""The shared copies (share/) are current and leak nothing the display rule or the case rules
hold back: scripts/build_share.py writes them and checks them, and these tests check the checks."""
import csv
import io
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_share as B  # noqa: E402


def test_share_folder_is_current():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_share.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_held_back_series_and_hidden_test_is_known_to_the_check():
    held = B.held_back_series()
    assert len(held) >= 12      # the twelve held back at the October 2026 run of run 3
    hidden = B.hidden_tests()
    assert len(hidden) == 2 and all(t["corridor"] and t["codes"] for t in hidden)


def test_the_shared_data_give_a_hidden_test_no_route():
    import json
    tests = json.loads((ROOT / "app" / "data" / "tests.json").read_text(encoding="utf-8"))
    hidden = [t for t in tests if not t["shown"]]
    assert len(hidden) == 2 and all(t["corridor"] == "" for t in hidden)
    assert all(t["run1_outcome"] == t["run2_outcome"] == "not shown (display rule)" for t in hidden)


def _dotted(code):
    return f"{code[:4]}.{code[4:]}" if len(code) == 6 else code


def test_the_check_reads_a_sentence_across_lines():
    country, code = sorted(B.held_back_series())[0]
    text = f"{country}'s figures hold none for 2019: at the October run its\n  baselines are USD 3 for {_dotted(code)}."
    assert any("in one sentence" in p for p in B.problems({"x.md": text}))


def test_the_check_catches_a_hidden_lead_time_by_subtraction(monkeypatch):
    # Made-up lead times: the check is tested on its own logic, not on the record.
    monkeypatch.setattr(B, "hidden_only_lead_times", lambda root=None, hidden=None: {7})
    text = "| X | Run | Yes | Current | lead times 2, 5 and 7 months |"
    assert any("only a hidden test has" in p for p in B.problems({"x.md": text}))
    assert not any("only a hidden test has" in p for p in B.problems({"x.md": "Lead times of the tests shown: 2 and 5 months."}))


def test_the_check_catches_a_lead_named_at_a_run_the_rule_holds_back():
    country, code, ym = sorted(B.small_first_leads())[0]
    month = B._month_forms(ym)[0]
    text = f"In the series table, {country} {_dotted(code)} becomes a lead from {month}."
    assert any("a run the display rule holds back" in p for p in B.problems({"x.md": text}))


def test_the_check_catches_a_uk_figure_beside_a_case_period():
    (country, code), (ids, ref) = sorted(B.test_routes().items())[0]
    month = B._month_forms(ref)[0]
    bad = f"{ids[0]}'s run of {month} passes (GBP 300,001)."
    assert any("before its first public action" in p for p in B.problems({"x.md": bad}))
    ok = f"It now names {country} {_dotted(code)} ($123k against £456k) at the October 2026 run."
    assert not any("before its first public action" in p for p in B.problems({"x.md": ok}))


def test_the_licence_line_links_to_the_licence():
    assert any("no link to the licence" in p for p in B.problems({"x.md": "Contains public sector information licensed under the Open Government Licence v3.0."}))
    assert B.problems({"x.md": "Licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)."}) == []


@pytest.mark.parametrize("line, why", [
    ("{country} {dotted} was a lead at 12 runs.", "names a series"),
    ("Exports of {dotted} to {country} rose.", "names a series"),
    ("{country}, {dotted} | Hit |", "names a series"),
    ("{test} is named here.", "by its id"),
    ("See https://example.org/case for the record.", "a URL"),
    ("The window held £111,111 of exports.", "under the display rule"),
    ("UK exports of GBP 123,456 in 10 months.", "under the display rule"),
])
def test_the_check_catches_what_must_not_leave(line, why):
    country, code = sorted(B.held_back_series())[0]
    dotted = f"{code[:4]}.{code[4:]}" if len(code) == 6 else code
    test = B.hidden_tests()[0]["test_id"]
    text = line.format(country=country, dotted=dotted, test=test)
    found = B.problems({"x.md": text})
    assert any(why in p for p in found), (text, found)


@pytest.mark.parametrize("line", [
    "Rules: at least £20,000 above the baseline, and at least £250,000 in the window to be shown.",
    "HMRC ids from the uktradeinfo API's country list (`https://api.uktradeinfo.com/Country`).",
    "The nine added: 4 leads (all shown) and 17 watch items, 4 held back, counted, not shown.",
])
def test_the_check_passes_what_may_leave(line):
    assert B.problems({"x.md": line}) == []


def test_the_case_register_copy_cites_official_references_only():
    rows = list(csv.DictReader(io.StringIO((ROOT / "share" / "cases.csv").read_text(encoding="utf-8"))))
    src = list(csv.DictReader((ROOT / "backtest" / "data" / "cases.csv").open(encoding="utf-8")))
    assert [r["case_id"] for r in rows] == [r["case_id"] for r in src]
    assert not set(B.DROPPED_COLUMNS) & set(rows[0])
    assert all(r["official_reference"] for r in rows)
    assert not any("http" in v for r in rows for v in r.values())


def test_a_case_that_did_not_end_in_an_outcome_stops_the_build(tmp_path):
    src = (ROOT / "backtest" / "data" / "cases.csv").read_text(encoding="utf-8").splitlines()
    head, first = src[0], next(csv.DictReader(io.StringIO("\n".join(src[:2]))))
    first.update(enforcement_stage="charged", outcome="charges pending", status="open")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=head.split(","))
    w.writeheader()
    w.writerow(first)
    p = tmp_path / "cases.csv"
    p.write_text(buf.getvalue(), encoding="utf-8")
    with pytest.raises(SystemExit, match="counted, never referenced"):
        B.shared_cases(p)


def test_an_edit_that_no_longer_matches_stops_the_build():
    with pytest.raises(SystemExit, match="matches 0 times"):
        B.shared_log("a log that has changed", [{"why": "test", "old": "text that is gone", "new": "x"}])


def test_the_front_page_passes_the_same_checks_as_the_shared_copies():
    assert B.problems({"README.md": (ROOT / "README.md").read_text(encoding="utf-8")}) == []
