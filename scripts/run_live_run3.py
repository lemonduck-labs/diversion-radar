"""Run 3: the radar's October 2026 run with 18 corridors, on run 2's rule, unchanged
(pre-registered in backtest/RESEARCH_LOG.md, entry R3).

The nine corridors added are the countries the UK guidance for businesses names for enhanced
due diligence that the radar did not yet watch (config/countries_run3.csv). The engine is run
2's live engine (scripts/run_live.build), run on run 3's tables (scripts/build_run3_tables.py),
with the monthly check for every corridor with monthly UN Comtrade data after 2019 (run 2's
criterion) and the case routes the register links to the new corridors added to the display
rule's routes (config/case_routes_run3.csv).

Writes:
- data/processed/live_2026-10_run3.csv   all 162 series, in run 2's columns plus the run label
- backtest/reports/run3.md               leads and watch items by corridor and code, which pass
                                          the display rule, and the check against run 2
Stops if the original nine's rows differ from run 2's output (data/processed/live_2026-10.csv)
in any byte of run 2's columns. Run 2's outputs are read, never written.

Usage:  python scripts/run_live_run3.py

A rise in exports is a lead, not evidence of a breach.
Contains public sector information licensed under the Open Government Licence v3.0.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest import asof  # noqa: E402
from radar import display  # noqa: E402

DATA, BT, CONFIG = ROOT / "data" / "processed", ROOT / "backtest" / "data", ROOT / "config"
RUN, RUN_DATE, LABEL = 202610, "21 October 2026", "run3"
RUN2_OUT = DATA / "live_2026-10.csv"
RUN2_OUT_SHA256 = "5303eb673ca1344934abd9f8e8ced2c8c82f18b938d72e3de9095b7264dfb86c"
OUT, REPORT = DATA / "live_2026-10_run3.csv", ROOT / "backtest" / "reports" / "run3.md"
PREREG_COMMIT = "5447f08"
INPUTS = {
    "monthly": DATA / "hmrc_monthly_run3.csv",
    "comtrade_annual": DATA / "comtrade_annual_run3.csv",
    "release_dates": BT / "comtrade_release_dates_run3.csv",
    "comtrade_monthly": BT / "comtrade_monthly_run3.csv",
    "monthly_release_dates": BT / "comtrade_monthly_release_dates_run3.csv",
    "countries": CONFIG / "countries_run3.csv",
}
HOUSE_LINE = "A rise in exports is a lead, not evidence of a breach."
OGL = ("Contains public sector information licensed under the Open Government Licence v3.0. "
       "Licence: https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/")


def _module(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_for_run3", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def corridors() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(run 2's nine corridors, the nine added)."""
    run3 = pd.read_csv(INPUTS["countries"])
    run3 = run3[run3.role == "corridor"].astype({"hmrc_country_id": int, "comtrade_code": int})
    run2 = pd.read_csv(CONFIG / "countries.csv")
    run2 = run2[run2.role == "corridor"].astype({"hmrc_country_id": int, "comtrade_code": int})
    return run2, run3[~run3.hmrc_country_id.isin(run2.hmrc_country_id)]


def monthly_reporters(rb2_seven: set) -> tuple[list[int], list[int]]:
    """Run 2's criterion, monthly UN Comtrade data after 2019, over all 18 corridors. For the
    original nine it must give run 2's seven; returns (all, new ones)."""
    rel_m = pd.read_csv(INPUTS["monthly_release_dates"])
    after = set(int(r) for r in rel_m[rel_m.period > 201912].reporter)
    run2, new = corridors()
    orig = set(run2.comtrade_code) & after
    if orig != set(rb2_seven):
        raise SystemExit(f"monthly criterion gives {sorted(orig)} for the original nine, not run 2's seven")
    new_m = sorted(set(new.comtrade_code) & after)
    return sorted(orig | set(new_m)), new_m


