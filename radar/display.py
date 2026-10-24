"""What may be shown outside the repo (CLAUDE.md: a minimum size for any series shown as a
lead, so a small flow cannot point at an identifiable exporter).

A series the radar flags (a lead or a watch item) is shown with its corridor, code and
figures only when, over the 12 published UK months behind the flag:

- UK exports total at least MIN_DISPLAY_GBP, and
- exports were recorded in at least MIN_DISPLAY_MONTHS separate months.

The second test matters because the UK signal uses a trailing 12-month sum. One large
consignment keeps that sum high for a year, and the three-months-running test does not
remove it. The months test screens out flows that came in fewer than 6 months; one large
consignment with small sales in five other months still passes. A series that fails
either test is counted, never shown by corridor or code. The rule makes it less likely
that a small flow points at one exporter; it cannot rule that out [Likely].

The same test applies to every past run drawn (screen_runs), and on a route from a tested
case only 12-month windows that start after the case's first public action are drawn.

Both levels are judgement calls made on 21 October 2026. They are not taken from HMRC's
disclosure rules: HMRC suppresses a figure only when a trader asks. Change them here; the
decision is logged in docs/decision_log.md.

A rise in exports is a lead, not evidence of a breach.
"""

from __future__ import annotations

import pandas as pd

MIN_DISPLAY_GBP = 250_000
MIN_DISPLAY_MONTHS = 6
WINDOW = 12


def window_months(end: int, n: int = WINDOW) -> list[int]:
    """The n data months ending at end (YYYYMM), oldest first."""
    y, m = divmod(end, 100)
    idx = y * 12 + (m - 1)
    return [((i // 12) * 100 + i % 12 + 1) for i in range(idx - n + 1, idx + 1)]


def window_stats(monthly: pd.DataFrame, country_id: int, code: str, end: int,
                 n: int = WINDOW) -> tuple[float, int]:
    """Total UK exports and the number of months with exports above zero, over the n data
    months ending at end, for one corridor and code."""
    months = window_months(end, n)
    s = monthly[(monthly.country_id == country_id) & (monthly.code == code)
                & (monthly.month.isin(months))]
    by_month = s.groupby("month").value_gbp.sum()
    return float(by_month.sum()), int((by_month > 0).sum())


def displayable(total_gbp: float, months_with_exports: int) -> tuple[bool, str]:
    """Whether a flagged series may be shown, and why not when it may not."""
    reasons = []
    if not total_gbp >= MIN_DISPLAY_GBP:
        reasons.append(f"UK exports under GBP {MIN_DISPLAY_GBP:,} in the window")
    if not months_with_exports >= MIN_DISPLAY_MONTHS:
        reasons.append(f"exports in fewer than {MIN_DISPLAY_MONTHS} of {WINDOW} months")
    return (not reasons), "; ".join(reasons)


CASE_WINDOW_REASON = "window starts before a linked case's first public action"


def window_start(run: pd.Period, lag: int, n: int = WINDOW) -> pd.Period:
    """First data month of the n published months behind the run at the end of month run."""
    return run - lag - (n - 1)


def case_routes(plan: pd.DataFrame) -> dict[tuple[int, str], tuple[frozenset, pd.Period]]:
    """Routes linked to enforcement cases: the backtest's test plan (backtest/data/test_plan.csv,
    primary and sensitivity) and the further routes the case register links to cases
    (config/case_routes_extra.csv). Keys are (HMRC country id, code) and (HMRC country id,
    four-digit heading); values are the case ids and the latest month of their first public
    actions. Look routes up with route_for()."""
    routes: dict[tuple[int, str], tuple[frozenset, pd.Period]] = {}
    for t in plan.itertuples():
        month = pd.Period(str(t.reference_date)[:7], freq="M")
        for code in str(t.codes).split(";"):
            for key in ((int(t.hmrc_country_id), code.strip()), (int(t.hmrc_country_id), "h" + code.strip()[:4])):
                cases, latest = routes.get(key, (frozenset(), month))
                routes[key] = (cases | {t.case_id}, max(latest, month))
    return routes


def load_case_routes(root) -> dict[tuple[int, str], tuple[frozenset, pd.Period]]:
    """case_routes() over the test plan and config/case_routes_extra.csv."""
    from pathlib import Path
    root = Path(root)
    cols = ["case_id", "hmrc_country_id", "codes", "reference_date"]
    plan = pd.read_csv(root / "backtest" / "data" / "test_plan.csv", dtype={"codes": str})[cols]
    extra = pd.read_csv(root / "config" / "case_routes_extra.csv", dtype={"codes": str})[cols]
    return case_routes(pd.concat([plan, extra], ignore_index=True))


def route_for(routes: dict, country_id: int, code: str) -> tuple[str, pd.Period, str] | None:
    """The cases linked to a series, the latest month of their first public actions, and how:
    "route" when every case listed links the series' own code, "heading" when they link only
    its four-digit heading (a case's goods are mapped to codes, so a sibling code may cover them
    too), "mixed" otherwise."""
    exact = routes.get((int(country_id), code))
    head = routes.get((int(country_id), "h" + code[:4]))
    if exact is None and head is None:
        return None
    found = [r for r in (exact, head) if r is not None]
    cases = frozenset().union(*[r[0] for r in found])
    exact_cases = exact[0] if exact is not None else frozenset()
    kind = "route" if exact_cases == cases else ("heading" if not exact_cases else "mixed")
    return ", ".join(sorted(cases)), max(r[1] for r in found), kind


def screen_runs(monthly: pd.DataFrame, country_id: int, code: str, runs, lag: int,
                case_month: pd.Period | None = None) -> pd.DataFrame:
    """Whether each run of a series may be drawn outside the repo, and why not.

    The display rule applies at every run, not only the latest: a run is drawn only when its
    own 12 published months pass displayable(). On a route from a tested case, a run is drawn
    only when its 12 months start after the month of the case's first public action, so no
    UK figure drawn covers a case's stated period of conduct; where the case register states no
    end date, that is Likely, not Certain (backtest/RESEARCH_LOG.md, R3.5). The cases named no
    UK goods or UK party."""
    rows = []
    for p in runs:
        end = p - lag
        total, months = window_stats(monthly, country_id, code, end.year * 100 + end.month)
        ok, why = displayable(total, months)
        if case_month is not None and not window_start(p, lag) > case_month:
            ok, why = False, CASE_WINDOW_REASON
        rows.append({"run": p, "shown": bool(ok), "not_shown_because": "" if ok else why})
    return pd.DataFrame(rows).set_index("run")
