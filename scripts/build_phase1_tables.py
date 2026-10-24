"""Rebuild the phase 1 input tables from the four browser snapshots, checking every
checksum, and confirm they match data/processed row for row (or write them with
--write). Also writes the UN Comtrade release dates used by the backtest.

    python scripts/build_phase1_tables.py           # check only
    python scripts/build_phase1_tables.py --write   # write the tables
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from radar import snapshots  # noqa: E402

RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed"
AVAILABILITY_SHA256 = "c3446c1bd690f0ccd8011f21cfaa79bed8003baf550cfc72739b63e6c2a146d3"


def main(write: bool) -> int:
    hmrc = pd.concat([snapshots.read_hmrc(RAW / "hmrc_monthly_browser_2026-10-21.txt"),
                      snapshots.read_hmrc(RAW / "hmrc_monthly_browser_2026-10-21b.txt")])
    hmrc = hmrc.sort_values(["country_id", "code", "month"]).reset_index(drop=True)
    ct = pd.concat([snapshots.read_comtrade(RAW / "comtrade_annual_browser_2026-10-21.txt"),
                    snapshots.read_comtrade(RAW / "comtrade_annual_browser_2026-10-21b.txt")],
                   ignore_index=True)
    da = snapshots.read_availability(RAW / "comtrade_availability_browser_2026-10-21.txt",
                                     AVAILABILITY_SHA256)
    print(f"HMRC {len(hmrc)} rows, £{hmrc.value_gbp.sum():,}; Comtrade {len(ct)} rows, "
          f"${ct.value_usd.sum():,}; release dates {len(da['annual'])} annual, "
          f"{len(da['monthly'])} monthly")
    targets = {OUT / "hmrc_monthly_phase1.csv": (hmrc, ["country_id", "code", "month"]),
               OUT / "comtrade_annual_phase1.csv": (ct, ["reporter", "partner", "flow", "code", "year"])}
    ok = True
    for path, (df, keys) in targets.items():
        if write:
            df.to_csv(path, index=False)
            print("wrote", path.name)
            continue
        have = pd.read_csv(path, dtype={"code": str})
        a = df.sort_values(keys).reset_index(drop=True)
        b = have.sort_values(keys).reset_index(drop=True)[a.columns]
        same = a.astype(str).equals(b.astype(str))
        ok &= same
        print(f"{path.name}: {'matches' if same else 'DIFFERS'} ({len(b)} rows on disk)")
    bt = ROOT / "backtest" / "data"
    da["annual"].to_csv(bt / "comtrade_release_dates.csv", index=False)
    da["monthly"].to_csv(bt / "comtrade_monthly_release_dates_2022_2023.csv", index=False)
    da["monthly_summary"].to_csv(bt / "comtrade_monthly_coverage.csv", index=False)
    print("wrote the release-date tables in backtest/data")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main("--write" in sys.argv))
