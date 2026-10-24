"""Phase 1 analysis: the averaged and persistent UK rise rules, the onward check
and the mirror check, for every corridor and goods code in config/.

    python scripts/analyse.py [--hmrc PATH] [--comtrade PATH]

Default inputs, in data/processed/:
- HMRC: hmrc_monthly_phase1.csv (the phase 0 hmrc_monthly.csv if it is absent);
- Comtrade: comtrade_annual_phase1.csv when present, else comtrade_annual.csv.

Writes data/processed/leads_phase1.csv (one row per corridor and code) and
data/processed/mirror_phase1.csv (one row per corridor, code and year). Countries
with no data yet are reported as "no data". scripts/analyse_spike.py and its
outputs are left alone, so phase 0 stays reproducible.

A rise in exports is a lead, not evidence of a breach.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from radar import config, leads, mirror, rules  # noqa: E402

PROC = config.PROCESSED
HMRC_DEFAULT, HMRC_FALLBACK = PROC / "hmrc_monthly_phase1.csv", PROC / "hmrc_monthly.csv"
CT_DEFAULT, CT_FALLBACK = PROC / "comtrade_annual_phase1.csv", PROC / "comtrade_annual.csv"
LEADS_OUT, MIRROR_OUT = PROC / "leads_phase1.csv", PROC / "mirror_phase1.csv"

HMRC_COLS = ["country_id", "code", "month", "value_gbp", "net_mass_kg"]
CT_COLS = ["reporter", "partner", "flow", "code", "year", "value_usd", "net_wgt_kg"]
OGL = "Contains public sector information licensed under the Open Government Licence v3.0."


def pick(preferred: Path, fallback: Path) -> Path:
    """The preferred file when it exists, else the fallback."""
    return preferred if preferred.exists() else fallback


def read(path: Path, cols: list[str]) -> pd.DataFrame:
    """A processed table, or an empty one with the expected columns if the file is
    missing, so a country or source with no data yet does not stop the run."""
    if not path.exists():
        print(f"Not found, treated as no data: {path}")
        return pd.DataFrame({c: pd.Series(dtype="str" if c in ("code", "flow") else "float")
                             for c in cols})
    return pd.read_csv(path, dtype={"code": str, "flow": str})


def _fmt(v) -> str:
    return "" if pd.isna(v) else f"{v:,.0f}"


def report(out: pd.DataFrame, mirror_rows: pd.DataFrame, countries: list[dict]) -> None:
    show = ["country", "code", "baseline_avg", "gbp_2023", "gbp_2024", "gbp_2025",
            "uk_years_met", "uk_rise_avg", "uk_rise_persistent", "onward_ratio", "mirror_gap"]
    with pd.option_context("display.width", 250, "display.max_columns", 30,
                           "display.float_format", "{:,.1f}".format):
        for status in [leads.LEAD, leads.DROPPED, leads.UK_NO_ONWARD_DATA, leads.UK_ONLY]:
            part = out[out["status"] == status]
            print(f"\n{status}: {len(part)}")
            if len(part):
                print(part[show].to_string(index=False))

    flagged = mirror_rows[mirror_rows["flag"] != ""]
    print(f"\nMirror gaps: {len(flagged)} flagged years in "
          f"{(mirror_rows['status'] == mirror.CHECKED).sum()} checked (all in {MIRROR_OUT.name})")
    if len(flagged):
        counts = flagged.pivot_table(index="country", columns="flag", values="year",
                                     aggfunc="count", fill_value=0)
        print(counts.to_string())

    def lines(rows):
        for r in rows.itertuples(index=False):
            print(f"  {r.country:<22} {r.code:<7} {r.year}  {r.flag:<16} corridor imports "
                  f"${_fmt(r.corridor_imports_usd)} vs UK exports ${_fmt(r.uk_exports_usd)} "
                  f"(GBP {_fmt(r.uk_exports_gbp)} at {r.usd_per_gbp})")

    keyed = out[out["status"].isin([leads.LEAD, leads.DROPPED])][["country_id", "code"]]
    on_leads = flagged.merge(keyed, on=["country_id", "code"])
    print(f"\nMirror gaps on leads and dropped leads: {len(on_leads)}")
    lines(on_leads)
    higher = flagged[flagged["flag"] == mirror.CORRIDOR_HIGHER]
    print(f"\nAll '{mirror.CORRIDOR_HIGHER}' years: {len(higher)}")
    lines(higher)

    print("\nData coverage by corridor (years used; 2022 is outside both onward windows):")
    for c in config.corridors(countries):
        rows = out[out["country"] == c["name"]]
        first = rows.iloc[0]
        checked = mirror_rows[(mirror_rows["country"] == c["name"])
                              & (mirror_rows["status"] == mirror.CHECKED)]["year"]
        onward_years = (f"{first['onward_base_years']} | {first['onward_post_years']}"
                        if first["onward_data"] != "no data" else "no data")
        mirror_years = ",".join(map(str, sorted(set(checked)))) or "; ".join(
            sorted(set(rows["mirror_data"])))
        print(f"  {c['name']:<22} UK {first['uk_data']:<8} onward {onward_years:<34} "
              f"mirror {mirror_years}")
    print("\nA rise in exports is a lead, not evidence of a breach. " + OGL)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hmrc", type=Path, default=pick(HMRC_DEFAULT, HMRC_FALLBACK))
    ap.add_argument("--comtrade", type=Path, default=pick(CT_DEFAULT, CT_FALLBACK))
    args = ap.parse_args(argv)
    print(f"HMRC input:     {args.hmrc}")
    print(f"Comtrade input: {args.comtrade}")

    monthly = read(args.hmrc, HMRC_COLS)
    ct = read(args.comtrade, CT_COLS)
    countries, codes = config.countries(), config.codes()
    fx = mirror.load_fx()
    skipped = [y for y in mirror.YEARS if y not in fx]
    if skipped:
        print(f"No verified FX rate for {skipped}: the mirror check skips those years")

    out, mirror_rows = leads.build(monthly, ct, countries, codes, fx)
    out.to_csv(LEADS_OUT, index=False)
    mirror_rows.to_csv(MIRROR_OUT, index=False)
    print(f"Wrote {LEADS_OUT} ({len(out)} rows) and {MIRROR_OUT} ({len(mirror_rows)} rows)")
    print(f"Rules: UK rise {rules.MIN_UK_RATIO}x and GBP {rules.MIN_UK_EXCESS_GBP:,} on the "
          f"2023-25 average and in at least {rules.MIN_PERSIST_YEARS} of 2023, 2024, 2025; onward "
          f"{rules.MIN_ONWARD_RATIO}x and USD {rules.MIN_ONWARD_USD:,}; mirror gap "
          f"{mirror.MIN_GAP_RATIO}x and USD {mirror.MIN_GAP_USD:,}")
    report(out, mirror_rows, countries)


if __name__ == "__main__":
    main()
