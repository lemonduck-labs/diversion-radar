"""Phase 1 pull: everything scripts/analyse.py reads, for every country in
config/countries.csv.

Run from the repo root on a machine that can reach both APIs:

    python scripts/pull.py [--overwrite]

1. HMRC: monthly UK exports of the nine codes to every corridor country and to
   Russia, January 2019 onwards (radar/hmrc.py).
2. UN Comtrade: for every corridor, its exports to Russia (partner 643, flow X)
   and its imports from the UK (partner 826, flow M), 2019 to 2025, one year per
   call, because the preview endpoint takes one period per call (radar/comtrade.py).

Raw responses go to data/raw/ and every call is logged in data/ingest_log.jsonl.
The tidy tables go to data/processed/hmrc_monthly_phase1.csv and
comtrade_annual_phase1.csv. If either already exists (for example a
checksum-verified browser snapshot), the script stops before pulling anything
unless --overwrite is given. Nothing is written to data/processed until every
call has succeeded, so a failed run never leaves a partial table behind.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from radar import comtrade, config  # noqa: E402
from radar.hmrc import HMRCClient, pull_monthly_exports  # noqa: E402

YEARS = [str(y) for y in range(2019, 2026)]
RUSSIA, UK = 643, 826
FLOWS = ((RUSSIA, "X"), (UK, "M"))   # onward check, mirror check
HMRC_OUT = config.PROCESSED / "hmrc_monthly_phase1.csv"
COMTRADE_OUT = config.PROCESSED / "comtrade_annual_phase1.csv"
COMTRADE_COLS = ["reporter", "partner", "flow", "code", "year", "value_usd", "net_wgt_kg",
                 "is_reported", "classification"]


def hmrc_countries(countries: list[dict]) -> list[dict]:
    """Every corridor country and Russia: the rows with an HMRC id and role
    corridor or target."""
    return [c for c in countries
            if c["hmrc_country_id"].strip() and c["role"] in ("corridor", "target")]


def comtrade_jobs(countries: list[dict], years=YEARS) -> list[tuple[int, int, str, str]]:
    """(reporter, partner, flow, year) for every corridor: X to Russia and M from
    the UK, one year per job."""
    return [(int(c["comtrade_code"]), partner, flow, year)
            for c in config.corridors(countries) for partner, flow in FLOWS for year in years]


def comtrade_row(r: dict) -> dict:
    """One headline Comtrade record in the layout of the processed table."""
    return {"reporter": r["reporterCode"], "partner": r["partnerCode"], "flow": r["flowCode"],
            "code": r["cmdCode"], "year": int(r["period"]), "value_usd": r.get("primaryValue"),
            "net_wgt_kg": r.get("netWgt"), "is_reported": int(bool(r.get("isReported"))),
            "classification": r.get("classificationCode")}


def check_outputs(paths: list[Path], overwrite: bool) -> None:
    existing = [p for p in paths if p.exists()]
    if existing and not overwrite:
        names = ", ".join(str(p) for p in existing)
        raise SystemExit(f"Refusing to replace {names}; pass --overwrite to replace them")


def pull_hmrc(countries: list[dict], codes: list[dict], raw_dir: Path,
              client: HMRCClient | None = None) -> pd.DataFrame:
    client = client or HMRCClient()
    monthly = []
    for c in hmrc_countries(countries):
        cid = int(c["hmrc_country_id"])
        for k in codes:
            rows = pull_monthly_exports(client, cid, k["code"], int(k["cn8_from"]),
                                        int(k["cn8_to"]), raw_dir)
            monthly += [{"country_id": cid, "code": k["code"], "month": int(r["MonthId"]),
                         "value_gbp": r["Value"], "net_mass_kg": r["NetMass"]} for r in rows]
            print(f"HMRC {c['name']:<22} {k['code']}: {len(rows)} months")
    cols = ["country_id", "code", "month", "value_gbp", "net_mass_kg"]
    return pd.DataFrame(monthly, columns=cols).sort_values(["country_id", "code", "month"])


def pull_comtrade(countries: list[dict], codes: list[dict], raw_dir: Path,
                  years=YEARS, pull=comtrade.pull) -> pd.DataFrame:
    code_list = [k["code"] for k in codes]
    names = {int(c["comtrade_code"]): c["name"] for c in countries}
    out = []
    for reporter, partner, flow, year in comtrade_jobs(countries, years):
        rows = pull(reporter, partner, code_list, [year], raw_dir, flow=flow)
        out += [comtrade_row(r) for r in rows]
        print(f"Comtrade {names[reporter]:<22} {flow} partner {partner} {year}: {len(rows)} rows")
    return pd.DataFrame(out, columns=COMTRADE_COLS)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pull HMRC and UN Comtrade data for phase 1")
    ap.add_argument("--overwrite", action="store_true",
                    help="replace existing processed tables")
    args = ap.parse_args(argv)
    check_outputs([HMRC_OUT, COMTRADE_OUT], args.overwrite)
    config.RAW.mkdir(parents=True, exist_ok=True)
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    countries, codes = config.countries(), config.codes()

    monthly = pull_hmrc(countries, codes, config.RAW)
    ct = pull_comtrade(countries, codes, config.RAW)

    monthly.to_csv(HMRC_OUT, index=False)
    ct.to_csv(COMTRADE_OUT, index=False)
    print(f"Wrote {HMRC_OUT} ({len(monthly)} rows) and {COMTRADE_OUT} ({len(ct)} rows)")
    pulled = set(monthly["country_id"])
    empty = [c["name"] for c in hmrc_countries(countries) if int(c["hmrc_country_id"]) not in pulled]
    print(f"Countries with no HMRC rows: {', '.join(empty) or 'none'}")
    for name, flow, missing in missing_years(countries, ct):
        print(f"Comtrade {name} flow {flow}: no records for {missing} (not yet published, or nil)")


def missing_years(countries: list[dict], ct: pd.DataFrame, years=YEARS):
    """(corridor, flow, years with no records) for every corridor and flow with a gap."""
    have = ct.groupby(["reporter", "flow"])["year"].agg(set).to_dict() if len(ct) else {}
    for c in config.corridors(countries):
        for _, flow in FLOWS:
            got = have.get((int(c["comtrade_code"]), flow), set())
            missing = [int(y) for y in years if int(y) not in got]
            if missing:
                yield c["name"], flow, missing


if __name__ == "__main__":
    main()
