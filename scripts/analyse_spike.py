"""Phase 0 analysis: compare each corridor and code with its pre-2022 baseline,
check onward exports to Russia, and write the tables and charts for the report.

    python scripts/analyse_spike.py

Reads data/processed/hmrc_monthly.csv and data/processed/comtrade_annual.csv.
Writes data/processed/leads.csv and reports/charts/*.png.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from radar import baseline  # noqa: E402

PROC = ROOT / "data" / "processed"
CHARTS = ROOT / "reports" / "charts"

HMRC_NAMES = {83: "Kyrgyz Republic", 77: "Armenia", 79: "Kazakhstan", 76: "Georgia",
              647: "UAE", 75: "Russia"}
COMTRADE_TO_HMRC = {417: 83, 51: 77, 398: 79, 268: 76, 784: 647}

# Lead rules for the spike. Deliberately simple so a reviewer can check them by hand.
MIN_UK_RATIO = 2.0          # UK exports at least double the 2019-21 average
MIN_UK_EXCESS = 20_000      # and at least GBP 20k a year above it
MIN_ONWARD_RATIO = 2.0      # corridor exports of the same code to Russia at least double
MIN_ONWARD_USD = 100_000    # and average at least USD 100k a year after 2022

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]


def onward(ct: pd.DataFrame) -> pd.DataFrame:
    """Corridor exports to Russia: 2019-21 average versus the post-2022 years reported."""
    x = ct[(ct.partner == 643) & (ct.flow == "X")]
    w = x.pivot_table(index=["reporter", "code"], columns="year", values="value_usd",
                      aggfunc="sum", fill_value=0)
    for y in range(2019, 2026):
        if y not in w.columns:
            w[y] = 0
    reported = x.groupby("reporter").year.apply(lambda s: sorted(set(s)))
    rows = []
    for (rep, code), r in w.iterrows():
        years = reported.get(rep, [])
        post_years = [y for y in (2023, 2024, 2025) if y in years]
        base_years = [y for y in (2019, 2020, 2021) if y in years]
        base = r[base_years].mean() if base_years else np.nan
        post = r[post_years].mean() if post_years else np.nan
        rows.append({"country_id": COMTRADE_TO_HMRC[rep], "code": code,
                     "onward_base_usd": base, "onward_post_usd": post,
                     "onward_post_years": ",".join(map(str, post_years)),
                     "onward_ratio": (post / base) if base and base > 0 else (np.inf if post and post > 0 else np.nan)})
    return pd.DataFrame(rows)


def leads(monthly: pd.DataFrame, ct: pd.DataFrame) -> pd.DataFrame:
    a = baseline.annual(monthly)
    comp = baseline.compare(a)
    mass = baseline.compare(a, col="net_mass_kg")[["country_id", "code", "ratio"]].rename(
        columns={"ratio": "mass_ratio"})
    comp = comp.merge(mass, on=["country_id", "code"])
    comp = comp[comp.country_id != 75].merge(onward(ct), on=["country_id", "code"], how="left")
    comp["uk_rise"] = (comp.ratio >= MIN_UK_RATIO) & (comp.excess_per_year >= MIN_UK_EXCESS)
    comp["onward_rise"] = (comp.onward_ratio >= MIN_ONWARD_RATIO) & (comp.onward_post_usd >= MIN_ONWARD_USD)
    comp["lead"] = comp.uk_rise & comp.onward_rise
    comp["country"] = comp.country_id.map(HMRC_NAMES)
    return comp.sort_values("excess_total", ascending=False)


FOOTER = ("Source: HMRC overseas trade statistics (uktradeinfo), exports by month. Contains public sector "
          "information licensed under the Open Government Licence v3.0.\nA rise in exports is a lead, "
          "not evidence of a breach.")


def _footer(fig):
    """Source, licence and house line on every chart; leaves room at the bottom."""
    fig.text(0.01, 0.015, FOOTER, ha="left", va="bottom", fontsize=7, color=MUTED, linespacing=1.4)
    fig.tight_layout(rect=(0, 0.09, 1, 1))


def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def chart_russia_vs_corridors(monthly: pd.DataFrame):
    a = baseline.annual(monthly)
    a = a[a.year <= 2025]
    tot = a.groupby(["country_id", "year"]).value_gbp.sum().unstack(0).fillna(0) / 1e6
    corridors = tot[[79, 77, 83, 76]].sum(axis=1)
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=150)
    ax.plot(tot.index, tot[75], color=MUTED, linewidth=2, marker="o", markersize=4)
    ax.plot(tot.index, corridors, color=SERIES[0], linewidth=2, marker="o", markersize=4)
    ax.annotate("Russia, direct", (tot.index[0], tot[75].iloc[0]), xytext=(8, 0),
                textcoords="offset points", va="center", fontsize=9, color=INK)
    ax.annotate("Kazakhstan, Armenia,\nKyrgyz Republic, Georgia", (tot.index[-1], corridors.iloc[-1]),
                xytext=(8, 0), textcoords="offset points", va="center", fontsize=9, color=INK)
    ax.set_title("UK exports of the nine high-priority codes (£m a year, nominal)",
                 loc="left", fontsize=11, color=INK)
    ax.set_xlim(2018.7, 2027.4)
    ax.set_xticks(range(2019, 2026))
    _style(ax)
    _footer(fig)
    fig.savefig(CHARTS / "uk_exports_russia_vs_corridors.png")
    plt.close(fig)


def chart_series(monthly: pd.DataFrame, country_id: int, code: str, label: str, fname: str):
    s = monthly[(monthly.country_id == country_id) & (monthly.code == code)].copy()
    idx = pd.period_range("2019-01", "2026-08", freq="M")
    s["period"] = pd.PeriodIndex([f"{m // 100}-{m % 100:02d}" for m in s.month], freq="M")
    v = s.set_index("period").value_gbp.reindex(idx, fill_value=0) / 1e3
    roll = v.rolling(12).sum()
    base = v["2019-01":"2021-12"].sum() / 3
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=150)
    ax.plot(roll.index.to_timestamp(), roll.values, color=SERIES[0], linewidth=2)
    ax.axhline(base, color=MUTED, linewidth=1, linestyle="--")
    ax.annotate("2019-21 annual average", (pd.Timestamp("2020-01-01"), base), xytext=(0, 6),
                textcoords="offset points", fontsize=9, color=MUTED)
    ax.set_title(f"{label}: UK exports, rolling 12 months (£k, nominal)", loc="left",
                 fontsize=11, color=INK)
    _style(ax)
    _footer(fig)
    fig.savefig(CHARTS / fname)
    plt.close(fig)


def main():
    CHARTS.mkdir(parents=True, exist_ok=True)
    monthly = pd.read_csv(PROC / "hmrc_monthly.csv", dtype={"code": str})
    ct = pd.read_csv(PROC / "comtrade_annual.csv", dtype={"code": str})
    out = leads(monthly, ct)
    out.to_csv(PROC / "leads.csv", index=False)
    chart_russia_vs_corridors(monthly)
    chart_series(monthly, 79, "851762", "Kazakhstan, 8517.62 data transmission equipment",
                 "kazakhstan_851762.png")
    chart_series(monthly, 77, "851762", "Armenia, 8517.62 data transmission equipment",
                 "armenia_851762.png")
    cols = ["country", "code", "baseline_avg", "post_avg", "ratio", "excess_total", "mass_ratio",
            "onward_base_usd", "onward_post_usd", "onward_ratio", "onward_post_years", "lead"]
    with pd.option_context("display.width", 250, "display.max_rows", 60):
        print(out[cols].head(25).to_string(index=False))
    print("\nGross excess, all rising series (GBP):", round(baseline.gross_excess(out)))
    print("Excess where onward exports also rose (GBP):",
          round(out.loc[out.lead, "excess_total"].sum()))
    print("\nA rise in exports is a lead, not evidence of a breach.")
    print("Contains public sector information licensed under the Open Government Licence v3.0.")


if __name__ == "__main__":
    main()
