"""Baseline maths for the radar. Pure functions on pandas DataFrames, so every
number can be re-derived and tested.

Monthly input columns: country_id, code, month (YYYYMM int), value_gbp, net_mass_kg.
"""

from __future__ import annotations

import pandas as pd

BASELINE_YEARS = (2019, 2020, 2021)
POST_YEARS = (2023, 2024, 2025)


def add_year_month(monthly: pd.DataFrame) -> pd.DataFrame:
    out = monthly.copy()
    out["year"] = out["month"] // 100
    out["mon"] = out["month"] % 100
    return out


def annual(monthly: pd.DataFrame, upto_month: int | None = None) -> pd.DataFrame:
    """Totals per series and year. With upto_month (1-12), only months 1..upto_month
    are counted in every year, giving like-for-like year-to-date totals."""
    df = add_year_month(monthly)
    if upto_month is not None:
        df = df[df["mon"] <= upto_month]
    return (df.groupby(["country_id", "code", "year"], as_index=False)[["value_gbp", "net_mass_kg"]]
              .sum())


def wide(annual_df: pd.DataFrame, col: str = "value_gbp", years=None) -> pd.DataFrame:
    """One row per series, one column per year; missing years are true zeros
    (HMRC returns no row when nothing was recorded)."""
    w = annual_df.pivot_table(index=["country_id", "code"], columns="year", values=col,
                              aggfunc="sum", fill_value=0)
    if years is not None:
        for y in years:
            if y not in w.columns:
                w[y] = 0
        w = w[list(years)]
    return w


def compare(annual_df: pd.DataFrame, baseline_years=BASELINE_YEARS, post_years=POST_YEARS,
            col: str = "value_gbp") -> pd.DataFrame:
    """Baseline average versus post-2022 average for each series.

    excess_per_year = post average minus baseline average.
    ratio = post average / baseline average (inf when the baseline is zero).
    """
    w = wide(annual_df, col, years=sorted(set(baseline_years) | set(post_years)))
    return compare_wide(w, baseline_years, post_years).reset_index()


def compare_wide(w: pd.DataFrame, baseline_years=BASELINE_YEARS,
                 post_years=POST_YEARS) -> pd.DataFrame:
    """compare() on a table that is already one row per series and one column per
    year. Rows that are all NaN (a country with no data) stay NaN throughout."""
    out = pd.DataFrame(index=w.index)
    out["baseline_avg"] = w[list(baseline_years)].mean(axis=1)
    out["post_avg"] = w[list(post_years)].mean(axis=1)
    out["excess_per_year"] = out["post_avg"] - out["baseline_avg"]
    out["excess_total"] = (w[list(post_years)].sub(out["baseline_avg"], axis=0)).sum(axis=1, min_count=1)
    out["ratio"] = out["post_avg"] / out["baseline_avg"].where(out["baseline_avg"] > 0)
    out.loc[(out["baseline_avg"] == 0) & (out["post_avg"] > 0), "ratio"] = float("inf")
    return out


def gross_excess(comp: pd.DataFrame) -> float:
    """Sum of excess over the post years, counting only series that rose.
    Falls in one corridor do not cancel rises in another."""
    return float(comp.loc[comp["excess_total"] > 0, "excess_total"].sum())