def case_routes() -> dict:
    """The display rule's case routes: the test plan, config/case_routes_extra.csv and, for the
    new corridors, config/case_routes_run3.csv."""
    cols = ["case_id", "hmrc_country_id", "codes", "reference_date"]
    frames = [pd.read_csv(ROOT / "backtest" / "data" / "test_plan.csv", dtype={"codes": str})[cols],
              pd.read_csv(CONFIG / "case_routes_extra.csv", dtype={"codes": str})[cols]]
    run3 = pd.read_csv(CONFIG / "case_routes_run3.csv", dtype={"codes": str})
    run2_ids = set(corridors()[0].hmrc_country_id)
    if run3.hmrc_country_id.isin(run2_ids).any():
        raise SystemExit("config/case_routes_run3.csv may only add routes for the new corridors")
    routes = display.case_routes(pd.concat(frames + [run3[cols]], ignore_index=True))
    base = display.load_case_routes(ROOT)
    if {k: v for k, v in routes.items() if k[0] in run2_ids} != base:
        raise SystemExit("run 3's case routes differ from run 2's for the original corridors")
    return routes


def compare_with_run2(df: pd.DataFrame) -> dict:
    """The original nine's rows, in run 2's columns, written as CSV, against run 2's file."""
    old = RUN2_OUT.read_bytes()
    if hashlib.sha256(old).hexdigest() != RUN2_OUT_SHA256:
        raise SystemExit("data/processed/live_2026-10.csv is not run 2's output as committed")
    cols = pd.read_csv(RUN2_OUT, nrows=0).columns.tolist()
    run2_ids = set(corridors()[0].hmrc_country_id)
    buf = io.StringIO()
    df[df.hmrc_country_id.isin(run2_ids)][cols].to_csv(buf, index=False)
    same = buf.getvalue().encode() == old
    if not same:
        a, b = buf.getvalue().splitlines(), old.decode().splitlines()
        diff = [i for i, (x, y) in enumerate(zip(a, b)) if x != y][:5]
        raise SystemExit(f"the original nine differ from run 2's output (first lines {diff}, "
                         f"{len(a)} against {len(b)} lines)")
    return {"rows": int(len(df[df.hmrc_country_id.isin(run2_ids)])), "identical": same, "columns": len(cols)}


