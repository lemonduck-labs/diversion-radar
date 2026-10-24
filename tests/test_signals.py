"""The research signals in radar/signals (pre-registered in radar/signals/RESEARCH.md, S0), on
synthetic data, and the committed results against a recomputation from the processed tables."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from radar import display  # noqa: E402
from radar.signals import codeshift, common, displacement, evaluate, price  # noqa: E402

CORRIDORS = [52, 76, 77, 78, 79, 81, 82, 83, 647]


def _monthly(rows):
    return pd.DataFrame(rows, columns=["country_id", "code", "month", "value_gbp", "net_mass_kg"])


def _months(start, end):
    return [int(p.strftime("%Y%m")) for p in pd.period_range(
        f"{start // 100}-{start % 100:02d}", f"{end // 100}-{end % 100:02d}", freq="M")]


def _first(s: pd.Series):
    return str(s.index[s.values][0]) if s.any() else None


RUNS = common.runs(202201, 202412)


# Shared pieces

def test_headings_come_from_the_cn8_ranges():
    codes = common.load_codes()
    h = common.headings(codes)
    assert sorted(h["8542"]) == ["854231", "854232", "854233", "854239"]
    assert sorted(h["8532"]) == ["853221", "853224"]
    assert h["8548"] == ["8548"] and h["8517"] == ["851762"] and h["8526"] == ["852691"]
    sib = common.sibling_map(codes)
    assert len(sib) == 6 and sib["853224"] == ["853221"]
    assert len([(c, a) for c in CORRIDORS for a in sib]) == 54


def test_overlapping_or_straddling_ranges_are_refused():
    bad = pd.DataFrame({"code": ["854231", "854232"], "cn8_from": ["85423100", "85423150"],
                        "cn8_to": ["85423199", "85423299"]})
    with pytest.raises(ValueError, match="overlap"):
        common.headings(bad)
    straddle = pd.DataFrame({"code": ["x"], "cn8_from": ["85420000"], "cn8_to": ["85439999"]})
    with pytest.raises(ValueError, match="one heading"):
        common.headings(straddle)


def test_a_data_month_is_first_seen_two_runs_later():
    idx = common.runs(202201, 202212)
    s = pd.Series(False, index=idx)
    s[pd.Period("2022-03", freq="M")] = True
    seen = common.at_runs(s, idx)
    assert _first(seen) == "2022-05" and seen.sum() == 1


def test_window_display_rule_matches_radar_display():
    rows = [(79, "851762", m, 30_000, 10) for m in _months(202301, 202312) if m % 2 == 0]
    rows += [(79, "851762", m, 25_000, 10) for m in _months(202401, 202406)]
    monthly = _monthly(rows)
    panel = common.Panel(monthly, 202201, 202412)
    ours = common.display_window(panel.series("value_gbp", 79, "851762"))
    for p in common.runs(202212, 202412):
        end = int(p.strftime("%Y%m"))
        theirs = display.displayable(*display.window_stats(monthly, 79, "851762", end))[0]
        assert bool(ours[p]) == theirs, p


# S1. Price per kilogram

def _s1_monthly(value=50_000, mass_after=20, base_value=None):
    """Corridor 79 and corridor 77 ship 851762 at GBP 1,000 a kg in every month of 2019-21.
    From January 2022, corridor 79 ships the same value on less mass."""
    base_value = value if base_value is None else base_value
    rows = []
    for m in _months(201901, 202412):
        late = m >= 202201
        rows.append((79, "851762", m, value if late else base_value, mass_after if late else base_value / 1000))
        rows.append((77, "851762", m, 50_000, 50))
    return _monthly(rows)


def test_s1_flags_a_doubling_after_three_windows_and_the_lag():
    # The window's price per kg reaches 2x with October 2022 (10 of 12 months at 2.5x); three
    # windows running end in December 2022, which the run at the end of February 2023 first sees.
    monthly = _s1_monthly()
    panel = common.Panel(monthly, 201901, 202412)
    t = price.timeline(panel, CORRIDORS, 79, "851762", common.WAR_BASE, RUNS)
    assert _first(t.s1) == "2023-02"
    assert set(t.s1_direction[t.s1]) == {"up"}
    assert t.d[pd.Period("2023-02", freq="M")] == pytest.approx(2.5)
    # The other corridor's price fell relative to the pool, by the same move.
    other = price.timeline(panel, CORRIDORS, 77, "851762", common.WAR_BASE, RUNS)
    assert set(other.s1_direction[other.s1]) == {"down"}


def test_s1_needs_the_display_rule_and_a_baseline_that_is_not_one_consignment():
    small = common.Panel(_s1_monthly(value=15_000, mass_after=6), 201901, 202412)
    assert not price.timeline(small, CORRIDORS, 79, "851762", common.WAR_BASE, RUNS).s1.any()
    # Baseline 2019-21 priced value GBP 54,000 (1,500 a month): under GBP 60,000.
    thin = common.Panel(_s1_monthly(base_value=1_500), 201901, 202412)
    assert not price.timeline(thin, CORRIDORS, 79, "851762", common.WAR_BASE, RUNS).s1.any()


def test_s1_ignores_rows_without_net_mass():
    monthly = _s1_monthly()
    zero_mass = _monthly([(79, "851762", 202206, 400_000, 0)])
    with_row = pd.concat([monthly, zero_mass], ignore_index=True)
    a = price.timeline(common.Panel(monthly, 201901, 202412), CORRIDORS, 79, "851762", common.WAR_BASE, RUNS)
    b = price.timeline(common.Panel(with_row, 201901, 202412), CORRIDORS, 79, "851762", common.WAR_BASE, RUNS)
    pd.testing.assert_series_equal(a.d, b.d)


def test_s1_needs_the_same_direction_three_windows_running(monkeypatch):
    idx = common.runs(202201, 202212)
    up = pd.Series([True, True, False, True, True, True] + [False] * 6, index=idx)
    down = pd.Series([False, False, True] + [False] * 9, index=idx)
    frame = pd.DataFrame({"d": 1.0, "shown": True, "base_priced_gbp": 1e6, "rule_up": up, "rule_down": down,
                          "run_up": common.persist(up), "run_down": common.persist(down)}, index=idx)
    monkeypatch.setattr(price, "drift", lambda *a, **k: frame)
    t = price.timeline(None, CORRIDORS, 79, "851762", common.WAR_BASE, idx)
    # up, up, down, up, up, up: only the second run of three counts, and two months later.
    assert list(t.index[t.s1].astype(str)) == ["2022-08"]


# S2. Code shift within a heading

def _s2_monthly(focal_base=10_000, focal_after=0, sib_base=5_000, sib_after=20_000):
    rows = []
    for m in _months(201901, 202412):
        late = m >= 202201
        rows.append((647, "854231", m, focal_after if late else focal_base, 1))
        rows.append((647, "854239", m, sib_after if late else sib_base, 1))
    return _monthly(rows)


def test_s2_flags_a_fall_made_up_by_the_siblings():
    # Focal GBP 240,000 a year falls to zero; siblings GBP 120,000 a year rise to 480,000. The focal
    # total is at most half its baseline from June 2022; three windows running end in August, which
    # the October 2022 run first sees. The heading's total then passes the display rule.
    panel = common.Panel(_s2_monthly(focal_base=20_000, sib_base=10_000, sib_after=40_000), 201901, 202412)
    t = codeshift.timeline(panel, 647, "854231", ["854232", "854233", "854239"], common.WAR_BASE, RUNS)
    assert _first(t.s2) == "2022-10"
    assert t.heading_shown[pd.Period("2022-10", freq="M")]
    # The sibling that rose is not itself flagged: its own focal test (a fall) never holds.
    sib = codeshift.timeline(panel, 647, "854239", ["854231", "854232", "854233"], common.WAR_BASE, RUNS)
    assert not sib.s2.any()


def test_s2_needs_the_offset_and_a_focal_baseline():
    # A large fall with a small sibling rise: the rise passes the UK rule but not the offset.
    big_fall = common.Panel(_s2_monthly(focal_base=100_000, sib_base=500, sib_after=2_500), 201901, 202412)
    t = codeshift.timeline(big_fall, 647, "854231", ["854239"], common.WAR_BASE, RUNS)
    assert t.rise.any() and t.fall.any() and not t.offset[t.fall & t.rise].any() and not t.s2.any()
    # A focal baseline under GBP 20,000 a year.
    small = common.Panel(_s2_monthly(focal_base=1_500), 201901, 202412)
    assert not codeshift.timeline(small, 647, "854231", ["854239"], common.WAR_BASE, RUNS).s2.any()


def test_s2_heading_display_rule_uses_the_heading_total():
    panel = common.Panel(_s2_monthly(focal_base=2_000, sib_base=1_000, sib_after=15_000), 201901, 202412)
    t = codeshift.timeline(panel, 647, "854231", ["854239"], common.WAR_BASE, RUNS)
    assert not t.heading_shown.any()   # GBP 180,000 a year at most: under GBP 250,000


# S3. Displacement from Russia

def _s3_monthly(russia=50_000, corridor_base=2_500, corridor_after=20_000):
    rows = []
    for m in _months(201901, 202412):
        late = m >= 202201
        rows.append((75, "851762", m, 0 if late else russia, 1))
        rows.append((79, "851762", m, corridor_after if late else corridor_base, 1))
    return _monthly(rows)


def test_s3_needs_the_russia_fall_the_uk_signal_and_the_magnitude():
    # UK signal from the June 2022 run; Russia's window falls to half its average with June 2022
    # data, first seen at the August 2022 run; then the corridor's excess (GBP 105,000) is over
    # 10% and 25% of the shortfall (GBP 300,000) but never over 50%.
    monthly = _s3_monthly()
    panel = common.Panel(monthly, 201901, 202412)
    t = displacement.timeline(panel, monthly, 79, "851762", RUNS, factors=(0.10, 0.25, 0.50))
    assert _first(t.uk_signal) == "2022-06"
    assert _first(t.russia_fall) == "2022-08"
    assert _first(t["s3_0.10"]) == "2022-08" and _first(t["s3_0.25"]) == "2022-08"
    assert not t["s3_0.50"].any()


def test_s3_needs_a_material_russia_baseline():
    monthly = _s3_monthly(russia=8_000)       # GBP 96,000 a year: under GBP 100,000
    panel = common.Panel(monthly, 201901, 202412)
    t = displacement.timeline(panel, monthly, 79, "851762", RUNS)
    assert t.uk_signal.any() and not t.russia_fall.any() and not t["s3_0.10"].any()


# Evaluation

def _plan():
    return pd.DataFrame([
        {"test_id": "X1", "case_id": "C-1", "role": "primary", "country": "A", "hmrc_country_id": 79,
         "codes": "851762", "reference_date": "2023-06-15"},
        {"test_id": "X2", "case_id": "C-1", "role": "sensitivity", "country": "A", "hmrc_country_id": 79,
         "codes": "854231", "reference_date": "2023-06-15"},
        {"test_id": "X3", "case_id": "C-2", "role": "primary", "country": "B", "hmrc_country_id": 77,
         "codes": "851762", "reference_date": "2023-06-15"}])


def _run2():
    return pd.DataFrame([
        {"test_id": "X1", "outcome": "hit", "first_lead_before": "2023-04", "lead_time_months": 2.0, "role": "primary"},
        {"test_id": "X2", "outcome": "miss", "first_lead_before": None, "lead_time_months": None, "role": "sensitivity"},
        {"test_id": "X3", "outcome": "miss", "first_lead_before": None, "lead_time_months": None, "role": "primary"}])


def _flags(on: dict):
    idx = common.runs(202201, 202412)
    out = {}
    for key in [(79, "851762"), (79, "854231"), (77, "851762")]:
        s = pd.Series(False, index=idx)
        for p in on.get(key, []):
            s[pd.Period(p, freq="M")] = True
        out[key] = s
    return out


def test_a_hit_needs_a_run_that_ends_before_the_reference_date():
    # The June 2023 run ends after 15 June 2023, so a flag there is not before the action.
    flags = _flags({(79, "851762"): ["2023-06"], (77, "851762"): ["2023-05"]})
    r = evaluate.evaluate_tests(flags, _plan(), _run2(), "test").set_index("test_id")
    assert r.loc["X1", "outcome"] == "miss" and r.loc["X3", "outcome"] == "hit"
    assert r.loc["X3", "lead_time_months"] == 0 and bool(r.loc["X3", "beats_run2"])   # run 2 missed X3


def test_beating_run2_needs_three_months_on_a_primary_test():
    flags = _flags({(79, "851762"): ["2023-02"], (79, "854231"): ["2022-01"]})
    r = evaluate.evaluate_tests(flags, _plan(), _run2(), "test").set_index("test_id")
    assert r.loc["X1", "months_earlier_than_run2"] == 2 and not r.loc["X1", "beats_run2"]
    assert r.loc["X2", "outcome"] == "hit" and not r.loc["X2", "beats_run2"]          # sensitivity
    flags = _flags({(79, "851762"): ["2023-01"]})
    r = evaluate.evaluate_tests(flags, _plan(), _run2(), "test").set_index("test_id")
    assert r.loc["X1", "months_earlier_than_run2"] == 3 and r.loc["X1", "beats_run2"]
    na = evaluate.evaluate_tests(flags, _plan(), _run2(), "test", applicable={"854231"}).set_index("test_id")
    assert na.loc["X1", "outcome"] == "not applicable" and na.loc["X2", "outcome"] == "miss"


def test_verdicts_follow_the_preregistered_criteria():
    flags = _flags({(77, "851762"): ["2023-05"]})
    tests = evaluate.evaluate_tests(flags, _plan(), _run2(), "test")
    cost = evaluate.cost(flags)
    assert cost == {"series": 3, "series_ever": 1, "runs_flagged": 1}
    ok = evaluate.verdict_new_flag(tests, cost, {"passes": True}, 30)
    assert ok["recommended"]
    assert not evaluate.verdict_new_flag(tests, cost, {"passes": False}, 30)["recommended"]
    assert evaluate.verdict_new_flag(tests, cost, None, 30)["c3_placebo"] == "not computable"
    assert not evaluate.verdict_new_flag(tests, {**cost, "series_ever": 31}, None, 30)["recommended"]
    # A filter must keep run 2's primary hit X1.
    f = evaluate.verdict_filter(tests, _run2(), cost)
    assert f["primary_hits_kept"] == {"X1": False} and not f["recommended"]
    p = evaluate.placebo({"a": pd.Series([True]), "b": pd.Series([False])},
                         {"a": pd.Series([True]), "b": pd.Series([True])})
    assert p["peace_series_ever"] == 1 and p["war_series_ever"] == 2 and p["passes"]


def test_nameable_holds_back_case_route_windows():
    idx = common.runs(202401, 202412)
    flag, shown = pd.Series(True, index=idx), pd.Series(True, index=idx)
    routes = {(79, "851762"): (frozenset({"C-1"}), pd.Period("2023-10", freq="M"))}
    n = common.nameable(flag, shown, routes, 79, "851762")
    # The window behind a run starts 13 months before it (lag 2, 12 months): the December 2024
    # run's window starts in November 2023, the first after October 2023.
    assert list(n.index[n.values].astype(str)) == ["2024-12"]
    n = common.nameable(flag, shown, {}, 79, "851762")
    assert n.all()
    n = common.nameable(flag, shown.where(shown.index != pd.Period("2024-12", freq="M"), False), routes, 79, "851762")
    assert not n.any()


# The committed results

def test_committed_results_match_a_recomputation():
    """S1, S2 and S3 flags in results/runs.csv, recomputed from the processed table."""
    runs_csv = ROOT / "radar" / "signals" / "results" / "runs.csv"
    res = pd.read_csv(runs_csv, dtype={"code": str})
    monthly = common.load_monthly(common.WAR_FILE)
    panel = common.Panel(monthly, 201901, 202608)
    war_runs = common.runs(*common.WAR_RUNS)
    sib = common.sibling_map(common.load_codes())
    codes = common.load_codes().code.tolist()
    s1 = s2 = s3 = 0
    for c in CORRIDORS:
        for k in codes:
            r = res[(res.hmrc_country_id == c) & (res.code == k)].set_index("run")
            t1 = price.timeline(panel, CORRIDORS, c, k, common.WAR_BASE, war_runs)
            assert list(t1.s1.values) == list(r.s1.values), (c, k)
            s1 += int(t1.s1.sum())
            t3 = displacement.timeline(panel, monthly, c, k, war_runs)
            assert list(t3["s3_0.10"].values) == list(r["s3_0.10"].values), (c, k)
            s3 += int(t3["s3_0.10"].sum())
            if k in sib:
                t2 = codeshift.timeline(panel, c, k, sib[k], common.WAR_BASE, war_runs)
                assert list(t2.s2.values) == list(r.s2.astype(bool).values), (c, k)
                s2 += int(t2.s2.sum())
    assert (s1, s2, s3) == (int(res.s1.sum()), int(res.s2.fillna(False).astype(bool).sum()),
                            int(res["s3_0.10"].sum()))
