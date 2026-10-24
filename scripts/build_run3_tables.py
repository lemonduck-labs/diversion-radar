"""Builds run 3's inputs (backtest/RESEARCH_LOG.md, entry R3): run 2's live inputs with the
nine new corridors' rows added, and nothing else changed.

Reads, refusing anything whose checksums do not match:
- data/raw/hmrc_monthly_run3_browser_2026-10-21.txt        HMRC (header sums and SHA-256)
- data/raw/hmrc_monthly_run3_calls_browser_2026-10-21.txt  the 81 HMRC calls (SHA-256)
- data/raw/comtrade_run3_browser_2026-10-21.txt            UN Comtrade (SHA-256, section sums)
- run 2's tables, whose SHA-256 values are pinned below

Writes each run 3 table as its run 2 table, byte for byte, followed by the new rows:
- data/processed/hmrc_monthly_run3.csv                  from data/processed/hmrc_monthly_2016_2026.csv
- data/processed/comtrade_annual_run3.csv               from data/processed/comtrade_annual_phase1.csv
- backtest/data/comtrade_release_dates_run3.csv         from backtest/data/comtrade_release_dates.csv
- backtest/data/comtrade_monthly_run3.csv               from backtest/data/comtrade_monthly_run2.csv
- backtest/data/comtrade_monthly_release_dates_run3.csv from backtest/data/comtrade_monthly_release_dates.csv
- backtest/data/run3_inputs_report.json                 checks, coverage and gaps
and, with --log, one ingest entry per browser call.

The new rows are processed as run 2's were: annual release dates for 2018 onwards in the
original classification, monthly release dates from January 2018, the earliest release kept
where getDA lists a dataset twice, and release times cut to the second (getDA gives them to
a fraction of one; phase 1 and run 2 stored seconds). The build stops if a run 2 table is
not as pinned, before or after; if a run 3 table does not start with its run 2 table's bytes;
if a new row belongs to an original corridor; or if a monthly dataset from January 2019 for a
corridor with the monthly check was not queried.

Usage:  python scripts/build_run3_tables.py [--log]

A rise in exports is a lead, not evidence of a breach.
Contains public sector information licensed under the Open Government Licence v3.0.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from radar import snapshots  # noqa: E402
from radar.hmrc import monthly_exports_url  # noqa: E402
from radar.ingest_log import LICENCES, LOG_PATH  # noqa: E402

RAW, DATA, BT, CONFIG = ROOT / "data" / "raw", ROOT / "data" / "processed", ROOT / "backtest" / "data", ROOT / "config"
HMRC_RAW = RAW / "hmrc_monthly_run3_browser_2026-10-21.txt"
HMRC_CALLS = RAW / "hmrc_monthly_run3_calls_browser_2026-10-21.txt"
COMTRADE_RAW = RAW / "comtrade_run3_browser_2026-10-21.txt"
# SHA-256 values the browser computed before each file left it
HMRC_SHA256 = "e6dc508b61956d39c27f994d6e7886fa5644ca20c57fe96091703f7dfcda5842"
HMRC_CALLS_SHA256 = "8ba610c99c453f1ebb310928a1dfe5f4930d1e3900fd95255276c407be3d4a56"
COMTRADE_SHA256 = "73db5d9be0ded10201625b42740e55eaa8b03f684348cce2604e468448480ed1"

# Run 2's tables, as committed (pinned so a change to them stops the build)
RUN2 = {
    "hmrc_monthly_2016_2026": (DATA / "hmrc_monthly_2016_2026.csv",
                               "e141231ca5592460156fbcec415287cbf5dad2d375a6ee33add60ad3b7268ec5"),
    "hmrc_monthly_phase1": (DATA / "hmrc_monthly_phase1.csv",
                            "942706af5f37b617b9eda7e25f073f28cb6069d9fcf7b6a4268015512f98770b"),
    "comtrade_annual_phase1": (DATA / "comtrade_annual_phase1.csv",
                               "bfdce40bdf2d8bac53adc80b7d4339063e06d5b9bc5a8e87ce367fa3eaeefe7d"),
    "comtrade_release_dates": (BT / "comtrade_release_dates.csv",
                               "5728cace1b288df63affe0060639bdca525bda42d25387867cd97eb45e6de325"),
    "comtrade_monthly_run2": (BT / "comtrade_monthly_run2.csv",
                              "fa9f2acf6e55d9b4d5c3565629cc8735c7670775890ae2e64903dc7f7976b4a2"),
    "comtrade_monthly_release_dates": (BT / "comtrade_monthly_release_dates.csv",
                                       "0b0debae00cf0a98d613f8ddee4e08371d1cbd46fabc07d9ee0722816048b02b"),
    "countries": (CONFIG / "countries.csv",
                  "0d8c90b204ea586668a33a8950f3a13140f51e585abd0b822c79b9a18bb5f5df"),
}
RUN3 = {  # run 3 table: (run 2 table it extends, path)
    "hmrc_monthly": ("hmrc_monthly_2016_2026", DATA / "hmrc_monthly_run3.csv"),
    "comtrade_annual": ("comtrade_annual_phase1", DATA / "comtrade_annual_run3.csv"),
    "release_dates": ("comtrade_release_dates", BT / "comtrade_release_dates_run3.csv"),
    "monthly": ("comtrade_monthly_run2", BT / "comtrade_monthly_run3.csv"),
    "monthly_release_dates": ("comtrade_monthly_release_dates", BT / "comtrade_monthly_release_dates_run3.csv"),
}
RETRIEVED_DATE = "2026-10-21"
MONTHLY_FROM = 201901


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def corridors() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(run 2's nine corridors, run 3's nine new ones) from config/countries_run3.csv."""
    run3 = pd.read_csv(CONFIG / "countries_run3.csv")
    run3 = run3[run3.role == "corridor"].astype({"hmrc_country_id": int, "comtrade_code": int})
    run2 = pd.read_csv(CONFIG / "countries.csv")
    run2 = run2[run2.role == "corridor"].astype({"hmrc_country_id": int, "comtrade_code": int})
    new = run3[~run3.hmrc_country_id.isin(run2.hmrc_country_id)]
    return run2, new


