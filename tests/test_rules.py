import math

import numpy as np
import pandas as pd
import pytest

from radar import rules

YEARS = list(range(2019, 2026))


def _wide(rows):
    """{series: [2019, 2020, ..., 2025]} in GBP."""
    return pd.DataFrame.from_dict(rows, orient="index", columns=YEARS).astype(float)


def _ct(rows):
    return pd.DataFrame(rows, columns=["reporter", "partner", "flow", "code", "year", "value_usd"])


def test_thresholds_are_the_documented_ones():
    assert (rules.MIN_UK_RATIO, rules.MIN_UK_EXCESS_GBP, rules.MIN_PERSIST_YEARS) == (2.0, 20_000, 2)
    assert rules.BASELINE_YEARS == (2019, 2020, 2021) and rules.POST_YEARS == (2023, 2024, 2025)
    assert (rules.MIN_ONWARD_RATIO, rules.MIN_ONWARD_USD) == (2.0, 100_000)


@pytest.mark.parametrize("value, base, expected", [
    (20_000, 0, True),         # new trade: GBP 20k above a zero baseline
    (19_999, 0, False),
    (100_000, 50_000, True),   # exactly 2x and GBP 50k above
    (99_999, 50_000, False),   # just under 2x
    (30_000, 10_000, True),    # 3x and exactly GBP 20k above
    (29_999, 10_000, False),   # 3x, but under GBP 20k above
    (float("nan"), 0, False),  # no data never passes
])
def test_rise_test_boundaries(value, base, expected):
    assert bool(rules.meets_rise(value, base)) is expected


def test_persistence_needs_two_of_the_three_post_years():
    w = _wide({
        "all three": [100e3, 100e3, 100e3, 0, 250e3, 250e3, 250e3],
        "two":       [100e3, 100e3, 100e3, 0, 250e3, 150e3, 250e3],  # 2024 only 1.5x
        "one":       [100e3, 100e3, 100e3, 0, 900e3, 150e3, 150e3],
    })
    r = rules.uk_rise(w)
    assert r.loc["all three", "uk_years_met"] == "2023,2024,2025"
    assert r.loc["two", "uk_years_met"] == "2023,2025"
    assert r.loc["two", "uk_rise_persistent"] and r.loc["two", "uk_rise"]
    assert r.loc["one", "uk_n_years_met"] == 1
    assert r.loc["one", "uk_rise_avg"]                 # the average is 4x ...
    assert not r.loc["one", "uk_rise_persistent"]      # ... but the rise did not hold
    assert not r.loc["one", "uk_rise"]


def test_one_off_spike_from_zero_passes_the_average_only():
    # The phase 0 pattern that persistence is meant to drop: one large post year.
    r = rules.uk_rise(_wide({"spike": [0, 0, 0, 89e3, 108e3, 0, 0]})).loc["spike"]
    assert r.uk_rise_avg and r.uk_years_met == "2023"
    assert not r.uk_rise_persistent and not r.uk_rise


def test_persistent_years_with_an_average_below_the_rule_is_not_a_rise():
    # Two years each above 2x, then nothing: the average is only 1.4x. Both rules must hold.
    r = rules.uk_rise(_wide({"x": [100e3, 100e3, 100e3, 0, 210e3, 210e3, 0]})).loc["x"]
    assert r.uk_rise_persistent and not r.uk_rise_avg and not r.uk_rise


def test_each_year_is_tested_against_the_2019_21_average():
    # Baseline 10k, 40k, 10k averages 20k; 2023 and 2024 at 45k pass (2.25x, 25k above).
    r = rules.uk_rise(_wide({"x": [10e3, 40e3, 10e3, 0, 45e3, 45e3, 30e3]})).loc["x"]
    assert r.uk_years_met == "2023,2024"


def test_2022_is_ignored():
    r = rules.uk_rise(_wide({"x": [0, 0, 0, 5e6, 0, 0, 0]})).loc["x"]
    assert r.uk_n_years_met == 0 and not r.uk_rise_avg


def test_minimum_years_is_a_parameter():
    w = _wide({"x": [0, 0, 0, 0, 50e3, 50e3, 0]})
    assert rules.uk_rise(w, min_years=2).loc["x", "uk_rise_persistent"]
    assert not rules.uk_rise(w, min_years=3).loc["x", "uk_rise_persistent"]


def test_no_data_fails_every_test():
    r = rules.uk_rise(_wide({"none": [np.nan] * 7})).loc["none"]
    assert not r.uk_rise_avg and not r.uk_rise_persistent
    assert r.uk_n_years_met == 0 and r.uk_years_met == ""


def test_onward_uses_reported_years_only_and_zero_for_missing_codes():
    ct = _ct([
        (417, 643, "X", "851762", 2019, 50e3), (417, 643, "X", "851762", 2020, 50e3),
        (417, 643, "X", "851762", 2021, 50e3), (417, 643, "X", "851762", 2023, 300e3),
        (417, 643, "X", "854231", 2024, 1),     # 2024 reported, so 851762 counts as zero in 2024
        (417, 826, "M", "851762", 2025, 9e9),   # imports from the UK are not onward exports
    ])
    r = rules.onward(ct, [417], ["851762"]).loc[(417, "851762")]
    assert r.onward_data == "ok"
    assert r.onward_post_years == "2023,2024"   # 2025 not reported
    assert r.onward_base_usd == 50e3 and r.onward_post_usd == 150e3
    assert r.onward_ratio == 3 and r.onward_rise


def test_onward_needs_usd_100k_a_year():
    ct = _ct([(398, 643, "X", "854239", y, v) for y, v in
              [(2019, 10e3), (2020, 10e3), (2021, 10e3), (2023, 90e3), (2024, 90e3), (2025, 90e3)]])
    r = rules.onward(ct, [398], ["854239"]).loc[(398, "854239")]
    assert r.onward_ratio == 9 and not r.onward_rise


def test_onward_zero_baseline_in_reported_years_is_infinite():
    ct = _ct([(268, 643, "X", "854231", 2019, 5), (268, 643, "X", "851762", 2023, 200e3)])
    r = rules.onward(ct, [268], ["851762"]).loc[(268, "851762")]
    assert math.isinf(r.onward_ratio) and r.onward_rise


def test_onward_without_baseline_years_has_no_ratio():
    r = rules.onward(_ct([(31, 643, "X", "851762", 2023, 500e3)]), [31], ["851762"]).loc[(31, "851762")]
    assert r.onward_data == "no baseline years"
    assert math.isnan(r.onward_ratio) and not r.onward_rise


def test_onward_reporter_with_no_records_is_no_data():
    r = rules.onward(_ct([]), [762], ["8548"]).loc[(762, "8548")]
    assert r.onward_data == "no data" and not r.onward_rise
