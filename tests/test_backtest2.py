"""Run 2's combination of the annual and monthly onward signals, and its snapshot reader,
on synthetic data."""
import hashlib
import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from radar import snapshots  # noqa: E402

spec = importlib.util.spec_from_file_location("run_backtest2", ROOT / "scripts" / "run_backtest2.py")
rb2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rb2)


def _monthly(rows):
    return pd.DataFrame(rows, columns=["country_id", "code", "month", "value_gbp", "net_mass_kg"])


def _ct(rows):
    return pd.DataFrame(rows, columns=["reporter", "partner", "flow", "code", "year", "value_usd"])


def _release(rows):
    df = pd.DataFrame(rows, columns=["reporter", "year", "first_released"])
    df["first_released"] = pd.to_datetime(df.first_released)
    return df


def _setup():
    # UK: baseline 30k a year (one June shipment a year), then 10k every month from January
    # 2022. With June 2021's 30k still in the window, the trailing sum reaches 60k (2x the
    # baseline) with March 2022's data; three months running takes it to May, which HMRC
    # publishes by the end of July -> UK signal from the July 2022 run.
    uk = ([(79, "851762", m, 30_000, 1) for m in (201906, 202006, 202106)]
          + [(79, "851762", y * 100 + m, 10_000, 1) for y in (2022, 2023) for m in range(1, 13)])
    # Annual onward: 2022 rises 9x, but 2022 data are only released in June 2023.
    ct = _ct([(398, 643, "X", "851762", y, v) for y, v in
              [(2019, 100_000), (2020, 100_000), (2021, 100_000), (2022, 900_000)]])
    rel = _release([(398, y, f"{y + 1}-06-01") for y in (2019, 2020, 2021)] + [(398, 2022, "2023-06-01")])
    # Monthly onward: every month 2019-21 is 10k; from Jan 2022, 80k a month, each month released
    # 45 days after it ends.
    months = [y * 100 + m for y in (2019, 2020, 2021, 2022) for m in range(1, 13)]
    ctm = pd.DataFrame([(398, p, "851762", 10_000.0 if p < 202201 else 80_000.0) for p in months],
                       columns=["reporter", "period", "code", "value_usd"])
    rel_m = pd.DataFrame([(398, p, pd.Period(f"{p // 100}-{p % 100:02d}", "M").end_time + pd.Timedelta(days=45))
                          for p in months], columns=["reporter", "period", "first_released"])
    return _monthly(uk), ct, rel, ctm, rel_m


def test_monthly_signal_brings_the_lead_forward():
    monthly, ct, rel, ctm, rel_m = _setup()
    t = rb2.part_a_timeline(monthly, ct, rel, ctm, rel_m, 79, 398, "851762", 202201, 202312)
    first_run1 = t.index[t.lead_run1][0]
    first_run2 = t.index[t.lead][0]
    assert str(first_run1) == "2023-06"          # annual 2022 data released 1 June 2023
    assert str(first_run2) == "2022-07"          # the monthly window already passes 2x and $100k
    assert (t.lead_run1 <= t.lead).all()         # run 2 can only add leads, never remove one


def test_corridors_without_monthly_data_keep_the_annual_signal_only():
    monthly, ct, rel, ctm, rel_m = _setup()
    ct = ct.assign(reporter=784)
    rel = rel.assign(reporter=784)
    t = rb2.part_a_timeline(monthly, ct, rel, ctm, rel_m, 79, 784, "851762", 202201, 202312)
    assert not t.onward_monthly.any()
    assert (t.lead == t.lead_run1).all()


def _snapshot_text():
    lines = ["#comtrade run2 snapshot|built 2026-10-21T12:00:00Z",
             "#SECTION DA_A|rows 1", "417|2016|H4|2017-03-15T23:15:47|2017-03-15T23:15:47",
             "#SECTION DA_M|rows 2", "417|201901|H5|2019-03-01T00:00:00|2019-03-01T00:00:00",
             "417|201902|H5|2019-04-01T00:00:00|2019-04-01T00:00:00",
             "#SECTION ANN|rows 1|sumValue 16163",
             "reporter,partner,flow,code,year,value_usd,net_wgt_kg,is_reported,classification",
             "417,643,X,8548,2016,16163,20000,1,H4",
             "#SECTION MON|rows 2|sumValue 1500.5", "417|201901|851762|1000.25", "417|201902|8548|500.25",
             "#SECTION CALLS|rows 2", "417|201901", "417|201902"]
    return "\n".join(lines) + "\n"


def test_run2_snapshot_reader_checks_hash_rows_and_sums(tmp_path):
    p = tmp_path / "snap.txt"
    text = _snapshot_text()
    p.write_text(text)
    sha = hashlib.sha256(text.encode()).hexdigest()
    out = snapshots.read_comtrade_run2(p, sha)
    assert len(out["monthly"]) == 2 and out["annual"].value_usd.sum() == 16163
    assert out["monthly_availability"].first_released.dt.year.tolist() == [2019, 2019]
    with pytest.raises(snapshots.SnapshotMismatch):
        snapshots.read_comtrade_run2(p, "0" * 64)
    bad = text.replace("#SECTION MON|rows 2|sumValue 1500.5", "#SECTION MON|rows 2|sumValue 1600.5")
    p.write_text(bad)
    with pytest.raises(snapshots.SnapshotMismatch):
        snapshots.read_comtrade_run2(p, hashlib.sha256(bad.encode()).hexdigest())


def test_peacetime_rule_uses_2016_18_and_onward_years_from_2019():
    from backtest import asof
    # UK: 2016-18 baseline 30k a year; 10k a month from January 2019.
    uk = ([(79, "851762", y * 100 + 6, 30_000, 1) for y in (2016, 2017, 2018)]
          + [(79, "851762", y * 100 + m, 10_000, 1) for y in (2019, 2020, 2021) for m in range(1, 13)])
    ct = _ct([(398, 643, "X", "851762", y, v) for y, v in
              [(2016, 50_000), (2017, 50_000), (2018, 50_000), (2019, 400_000), (2020, 400_000)]])
    rel = _release([(398, y, f"{y + 1}-06-01") for y in (2016, 2017, 2018, 2019, 2020)])
    t = asof.timeline(_monthly(uk), ct, 79, 398, "851762", 201901, 202112, asof.UK_LAG_MONTHS, rel,
                      (2016, 2017, 2018), 2019)
    # 2018 data (released June 2019) is below the first onward year: no onward signal until
    # 2019 data are released in June 2020.
    assert not t.loc[:"2020-05"].onward_signal.any()
    assert bool(t.loc[pd.Period("2020-06", "M"), "onward_signal"])
    assert str(t.index[t.lead][0]) == "2020-06"
