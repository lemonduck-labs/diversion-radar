"""The radar as it stands now, with each series' history, on the rules the backtest tested.

Runs the as-of engine (backtest/asof.py: UK signal from HMRC monthly data with its
publication lag, onward signal from each corridor's annual UN Comtrade data from the date it
was first released) for every corridor and code at every month end from January 2022 to the
run month, then applies the display rule (radar/display.py).

Writes:
- data/processed/live_<run>.csv  all 81 series: status at the run, the values behind it,
                                  history since January 2022, and whether it may be shown
- reports/live_<run>.md          what may be shown outside the repo: shown series in full,
                                  the rest as counts only

Usage:  python scripts/run_live.py [--run 2026-10] [--date "21 October 2026"]

A rise in exports is a lead, not evidence of a breach.
Contains public sector information licensed under the Open Government Licence v3.0.
"""
from __future__ import annotations

import argparse
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest import asof  # noqa: E402
from radar import display  # noqa: E402

DATA, BT, REPORTS = ROOT / "data" / "processed", ROOT / "backtest" / "data", ROOT / "reports"
START = 202201
HOUSE_LINE = "A rise in exports is a lead, not evidence of a breach."
OGL = ("Contains public sector information licensed under the Open Government Licence v3.0. "
       "Licence: https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/")
COMTRADE = "Onward figures: UN Comtrade."
# The tables a run reads. Run 2's are the default; run 3 (scripts/run_live_run3.py) passes its own.
RUN2_INPUTS = {
    "monthly": DATA / "hmrc_monthly_phase1.csv",
    "comtrade_annual": DATA / "comtrade_annual_phase1.csv",
    "release_dates": BT / "comtrade_release_dates.csv",
    "comtrade_monthly": BT / "comtrade_monthly_run2.csv",
    "monthly_release_dates": BT / "comtrade_monthly_release_dates.csv",
    "countries": ROOT / "config" / "countries.csv",
}


def load(inputs: dict | None = None):
    p = {**RUN2_INPUTS, **(inputs or {})}
    monthly = pd.read_csv(p["monthly"], dtype={"code": str})
    ct = pd.read_csv(p["comtrade_annual"], dtype={"code": str})
    release = pd.read_csv(p["release_dates"])
    release["first_released"] = pd.to_datetime(release.first_released, format="ISO8601")
    countries = pd.read_csv(p["countries"])
    corridors = countries[countries.role == "corridor"].astype({"hmrc_country_id": int, "comtrade_code": int})
    codes = pd.read_csv(ROOT / "config" / "codes.csv", dtype={"code": str})
    return monthly, ct, release, corridors, codes


def _streak_start(flags: pd.Series) -> str:
    """First month of the run of True values that ends at the last row, or ''."""
    if not len(flags) or not bool(flags.iloc[-1]):
        return ""
    start = flags.index[-1]
    for p in reversed(flags.index):
        if not bool(flags.loc[p]):
            break
        start = p
    return str(start)


