"""The facts for one flagged series at one radar run: the context an analyst brief is
drafted from, and the only thing a drafter may use.

build_context(run, series_key, variant=...) reads the same tables the live run uses:
- data/processed/live_<run>.csv (run 2) or live_<run>_run3.csv (run 3, the workspace's
  current run and the default): the run's status, figures and display flag;
- the UK monthly figures and the onward tables through scripts/run_live.load(), with run 2's
  monthly onward check (scripts/run_backtest2.part_a_timeline), screened at every run by
  radar/display.screen_runs; for run 3, its tables, monthly corridors and case routes
  (scripts/build_demo_data.variant);
- backtest/data/cases.csv at case level only, linked through radar/display's case routes.

It refuses (BriefRefused) any series that is not flagged at the run or does not pass the
display rule, and it re-checks the rule from the monthly table rather than trusting the
flag. Every fact carries a source reference (dataset and field) and a confidence tag.
Nothing per person and no URL is copied: a case gives its id, jurisdiction, case-level
outcome, what its reference rests on and its first public action, nothing else.

Contains public sector information licensed under the Open Government Licence v3.0.
A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

import functools
import importlib.util
import json
import math
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from radar import display, onward as onward_rule
from radar.brief import redflags as rf

ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).resolve().parent / "spec"
SCHEMA = "radar-brief-context/1"
HOUSE_LINE = "A rise in exports is a lead, not evidence of a breach."
OGL_LINE = "Contains public sector information licensed under the Open Government Licence v3.0."
SOURCES_LINE = "UK figures: HMRC overseas trade statistics. Onward figures: UN Comtrade."

#: Register columns that never enter a context: per-person detail, conduct, values, links.
NEVER_COPIED = ("enforcing_body", "official_reference", "enforcement_date", "enforcement_stage",
                "conduct_start", "conduct_end", "conduct_as_stated", "goods_as_described",
                "hs_code_stated", "mapping_reasoning", "origin_or_export_country", "uk_involvement",
                "transit_or_corridor_countries", "radar_corridor_match", "final_destination",
                "value_of_goods", "testable_now", "source_url", "other_sources", "verification_notes")
URL = re.compile(r"(?i)\bhttps?://|\bwww\.|\b[a-z0-9-]+\.(?:com|org|net|gov|int|eu|uk)/")
PER_PERSON = re.compile(r"(?i)\b(?:sentenced\s+to|years?\s+in\s+prison|months?\s+in\s+prison|prison|jail\w*|"
                        r"imprison\w*|nationality|citizen\s+of|resident\s+of|residing\s+in|arrested\s+on|"
                        r"date\s+of\s+birth|aged\s+\d+)\b")
#: Context fields that hold official text and may carry words the brief screen blocks in a
#: draft: case-level outcomes from the register and the titles of official guidance.
OFFICIAL_TEXT = (re.compile(r"^cases\[\d+\]\.(?:outcome|text)$"),
                 re.compile(r"^red_flags\[\d+\]\.(?:citation|also_cited\[\d+\])\.title$"))


class BriefRefused(ValueError):
    """The series may not have a brief: not in the run, not flagged, or not shown under
    the display rule."""


def slug(series: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(series).lower()).strip("-")


def _period(run) -> pd.Period:
    if isinstance(run, pd.Period):
        return run.asfreq("M")
    s = str(run).strip()
    if re.fullmatch(r"\d{6}", s):
        s = f"{s[:4]}-{s[4:]}"
    if not re.fullmatch(r"\d{4}-\d{2}", s):
        raise ValueError(f"run must be YYYY-MM or YYYYMM, not {run!r}")
    return pd.Period(s, freq="M")


def _module(root: Path, name: str):
    spec = importlib.util.spec_from_file_location(f"brief_{name}", root / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@functools.lru_cache(maxsize=2)
def _variants(root: str) -> tuple[str, tuple[str, ...]]:
    """The workspace's current variant of the run and the variants there are
    (scripts/build_demo_data.CURRENT and VARIANTS)."""
    demo = _module(Path(root), "build_demo_data")
    return demo.CURRENT, tuple(demo.VARIANTS)


def _variant(root: Path, variant) -> str:
    current, known = _variants(str(root))
    v = current if variant is None else str(variant)
    if v not in known:
        raise ValueError(f"variant must be one of {', '.join(known)}, not {variant!r}")
    return v


@functools.lru_cache(maxsize=4)
def _inputs(root: str, variant: str) -> SimpleNamespace:
    base = Path(root)
    if root not in sys.path:
        sys.path.insert(0, root)
    from backtest import asof, monthly as monthly_mod
    live_mod = _module(base, "run_live")
    rb2 = _module(base, "run_backtest2")
    demo = _module(base, "build_demo_data")
    v = demo.variant(variant)
    if v.monthly_reporters is not None:
        rb2.MONTHLY_REPORTERS = set(int(x) for x in v.monthly_reporters)
    monthly, ct, release, corridors, codes = live_mod.load(v.inputs)
    bt = base / "backtest" / "data"
    ctm = pd.read_csv(v.inputs["comtrade_monthly"], dtype={"code": str})
    rel_m = pd.read_csv(v.inputs["monthly_release_dates"])
    rel_m["first_released"] = pd.to_datetime(rel_m.first_released, format="ISO8601")
    # The tables each fact cites, as paths in the repo.
    ds = {k: Path(p).resolve().relative_to(base.resolve()).as_posix() for k, p in v.inputs.items()}
    return SimpleNamespace(asof=asof, monthly_mod=monthly_mod, live_mod=live_mod, rb2=rb2, demo=demo,
                           monthly=monthly, ct=ct, release=release, corridors=corridors, codes=codes,
                           ctm=ctm, rel_m=rel_m, cases=pd.read_csv(bt / "cases.csv").set_index("case_id"),
                           routes=v.routes, route_files=v.route_files, monthly_source=v.monthly_source,
                           suffix=v.suffix, ds=ds)


@functools.lru_cache(maxsize=4)
def _live(root: str, tag: str, variant: str) -> pd.DataFrame:
    suffix = "_run3" if variant == "run3" else ""
    path = Path(root) / "data" / "processed" / f"live_{tag}{suffix}.csv"
    if not path.exists():
        script = "scripts/run_live_run3.py" if variant == "run3" else f"scripts/run_live.py --run {tag}"
        raise BriefRefused(f"no live table for the {tag} run ({variant}); run {script} first")
    return pd.read_csv(path, dtype={"code": str})


def flagged_shown(run, root=None, variant=None) -> list[str]:
    """The series flagged at a run that pass the display rule, in the demo's order. variant:
    "run2" or "run3"; the default is the workspace's current run."""
    root = Path(root or ROOT).resolve()
    live = _live(str(root), _period(run).strftime("%Y-%m"), _variant(root, variant))
    shown = live[(live.status != "none") & live.display]
    shown = shown.sort_values(["status", "uk_trailing12_gbp"], ascending=[True, False])
    return [f"{r.country} {r.code}" for r in shown.itertuples()]


