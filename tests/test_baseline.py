import math

import pandas as pd

from radar import baseline


def _monthly(rows):
    return pd.DataFrame(rows, columns=["country_id", "code", "month", "value_gbp", "net_mass_kg"])


def test_annual_and_ytd():
    m = _monthly([
        (83, "854231", 201901, 100, 1), (83, "854231", 201907, 50, 1),
        (83, "854231", 202301, 300, 3), (83, "854231", 202312, 200, 2),
    ])
    a = baseline.annual(m)
    assert a.loc[a.year == 2019, "value_gbp"].item() == 150
    ytd = baseline.annual(m, upto_month=6)
    assert ytd.loc[ytd.year == 2019, "value_gbp"].item() == 100
    assert ytd.loc[ytd.year == 2023, "value_gbp"].item() == 300


def test_compare_counts_missing_years_as_zero():
    m = _monthly([
        (83, "854231", 201905, 300, 1),          # 2019: 300, 2020: 0, 2021: 0 -> baseline 100
        (83, "854231", 202302, 400, 1),          # 2023: 400
        (83, "854231", 202402, 400, 1),          # 2024: 400
        (83, "854231", 202502, 400, 1),          # 2025: 400 -> post avg 400
    ])
    c = baseline.compare(baseline.annual(m))
    row = c.iloc[0]
    assert row.baseline_avg == 100
    assert row.post_avg == 400
    assert row.excess_per_year == 300
    assert row.excess_total == 900
    assert row.ratio == 4


def test_zero_baseline_gives_infinite_ratio_and_gross_ignores_falls():
    m = _monthly([
        (83, "854231", 202301, 90, 1), (83, "854231", 202401, 90, 1), (83, "854231", 202501, 90, 1),
        (77, "854231", 201901, 300, 1), (77, "854231", 202001, 300, 1), (77, "854231", 202101, 300, 1),
    ])
    c = baseline.compare(baseline.annual(m)).set_index("country_id")
    assert math.isinf(c.loc[83, "ratio"])
    assert c.loc[77, "excess_total"] == -900
    assert baseline.gross_excess(c.reset_index()) == 270
