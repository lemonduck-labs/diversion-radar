from urllib.parse import parse_qs, urlparse

import pytest

from radar import comtrade, config

YEARS = [str(y) for y in range(2019, 2026)]


def test_hmrc_covers_every_corridor_and_russia(pull_script):
    countries = config.countries()
    names = {c["name"] for c in pull_script.hmrc_countries(countries)}
    assert names == {c["name"] for c in config.corridors(countries)} | {"Russia"}


def test_comtrade_jobs_cover_x_and_m_for_every_corridor_and_year(pull_script):
    countries = config.countries()
    jobs = pull_script.comtrade_jobs(countries)
    corridors = config.corridors(countries)
    assert len(jobs) == len(corridors) * 2 * len(YEARS)
    for c in corridors:
        for partner, flow in [(643, "X"), (826, "M")]:
            years = [y for r, p, f, y in jobs if (r, p, f) == (int(c["comtrade_code"]), partner, flow)]
            assert years == YEARS, (c["name"], flow)


def test_each_comtrade_call_asks_for_one_year(tmp_path, monkeypatch, pull_script):
    urls = []

    class Response:
        status_code, content, text = 200, b"{}", ""

        def __init__(self, url):
            self.url = url

        def raise_for_status(self):
            pass

        def json(self):
            q = {k: v[0] for k, v in parse_qs(urlparse(self.url).query).items()}
            return {"data": [{"reporterCode": int(q["reporterCode"]), "partnerCode": int(q["partnerCode"]),
                              "flowCode": q["flowCode"], "cmdCode": "851762", "period": q["period"],
                              "primaryValue": 1.0, "netWgt": 1.0, "isReported": False,
                              "classificationCode": "H6", "partner2Code": 0, "customsCode": "C00",
                              "motCode": 0}]}

    def fake_get(url, headers=None, timeout=None):
        urls.append(url)
        return Response(url)

    monkeypatch.setattr(comtrade.requests, "get", fake_get)
    monkeypatch.setattr(comtrade.time, "sleep", lambda s: None)
    monkeypatch.setattr(comtrade, "log_pull", lambda *a, **k: None)   # keep the real log clean
    monkeypatch.delenv("COMTRADE_KEY", raising=False)
    countries = [c for c in config.countries() if c["name"] in ("Turkey", "Russia")]
    ct = pull_script.pull_comtrade(countries, config.codes(), tmp_path)
    assert len(urls) == 2 * len(YEARS)
    for url in urls:
        period = parse_qs(urlparse(url).query)["period"][0]
        assert len(period) == 4 and period.isdigit(), url
    assert set(ct["flow"]) == {"X", "M"} and set(ct["partner"]) == {643, 826}
    assert sorted(set(ct["year"])) == [int(y) for y in YEARS]
    assert list(ct.columns) == pull_script.COMTRADE_COLS


def test_hmrc_pull_asks_for_every_code_for_every_country(tmp_path, monkeypatch, pull_script):
    calls = []

    def fake_pull(client, country_id, code, lo, hi, out_dir, month_from=201901):
        calls.append((country_id, code))
        return [{"MonthId": 202301, "Value": 5, "NetMass": 1}]

    monkeypatch.setattr(pull_script, "pull_monthly_exports", fake_pull)
    countries, codes = config.countries(), config.codes()
    df = pull_script.pull_hmrc(countries, codes, tmp_path, client=object())
    assert len(calls) == len(pull_script.hmrc_countries(countries)) * len(codes)
    assert list(df.columns) == ["country_id", "code", "month", "value_gbp", "net_mass_kg"]


def test_processed_layouts_match_the_snapshots(pull_script):
    header = (config.PROCESSED / "comtrade_annual.csv").open().readline().strip().split(",")
    assert pull_script.COMTRADE_COLS == header


def test_refuses_to_replace_existing_tables(tmp_path, pull_script):
    existing = tmp_path / "hmrc_monthly_phase1.csv"
    existing.write_text("verified snapshot")
    with pytest.raises(SystemExit):
        pull_script.check_outputs([existing], overwrite=False)
    pull_script.check_outputs([existing], overwrite=True)


def test_missing_years_are_reported(pull_script):
    import pandas as pd
    countries = [c for c in config.countries() if c["name"] == "Tajikistan"]
    ct = pd.DataFrame({"reporter": [762] * 5, "flow": ["X"] * 5, "year": [2019, 2020, 2021, 2022, 2023]})
    gaps = list(pull_script.missing_years(countries, ct))
    assert ("Tajikistan", "X", [2024, 2025]) in gaps
    assert ("Tajikistan", "M", list(range(2019, 2026))) in gaps