def _find(live: pd.DataFrame, key: str):
    want = str(key).strip()
    for r in live.itertuples():
        label = f"{r.country} {r.code}"
        if want in (label, slug(label)):
            return r, label
    raise BriefRefused(f"{key!r} is not a series in this run")


def _day(ts) -> str:
    return pd.Timestamp(ts).strftime("%-d %b %Y")


def _iso(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def _mon(p) -> str:
    return pd.Period(str(p), freq="M").strftime("%b %Y")


#: UN Comtrade reporters whose reported exports include re-exports (data/SOURCES.md, run 3
#: corridors) [Likely]: Hong Kong.
REEXPORTERS = frozenset({344})

#: Corridor names that take "the" in running text.
ARTICLE = frozenset({"United Arab Emirates", "Kyrgyz Republic"})


def _name(country: str, start: bool = False) -> str:
    s = f"the {country}" if country in ARTICLE else country
    return s[0].upper() + s[1:] if start else s


def _poss(country: str, start: bool = False) -> str:
    s = _name(country, start)
    return s + ("'" if s.endswith("s") else "'s")


def _num(x, nd: int = 0):
    """Rounded halves up, as the dashboard's data files are; None for a missing value."""
    if x is None or pd.isna(x):
        return None
    q = Decimal(str(float(x))).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP)
    return float(q) if nd else int(q)


