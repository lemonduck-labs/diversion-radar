"""Phase 0 data spike: pull everything the baseline check needs.

Run from the repo root on a machine with internet access:

    python scripts/pull_spike.py

Writes raw responses to data/raw/, logs every call in data/ingest_log.jsonl,
and writes data/processed/hmrc_monthly.csv and data/processed/comtrade_annual.csv.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from radar import comtrade  # noqa: E402
from radar.hmrc import HMRCClient, pull_monthly_exports  # noqa: E402

RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
YEARS = [str(y) for y in range(2019, 2026)]


def load_config():
    codes = list(csv.DictReader((ROOT / "config" / "codes.csv").open()))
    countries = list(csv.DictReader((ROOT / "config" / "countries.csv").open()))
    return codes, countries


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    codes, countries = load_config()

    # 1. UK exports to each corridor country, and to Russia for reference
    client = HMRCClient()
    monthly = []
    for c in countries:
        if not c["hmrc_country_id"]:
            continue
        for k in codes:
            rows = pull_monthly_exports(client, int(c["hmrc_country_id"]), k["code"],
                                        int(k["cn8_from"]), int(k["cn8_to"]), RAW)
            for r in rows:
                monthly.append({"country_id": int(c["hmrc_country_id"]), "code": k["code"],
                                "month": int(r["MonthId"]), "value_gbp": r["Value"],
                                "net_mass_kg": r["NetMass"]})
            print(f"HMRC {c['name']:<22} {k['code']}: {len(rows)} months")
    pd.DataFrame(monthly).to_csv(PROCESSED / "hmrc_monthly.csv", index=False)

    # 2. Corridor countries' exports of the same codes to Russia (onward check),
    #    and their imports from the UK (mirror check)
    code_list = [k["code"] for k in codes]
    ct_rows = []
    for c in countries:
        if c["role"] != "corridor":
            continue
        for partner, flow in ((643, "X"), (826, "M")):
            rows = comtrade.pull(int(c["comtrade_code"]), partner, code_list, YEARS, RAW, flow=flow)
            for r in rows:
                ct_rows.append({"reporter": r["reporterCode"], "partner": r["partnerCode"],
                                "flow": r["flowCode"], "code": r["cmdCode"], "year": int(r["period"]),
                                "value_usd": r.get("primaryValue"), "net_wgt_kg": r.get("netWgt")})
            print(f"Comtrade {c['name']:<22} partner {partner} {flow}: {len(rows)} rows")
    pd.DataFrame(ct_rows).to_csv(PROCESSED / "comtrade_annual.csv", index=False)


if __name__ == "__main__":
    main()
