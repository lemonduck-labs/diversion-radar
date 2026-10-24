import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import asof  # noqa: E402


def _monthly(rows):
    return pd.DataFrame(rows, columns=["country_id", "code", "month", "value_gbp", "net_mass_kg"])


def _ct(rows):
    return pd.DataFrame(rows, columns=["reporter", "partner", "flow", "code", "year", "value_usd"])


def test_uk_signal_needs_three_months_running():
    rows = [(79, "851762", 201906, 30_000, 1), (79, "851762", 202006, 30_000, 1),
            (79, "851762", 202106, 30_000, 1)]  # baseline 30k a year
    rows += [(79, "851762", 202301, 100_000, 1)]  # trailing sum 100k from Jan 2023
    s = asof.uk_series(_monthly(rows), 79, "851762", end=202306, lag=0)
    assert bool(s.loc[pd.Period("2023-01", "M"), "uk_rule"])
    assert not bool(s.loc[pd.Period("2023-02", "M"), "uk_signal"])
    assert bool(s.loc[pd.Period("2023-03", "M"), "uk_signal"])


def test_onward_uses_only_published_years():
    ct = _ct([(398, 643, "X", "851762", y, v) for y, v in
              [(2019, 100_000), (2020, 100_000), (2021, 100_000), (2022, 900_000), (2023, 900_000)]])
    # June 2023: 2022 data not yet treated as published, latest is 2021 -> no onward signal
    assert asof.onward_signal(ct, 398, "851762", pd.Period("2023-06", "M"))[0] is False
    # July 2023: 2022 published -> 9x baseline -> signal
    assert asof.onward_signal(ct, 398, "851762", pd.Period("2023-07", "M"))[0] is True


def test_first_signal_and_lead_time():
    rows = [(79, "851762", m, 30_000, 1) for m in (201906, 202006, 202106)]
    rows += [(79, "851762", 202302, 100_000, 1)]
    ct = _ct([(398, 643, "X", "851762", y, v) for y, v in
              [(2019, 100_000), (2020, 100_000), (2021, 100_000), (2022, 900_000)]])
    out = asof.first_signal(_monthly(rows), ct, 79, 398, "851762", start=202201, end=202312, lag=0)
    assert out["first_watch"] == "2023-04"
    assert out["first_lead"] == "2023-07"
    assert asof.months_between(out["first_lead"], pd.Period("2024-01", "M")) == 6


def test_publication_lag_delays_the_uk_signal():
    rows = [(79, "851762", m, 30_000, 1) for m in (201906, 202006, 202106)]
    rows += [(79, "851762", 202302, 100_000, 1)]
    ct = _ct([(398, 643, "X", "851762", y, v) for y, v in
              [(2019, 100_000), (2020, 100_000), (2021, 100_000), (2022, 900_000)]])
    out = asof.first_signal(_monthly(rows), ct, 79, 398, "851762", start=202201, end=202312)
    assert out["first_watch"] == "2023-06"   # data to 2023-04 published by the end of 2023-06
    assert out["first_lead"] == "2023-07"    # onward year 2022 counts from July 2023


def test_release_dates_replace_the_july_rule():
    rows = [(79, "851762", m, 30_000, 1) for m in (201906, 202006, 202106)]
    rows += [(79, "851762", 202302, 100_000, 1)]
    ct = _ct([(398, 643, "X", "851762", y, v) for y, v in
              [(2019, 100_000), (2020, 100_000), (2021, 100_000), (2022, 900_000)]])
    release = pd.DataFrame({"reporter": [398, 398, 398, 398], "year": [2019, 2020, 2021, 2022],
                            "first_released": pd.to_datetime(["2020-03-01", "2021-03-01",
                                                              "2022-03-01", "2023-03-15T10:00"], format="ISO8601")})
    assert asof.onward_available_year(pd.Period("2023-02", "M"), 398, release) == 2021
    assert asof.onward_available_year(pd.Period("2023-03", "M"), 398, release) == 2022
    out = asof.first_signal(_monthly(rows), ct, 79, 398, "851762", start=202201, end=202312,
                            release=release)
    assert out["first_lead"] == "2023-06"    # onward from March, UK signal from June


def test_fallback_rule_uses_the_latest_reported_year():
    # 2023 never reported: from July 2024 the fallback rule keeps using 2022.
    ct = _ct([(784, 643, "X", "854232", y, v) for y, v in
              [(2019, 50_000), (2020, 50_000), (2021, 50_000), (2022, 300_000)]])
    assert asof.onward_signal(ct, 784, "854232", pd.Period("2024-08", "M"))[1]["onward_year"] == 2022
    assert asof.onward_signal(ct, 784, "854232", pd.Period("2024-08", "M"))[0] is True