def check_run2() -> dict:
    got = {k: sha256(p) for k, (p, _) in RUN2.items()}
    bad = {k: v for k, v in got.items() if v != RUN2[k][1]}
    if bad:
        raise SystemExit(f"run 2 tables differ from the pinned SHA-256: {sorted(bad)}")
    return got


def _second(ts: pd.Series) -> pd.Series:
    """Release times cut to the second and written as run 2's tables write them."""
    return ts.dt.floor("s").dt.strftime("%Y-%m-%d %H:%M:%S")


def new_rows(new: pd.DataFrame) -> tuple[dict[str, list[str]], dict, dict]:
    """The new corridors' rows for each run 3 table, as CSV lines, with the checks behind them."""
    hmrc = snapshots.read_hmrc(HMRC_RAW)
    if sha256(HMRC_RAW) != HMRC_SHA256 or sha256(HMRC_CALLS) != HMRC_CALLS_SHA256:
        raise SystemExit("HMRC snapshot or call list does not match the browser's SHA-256")
    if not COMTRADE_SHA256:
        raise SystemExit("COMTRADE_SHA256 is not set: transfer and verify the snapshot first")
    ct = snapshots.read_comtrade_run3(COMTRADE_RAW, COMTRADE_SHA256)
    new_ids, new_reps = set(new.hmrc_country_id), set(new.comtrade_code)
    rep_order = {r: i for i, r in enumerate(new.comtrade_code)}
    report: dict = {"hmrc_sha256": HMRC_SHA256, "comtrade_sha256": COMTRADE_SHA256}

    # HMRC: every series called once, with the URL the client in radar/hmrc.py would build
    codes = pd.read_csv(CONFIG / "codes.csv", dtype={"code": str})
    calls = [l.split("|") for l in HMRC_CALLS.read_text().splitlines() if l.strip()]
    want = [(cid, k.code, monthly_exports_url(cid, int(k.cn8_from), int(k.cn8_to), 201601))
            for cid in new.hmrc_country_id for k in codes.itertuples()]
    if [(int(c[0]), c[1], c[5]) for c in calls] != want:
        raise SystemExit("HMRC calls differ from the queries radar/hmrc.py builds")
    n = hmrc.groupby(["country_id", "code"]).size()
    if any(int(c[2]) != int(n.get((int(c[0]), c[1]), 0)) for c in calls):
        raise SystemExit("HMRC call row counts differ from the snapshot")
    if not set(hmrc.country_id) <= new_ids:
        raise SystemExit("HMRC snapshot holds a corridor that is not new")
    hmrc = hmrc.sort_values(["country_id", "code", "month"])
    lines = {"hmrc_monthly": [f"{r.country_id},{r.code},{r.month},{r.value_gbp},{r.net_mass_kg}"
                              for r in hmrc.itertuples()]}
    # The value and mass sums are the snapshot header's checksums (read_hmrc checks them); they
    # are not repeated here.
    report["hmrc"] = {"rows": int(len(hmrc)), "first_month": int(hmrc.month.min()),
                      "last_month": int(hmrc.month.max()),
                      "series_with_no_exports": sorted(f"{c[0]},{c[1]}" for c in calls if int(c[2]) == 0)}

    # UN Comtrade annual: sorted, values written as pandas writes a float column (as in
    # comtrade_annual_2016_2025.csv: a whole number gains ".0"); every value reads back the same
    ann = ct["annual"]
    if not set(ann.reporter) <= new_reps:
        raise SystemExit("annual records for a corridor that is not new")
    ann = ann.assign(o=ann.reporter.map(rep_order)).sort_values(["o", "partner", "flow", "code", "year"])
    ann = ann.drop(columns="o").astype({"value_usd": float, "net_wgt_kg": float})
    csv_text = ann[snapshots.ANN_COLUMNS].to_csv(header=False, index=False, lineterminator="\n")
    lines["comtrade_annual"] = csv_text.splitlines()
    back = pd.read_csv(io.StringIO(",".join(snapshots.ANN_COLUMNS) + "\n" + csv_text), dtype={"code": str})
    if not back.reset_index(drop=True).equals(ann[snapshots.ANN_COLUMNS].reset_index(drop=True)):
        raise SystemExit("annual rows do not read back to the snapshot's values")

    # Release dates, processed as phase 1 and run 2 did
    da_a, da_m = ct["annual_availability"].copy(), ct["monthly_availability"].copy()
    if not (set(da_a.reporter) | set(da_m.reporter)) <= new_reps:
        raise SystemExit("availability records for a corridor that is not new")
    report["availability_rows"] = {"annual": int(len(da_a)), "monthly": int(len(da_m))}
    report["availability_not_original"] = {"annual": int((da_a.is_original_classification != "true").sum()),
                                           "monthly": int((da_m.is_original_classification != "true").sum())}
    a = da_a[(da_a.year >= 2018) & (da_a.is_original_classification == "true")]
    dup_a = int(a.duplicated(["reporter", "year"]).sum())
    a = a.sort_values("first_released").drop_duplicates(["reporter", "year"])
    a = a.assign(o=a.reporter.map(rep_order)).sort_values(["o", "year"])
    lines["release_dates"] = [f"{r.reporter},{r.year},{r.classification},true,{f},{l},{r.total_records},{r.dataset_checksum}"
                              for r, f, l in zip(a.itertuples(), _second(a.first_released), _second(a.last_released))]
    m = da_m[da_m.period >= 201801]
    dup_m = int(m.duplicated(["reporter", "period"]).sum())
    m = m.sort_values("first_released").drop_duplicates(["reporter", "period"])
    m = m.sort_values(["reporter", "period"])
    lines["monthly_release_dates"] = [f"{r.reporter},{r.period},{r.classification},{f},{l}"
                                      for r, f, l in zip(m.itertuples(), _second(m.first_released), _second(m.last_released))]
    report["duplicate_availability_rows"] = {"annual": dup_a, "monthly": dup_m}

    # Which new corridors get the monthly check: run 2's criterion, monthly data after 2019
    monthly_reps = sorted(int(r) for r in set(da_m[da_m.period > 201912].reporter))
    report["monthly_check_new_corridors"] = monthly_reps

    # Monthly values: every dataset from January 2019 for those corridors must have been queried
    queried = set()
    for url in ct["calls"].url:
        mm = re.search(r"/preview/C/M/HS\?reporterCode=([\d,]+)&partnerCode=643&.*period=(\d{6})&flowCode=X$", url)
        if mm:
            for r in mm.group(1).split(","):
                queried.add((int(r), int(mm.group(2))))
    need = {(int(r), int(p)) for r, p in da_m[(da_m.period >= MONTHLY_FROM) & da_m.reporter.isin(monthly_reps)][
        ["reporter", "period"]].values}
    missing = sorted(need - queried)
    if missing:
        raise SystemExit(f"monthly datasets not queried: {missing[:10]}")
    mon = ct["monthly"]
    stray = [(int(r), int(p)) for r, p in mon[["reporter", "period"]].values if (int(r), int(p)) not in queried]
    if stray:
        raise SystemExit(f"monthly rows outside the calls made: {stray[:10]}")
    raw_mon = {}  # the snapshot's own value strings, so no number is reformatted
    for line in ct["monthly_lines"].line:
        r, p, c, v = line.split("|")
        raw_mon.setdefault((int(r), int(p), c), []).append(v)
    keys = sorted(raw_mon)
    lines["monthly"] = [f"{r},{p},{c},{v}" for (r, p, c) in keys for v in raw_mon[(r, p, c)]]
    report["monthly_queried_corridor_months"] = len(queried)
    report["calls"] = {"comtrade": int(len(ct["calls"])), "hmrc": len(calls)}

    # Coverage and gaps by corridor
    cov = {}
    hm = hmrc.groupby("country_id")
    for c in new.itertuples():
        rep, cid = int(c.comtrade_code), int(c.hmrc_country_id)
        x = ann[(ann.reporter == rep)]
        cov[c.name] = {
            "hmrc_months": int(len(hm.get_group(cid))) if cid in hm.groups else 0,
            "hmrc_codes_with_exports": int(hmrc[hmrc.country_id == cid].code.nunique()),
            "annual_years_exports_to_russia": sorted(int(y) for y in set(x[(x.partner == 643) & (x.flow == "X")].year)),
            "annual_years_imports_from_uk": sorted(int(y) for y in set(x[(x.partner == 826) & (x.flow == "M")].year)),
            "annual_years_released": sorted(int(y) for y in set(da_a[(da_a.reporter == rep)].year) if y >= 2019),
            "monthly_check": rep in monthly_reps,
            "monthly_first": int(da_m[da_m.reporter == rep].period.min()) if (da_m.reporter == rep).any() else None,
            "monthly_last": int(da_m[da_m.reporter == rep].period.max()) if (da_m.reporter == rep).any() else None,
            "monthly_datasets_from_2019": int(((da_m.reporter == rep) & (da_m.period >= MONTHLY_FROM)).sum()),
            "monthly_rows": int((mon.reporter == rep).sum()),
        }
    report["coverage"] = cov
    return lines, report, {"comtrade": ct, "hmrc_calls": calls}


