import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from radar import display  # noqa: E402


def _monthly(rows):
    return pd.DataFrame(rows, columns=["country_id", "code", "month", "value_gbp", "net_mass_kg"])


def test_window_months_crosses_the_year():
    assert display.window_months(202602, 3) == [202512, 202601, 202602]
    assert len(display.window_months(202608)) == 12


def test_one_consignment_is_not_shown_however_large():
    m = _monthly([(79, "851762", 202603, 5_000_000, 1)])
    total, months = display.window_stats(m, 79, "851762", 202608)
    assert (total, months) == (5_000_000, 1)
    ok, why = display.displayable(total, months)
    assert not ok and "fewer than" in why


def test_spread_and_large_enough_is_shown():
    m = _monthly([(79, "851762", mm, 50_000, 1) for mm in display.window_months(202608)])
    assert display.displayable(*display.window_stats(m, 79, "851762", 202608)) == (True, "")
    small = _monthly([(79, "851762", mm, 10_000, 1) for mm in display.window_months(202608)])
    ok, why = display.displayable(*display.window_stats(small, 79, "851762", 202608))
    assert not ok and "under GBP" in why


def test_streak_start(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_live", Path(__file__).resolve().parent.parent / "scripts" / "run_live.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    idx = pd.period_range("2026-01", "2026-05", freq="M")
    assert mod._streak_start(pd.Series([True, False, True, True, True], index=idx)) == "2026-03"
    assert mod._streak_start(pd.Series([True, True, True, True, False], index=idx)) == ""
    assert mod.usd_k(8) == "$8" and mod.gbp_k(799_499) == "£799k" and mod.gbp_k(8_012_904) == "£8.0m"


def test_window_start_is_twelve_months_behind_the_lagged_run():
    assert display.window_start(pd.Period("2024-12", freq="M"), 2) == pd.Period("2023-11", freq="M")


def test_past_runs_are_screened_one_by_one():
    # Small and spread until mid-2025, then large: early runs are not drawn, later ones are.
    rows = [(79, "851762", mm, 5_000, 1) for mm in display.window_months(202506, 18)]
    rows += [(79, "851762", mm, 60_000, 1) for mm in display.window_months(202608, 14)]
    m = _monthly(rows)
    runs = pd.period_range("2025-01", "2026-10", freq="M")
    scr = display.screen_runs(m, 79, "851762", runs, 2)
    assert not scr.loc[pd.Period("2025-01", freq="M"), "shown"]
    assert "under GBP" in scr.loc[pd.Period("2025-01", freq="M"), "not_shown_because"]
    assert scr.loc[pd.Period("2026-10", freq="M"), "shown"]


def test_case_routes_cover_codes_and_headings_and_cut_the_case_period():
    plan = pd.DataFrame({"case_id": ["X-01"], "hmrc_country_id": [79], "codes": ["854231;854239"],
                         "reference_date": ["2023-10-31"]})
    routes = display.case_routes(plan)
    assert display.route_for(routes, 79, "854239") == ("X-01", pd.Period("2023-10", freq="M"), "route")
    assert display.route_for(routes, 79, "854232") == ("X-01", pd.Period("2023-10", freq="M"), "heading")
    assert display.route_for(routes, 79, "851762") is None
    assert display.route_for(routes, 81, "854239") is None
    m = _monthly([(79, "854239", mm, 60_000, 1) for mm in display.window_months(202608, 60)])
    runs = pd.period_range("2024-11", "2024-12", freq="M")
    scr = display.screen_runs(m, 79, "854239", runs, 2, routes[(79, "854239")][1])
    # The run of Nov 2024 sees Oct 2023 to Sep 2024, which starts in the case's month.
    assert not scr.iloc[0].shown and scr.iloc[0].not_shown_because == display.CASE_WINDOW_REASON
    assert scr.iloc[1].shown


def test_a_route_in_two_cases_keeps_both_and_the_later_month():
    plan = pd.DataFrame({"case_id": ["A-01", "B-02"], "hmrc_country_id": [647, 647],
                         "codes": ["854232", "854239"], "reference_date": ["2023-10-31", "2024-03-01"]})
    routes = display.case_routes(plan)
    assert display.route_for(routes, 647, "854232") == ("A-01, B-02", pd.Period("2024-03", freq="M"), "mixed")
    assert display.route_for(routes, 647, "854239") == ("A-01, B-02", pd.Period("2024-03", freq="M"), "mixed")


def test_register_routes_are_loaded_with_the_test_plan():
    root = Path(__file__).resolve().parent.parent
    routes = display.load_case_routes(root)
    cases, month, kind = display.route_for(routes, 647, "854232")
    assert "US-01" in cases and "EU-05" in cases and month == pd.Period("2024-03", freq="M")
