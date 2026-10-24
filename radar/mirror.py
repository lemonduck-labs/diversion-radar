"""Mirror-gap check: what a corridor country says it imported from the UK, set
against what the UK says it exported to that country.

For each corridor, goods code and year, the corridor's reported imports from the
UK (UN Comtrade, partner 826, flow M, US dollars) are compared with UK exports to
that corridor (HMRC, pounds, converted to dollars at the official annual average
rate in config/fx_usd_per_gbp.csv). A year is flagged when one side is at least
MIN_GAP_RATIO times the other and at least MIN_GAP_USD above it, in either
direction:

- "corridor higher": the corridor records far more UK-origin goods than the UK
  records sending there;
- "UK higher": the UK records sending far more than the corridor records
  receiving from the UK.

Gaps between the two records are normal, and most have ordinary causes:

- Origin versus consignment. Most countries record imports by country of
  origin; HMRC records exports by country of destination. Goods made in the UK
  but shipped from a distributor's stock in another country show up as UK-origin
  imports in the corridor's data, yet never as UK exports to it.
- Re-exports. UK exports include goods made elsewhere that passed through the
  UK. The corridor records those under their true origin, not the UK.
- CIF versus FOB. Imports are usually valued with insurance and freight to the
  border (CIF), exports at the UK border (FOB), so imports run a few per cent
  higher on valuation alone.
- Timing. Goods leaving the UK late in December can be recorded as arriving in
  January, in the next year.
- Also: an annual average exchange rate only approximates the rates on the day;
  the two customs services can classify the same goods under different codes;
  HS versions change (heading 8548 in 2022); HMRC suppresses some figures to
  protect traders; low-value consignments can fall under reporting thresholds;
  and either side can revise its figures later.

So a flag is a prompt to look closer, never evidence on its own. A large gap that
repeats is worth an analyst's time; the data shows the gap, not why it is there.

Years are skipped, never guessed: a year with no official exchange rate, a year
the corridor did not report, and a corridor or country with no data at all are
all shown with a status instead of a flag.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

MIN_GAP_RATIO = 3.0      # one side at least three times the other
MIN_GAP_USD = 100_000    # and at least USD 100k above it in the year
YEARS = tuple(range(2019, 2026))
UK = 826                 # Comtrade partner code for the United Kingdom
FX_PATH = Path(__file__).resolve().parent.parent / "config" / "fx_usd_per_gbp.csv"

CORRIDOR_HIGHER = "corridor higher"
UK_HIGHER = "UK higher"

CHECKED = "checked"
NO_UK_DATA = "no UK data"
NO_CORRIDOR_DATA = "no corridor data"
NOT_REPORTED = "corridor did not report"
NO_FX = "no FX rate"

COLUMNS = ["country", "country_id", "comtrade_code", "code", "year", "status",
           "uk_exports_gbp", "usd_per_gbp", "uk_exports_usd", "corridor_imports_usd",
           "ratio_corridor_to_uk", "gap_usd", "flag"]


def load_fx(path: Path = FX_PATH) -> dict[int, float]:
    """US dollars per pound, annual average, by year. A blank rate means the year
    could not be checked against an official source: it is left out, so the
    mirror check skips that year. A rate without a source is refused."""
    rates: dict[int, float] = {}
    with Path(path).open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            raw = (row.get("usd_per_gbp") or "").strip()
            if not raw:
                continue
            rate = float(raw)
            if not rate > 0:
                raise ValueError(f"FX rate for {row['year']} must be positive, got {raw}")
            if not (row.get("source") or "").strip():
                raise ValueError(f"FX rate for {row['year']} has no source")
            rates[int(row["year"])] = rate
    return rates


def flag(uk_usd: float, corridor_usd: float, min_ratio: float = MIN_GAP_RATIO,
         min_usd: float = MIN_GAP_USD) -> str:
    """Which side, if either, is at least min_ratio times the other and at least
    min_usd above it. Returns CORRIDOR_HIGHER, UK_HIGHER or ""."""
    if corridor_usd >= min_ratio * uk_usd and corridor_usd - uk_usd >= min_usd:
        return CORRIDOR_HIGHER
    if uk_usd >= min_ratio * corridor_usd and uk_usd - corridor_usd >= min_usd:
        return UK_HIGHER
    return ""


def gaps(uk_annual: pd.DataFrame, ct: pd.DataFrame, fx: dict[int, float],
         corridors: Iterable[dict], codes: Iterable[str], years: Iterable[int] = YEARS,
         min_ratio: float = MIN_GAP_RATIO, min_usd: float = MIN_GAP_USD) -> pd.DataFrame:
    """One row per corridor, code and year, with a status saying whether the year
    was checked and, if not, why not.

    uk_annual: HMRC annual totals with columns country_id, code, year, value_gbp
        (as from baseline.annual). A country with no rows at all counts as not
        pulled ("no UK data"). For a country that has rows, a missing code or year
        is a true zero, because HMRC returns no row when nothing was recorded.
    ct: Comtrade annual records with columns reporter, partner, flow, code, year,
        value_usd. Only partner 826, flow M is used. A corridor year counts as
        reported when the corridor has any import record from the UK for any of
        the codes that year; within a reported year, a code with no record counts
        as zero.
    fx: year to US dollars per pound, from load_fx. Years without a rate are skipped.
    corridors: rows of config/countries.csv with role corridor.
    codes: goods codes, as in config/codes.csv.
    """
    codes, years = list(codes), list(years)
    uk_present = set(int(c) for c in uk_annual["country_id"].unique())
    uk_val = uk_annual.groupby(["country_id", "code", "year"])["value_gbp"].sum()
    m = ct[(ct["partner"] == UK) & (ct["flow"] == "M")]
    m_val = m.groupby(["reporter", "code", "year"])["value_usd"].sum()
    m_years = {int(r): set(int(y) for y in ys) for r, ys in m.groupby("reporter")["year"]}
    rows = []
    for c in corridors:
        cid = int(c["hmrc_country_id"]) if str(c.get("hmrc_country_id", "")).strip() else None
        rep = int(c["comtrade_code"])
        reported = m_years.get(rep, set())
        for code in codes:
            for y in years:
                if cid not in uk_present:
                    status = NO_UK_DATA
                elif not reported:
                    status = NO_CORRIDOR_DATA
                elif y not in reported:
                    status = NOT_REPORTED
                elif y not in fx:
                    status = NO_FX
                else:
                    status = CHECKED
                gbp = float(uk_val.get((cid, code, y), 0.0)) if cid in uk_present else np.nan
                rate = fx.get(y, np.nan)
                uk_usd = gbp * rate
                imp = float(m_val.get((rep, code, y), 0.0)) if y in reported else np.nan
                ratio = gap = np.nan
                fl = ""
                if status == CHECKED:
                    gap = imp - uk_usd
                    ratio = imp / uk_usd if uk_usd > 0 else (np.inf if imp > 0 else np.nan)
                    fl = flag(uk_usd, imp, min_ratio, min_usd)
                rows.append({"country": c["name"], "country_id": cid, "comtrade_code": rep,
                             "code": code, "year": y, "status": status,
                             "uk_exports_gbp": gbp, "usd_per_gbp": rate, "uk_exports_usd": uk_usd,
                             "corridor_imports_usd": imp, "ratio_corridor_to_uk": ratio,
                             "gap_usd": gap, "flag": fl})
    return pd.DataFrame(rows, columns=COLUMNS)


def summarise(g: pd.DataFrame) -> pd.DataFrame:
    """One row per corridor and code, indexed by (country_id, code): how many
    years were checked, which years were flagged each way, and mirror_data, which
    is "ok" when at least one year was checked and otherwise names why not."""
    rows = []
    for (cid, code), s in g.groupby(["country_id", "code"], sort=False, dropna=False):
        checked = s[s["status"] == CHECKED]
        years_with = lambda f: ",".join(str(y) for y in checked.loc[checked["flag"] == f, "year"])
        rows.append({
            "country_id": cid, "code": code,
            "mirror_data": "ok" if len(checked) else "; ".join(sorted(set(s["status"]))),
            "mirror_years_checked": len(checked),
            "mirror_corridor_higher": years_with(CORRIDOR_HIGHER),
            "mirror_uk_higher": years_with(UK_HIGHER),
            "mirror_gap": bool((checked["flag"] != "").any()),
        })
    cols = ["country_id", "code", "mirror_data", "mirror_years_checked",
            "mirror_corridor_higher", "mirror_uk_higher", "mirror_gap"]
    return pd.DataFrame(rows, columns=cols).set_index(["country_id", "code"])
