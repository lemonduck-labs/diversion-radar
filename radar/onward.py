"""Why an onward check did not pass, in the rule's own words.

One function for every file that says so (the brief contexts, the dashboard's leads and the
workspace's signals), so they never give different reasons for the same series. The rule is
backtest/asof.py's: at least $100,000 and, where the 2019-21 average is above zero, at least
2x it. A year with no exports reported is given as such, whatever the average.

The engine also counts a 2019-21 baseline year only when the corridor reported one of the
radar's codes to Russia that year (asof.onward_signal); neither R3 nor run 2's
pre-registration states that, so RESEARCH_LOG.md R3.4 does.
"""
from __future__ import annotations

import pandas as pd

from backtest import asof

NO_EXPORTS = "no exports reported"
FLOOR = f"under the ${asof.ONWARD_MIN_USD:,} floor"
RATIO = f"under {asof.ONWARD_RATIO:g}x the 2019-21 average"
#: The same reasons in a few words, for tables.
SHORT = {NO_EXPORTS: "none reported", FLOOR: f"under ${asof.ONWARD_MIN_USD // 1000:,}k",
         RATIO: f"under {asof.ONWARD_RATIO:g}x"}


def why_not(usd, base) -> list[str]:
    """The reasons a value fails the onward test, in a fixed order. Raises if it passes."""
    if usd is None or pd.isna(usd) or float(usd) == 0.0:
        return [NO_EXPORTS]
    usd = float(usd)
    base = 0.0 if base is None or pd.isna(base) else float(base)
    out = []
    if usd < asof.ONWARD_MIN_USD:
        out.append(FLOOR)
    if base > 0 and usd < asof.ONWARD_RATIO * base:
        out.append(RATIO)
    if not out:
        raise ValueError(f"onward check failed with no reason: {usd} against {base}")
    return out


def why_not_text(usd, base) -> str:
    return " and ".join(why_not(usd, base))


def why_not_short(usd, base) -> str:
    return " and ".join(SHORT[x] for x in why_not(usd, base))
