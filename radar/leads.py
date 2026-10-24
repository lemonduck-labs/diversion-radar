"""The phase 1 leads table: one row per corridor and goods code, with the UK rise
rules (averaged and persistent), the onward check and the mirror check side by
side, and the per-year values behind them, so every flag can be checked by hand.

Countries with no data are kept in the table with status "no data" rather than
dropped, so a missing pull is visible.

Key columns: lead (phase 1: both UK rules and the onward rise); lead_phase0 (the
phase 0 rule, averaged UK rise and onward rise, on the same inputs, for
comparison); mirror_gap (any flagged year either way, shown beside a lead, never
part of it); status, one of STATUS_ORDER ("dropped: not persistent" is a phase 0
lead that fails the persistence rule; "UK rise, no onward data" means the onward
test could not be run). country_id is HMRC's id; comtrade_code is the UN M49 code.

A rise in exports is a lead, not evidence of a breach.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import baseline, mirror, rules

YEARS = tuple(range(2019, 2026))   # per-year UK columns shown in the table

LEAD = "lead"
DROPPED = "dropped: not persistent"
UK_NO_ONWARD_DATA = "UK rise, no onward data"
UK_ONLY = "UK rise only"
ONWARD_ONLY = "onward rise only"
NONE = "none"
NO_DATA = "no data"
STATUS_ORDER = [LEAD, DROPPED, UK_NO_ONWARD_DATA, UK_ONLY, ONWARD_ONLY, NONE, NO_DATA]

COLUMNS = (
    ["country", "country_id", "comtrade_code", "code", "description",
     "status", "lead", "lead_phase0", "mirror_gap",
     "uk_data"] + [f"gbp_{y}" for y in YEARS] +
    ["baseline_avg", "post_avg", "ratio", "excess_per_year", "excess_total", "mass_ratio",
     "uk_rise_avg", "uk_years_met", "uk_n_years_met", "uk_rise_persistent", "uk_rise",
     "onward_data", "onward_base_years", "onward_post_years", "onward_base_usd",
     "onward_post_usd", "onward_ratio", "onward_rise",
     "mirror_data", "mirror_years_checked", "mirror_corridor_higher", "mirror_uk_higher"]
)


def _wide(a: pd.DataFrame, index: pd.MultiIndex, present: set, col: str) -> pd.DataFrame:
    """Per-year values on the full corridor-by-code grid: zero where a country with
    data has no record (HMRC returns no row when nothing was recorded), NaN for a
    country with no data at all."""
    w = baseline.wide(a, col, years=YEARS) if len(a) else pd.DataFrame(columns=list(YEARS))
    w = w.reindex(index)
    has_data = index.get_level_values(0).isin(list(present))
    w.loc[has_data] = w.loc[has_data].fillna(0)
    return w.astype(float)


def _status(r) -> str:
    if r["uk_data"] != "ok":
        return NO_DATA
    if r["lead"]:
        return LEAD
    if r["lead_phase0"]:
        return DROPPED
    if r["uk_rise"]:
        return UK_ONLY if r["onward_data"] == "ok" else UK_NO_ONWARD_DATA
    if r["onward_rise"]:
        return ONWARD_ONLY
    return NONE


def build(monthly: pd.DataFrame, ct: pd.DataFrame, countries: list[dict], codes: list[dict],
          fx: dict[int, float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (leads, mirror_rows).

    monthly: HMRC monthly exports (country_id, code, month, value_gbp, net_mass_kg).
    ct: Comtrade annual records (reporter, partner, flow, code, year, value_usd, ...).
    countries, codes: rows of config/countries.csv and config/codes.csv.
    fx: US dollars per pound by year, from mirror.load_fx.
    """
    corridors = [c for c in countries if c["role"] == "corridor"]
    code_list = [k["code"] for k in codes]
    desc = {k["code"]: k["description"] for k in codes}
    grid = pd.DataFrame([{"country": c["name"], "country_id": int(c["hmrc_country_id"]),
                          "comtrade_code": int(c["comtrade_code"]), "code": k}
                         for c in corridors for k in code_list])
    index = pd.MultiIndex.from_frame(grid[["country_id", "code"]])

    ids = set(grid["country_id"])
    a = baseline.annual(monthly[monthly["country_id"].isin(ids)])
    present = set(int(c) for c in a["country_id"].unique())

    w = _wide(a, index, present, "value_gbp")
    comp = baseline.compare_wide(w)
    mass = baseline.compare_wide(_wide(a, index, present, "net_mass_kg"))["ratio"].rename("mass_ratio")
    uk = rules.uk_rise(w)
    per_year = w.rename(columns={y: f"gbp_{y}" for y in YEARS})

    on = rules.onward(ct, grid["comtrade_code"].unique(), code_list)
    on = on.reindex(pd.MultiIndex.from_frame(grid[["comtrade_code", "code"]]))
    on.index = index

    mirror_rows = mirror.gaps(a, ct, fx, corridors, code_list)
    ms = mirror.summarise(mirror_rows).reindex(index)

    out = pd.concat([per_year, comp, mass, uk, on, ms], axis=1).reset_index()
    out = grid.merge(out, on=["country_id", "code"], how="left")
    out["description"] = out["code"].map(desc)
    out["uk_data"] = np.where(out["country_id"].isin(list(present)), "ok", NO_DATA)
    for col in ["uk_rise_avg", "uk_rise_persistent", "uk_rise", "onward_rise", "mirror_gap"]:
        out[col] = out[col].fillna(False).astype(bool)
    out["lead_phase0"] = out["uk_rise_avg"] & out["onward_rise"]
    out["lead"] = out["uk_rise"] & out["onward_rise"]
    out["status"] = out.apply(_status, axis=1)

    order = {s: i for i, s in enumerate(STATUS_ORDER)}
    out = (out.assign(_o=out["status"].map(order))
              .sort_values(["_o", "excess_total"], ascending=[True, False], na_position="last")
              .drop(columns="_o"))
    return out[COLUMNS].reset_index(drop=True), mirror_rows