def write_tables(lines: dict[str, list[str]]) -> dict:
    """Each run 3 table: run 2's bytes, then the new lines. Checked by reading back."""
    out = {}
    for key, (base, path) in RUN3.items():
        base_bytes = RUN2[base][0].read_bytes()
        if not base_bytes.endswith(b"\n"):
            raise SystemExit(f"{RUN2[base][0].name} does not end with a newline")
        add = "".join(l + "\n" for l in lines[key]).encode()
        path.write_bytes(base_bytes + add)
        back = path.read_bytes()
        if not back.startswith(base_bytes) or back[len(base_bytes):] != add:
            raise SystemExit(f"{path.name}: read-back check failed")
        out[path.name] = {"extends": RUN2[base][0].name, "run2_rows": base_bytes.count(b"\n") - 1,
                          "new_rows": len(lines[key]), "sha256": hashlib.sha256(back).hexdigest()}
    return out


def _first_field(line: str) -> int:
    return int(line.split(",")[0])  # country_id or reporter comes first in every table


def check_original_rows(new_ids: set, new_reps: set) -> dict:
    """Read as text, the rows of each run 3 table for every country its run 2 table holds (the
    nine corridors, and Russia in the HMRC tables, kept there for reference) equal run 2's table
    line for line, and every other row belongs to a new corridor. For HMRC, also against the
    phase 1 table that run 2's live run read (months from January 2019)."""
    res = {}
    for key, (base, path) in RUN3.items():
        old = RUN2[base][0].read_text().splitlines()
        new = path.read_text().splitlines()
        ids = {_first_field(l) for l in old[1:]}
        orig = [l for l in new[1:] if _first_field(l) in ids]
        others = {_first_field(l) for l in new[1:] if _first_field(l) not in ids}
        allowed = new_ids if key == "hmrc_monthly" else new_reps
        ok = new[0] == old[0] and orig == old[1:] and others <= allowed and not (ids & allowed)
        res[path.name] = {"header_same": new[0] == old[0], "original_rows_same": orig == old[1:],
                          "original_rows": len(orig), "countries_in_run2_table": sorted(ids),
                          "new_countries": sorted(others)}
        if not ok:
            raise SystemExit(f"{path.name}: the original rows differ from {RUN2[base][0].name}, or a row "
                             "belongs to neither")
    phase1 = RUN2["hmrc_monthly_phase1"][0].read_text().splitlines()
    new = RUN3["hmrc_monthly"][1].read_text().splitlines()
    ids = {_first_field(l) for l in phase1[1:]}
    orig19 = [l for l in new[1:] if _first_field(l) in ids and int(l.split(",")[2]) >= 201901]
    same = orig19 == phase1[1:]
    res["hmrc_monthly_run3.csv against hmrc_monthly_phase1.csv, from 2019"] = {"original_rows_same": same,
                                                                              "original_rows": len(orig19)}
    if not same:
        raise SystemExit("HMRC run 3 rows for the original corridors differ from the phase 1 table")
    return res