# ------------------------------------------------------------------ report
def report(df: pd.DataFrame, live, inputs_report: dict, check: dict, monthly_all: list[int],
           monthly_new: list[int]) -> str:
    run2, new = corridors()
    is_new = df.hmrc_country_id.isin(new.hmrc_country_id)
    groups = (("The nine added", df[is_new]), ("The original nine", df[~is_new]), ("All 18", df))

    def counts(d):
        lead, watch = d[d.status == "lead"], d[d.status == "watch"]
        return (len(lead), int(lead.display.sum()), len(watch), int(watch.display.sum()),
                int((d.runs_as_lead > 0).sum()), len(d))

    def against(x, base=None) -> str:
        if base is not None and pd.notna(base) and float(base) == 0.0:
            return "a zero 2019-21 baseline"
        return "no 2019-21 baseline" if x is None or pd.isna(x) else f"{live.ratio(x)} the 2019-21 level"

    def has_monthly(r) -> bool:
        return pd.notna(r.monthly_window_usd) and pd.notna(r.monthly_end)

    def monthly_part(r) -> str:
        base = r.monthly_base_usd
        rat_m = (r.monthly_window_usd / base) if pd.notna(base) and base else None
        return (f"monthly, 12 months to {live.month_name(str(asof.to_period(int(r.monthly_end))))}: "
                f"{live.usd_k(r.monthly_window_usd)}, {against(rat_m, base)}")

    def onward(r) -> str:
        """The check that is on, then the other one beside it (R3.4), as on the dashboard."""
        label, val, rat = live.onward_desc(r)
        if r.status == "lead":
            base_on = r.onward_base_usd if r.onward_annual else r.monthly_base_usd
            out = f"on, {label}: {live.usd_k(val)}, {against(rat, base_on)}"
            if r.onward_annual and has_monthly(r):
                out += "; " + monthly_part(r) + ("" if r.onward_monthly else ", not passed")
            elif not r.onward_annual and pd.notna(r.onward_usd):
                out += (f"; annual {int(r.onward_year)}: {live.usd_k(r.onward_usd)}, "
                        f"{against(r.onward_ratio, r.onward_base_usd)}, not passed")
            return out
        parts = []
        if pd.isna(r.onward_usd):
            parts.append("annual: no records for the latest year released")
        else:
            parts.append(f"annual {int(r.onward_year)}: {live.usd_k(r.onward_usd)}, "
                         f"{against(r.onward_ratio, r.onward_base_usd)}")
        if has_monthly(r):
            parts.append(monthly_part(r))
        return "off; " + "; ".join(parts)

    def onward_below_uk(r) -> tuple[float, float] | None:
        """For a lead, the largest onward figure that passed (USD) where it is smaller than the UK
        flow (GBP) as figures. The pound's annual average was above $1 in every year of
        config/fx_usd_per_gbp.csv (Bank of England, 2019 to 2025), so it is smaller in either
        currency."""
        passed = [float(v) for ok, v in ((r.onward_annual, r.onward_usd), (r.onward_monthly, r.monthly_window_usd))
                  if ok and pd.notna(v)]
        if r.status == "lead" and passed and max(passed) < float(r.uk_trailing12_gbp):
            return max(passed), float(r.uk_trailing12_gbp)
        return None

    def table(d: pd.DataFrame, title: str) -> list[str]:
        if not len(d):
            return [f"### {title}", "", "None.", ""]
        out = [f"### {title}", "",
               "| Corridor | Code | Shown under the display rule | UK exports, last 12 months | Against 2019-21 "
               "| Months with exports | Onward check | First shown as a lead | Runs shown as a lead |",
               "|---|---|---|---|---|---|---|---|---|"]
        for _, r in d.sort_values(["display", "uk_trailing12_gbp"], ascending=[False, False]).iterrows():
            if r.display:
                uk = (live.gbp_k(r.uk_trailing12_gbp), live.ratio(r.uk_ratio), f"{r.uk_months_with_exports} of 12")
                first = live.month_name(str(r.first_lead_shown)) if str(r.first_lead_shown) not in ("", "nan") else "-"
                runs = f"{int(r.runs_shown_as_lead)} of {int(r.runs_shown)}"
                shown = "yes"
            else:
                uk = first = runs = "held back"
                uk = (uk, uk, uk)
                shown = "no: " + str(r.not_shown_because)
            out.append(f"| {r.country} | {r.code} | {shown} | {uk[0]} | {uk[1]} | {uk[2]} | {onward(r)} | "
                       f"{first} | {runs} |")
        return out + [""]

    cov = inputs_report["coverage"]
    lines = [
        "# Run 3: corridors added. The radar's October 2026 run with 18 corridors", "",
        OGL, "", "Onward figures: UN Comtrade.", "",
        f"{HOUSE_LINE} Nothing here names an exporter, and a lead never means a UK party was involved.", "",
        "**Internal research report.** It lists, by corridor and code, series that the display rule "
        "holds back, without their UK figures. Those series may not be shown outside the repo by "
        "corridor or code; anything shared goes through /review and /ship first.", "",
        f"Pre-registered in `backtest/RESEARCH_LOG.md`, entry R3 (commit {PREREG_COMMIT}), before any "
        "figures for the new corridors were pulled. Run 2's rule and display rule, unchanged, with the "
        "case routes the register links to the new corridors added to the display rule's routes; nine "
        "corridors added, the countries the UK guidance for businesses names for enhanced due "
        "diligence that the radar did not yet watch; nine goods codes; 162 series. The run is the "
        f"end of October 2026, made on {RUN_DATE}: HMRC data to August 2026, UN Comtrade data as "
        f"released by {RUN_DATE}. Run 3 is a live run, not a backtest: the backtest's tests are not "
        "changed or rerun, and nothing here is evidence for or against them.", "",
        "## Results at the October 2026 run", "",
        "| Corridors | Leads | Leads shown | Watch items | Watch items shown | A lead at some run since January 2022 |",
        "|---|---|---|---|---|---|",
    ]
    for name, d in groups:
        lc, ls, wc, ws, ever, n = counts(d)
        lines.append(f"| {name} | {lc} | {ls} | {wc} | {ws} | {ever} of {n} |")
    lines += ["", "A lead needs the UK signal and an onward signal at the run; a watch item has the UK "
              "signal only. Shown means the series passes the display rule at the run (at least "
              f"£{display.MIN_DISPLAY_GBP:,} of UK exports over the 12 published months, with exports in at "
              f"least {display.MIN_DISPLAY_MONTHS} of them). [Certain on the counts]", ""]
    lines += table(df[is_new & (df.status == "lead")], "Leads: the nine added")
    lines += table(df[is_new & (df.status == "watch")], "Watch items (UK signal, onward check not passed): the nine added")
    lines += table(df[~is_new & (df.status == "lead")], "Leads: the original nine, as in run 2")
    lines += table(df[~is_new & (df.status == "watch")], "Watch items: the original nine, as in run 2")
    lines += ["Runs are counted as shown only when their own 12 published months pass the display rule, "
              "as in run 2's report, so a watch item can show a past run as a lead. Series held back are "
              "listed without UK figures or months.", ""]
    on_routes = df[is_new & (df.case_route != "") & (df.status != "none")]
    if len(on_routes):
        items = [f"{r.country} {r.code} ({r.case_route})" for _, r in on_routes.iterrows()]
        lines += ["Case routes: for " + (items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1])
                  + ", the corridor and the code or its four-digit heading also appear in published "
                  "enforcement cases (in brackets; `config/case_routes_run3.csv`), so only 12-month windows "
                  "that start after the cases' first public actions are counted as shown. The cases named "
                  "no UK goods or UK party.", ""]
    lines += [
        "## Against run 2, for the original nine", "",
        f"Nothing changed. The original nine's {check['rows']} rows of `data/processed/live_2026-10_run3.csv`, "
        f"in run 2's {check['columns']} columns, are byte-identical to run 2's output "
        "(`data/processed/live_2026-10.csv`, which run 3 reads and does not write), and every run 3 input "
        "table starts with its run 2 table's bytes, with only the new corridors' rows after them "
        "(`backtest/data/run3_inputs_report.json`). Run 2's outputs stay as they are. [Certain]", "",
        "## Inputs for the nine added", "",
        f"- HMRC: {inputs_report['hmrc']['rows']:,} monthly rows from "
        f"{live.month_name(str(asof.to_period(inputs_report['hmrc']['first_month'])))} to "
        f"{live.month_name(str(asof.to_period(inputs_report['hmrc']['last_month'])))}, 81 queries, one "
        "snapshot (`data/raw/hmrc_monthly_run3_browser_2026-10-21.txt`).",
        f"- UN Comtrade: {inputs_report['calls']['comtrade']} calls: data availability, annual exports to "
        "Russia and imports from the UK for 2019 to 2025, and monthly exports to Russia from January 2019 "
        "(`data/raw/comtrade_run3_browser_2026-10-21.txt`).",
        "- Monthly check: run 2's criterion, monthly UN Comtrade data after 2019, gives all nine new "
        f"corridors ({', '.join(str(r) for r in monthly_new)}); the original nine keep run 2's seven.", "",
        "| Corridor | Annual exports to Russia, years held | Latest annual year released | Monthly data | "
        "Monthly datasets from 2019 |", "|---|---|---|---|---|",
    ]
    def below(mask):
        rows = [(r, onward_below_uk(r)) for _, r in df[mask & (df.status == "lead") & df.display]
                .sort_values("uk_trailing12_gbp", ascending=False).iterrows()]
        return [(r, x) for r, x in rows if x]

    def listed(items):
        return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]

    small_new, small_old = below(is_new), below(~is_new)
    def item(r, x):
        name = f"the {r.country}" if r.country in ("United Arab Emirates", "Kyrgyz Republic") else r.country
        return f"{name} {r.code} ({live.usd_k(x[0])} against {live.gbp_k(x[1])})"

    small_text = ""
    if small_new or small_old:
        parts = []
        if small_new:
            parts.append(listed([item(r, x) for r, x in small_new]) + " among the nine added")
        if small_old:
            parts.append(listed([item(r, x) for r, x in small_old]) + " among the original nine")
        small_text = ", and ".join(parts)
    # The comparison holds at any exchange rate above the largest onward / UK ratio, rounded up.
    top_ratio = max([x[0] / x[1] for _, x in small_new + small_old], default=0.0)
    rate_needed = math.ceil(top_ratio * 100) / 100
    fx = pd.read_csv(ROOT / "config" / "fx_usd_per_gbp.csv")
    fx_floor = int(fx.usd_per_gbp.min() * 100) / 100    # rounded down, so "above" stays true
    fx_years = f"{int(fx.year.min())} to {int(fx.year.max())}"
    for c in new.itertuples():
        v = cov[c.name]
        yrs = v["annual_years_exports_to_russia"]
        rel = v["annual_years_released"]
        lines.append(f"| {c.name} | {', '.join(str(y) for y in yrs) or 'none'} | {max(rel) if rel else 'none'} | "
                     f"{live.month_name(str(asof.to_period(v['monthly_first'])))} to "
                     f"{live.month_name(str(asof.to_period(v['monthly_last'])))} | {v['monthly_datasets_from_2019']} |")
    lines += ["", "Gaps are listed in `data/SOURCES.md`.", "",
              "## Limits", "",
              "1. **Ordinary trade can pass both tests**, and more so in large manufacturing hubs, which buy "
              "these goods for their own production and export finished electronics. A lead is a question "
              "for an analyst, not an answer. [Likely]",
              (f"2. **Onward flows smaller than the UK flow.** For {small_text}, the corridor's reported "
               "exports of the code to Russia, on the check that passed, are smaller than UK exports of it to "
               "the corridor over the 12 months, in US dollars against pounds. That holds at any exchange rate "
               f"above ${rate_needed:.2f} to the pound; the Bank of England's annual averages for {fx_years} in "
               f"`config/fx_usd_per_gbp.csv` are all above ${fx_floor:.2f}, and 2026 is not in the file. Even if "
               "every onward shipment were UK goods, they "
               "would match only part of the UK flow, so a UK rise can sit beside an onward rise with no "
               "link between them; the periods differ, so this compares scale only. [Likely]")
              if small_text else
              "2. **No lead among the nine added has an onward flow smaller than its UK flow.** [Certain]",
              "3. **Hong Kong's reported exports include re-exports.** [Likely]",
              "4. **The onward leg can be old.** China's monthly data end in December 2024; Vietnam's annual "
              "and monthly data end in 2023; a lead can rest on onward trade that has since stopped. "
              "[Certain on the dates]",
              "5. **The limits in run 2's report apply unchanged** (`reports/live_2026-10.md`): one "
              "consignment can carry the UK signal, figures are revised, the codes are broad, and the onward "
              "side is each corridor's own report.", "",
              "## Method and files", "",
              "- Rule: run 2's (`backtest/preregistration_run2.md`), run by `scripts/run_live.py` with run 3's "
              "inputs; display rule: `radar/display.py`, with the case routes in `config/case_routes_run3.csv` "
              "added for the new corridors.",
              "- Files: `data/processed/live_2026-10_run3.csv`; rebuild with "
              "`python scripts/build_run3_tables.py` then `python scripts/run_live_run3.py`.",
              "- Rounding: £ to the nearest thousand (one decimal place in £m), halves up.", "",
              HOUSE_LINE, "", OGL, ""]
    return "\n".join(lines)


def main() -> int:
    live = _module("run_live")
    rb2 = _module("run_backtest2")
    monthly_all, monthly_new = monthly_reporters(rb2.MONTHLY_REPORTERS)
    routes = case_routes()
    df = live.build(RUN, "run2", inputs=INPUTS, monthly_reporters=monthly_all, routes=routes)
    if len(df) != 162:
        raise SystemExit(f"expected 162 series, built {len(df)}")
    check = compare_with_run2(df)
    df["run"] = LABEL
    df.to_csv(OUT, index=False)
    inputs_report = json.loads((BT / "run3_inputs_report.json").read_text())
    REPORT.write_text(report(df, live, inputs_report, check, monthly_all, monthly_new))
    print(f"wrote {OUT.relative_to(ROOT)} and {REPORT.relative_to(ROOT)}")
    print(f"original nine: {check['rows']} rows identical to run 2's output")
    print(df.groupby(df.hmrc_country_id.isin(corridors()[1].hmrc_country_id)).status.value_counts().to_string())
    print(HOUSE_LINE)
    print(OGL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