def _run2_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_backtest2", ROOT / "scripts" / "run_backtest2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(run: int, rule: str = "run2", inputs: dict | None = None,
          monthly_reporters=None, routes=None) -> pd.DataFrame:
    """rule "run1": annual onward check only; "run2": annual or monthly (backtest run 2).

    inputs, monthly_reporters and routes default to run 2's: its tables (RUN2_INPUTS), the
    seven corridors with the monthly check (MONTHLY_REPORTERS in scripts/run_backtest2.py) and
    the case routes from display.load_case_routes. Run 3 passes its own; the rule's code is
    the same, since part_a_timeline reads MONTHLY_REPORTERS from its own copy of the module."""
    p = {**RUN2_INPUTS, **(inputs or {})}
    monthly, ct, release, corridors, codes = load(p)
    if rule == "run2":
        rb2 = _run2_module()
        if monthly_reporters is not None:
            rb2.MONTHLY_REPORTERS = set(int(r) for r in monthly_reporters)
        ctm = pd.read_csv(p["comtrade_monthly"], dtype={"code": str})
        rel_m = pd.read_csv(p["monthly_release_dates"])
        rel_m["first_released"] = pd.to_datetime(rel_m.first_released, format="ISO8601")
    run_p = asof.to_period(run)
    data_end = int((run_p - asof.UK_LAG_MONTHS).strftime("%Y%m"))
    if routes is None:
        routes = display.load_case_routes(ROOT)
    rows = []
    for _, c in corridors.iterrows():
        for _, k in codes.iterrows():
            if rule == "run2":
                t = rb2.part_a_timeline(monthly, ct, release, ctm, rel_m, int(c.hmrc_country_id),
                                        int(c.comtrade_code), k.code, START, run)
            else:
                t = asof.timeline(monthly, ct, int(c.hmrc_country_id), int(c.comtrade_code), k.code,
                                  START, run, asof.UK_LAG_MONTHS, release)
                t["onward_annual"], t["onward_monthly"], t["lead_run1"] = t.onward_signal, False, t.lead
            r = t.loc[run_p]
            total, months = display.window_stats(monthly, int(c.hmrc_country_id), k.code, data_end)
            status = "lead" if r.lead else ("watch" if r.uk_signal else "none")
            route = display.route_for(routes, int(c.hmrc_country_id), k.code)
            scr = display.screen_runs(monthly, int(c.hmrc_country_id), k.code, t.index,
                                      asof.UK_LAG_MONTHS, route[1] if route else None)
            shown_lead = t.lead & scr.shown
            if status == "none":
                show, why = False, "not flagged"
            else:
                show, why = bool(scr.loc[run_p, "shown"]), scr.loc[run_p, "not_shown_because"]
            base = float(r.baseline)
            ob = r.onward_base
            rows.append({
                "country": c["name"], "hmrc_country_id": int(c.hmrc_country_id),
                "comtrade_code": int(c.comtrade_code), "code": k.code, "description": k.description,
                "status": status, "uk_signal": bool(r.uk_signal), "onward_signal": bool(r.onward_signal),
                "uk_data_to": data_end,
                "uk_trailing12_gbp": float(r.trailing12_published), "uk_baseline_gbp": base,
                "uk_ratio": (float(r.trailing12_published) / base) if base > 0 else None,
                "uk_months_with_exports": months,
                "onward_year": r.onward_year, "onward_usd": r.onward_value, "onward_base_usd": ob,
                "onward_ratio": (r.onward_value / ob) if pd.notna(ob) and ob and ob > 0 else None,
                "first_lead": str(t.index[t.lead][0]) if t.lead.any() else "",
                "runs_as_lead": int(t.lead.sum()), "lead_since": _streak_start(t.lead),
                "first_watch": str(t.index[t.uk_signal][0]) if t.uk_signal.any() else "",
                "runs_as_watch_or_lead": int(t.uk_signal.sum()),
                "display": bool(show), "not_shown_because": "" if show else why,
                "case_route": route[0] if route else "",
                "case_match": route[2] if route else "",
                "history_from": str(scr.index[scr.shown][0]) if scr.shown.any() else "",
                "runs_shown": int(scr.shown.sum()),
                "first_lead_shown": str(t.index[shown_lead][0]) if shown_lead.any() else "",
                "runs_shown_as_lead": int(shown_lead.sum()),
                "rule": rule, "onward_annual": bool(r.onward_annual), "onward_monthly": bool(r.onward_monthly),
                "monthly_end": int(r.monthly_end) if "monthly_end" in t and pd.notna(r.get("monthly_end")) else None,
                "monthly_window_usd": float(r.monthly_window_usd) if "monthly_window_usd" in t and pd.notna(r.get("monthly_window_usd")) else None,
                "monthly_base_usd": float(r.monthly_base_usd) if "monthly_base_usd" in t and pd.notna(r.get("monthly_base_usd")) else None,
                "lead_under_run1_rule": bool(r.lead_run1),
            })
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ report formatting
def _half_up(x: float, places: int = 0) -> Decimal:
    q = Decimal(1).scaleb(-places)
    return Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP)


def _money(x: float, sign: str) -> str:
    """To the nearest 1,000 (one decimal place in millions); exact below 1,000."""
    if x >= 1_000_000:
        return f"{sign}{_half_up(x / 1e6, 1)}m"
    if x >= 1_000:
        return f"{sign}{int(_half_up(x / 1000)):,}k"
    return f"{sign}{int(_half_up(x)):,}"


def gbp_k(x: float) -> str:
    return _money(x, "£")


def usd_k(x: float) -> str:
    return _money(x, "$")


def ratio(x) -> str:
    if x is None or pd.isna(x):
        return "no baseline"
    return f"{_half_up(x, 1)}x"


def month_name(p: str) -> str:
    return pd.Period(p, freq="M").strftime("%b %Y") if p else "-"


def onward_desc(r) -> tuple[str, float | None, float | None]:
    """Which onward check is on for a lead, and the figures behind it."""
    if r.onward_annual:
        label = f"annual, {int(r.onward_year)}" + (" (monthly too)" if r.onward_monthly else "")
        return label, r.onward_usd, r.onward_ratio
    if r.onward_monthly:
        base = r.monthly_base_usd
        return (f"monthly, 12 months to {month_name(str(asof.to_period(int(r.monthly_end))))}",
                r.monthly_window_usd, (r.monthly_window_usd / base) if base else None)
    return "none", None, None


