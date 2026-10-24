"""The monthly onward check for backtest run 2 (backtest/preregistration_run2.md).

At the radar run at the end of month A, for one corridor and goods code:

1. L is the latest month of the corridor's monthly UN Comtrade data first released by the
   end of A. L must be January 2022 or later.
2. The window is the 12 months ending at L. Months in it not yet released at A, or not
   reported, count as zero.
3. The baseline is the average reported month in 2019-21, times 12. A month counts as
   reported when UN Comtrade holds a monthly dataset for that corridor and month; within
   a reported month, a code with no record counts as zero. A corridor with fewer than 12
   reported baseline months has no monthly signal.
4. The signal is on when the window sum is at least 2x the baseline and at least
   USD 100,000.

A rise in exports is a lead, not evidence of a breach.
"""

from __future__ import annotations

import pandas as pd

MIN_RATIO, MIN_USD = 2.0, 100_000
MIN_END = 202201
BASE_YEARS = (2019, 2020, 2021)


def _shift(period: int, months: int) -> int:
    y, m = divmod(period, 100)
    idx = y * 12 + (m - 1) + months
    return (idx // 12) * 100 + idx % 12 + 1


class MonthlyOnward:
    """Precomputed monthly onward check for one corridor and code."""

    def __init__(self, ctm: pd.DataFrame, release_m: pd.DataFrame, reporter: int, code: str,
                 base_years: tuple = BASE_YEARS):
        rel = release_m[release_m.reporter == reporter]
        self.release = dict(zip(rel.period.astype(int), rel.first_released))
        x = ctm[(ctm.reporter == reporter) & (ctm.code == code)]
        self.values = x.groupby("period").value_usd.sum().to_dict()
        base_periods = [p for p in self.release if p // 100 in base_years]
        self.base_months = len(base_periods)
        self.baseline = (sum(self.values.get(p, 0.0) for p in base_periods) / len(base_periods) * 12
                         if base_periods else None)

    def at(self, asof: pd.Period) -> tuple[bool, dict]:
        end = asof.end_time
        published = {p for p, t in self.release.items() if t <= end}
        info = {"monthly_end": None, "monthly_window_usd": None, "monthly_base_usd": self.baseline,
                "monthly_months_released": None}
        if not published or self.base_months < 12:
            return False, info
        last = max(published)
        if last < MIN_END:
            return False, info
        window = [_shift(last, -k) for k in range(11, -1, -1)]
        released = [p for p in window if p in published]
        total = sum(self.values.get(p, 0.0) for p in released)
        info.update({"monthly_end": last, "monthly_window_usd": total,
                     "monthly_months_released": len(released)})
        ok = bool(total >= MIN_USD and total >= MIN_RATIO * self.baseline)
        return ok, info
