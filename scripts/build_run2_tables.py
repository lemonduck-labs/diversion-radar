"""Builds backtest run 2's inputs from verified snapshots (backtest/preregistration_run2.md).

Reads, refusing anything whose checksums do not match:
- data/raw/hmrc_monthly_2016_2018_browser_2026-10-21.txt  HMRC 2016-18 (header sums)
- data/raw/comtrade_run2_browser_2026-10-21.txt           UN Comtrade (SHA-256 below)
- the phase 1 tables in data/processed

Writes:
- data/processed/hmrc_monthly_2016_2026.csv             HMRC 2016-18 and the phase 1 table
- data/processed/comtrade_annual_2016_2025.csv          exports to Russia 2016-18 and phase 1
- backtest/data/comtrade_monthly_run2.csv               monthly exports to Russia, 2019 onwards
- backtest/data/comtrade_monthly_release_dates.csv      monthly first release dates
- backtest/data/comtrade_release_dates_2015_2025.csv    annual first release dates
- backtest/data/run2_inputs_report.json                 checks and coverage
and logs one ingest entry per browser call (--log).

Usage:  python scripts/build_run2_tables.py [--log]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from radar import snapshots  # noqa: E402
from radar.ingest_log import LOG_PATH, LICENCES  # noqa: E402

RAW, DATA, BT = ROOT / "data" / "raw", ROOT / "data" / "processed", ROOT / "backtest" / "data"
HMRC_2016_18 = RAW / "hmrc_monthly_2016_2018_browser_2026-10-21.txt"
RUN2 = RAW / "comtrade_run2_browser_2026-10-21.txt"
RUN2_SHA256 = "a1b148abe84e11f7f8f883f3a0e3858729c3c8654018d4883b0ebac79282fa93"  # the browser's SHA-256
RETRIEVED_AT = "2026-10-21T12:12:03Z"  # when the browser assembled the snapshot (its header)
CODES = "854231,854232,854233,854239,851762,852691,853221,853224,8548"
MONTHLY_REPORTERS = (417, 51, 398, 268, 792, 860, 31)


def build() -> tuple[dict, dict]:
    if not RUN2_SHA256:
        raise SystemExit("RUN2_SHA256 is not set: transfer and verify the snapshot first")
    hmrc_old = snapshots.read_hmrc(HMRC_2016_18)
    hmrc_new = pd.read_csv(DATA / "hmrc_monthly_phase1.csv", dtype={"code": str})
    if hmrc_old.month.max() >= hmrc_new.month.min():
        raise SystemExit("HMRC tables overlap")
    hmrc = pd.concat([hmrc_old, hmrc_new], ignore_index=True)

    snap = snapshots.read_comtrade_run2(RUN2, RUN2_SHA256)
    ct_new = pd.read_csv(DATA / "comtrade_annual_phase1.csv", dtype={"code": str})
    ann = snap["annual"]
    if ann.year.max() >= ct_new.year.min():
        raise SystemExit("Comtrade annual tables overlap")
    ct = pd.concat([ann[ct_new.columns], ct_new], ignore_index=True)

    mon = snap["monthly"].rename(columns={"period": "period"})
    rel_m = snap["monthly_availability"]
    rel_a = snap["annual_availability"]

    # Checks
    report: dict = {"sha256": RUN2_SHA256, "rows": {k: int(len(v)) for k, v in snap.items()}}
    dup_a = rel_a.duplicated(["reporter", "year"]).sum()
    dup_m = rel_m.duplicated(["reporter", "period"]).sum()
    report["duplicate_availability_rows"] = {"annual": int(dup_a), "monthly": int(dup_m)}
    rel_a = rel_a.sort_values("first_released").drop_duplicates(["reporter", "year"])
    rel_m = rel_m.sort_values("first_released").drop_duplicates(["reporter", "period"])
    # Every monthly dataset from January 2019 for the seven corridors was queried.
    want = rel_m[(rel_m.period >= 201901) & rel_m.reporter.isin(MONTHLY_REPORTERS)][["reporter", "period"]]
    got = set(map(tuple, snap["calls"][["reporter", "period"]].values))
    missing = [f"{r}|{p}" for r, p in want.values if (r, p) not in got]
    report["monthly_datasets_from_2019_not_queried"] = missing   # 2018 months are not used
    stray = mon[~mon[["reporter", "period"]].apply(tuple, axis=1).isin(got)]
    report["monthly_rows_outside_calls"] = int(len(stray))
    # Annual release dates against run 1's table, where both have the year.
    run1 = pd.read_csv(BT / "comtrade_release_dates.csv")
    run1 = run1[run1.is_original_classification.astype(str).str.lower() == "true"]
    run1["first_released"] = pd.to_datetime(run1.first_released, format="ISO8601")
    j = run1.merge(rel_a, on=["reporter", "year"], suffixes=("_run1", "_run2"))
    diff = j[j.first_released_run1 != j.first_released_run2]
    report["annual_release_dates_compared"] = int(len(j))
    report["annual_release_dates_differing"] = [
        f"{r.reporter}|{r.year}: {r.first_released_run1} vs {r.first_released_run2}" for r in diff.itertuples()]
    report["monthly_coverage"] = {
        int(r): {"datasets_from_2019": int(((rel_m.reporter == r) & (rel_m.period >= 201901)).sum()),
                 "first": int(rel_m[rel_m.reporter == r].period.min()) if (rel_m.reporter == r).any() else None,
                 "last": int(rel_m[rel_m.reporter == r].period.max()) if (rel_m.reporter == r).any() else None,
                 "rows": int((mon.reporter == r).sum())}
        for r in MONTHLY_REPORTERS}

    tables = {
        DATA / "hmrc_monthly_2016_2026.csv": hmrc.sort_values(["country_id", "code", "month"]),
        DATA / "comtrade_annual_2016_2025.csv": ct.sort_values(["reporter", "partner", "flow", "code", "year"]),
        BT / "comtrade_monthly_run2.csv": mon.sort_values(["reporter", "period", "code"]),
        BT / "comtrade_monthly_release_dates.csv": rel_m.sort_values(["reporter", "period"]),
        BT / "comtrade_release_dates_2015_2025.csv": rel_a.sort_values(["reporter", "year"]),
    }
    return tables, report | {"_snap": snap}


def log_calls(snap: dict, retrieved_at: str) -> int:
    """One ingest entry per browser call, as for the earlier Comtrade snapshots. Calls that
    asked for several corridors at once are logged from section MULTI (the URL template the
    browser used, with the reporters in the order sent); the one-corridor calls made before
    them are logged with URLs rebuilt from the call record, and say so."""
    base = "https://comtradeapi.un.org/public/v1"
    out = str(RUN2.relative_to(ROOT))
    note = "Headline records only (partner2 0, customs C00, transport 0); SHA-256 verified on load"
    covered, entries = set(), []
    for p, reps in snap["multi"][["period", "reporters"]].values:
        entries.append((f"{base}/preview/C/M/HS?reporterCode={reps}&partnerCode=643&cmdCode={CODES}"
                        f"&period={p}&flowCode=X", note))
        for r in reps.split(","):
            covered.add((int(r), int(p)))
    for r, p in snap["calls"][["reporter", "period"]].values:
        if (int(r), int(p)) not in covered:
            entries.append((f"{base}/preview/C/M/HS?reporterCode={r}&partnerCode=643&cmdCode={CODES}"
                            f"&period={p}&flowCode=X", note + "; URL rebuilt from the call record"))
    for r, y in snap["annual"][["reporter", "year"]].drop_duplicates().values:
        entries.append((f"{base}/preview/C/A/HS?reporterCode={r}&partnerCode=643&cmdCode={CODES}"
                        f"&period={y}&flowCode=X", note + "; URL rebuilt from the call record"))
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        for url, n in entries:
            fh.write(json.dumps({"retrieved_at": retrieved_at, "source": "comtrade",
                                 "licence": LICENCES["comtrade"], "url": url, "method": "browser",
                                 "out_file": out, "note": n}) + "\n")
    return len(entries)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", action="store_true", help="append ingest entries for the browser calls")
    a = ap.parse_args(argv)
    tables, report = build()
    snap = report.pop("_snap")
    for path, df in tables.items():
        df.to_csv(path, index=False)
        print(f"wrote {path.relative_to(ROOT)} ({len(df)} rows)")
    (BT / "run2_inputs_report.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({k: v for k, v in report.items() if k != "monthly_coverage"}, indent=2, default=str))
    if a.log:
        print(f"logged {log_calls(snap, RETRIEVED_AT)} ingest entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
