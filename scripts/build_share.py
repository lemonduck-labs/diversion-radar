"""Write the shared copies of the radar's research files (share/) and check them.

The repository holds the full record, which names the series the display rule holds back and
links the case register to its sources. What goes to a reviewer outside the repo is a copy:

- share/RESEARCH_LOG.md: backtest/RESEARCH_LOG.md with the edits in config/share_log_edits.json
  applied. A series the display rule holds back is counted, never named, and no UK figure is
  given for a run that fails the rule; the backtest's tests that fail the rule have no route or
  result. Each edit must match exactly once, so a change to the log stops this build until the
  edits are brought up to date.
- share/cases.csv: backtest/data/cases.csv with the official references only, so no source
  URLs. Every case in the register ended in a settlement, a penalty, a plea or a conviction;
  the build stops if one does not, since such a case is counted, never referenced.
- share/README.md: what the folder holds and how it was made.

Checks, run on every build and by tests/test_share.py:
- no series held back at any live run (data/processed/live_*.csv), and no route of a test
  that the workspace does not show (app/data/tests.json, routes from the test plan), is
  named: next to each other, or anywhere in the same sentence, table row or list item;
- no hidden test is given by its id, and no list of lead times holds one that only a hidden
  test has, so no result can be had by subtraction;
- no series is named with the month of a first lead whose run fails the display rule (the
  backtest's series and placebo tables, screened as radar/display.py screens every run);
- no UK pound figure sits in the same sentence as a tested case's route or test id;
- no URL but a data publisher's or the licence's; in the log, no pound figure under the
  display rule's £250,000 other than the rule's own £20,000 margin; the licence line links to
  the licence; and the fd-core screen passes with the private deny list.

Usage:  python scripts/build_share.py [--check]

A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SHARE = ROOT / "share"
LOG = ROOT / "backtest" / "RESEARCH_LOG.md"
CASES = ROOT / "backtest" / "data" / "cases.csv"
EDITS = ROOT / "config" / "share_log_edits.json"
DENY = ROOT / "config" / "deny_list.txt"
DROPPED_COLUMNS = ["source_url", "other_sources"]
#: A case with a backtest test the display rule holds back keeps its record, but not the
#: corridors it documents or how it maps to the radar's routes: with those and the test shown on
#: the same case, the held-back routes could be worked out (review of the public copy, 24 Oct 2026).
ROUTE_COLUMNS = ["transit_or_corridor_countries", "radar_corridor_match", "testable_now"]
ROUTE_HELD = "not shown (display rule)"
REFERENCED_OUTCOMES = re.compile(r"settle|penalt|plea|convict|sentenc", re.I)
RULE_FLOOR_GBP = 250_000
RULE_MARGIN_GBP = 20_000

README = """# Shared copies

Written by `scripts/build_share.py`; do not edit by hand. These are the radar's research files as
they may leave the repository: the repository itself stays private.

- `RESEARCH_LOG.md`: every backtest of the radar, in the order it was run, including the ones
  superseded. A series the display rule holds back at a live run, because its UK exports in the
  12-month window are under £250,000 or were recorded in fewer than 6 of the 12 months, is
  counted and never named; no UK figure is given for a run that fails the rule, and no series is
  named as a lead at such a run. Two of the backtest's eight tests are not shown under the rule,
  so their routes and results are left out, and the counts of tests cover the six shown.
- `cases.csv`: the {n} cases in the register, with the goods, routes, periods and outcomes as
  their sources give them. {official} were checked against an official record ({official_ids}); the
  other {secondary} ({secondary_ids}) rest on secondary sources, as each row's verification notes
  say, and {unverified} UK rows are marked [Unverified]. Each case is cited by its official reference; for
  {nonum} of the {n} no case or notice number was found, so the reference gives the court or
  body, the date and the announcement. Source links are left out, as anything outside the
  repository cites the official reference only. Every case reached a settlement, a penalty, a
  plea or a conviction, in some at first instance: appeals or sentencing are still pending in
  some, as the outcome and status columns say. A case that a held-back test is on keeps its
  record but not the corridors it documents or how it maps to the radar's routes ("not shown").

None of the four cases the backtest tests names UK goods or a UK party, and a hit never means a
UK exporter was involved. The {uk} UK cases in the register are HMRC compound settlements with
UK firms, published without the goods codes and routes a test needs, so none of them is
tested. A rise in exports is a lead, not evidence of a breach.

Contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
"""


class ShareError(SystemExit):
    pass


def shared_log(text: str, edits: list[dict]) -> str:
    for e in edits:
        n = text.count(e["old"])
        if n != 1:
            raise ShareError(f"config/share_log_edits.json: an edit ({e['why']}) matches {n} times; the log has changed, so bring the edit up to date")
        text = text.replace(e["old"], e["new"])
    return text


def cases_with_hidden_tests(root: Path = ROOT) -> set[str]:
    """The cases that a backtest test the workspace does not show is on (from the test plan)."""
    tests = json.loads((root / "app" / "data" / "tests.json").read_text(encoding="utf-8"))
    plan = pd.read_csv(root / "backtest" / "data" / "test_plan.csv", dtype={"codes": str}).set_index("test_id")
    return {str(plan.loc[t["test_id"]].case_id) for t in tests if not t.get("shown")}


def shared_cases(path: Path = CASES, root: Path = ROOT) -> tuple[str, int]:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    bad = [r.case_id for r in df.itertuples() if not REFERENCED_OUTCOMES.search(f"{r.enforcement_stage} {r.outcome} {r.status}")]
    if bad:
        raise ShareError(f"cases not ending in a settlement, penalty, plea or conviction are counted, never referenced: {', '.join(bad)}")
    out = df.drop(columns=[c for c in DROPPED_COLUMNS if c in df.columns])
    held = out.case_id.isin(cases_with_hidden_tests(root))
    for c in ROUTE_COLUMNS:
        if c in out.columns:
            out.loc[held, c] = ROUTE_HELD
    buf = io.StringIO()
    out.to_csv(buf, index=False, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    return buf.getvalue(), len(out)


def held_back_series(root: Path = ROOT) -> set[tuple[str, str]]:
    """(country, code) for every series flagged and held back at any live run."""
    out: set[tuple[str, str]] = set()
    for f in sorted((root / "data" / "processed").glob("live_*.csv")):
        d = pd.read_csv(f, dtype={"code": str})
        if not {"status", "display", "country", "code"} <= set(d.columns):
            continue
        for r in d[d.status.isin(["lead", "watch"]) & ~d.display.astype(bool)].itertuples():
            out.add((r.country, r.code))
    return out


def hidden_tests(root: Path = ROOT) -> list[dict]:
    """The backtest tests the workspace does not show (app/data/tests.json), with their routes
    from the test plan: the shared data give a hidden test no route."""
    tests = json.loads((root / "app" / "data" / "tests.json").read_text(encoding="utf-8"))
    plan = pd.read_csv(root / "backtest" / "data" / "test_plan.csv", dtype={"codes": str}).set_index("test_id")
    out = []
    for t in tests:
        if t.get("shown"):
            continue
        if t.get("corridor"):
            raise ShareError(f"app/data/tests.json gives hidden test {t['test_id']} a route; rebuild the demo data")
        p_ = plan.loc[t["test_id"]]
        out.append({**t, "corridor": p_.country, "codes": ", ".join(p_.codes.split(";"))})
    return out


def test_routes(root: Path = ROOT) -> dict[tuple[str, str], tuple[list[str], str]]:
    """(country, code) -> the ids of the tests on that route and the earliest first public
    action among them (YYYY-MM), from the test plan."""
    plan = pd.read_csv(root / "backtest" / "data" / "test_plan.csv", dtype={"codes": str})
    out: dict[tuple[str, str], tuple[list[str], str]] = {}
    for r in plan.itertuples():
        for c in r.codes.split(";"):
            ids, ref = out.get((r.country, c), ([], "9999-12"))
            out[(r.country, c)] = (ids + [r.test_id], min(ref, str(r.reference_date)[:7]))
    return out


def _module(root: Path, name: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, root / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def small_first_leads(root: Path = ROOT) -> set[tuple[str, str, str]]:
    """(country, code, YYYY-MM) for each first lead in the backtest's series and placebo tables
    whose run fails the display rule. Naming the series with that month says that a small UK
    flow led, which the display rule forbids at every run (N5)."""
    sys.path.insert(0, str(root))
    from backtest import asof
    from radar import display
    _, monthly, *_ = _module(root, "run_backtest2").load_part_a()
    bt = root / "backtest" / "data"
    found = set()
    r1 = pd.read_csv(bt / "run1_series.csv", dtype={"code": str})
    found |= {(r.country, int(r.hmrc_country_id), r.code, r.first_lead) for r in r1.itertuples() if isinstance(r.first_lead, str)}
    for name, cols in (("run2_series.csv", ("first_lead_run1", "first_lead_run2")), ("run2_placebo.csv", ("peace_first_lead", "war_first_lead"))):
        d = pd.read_csv(bt / name, dtype={"code": str})
        for col in cols:
            found |= {(r.country, int(r.hmrc_country_id), r.code, getattr(r, col)) for r in d.itertuples() if isinstance(getattr(r, col), str)}
    out = set()
    for country, cid, code, month in found:
        scr = display.screen_runs(monthly, cid, code, [pd.Period(month[:7], freq="M")], asof.UK_LAG_MONTHS)
        if not bool(scr.shown.iloc[0]):
            out.add((country, code, month[:7]))
    return out


def hidden_only_lead_times(root: Path = ROOT, hidden: list[dict] | None = None) -> set[int]:
    """Lead times (months) that a hidden test has, under any run or rule, and no shown test has.
    A list of lead times holding one of them gives a hidden result away by subtraction. Run 1 as
    first reported counted a month more (B1.1), so each value and the one above it count."""
    bt = root / "backtest" / "data"
    hidden_ids = {t["test_id"] for t in (hidden if hidden is not None else hidden_tests(root))}
    vals: dict[bool, set[int]] = {True: set(), False: set()}
    for name, cols in (("run1_results.csv", ("lead_time_months",)), ("run2_results.csv", ("lead_time_months", "lead_time_months_run1"))):
        d = pd.read_csv(bt / name)
        for r in d.itertuples():
            for col in cols:
                v = getattr(r, col)
                if pd.notna(v):
                    vals[r.test_id in hidden_ids] |= {int(v), int(v) + 1}
    return vals[True] - vals[False]


def units(text: str) -> list[tuple[int, str]]:
    """(first line, text) for each sentence, table row, heading or list item, with the line
    breaks inside it joined, so a name and a code split across lines are still seen together."""
    out: list[tuple[int, str]] = []
    buf: list[str] = []
    start = 0

    def flush():
        if buf:
            joined = " ".join(x.strip() for x in buf)
            out.extend((start, u) for u in re.split(r"(?<=[.!?])\s+(?=[A-Z(\[*`\"])", joined))
            buf.clear()
    for i, line in enumerate(text.splitlines(), 1):
        st = line.strip()
        if not st or st.startswith("|") or st.startswith("#"):
            flush()
            if st:
                out.append((i, st))
            continue
        if re.match(r"(?:[-*+]|\d+\.)\s", st):
            flush()
        if not buf:
            start = i
        buf.append(line)
    flush()
    return out


MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December"]


def _month_forms(ym: str) -> list[str]:
    y, m = ym.split("-")
    name = MONTH_NAMES[int(m) - 1]
    return [f"{name} {y}", f"{name[:3]} {y}", ym]


MONTH_YEAR = re.compile(r"\b(" + "|".join(m[:3] for m in MONTH_NAMES) + r")[a-z]* (\d{4})\b|\b(\d{4})-(\d{2})\b")


def months_named(unit: str) -> list[str]:
    out = []
    for m in MONTH_YEAR.finditer(unit):
        if m.group(1):
            out.append(f"{m.group(2)}-{[x[:3] for x in MONTH_NAMES].index(m.group(1)) + 1:02d}")
        elif 1 <= int(m.group(4)) <= 12:
            out.append(f"{m.group(3)}-{m.group(4)}")
    return out


def _has(unit: str, words: list[str], digits: bool = False) -> bool:
    for w in words:
        pat = (r"(?<![0-9.])" + re.escape(w) + r"(?![0-9])") if digits else (r"(?<![A-Za-z0-9])" + re.escape(w) + r"(?![A-Za-z0-9])")
        if re.search(pat, unit):
            return True
    return False


def _names(country: str) -> list[str]:
    extra = {"Kyrgyz Republic": ["Kyrgyz"], "United Arab Emirates": ["UAE"]}
    return [country] + extra.get(country, [])


def _codes(code: str) -> list[str]:
    return [code, f"{code[:4]}.{code[4:]}"] if len(code) == 6 else [code]


def series_patterns(series) -> list[tuple[str, re.Pattern]]:
    """A series named either way round: the country then the code ("Exampleland 1234",
    "Exampleland, 1234.56") or the code then the country ("1234.56 to Exampleland")."""
    pats = []
    for country, code in sorted(series):
        for n in _names(country):
            for c in _codes(code):
                pats.append((f"{country} {code}", re.compile(re.escape(n) + r"[ ,:(]{1,3}(?:in |for )?" + re.escape(c) + r"(?![0-9])")))
                pats.append((f"{country} {code}", re.compile(r"(?<![0-9.])" + re.escape(c) + r"\)?[ ,]{1,3}(?:to |for |in |through |from )?(?:the )?" + re.escape(n) + r"\b")))
    return pats


MONEY = re.compile(r"(?:GBP|£) ?([0-9][0-9,]*(?:\.[0-9]+)?)(k|m|bn)?\b")
URL = re.compile(r"https?://([^/\s`)>]+)|\bwww\.([^/\s`)>]+)")
# Data publishers' and the licence's addresses may be cited; a case source never is.
URL_HOSTS = {"api.uktradeinfo.com", "www.uktradeinfo.com", "uktradeinfo.com", "comtradeapi.un.org", "comtradeplus.un.org",
             "comtrade.un.org", "unstats.un.org", "www.nationalarchives.gov.uk"}


def problems(files: dict[str, str], root: Path = ROOT) -> list[str]:
    from fnmatch import fnmatch

    from fdcore.guardrails import read_policy, scan_text

    policy = read_policy(str(root / "config" / "guardrails_policy.txt"))

    held = held_back_series(root)
    hidden = hidden_tests(root)
    secret = held | {(t["corridor"], c.strip()) for t in hidden for c in t["codes"].split(",")}
    pats = series_patterns(secret)
    ids = re.compile(r"\b(?:" + "|".join(re.escape(t["test_id"]) for t in hidden) + r")\b") if hidden else None
    deny = DENY.read_text(encoding="utf-8").splitlines() if DENY.exists() else []
    routes = test_routes(root)
    small = small_first_leads(root)
    hidden_times = hidden_only_lead_times(root, hidden)
    out = []
    for name, text in files.items():
        # Sentence-level checks on the prose; the case register's rows give each case's own
        # documented routes and dates, which say nothing about UK flows, and keep the per-line
        # checks below.
        for i, u in (units(text) if name.endswith(".md") else []):
            for country, code in sorted(secret):
                if _has(u, _names(country)) and _has(u, _codes(code), digits=True):
                    out.append(f"{name}:{i}: names a series or test route the display rule holds back, in one sentence ({country} {code})")
            for country, code, ym in sorted(small):
                tids = routes.get((country, code), ([], ""))[0]
                if (_has(u, _names(country)) and _has(u, _codes(code), digits=True) or _has(u, tids)) and any(f in u for f in _month_forms(ym)):
                    out.append(f"{name}:{i}: names {country} {code} as a lead in {ym}, a run the display rule holds back")
            # A count of leads split by onward check, beside the counts shown, tells a reader that a
            # held-back lead passes only the monthly check (guardrails review of 22 Oct 2026).
            if re.search(r"\d+\s+leads?\s*\(\s*\d+\s+under run 1's rule", u):
                out.append(f"{name}:{i}: splits a run's leads by onward check (a count under run 1's rule)")
            # B0's fourth corridor is held back as a backtest test; called a series the display rule
            # holds back, it reads as a live lead held back (verification of 22 Oct 2026).
            if re.search(r"one series the\s+display rule holds back|held-back series' result", u):
                out.append(f"{name}:{i}: calls a backtest route a series the display rule holds back")
            if re.search(r"lead times?", u, re.I):
                for m in re.finditer(r"((?:\d+(?:,\s*|\s+and\s+|,\s+and\s+))*\d+)\s+months?", u):
                    bad = sorted({int(x) for x in re.findall(r"\d+", m.group(1))} & hidden_times)
                    if bad:
                        out.append(f"{name}:{i}: a list of lead times holds {bad}, which only a hidden test has")
            # A UK figure beside a tested case's route and a month up to the case's first public
            # action may cover the case's period (N5): none is given.
            if MONEY.search(u):
                named = months_named(u)
                for (country, code), (tids, ref) in routes.items():
                    if ((_has(u, _names(country)) and _has(u, _codes(code), digits=True)) or _has(u, tids)) and any(m_ <= ref for m_ in named):
                        out.append(f"{name}:{i}: a UK pound figure beside a tested case's route and a month before its first public action ({country} {code})")
                        break
            if "Open Government Licence" in u and "nationalarchives.gov.uk" not in u:
                out.append(f"{name}:{i}: the licence line has no link to the licence")
        for i, line in enumerate(text.splitlines(), 1):
            for what, p in pats:
                if p.search(line):
                    out.append(f"{name}:{i}: names a series or test route the display rule holds back ({what})")
            if ids and ids.search(line):
                out.append(f"{name}:{i}: gives a held-back test by its id")
            for m in URL.finditer(line):
                host = m.group(1) or ("www." + m.group(2))
                if host not in URL_HOSTS:
                    out.append(f"{name}:{i}: a URL ({host})")
            if name.endswith(".md"):
                for m in MONEY.finditer(line):
                    v = float(m.group(1).replace(",", "")) * {"k": 1e3, "m": 1e6, "bn": 1e9, None: 1}[m.group(2)]
                    if v < RULE_FLOOR_GBP and v != RULE_MARGIN_GBP:
                        out.append(f"{name}:{i}: a UK figure under the display rule ({m.group(0)})")
        # The repository's own policy applies: the register's copy gives each case's official
        # outcome in its own words, as backtest/data/cases.csv does.
        skip = set().union(*[c for g, c in policy if fnmatch(f"share/{name}", g)]) if policy else set()
        for f in scan_text(text, name, deny, skip):
            out.append(f"{name}: fd-core screen: {f.kind}")
    return out


_WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
          11: "Eleven", 12: "Twelve"}


def _count_word(n: int) -> str:
    """A count that may open a sentence, in words up to twelve."""
    return _WORDS.get(n, str(n))


def id_ranges(ids) -> str:
    """Case ids as runs, prefix by prefix: UK-07 and US-01 to US-09."""
    by: dict[str, list[int]] = {}
    for cid in ids:
        pre, num = cid.rsplit("-", 1)
        by.setdefault(pre, []).append(int(num))
    parts = []
    for pre, nums in by.items():
        nums.sort()
        start = prev = nums[0]
        for x in nums[1:] + [None]:
            if x is not None and x == prev + 1:
                prev = x
                continue
            parts.append(f"{pre}-{start:02d}" if start == prev else f"{pre}-{start:02d} to {pre}-{prev:02d}")
            if x is not None:
                start = prev = x
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def build(root: Path = ROOT) -> dict[str, str]:
    edits = json.loads((root / "config" / "share_log_edits.json").read_text(encoding="utf-8"))["edits"]
    log = shared_log((root / "backtest" / "RESEARCH_LOG.md").read_text(encoding="utf-8"), edits)
    cases, n = shared_cases(root / "backtest" / "data" / "cases.csv", root)
    reg = pd.read_csv(root / "backtest" / "data" / "cases.csv", dtype=str, keep_default_na=False)
    nonum = int(reg.official_reference.str.contains(r"not found|not stated|not captured|no [A-Za-z ]*number found", regex=True).sum())
    uk = int(reg.case_id.str.startswith("UK-").sum())
    # A row rests on an official record when its verification notes open with the record that was
    # fetched (a release, a press release, a sentencing release or a gov.uk notice); every other row
    # rests on secondary sources, as its notes say.
    official = reg.verification_notes.str.match(r"(both releases|release|press release|sentencing release|gov\.uk notice) fetched")
    unverified = int(reg.verification_notes.str.startswith("[Unverified]").sum())
    files = {"RESEARCH_LOG.md": log, "cases.csv": cases,
             "README.md": README.format(n=n, nonum=nonum, uk=uk, official=_count_word(int(official.sum())),
                                        official_ids=id_ranges(reg.case_id[official]),
                                        secondary=int((~official).sum()), secondary_ids=id_ranges(reg.case_id[~official]),
                                        unverified=_count_word(unverified).lower())}
    bad = problems(files, root)
    if bad:
        raise ShareError("the shared copies would leak:\n  " + "\n  ".join(bad))
    return files


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if share/ is out of date")
    args = ap.parse_args()
    files = build()
    stale = [n for n, t in files.items() if not (SHARE / n).exists() or (SHARE / n).read_text(encoding="utf-8") != t]
    extra = sorted(p.name for p in SHARE.glob("*") if p.is_file() and p.name not in files) if SHARE.exists() else []
    if args.check:
        if stale or extra:
            print("share/ is out of date: " + ", ".join(stale + extra))
            sys.exit(1)
        print("share/ is up to date")
        return
    SHARE.mkdir(exist_ok=True)
    for n, t in files.items():
        (SHARE / n).write_text(t, encoding="utf-8")
    for n in extra:
        print(f"share/{n} is not written by this script; remove it or add it here")
    print(f"wrote share/: {', '.join(files)}")


if __name__ == "__main__":
    main()
