import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_code_ranges_match_codes():
    for row in csv.DictReader((ROOT / "config" / "codes.csv").open()):
        lo, hi, code = row["cn8_from"], row["cn8_to"], row["code"]
        assert lo.startswith(code) and hi.startswith(code), row
        assert int(lo) <= int(hi)
        assert len(lo) == len(hi) == 8


def test_nine_tier_one_and_two_codes():
    rows = list(csv.DictReader((ROOT / "config" / "codes.csv").open()))
    assert len(rows) == 9
    assert {r["tier"] for r in rows} == {"1", "2"}


def test_countries_have_unique_ids_and_codes():
    rows = list(csv.DictReader((ROOT / "config" / "countries.csv").open()))
    corridors = [r for r in rows if r["role"] == "corridor"]
    assert len(corridors) == 9
    assert all(r["hmrc_country_id"].isdigit() and r["comtrade_code"].isdigit() for r in corridors)
    ids = [r["hmrc_country_id"] for r in rows if r["hmrc_country_id"]]
    assert len(set(ids)) == len(ids)
    assert len({r["comtrade_code"] for r in rows}) == len(rows)
    roles = {r["name"]: (r["hmrc_country_id"], r["comtrade_code"], r["role"]) for r in rows}
    assert roles["Russia"] == ("75", "643", "target")
    assert roles["United Kingdom"] == ("", "826", "origin")


def test_phase1_corridors():
    # HMRC ids verified separately before the phase 1 pull; UN M49 codes from the UN
    # Statistics Division's M49 overview (URL in data/SOURCES.md). Azerbaijan's M49 code is 031.
    rows = {r["name"]: r for r in csv.DictReader((ROOT / "config" / "countries.csv").open())}
    expected = {"Turkey": ("52", "792"), "Uzbekistan": ("81", "860"),
                "Azerbaijan": ("78", "31"), "Tajikistan": ("82", "762")}
    for name, (hmrc_id, m49) in expected.items():
        r = rows[name]
        assert (r["hmrc_country_id"], r["comtrade_code"], r["role"]) == (hmrc_id, m49, "corridor")


def test_fx_rates_cover_2019_to_2025_and_each_rate_has_a_source():
    rows = list(csv.DictReader((ROOT / "config" / "fx_usd_per_gbp.csv").open()))
    assert [int(r["year"]) for r in rows] == list(range(2019, 2026))
    for r in rows:
        if r["usd_per_gbp"].strip():
            assert 1.0 < float(r["usd_per_gbp"]) < 1.6, r
            assert r["source"].strip() and r["source_url"].startswith("https://"), r
