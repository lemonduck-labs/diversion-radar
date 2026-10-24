import math

import pandas as pd
import pytest

from radar import mirror

FX = {2023: 1.25, 2024: 1.25, 2025: 1.25}
KG = {"name": "Kyrgyz Republic", "hmrc_country_id": "83", "comtrade_code": "417", "role": "corridor"}


def _uk(rows):
    """(country_id, code, year, value_gbp)"""
    return pd.DataFrame(rows, columns=["country_id", "code", "year", "value_gbp"])


def _ct(rows):
    """(reporter, code, year, value_usd): corridor imports from the UK."""
    return pd.DataFrame([(r, 826, "M", c, y, v) for r, c, y, v in rows],
                        columns=["reporter", "partner", "flow", "code", "year", "value_usd"])


def _one(uk_gbp, corridor_usd, year=2024, fx=FX):
    g = mirror.gaps(_uk([(83, "851762", year, uk_gbp)]), _ct([(417, "851762", year, corridor_usd)]),
                    fx, [KG], ["851762"], years=[year])
    assert len(g) == 1
    return g.iloc[0]


def test_corridor_higher_is_flagged():
    r = _one(10_000, 200_000)          # UK side: GBP 10k = USD 12.5k
    assert r.status == mirror.CHECKED
    assert r.uk_exports_usd == 12_500 and r.ratio_corridor_to_uk == 16 and r.gap_usd == 187_500
    assert r.flag == mirror.CORRIDOR_HIGHER


def test_exactly_3x_and_usd_100k_is_flagged():
    assert _one(40_000, 150_000).flag == mirror.CORRIDOR_HIGHER   # USD 50k against 150k


def test_ratio_without_the_dollar_gap_is_not_flagged():
    assert _one(1_000, 50_000).flag == ""          # 40x, but only USD 48,750 apart


def test_dollar_gap_without_the_ratio_is_not_flagged():
    assert _one(400_000, 1_200_000).flag == ""     # USD 500k against 1.2m: 2.4x


def test_reverse_gap_is_flagged():
    r = _one(400_000, 100_000)                     # USD 500k against 100k: 5x, 400k apart
    assert r.flag == mirror.UK_HIGHER


def test_reverse_gap_needs_usd_100k_too():
    assert _one(60_000, 1_000).flag == ""          # 75x, but only USD 74k apart


def test_no_uk_record_in_the_year_counts_as_zero():
    g = mirror.gaps(_uk([(83, "851762", 2023, 5)]), _ct([(417, "851762", 2024, 150_000)]),
                    FX, [KG], ["851762"], years=[2024])
    r = g.iloc[0]
    assert r.uk_exports_gbp == 0 and math.isinf(r.ratio_corridor_to_uk)
    assert r.flag == mirror.CORRIDOR_HIGHER


def test_year_without_an_fx_rate_is_skipped_not_guessed():
    r = _one(1, 50_000_000, year=2025, fx={2024: 1.25})
    assert r.status == mirror.NO_FX and r.flag == "" and math.isnan(r.uk_exports_usd)


def test_unreported_corridor_year_is_skipped_and_missing_codes_count_as_zero():
    uk = _uk([(83, "851762", 2024, 1_000_000), (83, "854231", 2023, 100_000)])
    ct = _ct([(417, "851762", 2023, 10)])          # the corridor reported 2023 only
    g = mirror.gaps(uk, ct, FX, [KG], ["851762", "854231"], years=[2023, 2024]).set_index(["code", "year"])
    assert g.loc[("851762", 2024), "status"] == mirror.NOT_REPORTED
    assert g.loc[("851762", 2024), "flag"] == ""
    # 2023 was reported, so 854231 with no record is a true zero: USD 125k against 0
    assert g.loc[("854231", 2023), "corridor_imports_usd"] == 0
    assert g.loc[("854231", 2023), "flag"] == mirror.UK_HIGHER


def test_conversion_uses_each_years_own_rate():
    fx = {2019: 1.2766, 2021: 1.3757}
    uk = _uk([(83, "851762", 2019, 100_000), (83, "851762", 2021, 100_000)])
    ct = _ct([(417, "851762", 2019, 1), (417, "851762", 2021, 1)])
    g = mirror.gaps(uk, ct, fx, [KG], ["851762"], years=[2019, 2021]).set_index("year")
    assert g.loc[2019, "uk_exports_usd"] == pytest.approx(127_660)
    assert g.loc[2021, "uk_exports_usd"] == pytest.approx(137_570)


def test_missing_sides_are_reported_as_no_data():
    no_m = mirror.gaps(_uk([(83, "851762", 2024, 1)]), _ct([]), FX, [KG], ["851762"], years=[2024])
    assert no_m.iloc[0].status == mirror.NO_CORRIDOR_DATA
    no_uk = mirror.gaps(_uk([]), _ct([(417, "851762", 2024, 1)]), FX, [KG], ["851762"], years=[2024])
    assert no_uk.iloc[0].status == mirror.NO_UK_DATA
    s = mirror.summarise(no_m).loc[(83, "851762")]
    assert s.mirror_data == mirror.NO_CORRIDOR_DATA and s.mirror_years_checked == 0 and not s.mirror_gap


def test_summary_lists_flagged_years_each_way():
    uk = _uk([(83, "851762", 2023, 400_000), (83, "851762", 2024, 10_000), (83, "851762", 2025, 10_000)])
    ct = _ct([(417, "851762", 2023, 1_000), (417, "851762", 2024, 500_000), (417, "851762", 2025, 500_000)])
    s = mirror.summarise(mirror.gaps(uk, ct, FX, [KG], ["851762"], years=[2023, 2024, 2025]))
    r = s.loc[(83, "851762")]
    assert r.mirror_years_checked == 3 and r.mirror_gap
    assert r.mirror_uk_higher == "2023" and r.mirror_corridor_higher == "2024,2025"


def test_load_fx_skips_blank_years_and_needs_a_source(tmp_path):
    p = tmp_path / "fx.csv"
    p.write_text("year,usd_per_gbp,source,source_url,retrieved\n"
                 "2024,1.2783,Official series,https://example.org,2026-10-21\n"
                 "2025,,,,\n")
    assert mirror.load_fx(p) == {2024: 1.2783}
    p.write_text("year,usd_per_gbp,source,source_url,retrieved\n2024,1.2783,,,\n")
    with pytest.raises(ValueError):
        mirror.load_fx(p)


def test_config_fx_rates_load():
    fx = mirror.load_fx()
    assert set(fx) <= set(mirror.YEARS)
    assert all(1.0 < v < 1.6 for v in fx.values())


def test_docstring_explains_the_ordinary_causes():
    for cause in ("origin", "Re-exports", "CIF", "FOB", "Timing"):
        assert cause in mirror.__doc__