def log_calls(extra: dict) -> int:
    """One ingest entry per browser call, with the time the browser recorded for it."""
    entries = []
    hmrc_out, ct_out = str(HMRC_RAW.relative_to(ROOT)), str(COMTRADE_RAW.relative_to(ROOT))
    for cid, code, n, pages, at, url in extra["hmrc_calls"]:
        entries.append({"retrieved_at": at, "source": "hmrc", "licence": LICENCES["hmrc"], "url": url,
                        "rows": int(n), "sha256": HMRC_SHA256, "out_file": hmrc_out, "method": "browser",
                        "note": "Run 3, nine corridors added; one snapshot for all 81 queries; header sums and "
                                "SHA-256 verified; call list in " + str(HMRC_CALLS.relative_to(ROOT))})
    for c in extra["comtrade"]["calls"].itertuples():
        kind = "data availability (first and last release dates)" if "/getDA/" in c.url else \
            "headline records only (partner2 0, customs C00, transport 0)"
        entries.append({"retrieved_at": c.retrieved_at, "source": "comtrade", "licence": LICENCES["comtrade"],
                        "url": c.url, "rows": int(c.headline), "sha256": COMTRADE_SHA256, "out_file": ct_out,
                        "method": "browser",
                        "note": f"Run 3, nine corridors added; {kind}; {int(c.records)} records returned; "
                                "SHA-256 verified on load"})
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")
    return len(entries)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", action="store_true", help="append ingest entries for the browser calls")
    a = ap.parse_args(argv)
    before = check_run2()
    run2, new = corridors()
    if len(run2) != 9 or len(new) != 9:
        raise SystemExit(f"expected 9 original and 9 new corridors, found {len(run2)} and {len(new)}")
    lines, report, extra = new_rows(new)
    report["tables"] = write_tables(lines)
    report["original_rows"] = check_original_rows({int(i) for i in new.hmrc_country_id},
                                                  {int(r) for r in new.comtrade_code})
    after = check_run2()
    report["run2_tables_unchanged"] = before == after
    report["run2_sha256"] = after
    (BT / "run3_inputs_report.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    for name, t in report["tables"].items():
        print(f"wrote {name}: {t['run2_rows']} run 2 rows, then {t['new_rows']} new")
    print("original corridors' rows identical to run 2's tables; run 2 tables unchanged")
    print("monthly check for the new corridors:", report["monthly_check_new_corridors"])
    if a.log:
        print(f"logged {log_calls(extra)} ingest entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
