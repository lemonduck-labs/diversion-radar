"""Shared pieces for the research signals (radar/signals/RESEARCH.md, entry S0).

All figures are UK exports from HMRC overseas trade statistics already in data/processed.
The radar runs at the end of month p and sees data months up to p - LAG, as the backtest does
(backtest/asof.py). Frames here are dated by data month (the last month of a 12-month window);
at_runs() moves them to the run that first sees them, so no run uses a month published after it.

A rise in exports is a lead, not evidence of a breach.
Contains public sector information licensed under the Open Government Licence v3.0.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from backtest import asof
from radar import display

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
CONFIG = ROOT / "config"

LAG = asof.UK_LAG_MONTHS            # data month M is first seen by the run at the end of M + 2
WINDOW = display.WINDOW             # 12 data months
PERSIST = 3                         # "3 published windows running"
RUSSIA_ID = 75                      # HMRC country id

WAR_BASE = (2019, 2020, 2021)
PEACE_BASE = (2016, 2017, 2018)
WAR_RUNS = (202201, 202608)         # 56 runs
PEACE_RUNS = (201901, 202112)       # 36 runs
WAR_PLACEBO_RUNS = (202201, 202412)  # the first 36 war-time runs

WAR_FILE = PROCESSED / "hmrc_monthly_phase1.csv"       # January 2019 to August 2026
PEACE_FILE = PROCESSED / "hmrc_monthly_2016_2026.csv"  # from January 2016 (Russia from 2019)


def load_monthly(path: Path = WAR_FILE) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"code": str})


def load_codes(path: Path = CONFIG / "codes.csv") -> pd.DataFrame:
    return pd.read_csv(path, dtype={"code": str, "cn8_from": str, "cn8_to": str})


def load_corridors(path: Path = CONFIG / "countries.csv") -> pd.DataFrame:
    c = pd.read_csv(path)
    return c[c.role == "corridor"].astype({"hmrc_country_id": int, "comtrade_code": int}).reset_index(drop=True)


def headings(codes: pd.DataFrame) -> dict[str, list[str]]:
    """Every four-digit heading and the list codes in it, from the CN8 ranges in
    config/codes.csv only. A code's range must sit inside one heading, and ranges in the same
    heading must not overlap (or a sibling would count the focal code's own goods)."""
    out: dict[str, list[tuple[str, str, str]]] = {}
    for c in codes.itertuples():
        lo, hi = str(c.cn8_from), str(c.cn8_to)
        if len(lo) != 8 or len(hi) != 8 or lo[:4] != hi[:4] or lo > hi:
            raise ValueError(f"code {c.code}: CN8 range {lo} to {hi} is not inside one heading")
        out.setdefault(lo[:4], []).append((lo, hi, str(c.code)))
    for h, rs in out.items():
        rs.sort()
        for (_, hi1, a), (lo2, _, b) in zip(rs, rs[1:]):
            if lo2 <= hi1:
                raise ValueError(f"heading {h}: the ranges of {a} and {b} overlap")
    return {h: [r[2] for r in rs] for h, rs in out.items()}


def sibling_map(codes: pd.DataFrame) -> dict[str, list[str]]:
    """Focal code -> the other list codes in its heading, for headings with two or more."""
    out = {}
    for _, cs in headings(codes).items():
        if len(cs) >= 2:
            for a in cs:
                out[a] = [s for s in cs if s != a]
    return out


def runs(start: int, end: int) -> pd.PeriodIndex:
    return asof.month_index(start, end)


class Panel:
    """Monthly UK exports by destination and code, zero where HMRC shows none, dated by data
    month. 'priced' keeps only rows with a value above zero and a net mass above zero (S1)."""

    def __init__(self, monthly: pd.DataFrame, start: int, end: int):
        self.index = asof.month_index(start, end)
        m = monthly[(monthly.month >= start) & (monthly.month <= end)].copy()
        m["period"] = [asof.to_period(int(x)) for x in m.month]
        priced = (m.value_gbp > 0) & (m.net_mass_kg > 0)
        m["priced_value"] = m.value_gbp.where(priced, 0.0)
        m["priced_mass"] = m.net_mass_kg.where(priced, 0.0)
        g = m.groupby(["country_id", "code", "period"])[
            ["value_gbp", "net_mass_kg", "priced_value", "priced_mass"]].sum()
        self.frames = {col: g[col].unstack(["country_id", "code"]).reindex(self.index).fillna(0.0)
                       for col in g.columns}
        self.start, self.end = start, end

    def series(self, col: str, country_id: int, code: str) -> pd.Series:
        f = self.frames[col]
        key = (int(country_id), str(code))
        if key in f.columns:
            return f[key].astype(float)
        return pd.Series(0.0, index=self.index)

    def total(self, col: str, country_ids, code: str) -> pd.Series:
        s = pd.Series(0.0, index=self.index)
        for c in country_ids:
            s = s + self.series(col, c, code)
        return s


def base_slice(base_years: tuple) -> slice:
    return slice(f"{min(base_years)}-01", f"{max(base_years)}-12")


def base_sum(s: pd.Series, base_years: tuple) -> float:
    return float(s[base_slice(base_years)].sum())


def roll(s: pd.Series, n: int = WINDOW) -> pd.Series:
    """Sum over the n data months ending at each month (NaN until n months exist)."""
    return s.rolling(n).sum()


def months_with_exports(s: pd.Series, n: int = WINDOW) -> pd.Series:
    return (s > 0).astype(int).rolling(n).sum()


def ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    """num / den, NaN where den is not above zero."""
    return num / den.where(den > 0)


def persist(rule: pd.Series, n: int = PERSIST) -> pd.Series:
    """True where the rule held at this data month and the n - 1 before it."""
    return rule.fillna(False).astype(int).rolling(n).sum() == n


def display_window(value: pd.Series) -> pd.Series:
    """The display rule (radar/display.py) on the 12-month window ending at each data month:
    at least GBP 250,000 and exports in at least 6 of the 12 months."""
    return ((roll(value) >= display.MIN_DISPLAY_GBP)
            & (months_with_exports(value) >= display.MIN_DISPLAY_MONTHS))


def at_runs(s: pd.Series, run_index: pd.PeriodIndex, lag: int = LAG):
    """A data-month series as the runs see it: the run at the end of month p sees month p - lag."""
    shifted = s.copy()
    shifted.index = shifted.index + lag
    out = shifted.reindex(run_index)
    if s.dtype == bool:
        return out.fillna(False).astype(bool)
    return out


def nameable(flag_runs: pd.Series, shown_runs: pd.Series, routes: dict, country_id: int,
             code: str, lag: int = LAG) -> pd.Series:
    """Runs at which a flagged series may be named outside the repo: the display rule passes on
    the run's own 12 published months, and on a route linked to a case (radar/display.route_for,
    exact code or same heading) the window starts after the case's first public action."""
    out = flag_runs & shown_runs
    r = display.route_for(routes, country_id, code)
    if r is not None:
        case_month = r[1]
        later = pd.Series([display.window_start(p, lag) > case_month for p in out.index], index=out.index)
        out = out & later
    return out