def build_context(run, series_key: str, root=None, variant=None) -> dict:
    """The facts for one series at one run. Raises BriefRefused for a series that is not
    flagged or not shown under the display rule. variant: "run2" (nine corridors) or "run3"
    (18); the default is the workspace's current run."""
    root = Path(root or ROOT).resolve()
    variant = _variant(root, variant)
    p = _period(run)
    tag = p.strftime("%Y-%m")
    r, label = _find(_live(str(root), tag, variant), series_key)
    if r.status not in ("lead", "watch"):
        raise BriefRefused(f"{label} is not flagged at the {tag} run")
    if not bool(r.display):
        raise BriefRefused(f"{label} is not shown under the display rule at the {tag} run "
                           f"({r.not_shown_because}); it is counted, never shown")
    d = _inputs(str(root), variant)
    asof, lm = d.asof, d.live_mod
    cid, rep, code = int(r.hmrc_country_id), int(r.comtrade_code), str(r.code)
    run_int = p.year * 100 + p.month

    # The display rule, re-checked from the monthly table for the run's 12 published months.
    end = p - asof.UK_LAG_MONTHS
    total, n_months = display.window_stats(d.monthly, cid, code, end.year * 100 + end.month)
    ok, why = display.displayable(total, n_months)
    if not ok:
        raise BriefRefused(f"{label} fails the display rule on the monthly table ({why})")
    live_ds = f"data/processed/live_{tag}{d.suffix}.csv"
    live_name = live_ds.rsplit("/", 1)[1]
    if abs(total - float(r.uk_trailing12_gbp)) > 0.5:
        raise RuntimeError(f"{label}: {live_name} and the monthly table disagree; rerun the live run")

    route = display.route_for(d.routes, cid, code)
    if r.rule == "run2":
        t = d.rb2.part_a_timeline(d.monthly, d.ct, d.release, d.ctm, d.rel_m, cid, rep, code, lm.START, run_int)
    else:
        t = asof.timeline(d.monthly, d.ct, cid, rep, code, lm.START, run_int, asof.UK_LAG_MONTHS, d.release)
    scr = display.screen_runs(d.monthly, cid, code, t.index, asof.UK_LAG_MONTHS, route[1] if route else None)
    if int(scr.shown.sum()) != int(r.runs_shown) or not bool(scr.loc[p, "shown"]):
        raise RuntimeError(f"{label}: screened runs differ from {live_name}; rerun the live run")

    run_label = p.strftime("%B %Y")
    data_to = _mon(end)
    desc = str(r.description)
    desc_l = desc[0].lower() + desc[1:]
    gbp, usd = lm.gbp_k, lm.usd_k

    def ratio(x) -> str:
        """The house ratio format, with a ratio that rounds to 0.0x written as under 0.1x."""
        return "less than 0.1x" if pd.notna(x) and 0 <= float(x) < 0.05 else lm.ratio(x)
    facts: list[dict] = []

    def fact(id_, group, label_, text, value, shown=None, dataset=live_ds, field="", confidence="Certain",
             released=None):
        f = {"id": id_, "group": group, "label": label_, "text": text, "value": value, "display": shown,
             "source": {"dataset": dataset, "field": field}, "confidence": confidence}
        if released is not None:
            f["released"] = released
        facts.append(f)

    # The series
    tier = d.codes.set_index("code").tier.get(code)
    country = str(r.country)
    fact("series.country", "series", "Corridor country", f"Corridor country: {country}.", country, field="country")
    fact("series.code", "series", "Goods code", f"Goods: HS {code}, {desc_l}.", code,
         dataset="config/codes.csv", field="code, description")
    fact("series.chpl_tier", "series", "CHPL tier",
         f"HS {code} is in Tier {int(tier)} of the Common High Priority Items List.", int(tier),
         dataset="config/codes.csv", field="tier")
    fact("series.status", "series", "Status at this run",
         (f"Status at the {run_label} run: a lead, with the UK and onward signals both on." if r.status == "lead"
          else f"Status at the {run_label} run: a watch item, with the UK signal on and the onward signal off."),
         str(r.status), field="status, uk_signal, onward_signal")

    # UK figures
    base = float(r.uk_baseline_gbp)
    thr = max(asof.UK_RATIO * base, base + asof.UK_MIN_EXCESS)
    fact("uk.data_to", "uk", "UK figures to",
         f"The {run_label} run uses UK figures to {data_to}, with a {asof.UK_LAG_MONTHS}-month publication lag.",
         str(end), field="uk_data_to")
    fact("uk.trailing12", "uk", "UK exports, 12 months",
         f"UK exports of {code} to {_name(country)} over the 12 months to {data_to}: {gbp(r.uk_trailing12_gbp)}.",
         _num(r.uk_trailing12_gbp), gbp(r.uk_trailing12_gbp), field="uk_trailing12_gbp")
    fact("uk.baseline", "uk", "UK exports, 2019-21 average",
         f"Average UK exports of {code} to {_name(country)} a year in 2019-21: {gbp(base)}.",
         _num(base), gbp(base), field="uk_baseline_gbp")
    fact("uk.ratio", "uk", "UK rise",
         f"UK exports over the 12 months to {data_to} were {ratio(r.uk_ratio)} the 2019-21 average.",
         _num(r.uk_ratio, 1), ratio(r.uk_ratio), field="uk_ratio")
    fact("uk.months", "uk", "Months with UK exports",
         f"UK exports were recorded in {int(r.uk_months_with_exports)} of the 12 months to {data_to}.",
         int(r.uk_months_with_exports), field="uk_months_with_exports")
    fact("uk.threshold", "uk", "UK threshold",
         (f"The UK threshold for {code} to {_name(country)} is {gbp(thr)} over 12 months: the larger of "
          f"{asof.UK_RATIO:g}x the 2019-21 average and that average plus £{asof.UK_MIN_EXCESS:,}."),
         _num(thr), gbp(thr), dataset="backtest/asof.py", field="UK_RATIO, UK_MIN_EXCESS")
    fact("display.rule", "display", "Display rule",
         (f"Shown under the display rule: at least £{display.MIN_DISPLAY_GBP:,} of UK exports over the 12 "
          f"published months to {data_to}, with exports in at least {display.MIN_DISPLAY_MONTHS} of them."),
         True, dataset="radar/display.py", field="MIN_DISPLAY_GBP, MIN_DISPLAY_MONTHS; displayable()")

    # Onward figures: the corridor's own exports to Russia, from every origin
    ct_ds, ct_field = d.ds["comtrade_annual"], "value_usd (reporter to Russia, flow X)"
    rel = d.release[d.release.reporter == rep].set_index("year").first_released
    has_year = pd.notna(r.onward_year)
    year = int(r.onward_year) if has_year else None
    has_month = pd.notna(r.monthly_window_usd)
    mend = asof.to_period(int(r.monthly_end)) if has_month and pd.notna(r.monthly_end) else None
    # Why a check did not pass, in radar/onward.py's words, as on the dashboard and the exporter screen
    a_why = (onward_rule.why_not(r.onward_usd, r.onward_base_usd)
             if has_year and not r.onward_annual else None)
    m_why = (onward_rule.why_not(r.monthly_window_usd, r.monthly_base_usd)
             if has_month and mend is not None and not r.onward_monthly else None)

    def annual_not(why):
        if why == [onward_rule.NO_EXPORTS]:
            return f"{_poss(country)} annual figures for {year} hold no exports of {code} to Russia"
        return f"{_poss(country)} annual figures for {year} are " + _and(why)

    def monthly_not(why):
        if why == [onward_rule.NO_EXPORTS]:
            return f"the 12 months to {_mon(mend)} hold no exports of {code} to Russia"
        return f"the 12 months to {_mon(mend)} are " + _and(why)

    if r.status == "lead":
        if r.onward_annual:
            check = f"Onward check passed on {_poss(country)} annual figures for {year}"
            if r.onward_monthly:
                check += "; the monthly check passed too."
            elif m_why:
                check += f"; the monthly check did not pass: {monthly_not(m_why)}."
            else:
                check += "."
        else:
            check = (f"Onward check passed on {_poss(country)} monthly figures for the 12 months to {_mon(mend)}; "
                     + (f"the annual check did not pass: {annual_not(a_why)}." if a_why
                        else "the annual check did not pass."))
    else:
        if not has_year:
            check = "The onward check has not passed: there are no annual onward figures for this run"
        else:
            check = f"The onward check has not passed: {annual_not(a_why)}"
        check += f"; the monthly check has not passed either: {monthly_not(m_why)}." if m_why else "."
    fact("onward.check", "onward", "Onward check", check, lm.onward_desc(r)[0] if r.status == "lead" else "not passed",
         field="onward_annual, onward_monthly, onward_year, onward_usd, onward_base_usd, monthly_end, "
               "monthly_window_usd, monthly_base_usd; reasons from radar/onward.py")
    if has_year and pd.notna(r.onward_usd):
        released = rel.get(year)
        base_o = float(r.onward_base_usd) if pd.notna(r.onward_base_usd) else None
        vs = (f"{ratio(r.onward_ratio)} the 2019-21 average of {usd(base_o)} a year" if base_o
              else "with no 2019-21 exports to compare")
        fact("onward.annual", "onward", f"Onward exports, {year}",
             (f"{_poss(country, True)} reported exports of {code} to Russia in {year}: {usd(r.onward_usd)}, {vs}"
              f" (released {_day(released)})."),
             _num(r.onward_usd), usd(r.onward_usd), dataset=ct_ds, field=ct_field + "; onward_ratio",
             released=_iso(released))
        if base_o is not None:
            thr_o = max(asof.ONWARD_RATIO * base_o, asof.ONWARD_MIN_USD)
            fact("onward.threshold", "onward", "Annual onward threshold",
                 (f"The annual onward threshold for {code} from {_name(country)} is {usd(thr_o)}: the larger of "
                  f"{asof.ONWARD_RATIO:g}x the 2019-21 average and ${asof.ONWARD_MIN_USD:,}."),
                 _num(thr_o), usd(thr_o), dataset="backtest/asof.py", field="ONWARD_RATIO, ONWARD_MIN_USD")
    if has_month and mend is not None:
        m_rel = d.rel_m[(d.rel_m.reporter == rep) & (d.rel_m.period == int(r.monthly_end))].first_released
        if m_rel.empty:
            raise RuntimeError(f"{label}: no release date for the monthly onward figures to {_mon(mend)}")
        base_m = float(r.monthly_base_usd) if pd.notna(r.monthly_base_usd) else None
        vs = (f"{ratio(r.monthly_window_usd / base_m)} the 2019-21 level of {usd(base_m)} a year" if base_m
              else "with no 2019-21 exports to compare")
        fact("onward.monthly", "onward", f"Onward exports, 12 months to {_mon(mend)}",
             (f"{_poss(country, True)} reported exports of {code} to Russia over the 12 months to {_mon(mend)}: "
              f"{usd(r.monthly_window_usd)}, {vs} ({_mon(mend)} released {_day(m_rel.iloc[0])})."),
             _num(r.monthly_window_usd), usd(r.monthly_window_usd),
             dataset=d.ds["comtrade_monthly"], field="value_usd (12 released months); "
             f"release dates from {d.ds['monthly_release_dates']}",
             released=_iso(m_rel.iloc[0]))
    x = d.ct[(d.ct.reporter == rep) & (d.ct.partner == asof.RUSSIA) & (d.ct.flow == "X") & (d.ct.code == code)]
    by_year = x.groupby("year").value_usd.sum()
    years = sorted(set(d.ct[(d.ct.reporter == rep) & (d.ct.partner == asof.RUSSIA) & (d.ct.flow == "X")].year))
    for y in years:
        released = rel.get(y)
        if released is None or pd.isna(released) or pd.Timestamp(released) > p.end_time:
            continue  # not released by the run
        v = float(by_year.get(y, 0.0))
        fact(f"onward.year.{int(y)}", "onward_year", f"Onward exports, {int(y)}",
             f"{_poss(country, True)} reported exports of {code} to Russia in {int(y)}: {usd(v)} (released {_day(released)}).",
             _num(v), usd(v), dataset=ct_ds, field=ct_field + "; first_released from "
             f"{d.ds['release_dates']}", released=_iso(released))

    # Screened history: only runs whose own 12 months pass the display rule (and, on a case
    # route, start after the case's first public action)
    shown_runs = [q for q in t.index if bool(scr.loc[q, "shown"])]
    lead_runs = [q for q in shown_runs if bool(t.loc[q, "lead"])]
    if str(shown_runs[0]) != str(r.history_from)[:7] or len(lead_runs) != int(r.runs_shown_as_lead):
        raise RuntimeError(f"{label}: screened history differs from {live_name}; rerun the live run")
    n = len(shown_runs)
    hist = (f"{n} run{'s' if n != 1 else ''} drawn under the display rule, the first in {_mon(shown_runs[0])} and "
            f"the latest in {_mon(shown_runs[-1])}; a lead at {len(lead_runs) or 'none'} of them")
    hist += f", first in {_mon(lead_runs[0])}." if lead_runs else "."
    fact("history.summary", "history", "Screened history", hist, n, dataset="radar/display.py",
         field=f"screen_runs() over {d.ds['monthly']}")
    for q in shown_runs:
        v = t.loc[q]
        fact(f"history.{q}", "history", f"Run of {_mon(q)}",
             (f"Run of {_mon(q)} (UK figures to {_mon(q - asof.UK_LAG_MONTHS)}): UK exports over 12 months "
              f"{gbp(v.trailing12_published)}; UK signal {'on' if v.uk_signal else 'off'}; onward signal "
              f"{'on' if v.onward_signal else 'off'}; {'a lead' if v.lead else 'not a lead'}."),
             _num(v.trailing12_published), gbp(v.trailing12_published),
             dataset=d.ds["monthly"],
             field="value_gbp, 12-month sum as published at the run; shown by radar/display.py screen_runs()")

    # The corridor in the UK guidance
    iso2 = str(d.corridors.set_index("hmrc_country_id").iso2.get(cid, ""))
    if rf.uk_edd_named(iso2):
        corr = (f"{_name(country, True)} is among the countries the UK guidance for businesses names for enhanced due "
                f"diligence (list as updated {rf.UK_EDD_AS_OF}; the guidance says the list is not exhaustive).")
    else:
        corr = (f"{_name(country, True)} is not among the countries the UK guidance for businesses names for enhanced due "
                f"diligence (list as updated {rf.UK_EDD_AS_OF}); the guidance says the list is not exhaustive.")
    fact("corridor.uk_guidance", "corridor", "UK guidance country list", corr, rf.uk_edd_named(iso2),
         dataset="radar/brief/redflags.py", field="UK_EDD_COUNTRIES")

    # The rule
    mo = d.monthly_mod
    fact("rule.uk", "rule", "UK signal",
         (f"UK signal: UK exports over the 12 published months at least {asof.UK_RATIO:g}x the 2019-21 average "
          f"and at least £{asof.UK_MIN_EXCESS:,} above it, for {asof.RUN_MONTHS} months running."),
         None, dataset="backtest/asof.py", field="UK_RATIO, UK_MIN_EXCESS, RUN_MONTHS")
    fact("rule.onward", "rule", "Onward signal",
         (f"Onward signal: the corridor's reported exports of the code to Russia at least {asof.ONWARD_RATIO:g}x "
          f"the 2019-21 average and at least ${asof.ONWARD_MIN_USD:,}, on the latest annual figures released by "
          f"the run or, where monthly figures exist, on the latest 12 released months (the same {mo.MIN_RATIO:g}x "
          f"and ${mo.MIN_USD:,})."),
         None, dataset="backtest/asof.py; backtest/monthly.py",
         field="ONWARD_RATIO, ONWARD_MIN_USD; MIN_RATIO, MIN_USD")
    fact("rule.lead", "rule", "Lead and watch",
         "A lead has the UK and onward signals both on; a watch item has the UK signal on and the onward signal off.",
         None, dataset="scripts/run_live.py", field="status")

    # Linked cases, case level only
    cases: list[dict] = []
    if route:
        exact = d.routes.get((cid, code), (frozenset(), None))[0]
        head = d.routes.get((cid, "h" + code[:4]), (frozenset(), None))[0]
        for case_id in sorted(exact | head):
            c = d.cases.loc[case_id]
            if str(c.uk_involvement).strip().lower() != "none stated":
                raise RuntimeError(f"{case_id}: the register records UK involvement; decide before drafting")
            basis = ("published reports only; no official judgment seen"
                     if "secondary source" in str(c.verification_notes) else "official records")
            link = "route" if case_id in exact else "heading"
            fpa = d.demo.action_label(c.first_public_action)
            how = ("this corridor and code" if link == "route"
                   else f"this corridor and the four-digit heading {code[:4]} only")
            cases.append({
                "id": f"case.{case_id}", "case_id": case_id, "jurisdiction": str(c.jurisdiction),
                "outcome": str(c.outcome), "basis": basis, "first_public_action": fpa, "link": link,
                "text": (f"{case_id} ({c.jurisdiction}): {c.outcome}. Basis: {basis}. First public action: {fpa}. "
                         f"Linked by {how}."),
                "source": {"dataset": "backtest/data/cases.csv",
                           "field": "case_id, jurisdiction, outcome, verification_notes, first_public_action; "
                                    "linked by " + _and(d.route_files)},
                "confidence": "Certain" if basis == "official records" else "Likely"})
    if cases:
        ids = ", ".join(c["case_id"] for c in cases)
        summary = (f"Linked cases: {ids}. They are enforcement cases whose goods map to this corridor and this "
                   "code or its four-digit heading. The case register records no UK involvement in them: they "
                   "named no UK goods or UK party.")
    else:
        summary = "No enforcement case in the register links this corridor and code."
    fact("cases.summary", "cases", "Linked cases", summary, len(cases), dataset="backtest/data/cases.csv",
         field="case_id, uk_involvement; radar/display.py route_for()")

    limits = _limits(r, p, run_label, country, code, desc_l, year, has_year, rel, mend, route, cases, rep, d,
                     live_ds, data_to)
    ctx = {"schema": SCHEMA, "series": label, "slug": slug(label), "country": country, "code": code,
           "description": desc, "run": tag, "run_label": run_label, "status": str(r.status), "rule": str(r.rule),
           "house_line": HOUSE_LINE, "ogl_line": OGL_LINE, "sources_line": SOURCES_LINE,
           "facts": facts, "cases": cases, "limits": limits, "red_flags": rf.items()}
    check_context(ctx)
    return ctx


