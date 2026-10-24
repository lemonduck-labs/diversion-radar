import pandas as pd

from radar import config, leads


def _redirect_outputs(monkeypatch, analyse_script, tmp_path):
    monkeypatch.setattr(analyse_script, "LEADS_OUT", tmp_path / "leads_phase1.csv")
    monkeypatch.setattr(analyse_script, "MIRROR_OUT", tmp_path / "mirror_phase1.csv")


def test_default_inputs_are_the_phase1_files(analyse_script):
    assert analyse_script.HMRC_DEFAULT.name == "hmrc_monthly_phase1.csv"
    assert analyse_script.CT_DEFAULT.name == "comtrade_annual_phase1.csv"
    assert analyse_script.CT_FALLBACK.name == "comtrade_annual.csv"
    assert analyse_script.LEADS_OUT.name == "leads_phase1.csv"


def test_prefers_the_phase1_file_when_present(tmp_path, analyse_script):
    preferred, fallback = tmp_path / "comtrade_annual_phase1.csv", tmp_path / "comtrade_annual.csv"
    fallback.write_text("x")
    assert analyse_script.pick(preferred, fallback) == fallback
    preferred.write_text("x")
    assert analyse_script.pick(preferred, fallback) == preferred


def test_missing_inputs_give_no_data_not_a_crash(tmp_path, monkeypatch, analyse_script):
    _redirect_outputs(monkeypatch, analyse_script, tmp_path)
    analyse_script.main(["--hmrc", str(tmp_path / "absent.csv"), "--comtrade", str(tmp_path / "absent2.csv")])
    out = pd.read_csv(tmp_path / "leads_phase1.csv")
    assert len(out) == len(config.corridors(config.countries())) * len(config.codes())
    assert (out["status"] == leads.NO_DATA).all()


def test_runs_on_the_repo_data(tmp_path, monkeypatch, analyse_script):
    _redirect_outputs(monkeypatch, analyse_script, tmp_path)
    analyse_script.main([])
    out = pd.read_csv(tmp_path / "leads_phase1.csv", dtype={"code": str})
    corridors = config.corridors(config.countries())
    assert len(out) == len(corridors) * len(config.codes())
    assert set(out["country"]) == {c["name"] for c in corridors}
    assert set(out["status"]) <= set(leads.STATUS_ORDER)
    led = out[out["lead"]]
    assert (led["uk_rise_avg"] & led["uk_rise_persistent"] & led["onward_rise"]).all()
    assert (led["uk_n_years_met"] >= 2).all()
    m = pd.read_csv(tmp_path / "mirror_phase1.csv", dtype={"code": str})
    assert len(m) == len(out) * 7
