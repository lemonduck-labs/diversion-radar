import numpy as np
import pandas as pd

from radar import config, leads, mirror

PROC = config.PROCESSED
FX = {y: 1.25 for y in range(2019, 2026)}
CODES = [{"code": "851762", "description": "Data transmission"}, {"code": "8548", "description": "Parts"}]
COUNTRIES = [
    {"name": "Kazakhstan", "hmrc_country_id": "79", "comtrade_code": "398", "role": "corridor"},
    {"name": "Tajikistan", "hmrc_country_id": "82", "comtrade_code": "762", "role": "corridor"},
    {"name": "Russia", "hmrc_country_id": "75", "comtrade_code": "643", "role": "target"},
]


def _monthly(rows):
    return pd.DataFrame(rows, columns=["country_id", "code", "month", "value_gbp", "net_mass_kg"])


def _ct(rows):
    return pd.DataFrame(rows, columns=["reporter", "partner", "flow", "code", "year", "value_usd"])


def _inputs():
    """One lead for Kazakhstan; nothing at all for Tajikistan."""
    monthly = _monthly(
        [(79, "851762", y * 100 + 6, 10_000, 1) for y in (2019, 2020, 2021)]
        + [(79, "851762", y * 100 + 6, 100_000, 5) for y in (2023, 2024, 2025)]
        + [(75, "851762", 201906, 9_999_999, 9)])           # Russia is never a corridor row
    ct = _ct([(398, 643, "X", "851762", y, 50_000) for y in (2019, 2020, 2021)]
             + [(398, 643, "X", "851762", y, 300_000) for y in (2023, 2024, 2025)]
             + [(398, 826, "M", "851762", y, 1_000_000) for y in (2023, 2024, 2025)])
    return monthly, ct


def test_lead_needs_both_uk_rules_and_the_onward_rise():
    out, _ = leads.build(*_inputs(), COUNTRIES, CODES, FX)
    r = out.set_index(["country", "code"]).loc[("Kazakhstan", "851762")]
    assert r.uk_rise_avg and r.uk_rise_persistent and r.onward_rise
    assert r.lead and r.lead_phase0 and r.status == leads.LEAD
    assert r.uk_years_met == "2023,2024,2025" and r.gbp_2024 == 100_000
    assert r.mirror_gap and r.mirror_corridor_higher == "2023,2024,2025"


def test_country_with_no_data_is_reported_as_no_data():
    out, mirror_rows = leads.build(*_inputs(), COUNTRIES, CODES, FX)
    assert len(out) == 2 * len(CODES)                       # corridors only, every code
    tj = out[out["country"] == "Tajikistan"]
    assert (tj["status"] == leads.NO_DATA).all() and (tj["uk_data"] == "no data").all()
    assert (tj["onward_data"] == "no data").all() and not tj["lead"].any()
    assert tj["baseline_avg"].isna().all() and tj["excess_total"].isna().all()
    assert (mirror_rows.loc[mirror_rows["country"] == "Tajikistan", "status"] == mirror.NO_UK_DATA).all()


def test_code_with_no_records_for_a_country_with_data_is_zero():
    out, _ = leads.build(*_inputs(), COUNTRIES, CODES, FX)
    r = out.set_index(["country", "code"]).loc[("Kazakhstan", "8548")]
    assert r.uk_data == "ok" and r.gbp_2023 == 0 and r.baseline_avg == 0 and r.status == leads.NONE


def test_empty_inputs_do_not_crash():
    out, mirror_rows = leads.build(_monthly([]), _ct([]), COUNTRIES, CODES, FX)
    assert (out["status"] == leads.NO_DATA).all() and len(mirror_rows) == 2 * len(CODES) * 7


def test_one_off_spike_is_dropped_not_lost():
    monthly = _monthly([(79, "851762", 202306, 108_000, 1)])
    _, ct = _inputs()
    out, _ = leads.build(monthly, ct, COUNTRIES, CODES, FX)
    r = out.set_index(["country", "code"]).loc[("Kazakhstan", "851762")]
    assert r.lead_phase0 and not r.lead and r.status == leads.DROPPED


def test_phase0_rules_reproduce_the_phase0_leads_table():
    """On the phase 0 inputs, the averaged rule and the onward rule give exactly the
    phase 0 flags and figures (data/processed/leads.csv)."""
    m0 = pd.read_csv(PROC / "hmrc_monthly.csv", dtype={"code": str})
    c0 = pd.read_csv(PROC / "comtrade_annual.csv", dtype={"code": str})
    phase0 = {"83", "77", "79", "76", "647"}
    countries = [c for c in config.countries() if c["role"] != "corridor" or c["hmrc_country_id"] in phase0]
    out, _ = leads.build(m0, c0, countries, config.codes(), mirror.load_fx())
    p0 = pd.read_csv(PROC / "leads.csv", dtype={"code": str})
    j = p0.merge(out, on=["country_id", "code"], suffixes=("_p0", ""))
    assert len(j) == len(p0)
    assert (j["uk_rise_p0"] == j["uk_rise_avg"]).all()
    assert (j["onward_rise_p0"] == j["onward_rise"]).all()
    assert (j["lead_p0"] == j["lead_phase0"]).all() and j["lead_p0"].sum() == 6
    for col in ["baseline_avg", "post_avg", "excess_total", "ratio", "mass_ratio", "onward_ratio"]:
        np.testing.assert_allclose(j[f"{col}_p0"], j[col], err_msg=col)