def _and(items) -> str:
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


#: The register's own wording for a conduct period whose end it does not give.
_NO_END = ("not stated", "no end date", "no dates given")
#: A period that ends on a date: "to May 2023", "through September 2024", "to on or about
#: 11 May 2023", or two whole years ("2022 and 2023"); not "to at least August 2024", and not a
#: list of events ("transshipments in May, June and July 2022").
_STATED_END = re.compile(r"(?:\bto|\bthrough)\s+(?!at least)(?:on or about |in or about )?"
                         r"(?:\d{1,2} )?(?:[A-Z][a-z]+ )?\d{4}\s*$|^\d{4} and \d{4}$")


def _end_stated(conduct_as_stated) -> bool:
    """Whether the register's conduct period states an end. A conduct_end the register worked
    out (the last message a source cites, the latest conduct it describes) is not one."""
    text = str(conduct_as_stated).strip()
    return not any(w in text.lower() for w in _NO_END) and bool(_STATED_END.search(text))


def _conduct_ended_by(case, month: pd.Period) -> bool:
    """Whether a case's stated end of conduct falls in or before a month. A year counts as its
    December; an end the register does not state never counts."""
    end = str(case.conduct_end).strip()
    if not re.fullmatch(r"\d{4}(-\d{2})?", end) or not _end_stated(case.conduct_as_stated):
        return False
    return pd.Period(end if len(end) == 7 else end + "-12", freq="M") <= month