def report(df: pd.DataFrame, run: int, run_date: str) -> str:
    rule = df.rule.iloc[0]
    run_p = asof.to_period(run)
    data_end = asof.to_period(int(df.uk_data_to.iloc[0]))
    leads, watch = df[df.status == "lead"], df[df.status == "watch"]
    shown_l, shown_w = leads[leads.display], watch[watch.display]
    held_l, held_w = leads[~leads.display], watch[~watch.display]
    ever = df[df.runs_as_lead > 0]
    lines = [
        f"# Radar run, {run_date}", "",
        OGL, "", COMTRADE, "",
        f"{HOUSE_LINE} Nothing here names an exporter, and a lead never means a UK party was "
        "involved.", "",
        f"The radar's {run_p.strftime('%B %Y')} run, made on {run_date}, on the rules the "
        "enforcement backtest tested. " + (
            "A lead needs a UK rise and an onward rise; the onward rise comes from the corridor's "
            "annual data or, for the seven corridors that report monthly, its last 12 released "
            "months (`backtest/preregistration_run2.md`). " if rule == "run2" else
            "A lead needs a UK rise and an onward rise in the corridor's annual data "
            "(`backtest/preregistration.md`). ") +
        f"UK side: HMRC monthly exports to {data_end.strftime('%B %Y')}, the latest published. "
        f"Onward side: each corridor's own exports of the code to Russia as UN Comtrade had "
        f"released them by {run_date}. Nine corridors, nine goods codes from the Common High "
        "Priority List: 81 series.", "",
        "## Limits of a lead", "",
        "1. **Ordinary trade can pass both tests.** A corridor's own demand for the goods can rise "
        "with its exports to Russia. A lead is a question for an analyst, not an answer. [Certain]",
        "2. **The onward leg can be old.** Annual UN Comtrade data arrive months after the year "
        "ends. The United Arab Emirates and Tajikistan have released no annual data for years after "
        "2023; the UAE has no monthly data after 2019 and Tajikistan none, so their onward check rests "
        "on 2023 trade. "
        "Monthly data shorten "
        "the lag for the other seven corridors, but releases are irregular. A lead can rest on "
        "onward trade that has since stopped. [Certain on the dates]",
        "3. **One consignment can carry the UK signal.** The UK test uses a trailing 12-month sum, "
        "so one large shipment keeps it on for a year. A flagged series is shown only if exports "
        f"were recorded in at least {display.MIN_DISPLAY_MONTHS} of the 12 months and total at least "
        f"£{display.MIN_DISPLAY_GBP:,}, and a past run counts below only when its own 12 months pass "
        "the same test. That screens out flows that came in fewer than "
        f"{display.MIN_DISPLAY_MONTHS} months; one large consignment with small sales in other months "
        "can still pass. [Certain on the mechanism]",
        "4. **Figures are revised.** These are the values published today; HMRC and the "
        "corridors revise them. [Certain]",
        "5. **The codes are broad.** A six-digit code covers many products, most of them in "
        "ordinary use. [Certain]",
        "6. **The onward side is the corridor's own report.** The onward check rests on what each "
        "corridor reports to UN Comtrade as its exports to Russia. [Certain]",
        "7. **One month can carry the monthly onward signal.** The rule does not test how spread "
        "out the onward exports are. [Certain]", "",
        "## Now", "",
        f"- Leads (both signals on): {len(leads)}; shown below: {len(shown_l)}; held back by "
        f"the display rule: {len(held_l)}.",
        f"- Watch items (UK signal only): {len(watch)}; shown below: {len(shown_w)}; held back: "
        f"{len(held_w)}.",
        f"- Series that would have been a lead at some run since January 2022, with today's rule "
        f"rerun on today's figures: {len(ever)} of {len(df)}.", "",
    ]
    if len(shown_l):
        lines += ["### Leads shown", "",
                  "| Corridor | Code | UK exports, last 12 months | Against 2019-21 | Months with exports | "
                  "Onward check | Corridor exports to Russia | Against 2019-21 | First shown as a lead | "
                  "Runs shown as a lead |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for _, r in shown_l.sort_values("uk_trailing12_gbp", ascending=False).iterrows():
            label, val, rat = onward_desc(r)
            lines.append(f"| {r.country} | {r.code} | {gbp_k(r.uk_trailing12_gbp)} | {ratio(r.uk_ratio)} | "
                         f"{r.uk_months_with_exports} of 12 | {label} | {usd_k(val)} | {ratio(rat)} | "
                         f"{month_name(r.first_lead_shown)} | {r.runs_shown_as_lead} of {r.runs_shown} |")
        lines.append("")
    if len(shown_w):
        lines += ["### Watch items shown (UK signal, no onward rise)", "",
                  "| Corridor | Code | UK exports, last 12 months | Against 2019-21 | Months with exports | "
                  "Why no onward signal |", "|---|---|---|---|---|---|"]
        for _, r in shown_w.sort_values("uk_trailing12_gbp", ascending=False).iterrows():
            if pd.isna(r.onward_usd):
                why = "no annual onward data for the latest year"
            elif r.onward_usd < asof.ONWARD_MIN_USD:
                why = f"annual: {usd_k(r.onward_usd)} in {int(r.onward_year)}, under the $100k floor"
            else:
                why = f"annual: {usd_k(r.onward_usd)} in {int(r.onward_year)}, under 2x its 2019-21 average"
            if rule == "run2" and r.monthly_end and pd.notna(r.monthly_window_usd):
                why += (f"; monthly: {usd_k(r.monthly_window_usd)} in the 12 months to "
                        f"{month_name(str(asof.to_period(int(r.monthly_end))))}")
            lines.append(f"| {r.country} | {r.code} | {gbp_k(r.uk_trailing12_gbp)} | {ratio(r.uk_ratio)} | "
                         f"{r.uk_months_with_exports} of 12 | {why} |")
        lines.append("")
    on_routes = df[df.display & (df.case_route != "")]
    if len(on_routes):
        items = [f"{r.country} {r.code} ({r.case_route})" for _, r in on_routes.iterrows()]
        listed = items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]
        lines += ["Runs are counted as shown only when their own 12 months pass the display rule. "
                  f"For {listed}, the corridor and the code or its four-digit goods heading also appear "
                  "in published enforcement cases (in brackets), so only 12-month windows that start "
                  "after the cases' first public actions are counted. The cases named no UK goods or UK "
                  "party.", ""]
    lines += [
        "## Method", "",
        f"- UK signal: trailing 12 months of UK exports at least 2x the 2019-21 annual average "
        "and at least £20,000 above it, for 3 published months running. HMRC month M counts "
        "from the end of month M + 2.",
        "- Onward signal, annual: the corridor's exports of the code to Russia in the latest year "
        "released (2022 or later) at least 2x its 2019-21 average and at least $100,000.",
        *(["- Onward signal, monthly (seven corridors): the 12 months ending at the latest month "
           "released (January 2022 or later) at least 2x the corridor's average 2019-21 month times "
           "12 and at least $100,000. Either onward signal counts.",
           f"- Under run 1's rule (annual check only) this run would show "
           f"{int(df.lead_under_run1_rule.sum())} leads."] if rule == "run2" else []),
        "- A lead needs both. These rules were fixed before the backtest runs "
        "(`backtest/preregistration.md`, `backtest/preregistration_run2.md`); the results are in "
        "`backtest/RESEARCH_LOG.md`.",
        f"- Display rule (`radar/display.py`): at least £{display.MIN_DISPLAY_GBP:,} of UK exports "
        f"and exports in at least {display.MIN_DISPLAY_MONTHS} of the 12 months, at the run and at "
        "every past run counted; anything smaller is counted, not shown by corridor or code. The "
        "2019-21 average is shown however small, as pre-war context.",
        "- Rounding: £ to the nearest thousand (one decimal place in £m), halves up.",
        f"- Files: `data/processed/live_{run_p.strftime('%Y-%m')}.csv`; rebuild with "
        f"`python scripts/run_live.py --run {run_p.strftime('%Y-%m')}`.", "",
        HOUSE_LINE, "", OGL, "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="2026-10")
    ap.add_argument("--date", default="21 October 2026")
    ap.add_argument("--rule", default="run2", choices=["run1", "run2"])
    a = ap.parse_args(argv)
    run = int(a.run.replace("-", ""))
    df = build(run, a.rule)
    tag = asof.to_period(run).strftime("%Y-%m")
    df.to_csv(DATA / f"live_{tag}.csv", index=False)
    (REPORTS / f"live_{tag}.md").write_text(report(df, run, a.date))
    print(f"wrote data/processed/live_{tag}.csv and reports/live_{tag}.md")
    print(df.status.value_counts().to_string())
    print(HOUSE_LINE)
    print(OGL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
