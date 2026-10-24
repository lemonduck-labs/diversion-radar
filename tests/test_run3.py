"""Run 3 (backtest/RESEARCH_LOG.md, entry R3): nine corridors added on run 2's rule.

Checks the new reporters' codes, the run 3 snapshots and readers, that every run 3 table is
its run 2 table byte for byte with only new corridors' rows after it, and that run 3 leaves
the original nine exactly as run 2 had them."""
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pandas as pd
import pytest

from radar import snapshots

ROOT = Path(__file__).resolve().parent.parent
CONFIG, DATA, BT = ROOT / "config", ROOT / "data" / "processed", ROOT / "backtest" / "data"

# Codes read from official lists on 21 October 2026 (R3): HMRC's country list, UN Comtrade's
# reporter list, the UN M49 overview. name: (iso2, HMRC country id, UN Comtrade code)
NEW = {
    "China": ("CN", 720, 156), "Hong Kong": ("HK", 740, 344), "Macao": ("MO", 743, 446),
    "India": ("IN", 664, 699), "Israel": ("IL", 624, 376), "Malaysia": ("MY", 701, 458),
    "Serbia": ("RS", 98, 688), "Thailand": ("TH", 680, 764), "Vietnam": ("VN", 690, 704),
}


def _script(name: str):
    spec = importlib.util.spec_from_file_location(f"test_{name}", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def build3():
    return _script("build_run3_tables")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------------ reporters and config
def test_new_corridors_have_the_verified_codes():
    run3 = pd.read_csv(CONFIG / "countries_run3.csv", keep_default_na=False)
    corr = run3[run3.role == "corridor"]
    assert len(corr) == 18 and corr.hmrc_country_id.is_unique and corr.comtrade_code.is_unique
    got = {r.name: (r.iso2, int(r.hmrc_country_id), int(r.comtrade_code)) for r in corr.itertuples()
           if r.name in NEW}
    assert got == NEW


def test_india_reports_to_comtrade_as_699_not_its_m49_code():
    # UN Comtrade keeps 356 for "India (...1974)"; its India from 1975 is 699.
    run3 = pd.read_csv(CONFIG / "countries_run3.csv")
    assert int(run3.loc[run3.name == "India", "comtrade_code"].iloc[0]) == 699


def test_original_rows_of_the_country_list_are_unchanged():
    old = (CONFIG / "countries.csv").read_text().splitlines()
    new = (CONFIG / "countries_run3.csv").read_text().splitlines()
    assert new[0] == old[0]
    assert [l for l in new[1:] if l in old] == old[1:]
    assert len(new) == len(old) + 9


def test_new_corridors_are_the_guidance_countries_not_yet_watched():
    spec = json.loads((ROOT / "radar" / "brief" / "spec" / "redflags.json").read_text())
    names = set(spec["uk_enhanced_due_diligence_countries"]["names"])
    aliases = {"Kyrgyzstan": {"Kyrgyz Republic"}, "T\u00fcrkiye": {"Turkey"}, "UAE": {"United Arab Emirates"},
               "China (including Hong Kong and Macau)": {"China", "Hong Kong", "Macao"}}
    guidance = set().union(*(aliases.get(n, {n}) for n in names))
    watched = set(pd.read_csv(CONFIG / "countries.csv").query("role == 'corridor'").name)
    assert guidance - watched == set(NEW)


def test_run3_case_routes_add_only_new_corridors_with_the_cases_dates():
    r = pd.read_csv(CONFIG / "case_routes_run3.csv", dtype={"codes": str})
    assert set(r.hmrc_country_id) <= {v[1] for v in NEW.values()}
    plan = pd.read_csv(BT / "test_plan.csv")
    dates = plan.groupby("case_id").reference_date.first()
    assert all(r.reference_date == r.case_id.map(dates))


# ------------------------------------------------------------------ snapshots and readers
def test_hmrc_snapshot_checksums(build3):
    df = snapshots.read_hmrc(build3.HMRC_RAW)
    assert _sha(build3.HMRC_RAW) == build3.HMRC_SHA256
    assert _sha(build3.HMRC_CALLS) == build3.HMRC_CALLS_SHA256
    assert set(df.country_id) <= {v[1] for v in NEW.values()}
    assert df.month.min() == 201601


def test_comtrade_snapshot_checksums(build3):
    ct = snapshots.read_comtrade_run3(build3.COMTRADE_RAW, build3.COMTRADE_SHA256)
    reps = {v[2] for v in NEW.values()}
    for key in ("annual", "monthly", "annual_availability", "monthly_availability"):
        assert set(ct[key].reporter) <= reps
    assert set(ct["annual"].partner) == {643, 826}


def _tiny_snapshot() -> str:
    return "\n".join([
        "#comtrade run3 snapshot|test",
        "#SECTION DA_A|rows 1", "156|2024|H6|true|2025-06-14T15:07:48.2233333|2025-07-04T17:03:56.8933333|855028|1903694698",
        "#SECTION DA_M|rows 1", "156|202401|H6|true|2024-03-20T09:00:00.5|2024-03-20T09:00:00.5",
        "#SECTION ANN|rows 1|sumValue 1500.50", ",".join(snapshots.ANN_COLUMNS), "156,643,X,854231,2024,1500.5,3,0,H6",
        "#SECTION MON|rows 2|sumValue 300.25", "156|202401|854231|100.25", "156|202401|8548|200",
        "#SECTION CALLS|rows 1", "https://example.invalid/preview|3|3|2026-10-21T15:00:00.000Z", ""])


def test_comtrade_run3_reader_round_trip_and_tampering(tmp_path):
    text = _tiny_snapshot()
    p = tmp_path / "snap.txt"
    p.write_text(text)
    sha = hashlib.sha256(text.encode()).hexdigest()
    out = snapshots.read_comtrade_run3(p, sha)
    assert len(out["annual"]) == 1 and len(out["monthly"]) == 2
    assert out["monthly_lines"].line.tolist() == ["156|202401|854231|100.25", "156|202401|8548|200"]
    assert str(out["annual_availability"].first_released.iloc[0]).startswith("2025-06-14 15:07:48.2233")
    with pytest.raises(snapshots.SnapshotMismatch):
        snapshots.read_comtrade_run3(p, "0" * 64)
    bad = text.replace("|100.25", "|101.25")
    p.write_text(bad)
    with pytest.raises(snapshots.SnapshotMismatch):  # the value sum no longer matches its header
        snapshots.read_comtrade_run3(p, hashlib.sha256(bad.encode()).hexdigest())
    short = text.replace("#SECTION MON|rows 2", "#SECTION MON|rows 3")
    p.write_text(short)
    with pytest.raises(snapshots.SnapshotMismatch):
        snapshots.read_comtrade_run3(p, hashlib.sha256(short.encode()).hexdigest())


# ------------------------------------------------------------------ byte-identical tables
def test_run2_tables_are_as_pinned(build3):
    for name, (path, want) in build3.RUN2.items():
        assert _sha(path) == want, name


def test_each_run3_table_is_its_run2_table_then_new_rows_only(build3):
    new_ids, new_reps = {v[1] for v in NEW.values()}, {v[2] for v in NEW.values()}
    for key, (base, path) in build3.RUN3.items():
        old, new = build3.RUN2[base][0].read_bytes(), path.read_bytes()
        assert new.startswith(old), path.name
        added = new[len(old):].decode().splitlines()
        assert added, path.name
        allowed = new_ids if key == "hmrc_monthly" else new_reps
        assert {int(l.split(",")[0]) for l in added} <= allowed, path.name


def test_hmrc_run3_rows_for_the_original_countries_match_run2s_live_input():
    # The phase 1 table run 2's live run read holds the nine corridors and Russia (for reference).
    phase1 = (DATA / "hmrc_monthly_phase1.csv").read_text().splitlines()
    ids = {int(l.split(",")[0]) for l in phase1[1:]}
    run3 = (DATA / "hmrc_monthly_run3.csv").read_text().splitlines()
    rows = [l for l in run3[1:] if int(l.split(",")[0]) in ids and int(l.split(",")[2]) >= 201901]
    assert rows == phase1[1:]


def test_inputs_report_records_the_checks():
    rep = json.loads((BT / "run3_inputs_report.json").read_text())
    assert rep["run2_tables_unchanged"] is True
    assert all(v["original_rows_same"] for v in rep["original_rows"].values())
    assert rep["monthly_check_new_corridors"] == sorted(v[2] for v in NEW.values())


# ------------------------------------------------------------------ the live run
def _run3_lines_for_original_nine() -> list[str]:
    corr = pd.read_csv(CONFIG / "countries.csv").query("role == 'corridor'")
    run2_ids = {str(int(i)) for i in corr.hmrc_country_id}
    text = (DATA / "live_2026-10_run3.csv").read_text().splitlines()
    head = next(csv.reader([text[0]]))
    assert head[-1] == "run"
    out = [text[0][: -len(",run")]]
    for line in text[1:]:
        f = next(csv.reader([line]))
        assert f[-1] == "run3"
        if f[head.index("hmrc_country_id")] in run2_ids:
            out.append(line[: -len(",run3")])
    return out


def test_run3_has_162_series():
    df = pd.read_csv(DATA / "live_2026-10_run3.csv", dtype={"code": str})
    assert len(df) == 162 and df.country.nunique() == 18 and set(df.rule) == {"run2"}


def test_run3_leaves_the_original_nine_byte_identical_to_run2():
    assert "\n".join(_run3_lines_for_original_nine()) + "\n" == (DATA / "live_2026-10.csv").read_text()


def test_run2_outputs_are_unchanged_and_still_reproduced():
    live = _script("run_live")
    run3 = _script("run_live_run3")
    assert _sha(DATA / "live_2026-10.csv") == run3.RUN2_OUT_SHA256
    df = live.build(202610, "run2")
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    assert buf.getvalue() == (DATA / "live_2026-10.csv").read_text()


def test_run3_report_carries_the_licence_and_house_lines():
    text = (ROOT / "backtest" / "reports" / "run3.md").read_text()
    assert "A rise in exports is a lead, not evidence of a breach." in text
    assert "Contains public sector information licensed under the Open Government Licence v3.0." in text
    assert "\u2014" not in text and "\u2013" not in text