def _limits(r, p, run_label, country, code, desc_l, year, has_year, rel, mend, route, cases, rep, d,
            live_ds, data_to) -> list[dict]:
    out: list[dict] = []

    def limit(id_, label_, text, dataset, field, confidence="Certain"):
        out.append({"id": id_, "label": label_, "text": text, "source": {"dataset": dataset, "field": field},
                    "confidence": confidence})

    limit("limit.lead_not_finding", "A lead, not a finding",
          f"The radar flags rises in published trade figures for a person to check. {HOUSE_LINE}",
          "CLAUDE.md", "house line")
    limit("limit.corridor_totals", "Onward figures are corridor totals",
          (f"Onward figures are {_poss(country)} reported exports of the code to Russia from every origin, not UK "
           "goods; they cannot show where the goods came from."),
          d.ds["comtrade_annual"], "reporter, partner 643, flow X (all origins)")
    if rep in REEXPORTERS:
        limit("limit.reexports", "Re-exports in the onward figures",
              (f"{_poss(country, True)} reported exports include re-exports, so its onward figures also count goods "
               "that only passed through it."),
              "data/SOURCES.md", "run 3 corridors: re-exports", confidence="Likely")
    if has_year:
        ended = (p.year - year) * 12 + p.month - 12
        text = (f"The annual onward figures are for {year}, released on {_day(rel.get(year))}; that year "
                f"ended {ended} months before the {run_label} run.")
        if mend is not None:
            text += f" The monthly figures run to {_mon(mend)}."
        limit("limit.onward_age", "Age of the onward figures", text,
              d.ds["release_dates"], "first_released")
    if rep not in d.rb2.MONTHLY_REPORTERS:
        limit("limit.no_monthly", "No monthly onward figures",
              f"The radar holds no monthly onward figures for {_name(country)}, so only the annual onward check runs.",
              *d.monthly_source)
    limit("limit.single_month", "One month can carry the total",
          (f"One large month can carry a 12-month total: the display rule needs exports in at least "
           f"{display.MIN_DISPLAY_MONTHS} of the 12 months, but one large consignment with smaller sales in five "
           "other months still passes."),
          "radar/display.py", "module notes on MIN_DISPLAY_MONTHS")
    limit("limit.code_breadth", "A broad goods code",
          (f"HS {code} covers a broad group of goods ({desc_l}); the figures cannot say which goods within it "
           "rose, or who traded them."),
          "config/codes.csv", "code, description")
    limit("limit.revisions", "Revisions",
          ("HMRC and UN Comtrade revise published figures; these are the figures held at this run, and later "
           "releases may change them."),
          f"data/SOURCES.md; {d.ds['monthly_release_dates']}", "first_released, last_released",
          confidence="Likely")
    limit("limit.one_run", "One run",
          f"This brief is for the {run_label} run only; a series can leave the list at a later run.",
          live_ds, "status")
    if r.status == "watch":
        limit("limit.watch", "A watch item",
              "This is a watch item: the UK signal is on, but the onward check has not passed.",
              live_ds, "status, onward_signal")
    if r.status == "lead":
        # The largest onward figure that passed, in US dollars, against the UK flow in pounds. The
        # comparison holds at any exchange rate above onward / UK dollars to the pound, which the
        # text gives rounded up; the periods differ, so the reading is Likely.
        passed = [(float(v), w) for ok, v, w in (
            (r.onward_annual, r.onward_usd, f"{year}"),
            (r.onward_monthly, r.monthly_window_usd, f"the 12 months to {_mon(mend)}" if mend is not None else ""))
            if ok and pd.notna(v)]
        if passed:
            top, when = max(passed)
            if top < float(r.uk_trailing12_gbp):
                usd, gbp = d.live_mod.usd_k, d.live_mod.gbp_k
                rate = math.ceil(top / float(r.uk_trailing12_gbp) * 100) / 100
                limit("limit.small_onward", "Onward flow smaller than the UK flow",
                      (f"{_poss(country, True)} reported exports of {code} to Russia ({usd(top)} in {when}) are smaller "
                       f"than UK exports of it to {_name(country)} ({gbp(r.uk_trailing12_gbp)} in the 12 months to "
                       f"{data_to}), at any exchange rate above ${rate:.2f} to the pound: even if every onward shipment "
                       "were UK goods, they would match only part of the UK flow, so the UK rise can sit beside the "
                       "onward rise with no link between them. The periods differ, so this compares scale only."),
                      f"{live_ds}; {d.ds['comtrade_annual']}; {d.ds['comtrade_monthly']}",
                      "uk_trailing12_gbp; onward_usd, monthly_window_usd where the check passed",
                      confidence="Likely")
    if route:
        # The window starts after the cases' first public actions. Where the register states no
        # end date for a linked case's conduct, it cannot confirm the window clears that case's
        # period, so the limit is Likely, not Certain.
        open_end = [c["case_id"] for c in cases if not _conduct_ended_by(d.cases.loc[c["case_id"]], route[1])]
        text = (f"On this route, runs are drawn only when their 12 months start after the latest first public "
                f"action of a linked case ({_mon(route[1])})")
        if open_end:
            text += (f". The case register states no end date for the conduct in {_and(open_end)}, so it cannot "
                     f"confirm that these runs start after the period {'that case covers' if len(open_end) == 1 else 'those cases cover'}"
                     "; they most likely do.")
        else:
            text += ", after every linked case's stated end of conduct, so no UK figure here covers the period of a case."
        limit("limit.case_window", "Runs drawn after the cases", text,
              "radar/display.py; backtest/data/cases.csv",
              "screen_runs(), CASE_WINDOW_REASON; conduct_end, conduct_as_stated",
              confidence="Likely" if open_end else "Certain")
        heading = [c["case_id"] for c in cases if c["link"] == "heading"]
        if heading:
            limit("limit.case_heading", "Linked by heading only",
                  (f"{', '.join(heading)} link{'s' if len(heading) == 1 else ''} this corridor at the four-digit "
                   f"heading {code[:4]} only, not at code {code}: a case's goods are mapped to codes, so a "
                   "sibling code may cover them."),
                  "radar/display.py", "route_for()")
    return out


def _walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


def check_context(ctx: dict) -> None:
    """Stop a context that breaks the rules: not matching spec/context.schema.json, a URL,
    per-person detail, a register column that is never copied, or wording the brief screen
    blocks outside the official text it carries (case outcomes, guidance titles)."""
    from radar.brief import screen
    import jsonschema
    schema = json.loads((SPEC / "context.schema.json").read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(ctx), key=lambda e: list(e.path))
    if errors:
        raise RuntimeError(f"context does not match context.schema.json: {errors[0].message}")
    bad = sorted(set(_keys(ctx)) & set(NEVER_COPIED))
    if bad:
        raise RuntimeError(f"context carries register columns that are never copied: {', '.join(bad)}")
    problems = []
    for path, s in _walk(ctx):
        if URL.search(s):
            problems.append(f"{path}: a URL")
        if PER_PERSON.search(s):
            problems.append(f"{path}: per-person detail")
        if not any(rx.match(path) for rx in OFFICIAL_TEXT):
            problems += [f"{path}: {pr['code']}" for pr in screen.text_problems(s, path)]
    if problems:
        raise RuntimeError("context fails its own checks: " + "; ".join(problems[:5]))
