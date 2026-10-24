"""Data files for the radar workspace (app/), the phase 2 tool.

The workspace is one HTML page with its data published beside it. This script writes
everything the page loads into app/data/ and app/spec/, from files already built and
reviewed for the demo, so nothing new leaves the repo by a side route:

- summary, leads, history, onward_years, tests, cases, placebo, cost: copied unchanged
  from demo/radar/ (scripts/build_demo_data.py, display rule applied at every run).
- signals.json: one row per corridor and code for the exporter screen. Where the series
  passes the display rule at this run (radar/display.py), the row gives the UK status and the
  onward side (each corridor's own exports to Russia, from UN Comtrade: national totals as
  each corridor reports them, not UK figures [Certain]); UK figures only where the series is
  flagged and shown, as on the dashboard. Where it does not, the row says "not shown (display
  rule)" for both sides and carries nothing else, so a held-back lead looks the same as every
  other series not shown: the onward check alone, beside the display rule's counts, singled
  one out (N7 in backtest/RESEARCH_LOG.md).
- codes.json and corridors.json: the radar's nine codes (with their CN8 ranges) and the
  run's corridors, 18 in run 3 (with the spellings an exporter's file may use).
- synthetic_shipments.csv: a made-up exporter's shipments for trying the exporter screen.
  Every reference starts SYN-; the file is seeded and rebuilt the same way each time. It
  describes no real exporter or customer [Certain].
- briefs/<series>.json and spec/*: the brief engine's per-lead contexts and its language-
  neutral spec (prompt, schema, screen rules, red flags), copied when present.
- triage/reports.json, list.json and spec.json: the triage view's synthetic reports
  with what each was read against, a synthetic list in the UK Sanctions List's format, and the
  view's rules (scripts/build_triage.py writes them to demo/radar/triage).
- monitor.json: the monitoring items filed from monitor/items.jsonl (phase 7), newest first.
- spec/land.json: land and country outlines for the overview's globe, from radar/geo/land.json
  (Natural Earth 1:110m, public domain, thinned to about half a degree).
- spec/memory_rules.json: fd-core's memory rules (fdcore.memory.rules_json), which the page's
  copy of the memory core (fd-core's memory.mjs, inlined by scripts/build_app_page.py) runs:
  the admission check on a lesson when it is proposed and the instruction screen on every
  recall. The manifest gives fd-core's commit.
- manifest.json: the run, the source commit and a SHA-256 for every file, so a page can
  show where its data came from.

The run's variant (run 3, 18 corridors, or run 2, nine) is the one demo/radar was built from
(the "variant" in demo/radar/summary.json), so the exporter screen and the copied files
always show the same run.

Usage:  python scripts/build_app_data.py [--run 2026-10]

A rise in exports is a lead, not evidence of a breach.
Contains public sector information licensed under the Open Government Licence v3.0.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from backtest import asof  # noqa: E402
from radar import display, onward as onward_rule  # noqa: E402
import build_demo_data  # noqa: E402

DEMO = ROOT / "demo" / "radar"
APP = ROOT / "app"
OUT = APP / "data"
SPEC_SRC = ROOT / "radar" / "brief" / "spec"
# Land and country outlines for the overview's globe (Natural Earth, public domain), thinned.
LAND_SRC = ROOT / "radar" / "geo" / "land.json"
# Monitoring items filed by scripts/monitor_ingest.py (phase 7), newest first in the app.
MONITOR_SRC = ROOT / "monitor" / "items.jsonl"
BRIEFS_SRC = ROOT / "demo" / "radar" / "briefs"
DECL_SRC = ROOT / "demo" / "radar" / "declarations"
DECL_FILES = ["cases", "evaluation", "signals_spec", "graph"]
TRIAGE_SRC = ROOT / "demo" / "radar" / "triage"
TRIAGE_FILES = ["reports", "list", "spec"]
COPIED = ["summary", "leads", "history", "onward_years", "tests", "cases", "placebo", "cost"]
NOT_SHOWN = "not shown (display rule)"

# Spellings an exporter's own file may use for each corridor, besides the name in the run's
# countries file (config/countries.csv, or config/countries_run3.csv for run 3) and its ISO
# code. Matched case-insensitively after trimming, whole field only, so "Hong Kong, China"
# is Hong Kong, not China. "Republic of China" is Taiwan's name and is not on any list.
ALIASES = {
    "KG": ["Kyrgyzstan", "Kyrgyz Republic", "Kirghizia"],
    "AM": ["Armenia"],
    "KZ": ["Kazakhstan", "Kazakstan"],
    "GE": ["Georgia"],
    "AE": ["United Arab Emirates", "UAE", "U.A.E.", "Emirates", "Dubai", "Abu Dhabi", "Sharjah"],
    "TR": ["Turkey", "Türkiye", "Turkiye"],
    "UZ": ["Uzbekistan"],
    "AZ": ["Azerbaijan"],
    "TJ": ["Tajikistan"],
    # Run 3's corridors
    "CN": ["China", "PRC", "P.R.C.", "P.R. China", "People's Republic of China", "Peoples Republic of China",
           "China, People's Republic of", "Mainland China"],
    "HK": ["Hong Kong", "Hong Kong SAR", "Hong Kong SAR, China", "Hong Kong, China", "China, Hong Kong SAR",
           "HKSAR", "Hongkong"],
    "MO": ["Macao", "Macau", "Macao SAR", "Macau SAR", "Macao SAR, China", "China, Macao SAR"],
    "IN": ["India"],
    "IL": ["Israel"],
    "MY": ["Malaysia"],
    "RS": ["Serbia", "Republic of Serbia"],
    "TH": ["Thailand"],
    "VN": ["Vietnam", "Viet Nam", "Socialist Republic of Viet Nam"],
}
# Destinations the screen stops on instead of screening (direct exports).
STOP = {"RU": ["Russia", "Russian Federation"], "BY": ["Belarus"]}


def _r(x, nd=0):
    """Rounded halves up; None for missing values."""
    if x is None or pd.isna(x):
        return None
    d = Decimal(str(float(x))).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP)
    return float(d) if nd else int(d)


def _yyyymm(v) -> str | None:
    if v is None or pd.isna(v):
        return None
    v = int(v)
    return f"{v // 100:04d}-{v % 100:02d}"


def why_not(usd, base, passes: bool) -> str | None:
    """Why an onward check did not pass, in the rule's own terms (radar/onward.py, shared with
    the brief contexts and the dashboard's leads). Checked against the live run's own verdict."""
    if passes:
        return None
    return onward_rule.why_not_text(usd, base)


def check_passes(usd, base) -> bool:
    usd = 0.0 if usd is None or pd.isna(usd) else float(usd)
    base = 0.0 if base is None or pd.isna(base) else float(base)
    return bool(usd >= asof.ONWARD_MIN_USD and (usd >= asof.ONWARD_RATIO * base if base > 0 else True))


def current_variant() -> str:
    """The variant demo/radar was built from (scripts/build_demo_data.py)."""
    return json.loads((DEMO / "summary.json").read_text())[0].get("variant", "run2")


def live_path(run: str, variant: str) -> Path:
    return ROOT / "data" / "processed" / f"live_{run}{build_demo_data.variant(variant).suffix}.csv"


def countries_path(variant: str) -> Path:
    return Path(build_demo_data.variant(variant).inputs["countries"])


def signals(run: str, variant: str | None = None) -> list[dict]:
    variant = variant or current_variant()
    live = pd.read_csv(live_path(run, variant), dtype={"code": str})
    countries = pd.read_csv(countries_path(variant))
    iso = dict(zip(countries.name, countries.iso2))
    # The engine gives no annual figure when the latest year holds no exports of the codes to
    # Russia, or when no 2019-21 year does (asof.onward_signal); radar/onward.py calls a missing
    # figure "no exports reported", which is only right in the first case. Stop on the second.
    ct = pd.read_csv(build_demo_data.variant(variant).inputs["comtrade_annual"], dtype={"code": str})
    ct = ct[(ct.partner == asof.RUSSIA) & (ct.flow == "X")]
    held_years = ct.groupby("reporter").year.agg(lambda y: set(int(v) for v in y)).to_dict()
    rows = []
    for r in live.itertuples():
        if pd.notna(r.onward_year) and pd.isna(r.onward_usd) and int(r.onward_year) in held_years.get(int(r.comtrade_code), set()):
            raise SystemExit(f"{r.country} {r.code}: exports held for {int(r.onward_year)} but no annual figure "
                             "(no 2019-21 baseline year); 'no exports reported' would be wrong")
        ok, why = display.displayable(float(r.uk_trailing12_gbp or 0), int(r.uk_months_with_exports or 0))
        flagged = r.status in ("lead", "watch")
        if flagged:
            # The live run applies the same rule, with the case windows; use its verdict.
            ok = bool(r.display)
        uk = {"shown": bool(ok)}
        if ok:
            uk["status"] = r.status if flagged else "not flagged"
            if flagged:
                uk.update({
                    "trailing12_gbp": _r(r.uk_trailing12_gbp),
                    "baseline_gbp": _r(r.uk_baseline_gbp),
                    "ratio": _r(r.uk_ratio, 1),
                    "months_with_exports": int(r.uk_months_with_exports),
                })
        else:
            uk["status"] = NOT_SHOWN
            rows.append({"country": r.country, "iso2": iso[r.country], "code": r.code, "description": r.description,
                         "uk_data_to": _yyyymm(r.uk_data_to), "uk": uk, "onward": {"shown": False, "status": NOT_SHOWN}})
            continue
        base = r.onward_base_usd
        mbase = r.monthly_base_usd
        if not pd.isna(r.onward_usd) and check_passes(r.onward_usd, base) != bool(r.onward_annual):
            raise ValueError(f"{r.country} {r.code}: annual check does not match the live run")
        onward = {
            "shown": True,
            "signal": bool(r.onward_signal),
            "annual": {
                "year": int(r.onward_year) if not pd.isna(r.onward_year) else None,
                "usd": _r(r.onward_usd),
                "base_usd": _r(base),
                "ratio": _r(r.onward_ratio, 1),
                "baseline_zero": bool(not pd.isna(base) and float(base) == 0.0),
                "passes": bool(r.onward_annual),
                "why_not": why_not(r.onward_usd, base, bool(r.onward_annual)),
            },
            "monthly": None,
        }
        if not pd.isna(r.monthly_end):
            if check_passes(r.monthly_window_usd, mbase) != bool(r.onward_monthly):
                raise ValueError(f"{r.country} {r.code}: monthly check does not match the live run")
            onward["monthly"] = {
                "to": _yyyymm(r.monthly_end),
                "usd": _r(r.monthly_window_usd),
                "base_usd": _r(mbase),
                "ratio": _r(float(r.monthly_window_usd) / float(mbase), 1)
                if not pd.isna(mbase) and float(mbase) > 0 else None,
                "baseline_zero": bool(not pd.isna(mbase) and float(mbase) == 0.0),
                "passes": bool(r.onward_monthly),
                "why_not": why_not(r.monthly_window_usd, mbase, bool(r.onward_monthly)),
            }
        rows.append({
            "country": r.country,
            "iso2": iso[r.country],
            "code": r.code,
            "description": r.description,
            "uk_data_to": _yyyymm(r.uk_data_to),
            "uk": uk,
            "onward": onward,
        })
    return rows


def codes() -> list[dict]:
    c = pd.read_csv(ROOT / "config" / "codes.csv", dtype={"code": str, "cn8_from": str, "cn8_to": str})
    return [{"code": r.code, "tier": int(r.tier), "description": r.description,
             "cn8_from": r.cn8_from, "cn8_to": r.cn8_to,
             "note": "" if pd.isna(r.note) else r.note} for r in c.itertuples()]


def corridors(variant: str | None = None) -> list[dict]:
    c = pd.read_csv(countries_path(variant or current_variant()))
    out = []
    for r in c[c.role == "corridor"].itertuples():
        out.append({"name": r.name, "iso2": r.iso2, "aliases": sorted(set(ALIASES[r.iso2] + [r.name]))})
    stops = [{"iso2": k, "aliases": v} for k, v in STOP.items()]
    return [{"corridors": out, "stop": stops}]


# A made-up exporter. Each customer buys one or two codes for one destination; the
# patterns are chosen so the screen has something to show: a new customer on a corridor
# whose onward check is on, a long-standing customer there, customers in corridors whose
# checks are off, customers outside the corridors, a code the radar does not track, and
# rows the screen cannot read. The last two customers are on corridors run 3 added: a
# rising customer to India (onward check on for 8517.62) and a long-standing one to Hong
# Kong, written "Hong Kong SAR" (onward check off for 8542.32). They come last, so the
# rows of the others are as they were.
MONTHS = [f"{y:04d}-{m:02d}" for y in (2024, 2025, 2026) for m in range(1, 13)]
MONTHS = [m for m in MONTHS if "2024-09" <= m <= "2026-08"]
CUSTOMERS = [
    # ref, destination as written in the file, commodity codes, first month, monthly base GBP, growth per month
    ("SYN-C0031", "Kazakhstan", ["85176200"], "2024-09", 21000, 0.00),
    ("SYN-C0107", "Kazakhstan", ["85176200"], "2026-03", 38000, 0.32),
    ("SYN-C0118", "KZ", ["85423190"], "2025-06", 9000, 0.05),
    ("SYN-C0058", "UAE", ["85423290"], "2024-09", 26000, 0.03),
    ("SYN-C0063", "United Arab Emirates", ["85322400"], "2024-11", 7000, 0.00),
    ("SYN-C0072", "Türkiye", ["85423290"], "2024-09", 14000, 0.04),
    ("SYN-C0079", "Turkey", ["85176200", "85269120"], "2025-02", 11000, 0.02),
    ("SYN-C0090", "Armenia", ["85322400"], "2025-04", 6000, 0.00),
    ("SYN-C0094", "Georgia", ["85322400"], "2024-10", 5000, 0.06),
    ("SYN-C0099", "Uzbekistan", ["85176200"], "2025-09", 12000, 0.08),
    ("SYN-C0012", "Germany", ["85423190", "85423290"], "2024-09", 64000, 0.00),
    ("SYN-C0015", "France", ["85176200"], "2024-09", 41000, 0.01),
    ("SYN-C0019", "Netherlands", ["85322400"], "2024-09", 23000, 0.00),
    ("SYN-C0024", "United States", ["85423990"], "2024-09", 52000, 0.01),
    ("SYN-C0027", "Poland", ["94036010"], "2024-09", 8000, 0.00),
    ("SYN-C0041", "Kazakhstan", ["94036010"], "2025-01", 4000, 0.00),
    ("SYN-C0123", "India", ["85176200"], "2025-11", 15000, 0.08),
    ("SYN-C0127", "Hong Kong SAR", ["85423290"], "2024-10", 19000, 0.02),
]


def synthetic_rows(seed: int = 20261021) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    n = 0
    for ref, dest, cns, first, base, growth in CUSTOMERS:
        live = [m for m in MONTHS if m >= first]
        for i, m in enumerate(live):
            for cn in cns:
                if rng.random() < 0.12:  # some months with no order
                    continue
                v = base * (1 + growth) ** i * rng.uniform(0.75, 1.25)
                n += 1
                rows.append({"order_ref": f"SYN-O{n:05d}", "customer_ref": ref, "destination": dest,
                             "commodity_code": cn, "month": m, "value_gbp": int(round(v, -1))})
    # Rows the screen cannot read or cannot place.
    rows += [
        {"order_ref": "SYN-O90001", "customer_ref": "SYN-C0107", "destination": "Kazakhstan",
         "commodity_code": "8517", "month": "2026-08", "value_gbp": 12000},
        {"order_ref": "SYN-O90002", "customer_ref": "SYN-C0063", "destination": "Atlantis",
         "commodity_code": "85322400", "month": "2026-07", "value_gbp": 3000},
        {"order_ref": "SYN-O90003", "customer_ref": "SYN-C0058", "destination": "UAE",
         "commodity_code": "85423290", "month": "July 2026", "value_gbp": 5000},
    ]
    rows.sort(key=lambda r: (r["month"], r["order_ref"]))
    return rows


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def uncommitted(paths: list[str]) -> list[str]:
    """Inputs that are not in HEAD as they are on disk (untracked, or changed since)."""
    out = []
    for p in paths:
        tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", p], capture_output=True).returncode == 0
        same = tracked and subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "HEAD", "--", p], capture_output=True).returncode == 0
        if not same:
            out.append(p)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", default="2026-10")
    args = ap.parse_args()
    variant = current_variant()
    OUT.mkdir(parents=True, exist_ok=True)
    for name in COPIED:
        shutil.copyfile(DEMO / f"{name}.json", OUT / f"{name}.json")
    dump = lambda name, obj: (OUT / f"{name}.json").write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")
    dump("signals", signals(args.run, variant))
    dump("codes", codes())
    dump("corridors", corridors(variant))
    with open(OUT / "synthetic_shipments.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["order_ref", "customer_ref", "destination", "commodity_code", "month", "value_gbp"])
        w.writeheader()
        w.writerows(synthetic_rows())
    # The restricted layer (synthetic declarations): the files the workspace shows. The
    # declaration lines, entities and ground truth stay in demo/radar/declarations.
    decl_out = OUT / "declarations"
    if decl_out.exists():
        shutil.rmtree(decl_out)
    if DECL_SRC.exists():
        decl_out.mkdir()
        for name in DECL_FILES:
            shutil.copyfile(DECL_SRC / f"{name}.json", decl_out / f"{name}.json")
    # The triage view (synthetic breach reports, a synthetic list in the UK Sanctions List's format).
    tri_out = OUT / "triage"
    if tri_out.exists():
        shutil.rmtree(tri_out)
    if TRIAGE_SRC.exists():
        tri_out.mkdir()
        for name in TRIAGE_FILES:
            shutil.copyfile(TRIAGE_SRC / f"{name}.json", tri_out / f"{name}.json")
    # The brief engine's outputs, when built.
    if (OUT / "briefs").exists():
        shutil.rmtree(OUT / "briefs")
    if BRIEFS_SRC.exists():
        shutil.copytree(BRIEFS_SRC, OUT / "briefs")
        if not (OUT / "briefs" / "index.json").exists():
            raise SystemExit("demo/radar/briefs has no index.json: run scripts/build_brief_contexts.py")
    spec_out = APP / "spec"
    if spec_out.exists():
        shutil.rmtree(spec_out)
    if SPEC_SRC.exists():
        shutil.copytree(SPEC_SRC, spec_out, ignore=shutil.ignore_patterns("__pycache__"))
    from fdcore import memory as fdmemory
    spec_out.mkdir(exist_ok=True)
    if LAND_SRC.exists():
        shutil.copyfile(LAND_SRC, spec_out / "land.json")
    items = [json.loads(x) for x in MONITOR_SRC.read_text(encoding="utf-8").splitlines() if x.strip()] if MONITOR_SRC.exists() else []
    items.sort(key=lambda i: (i["published"], i["id"]), reverse=True)
    shutil.copyfile(ROOT / "monitor" / "sources.json", spec_out / "monitor_sources.json")
    (OUT / "monitor.json").write_text(json.dumps(items, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (spec_out / "memory_rules.json").write_text(json.dumps(fdmemory.rules_json(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    fdcore_dir = Path(fdmemory.__file__).resolve().parent.parent
    fdcore_commit = subprocess.run(["git", "-C", str(fdcore_dir), "rev-parse", "--short", "HEAD"],
                                   capture_output=True, text=True).stdout.strip() or None
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    # The manifest names a commit as the source only when every input is in it as it is.
    inputs = ([f"demo/radar/{n}.json" for n in COPIED] + [f"demo/radar/declarations/{n}.json" for n in DECL_FILES]
              + [f"demo/radar/triage/{n}.json" for n in TRIAGE_FILES]
              + [str(live_path(args.run, variant).relative_to(ROOT)), str(countries_path(variant).relative_to(ROOT)),
                 "config/codes.csv", "scripts/build_app_data.py", str(LAND_SRC.relative_to(ROOT)), str(MONITOR_SRC.relative_to(ROOT)), "monitor/sources.json"]
              + sorted(str(q.relative_to(ROOT)) for d in (BRIEFS_SRC, SPEC_SRC) if d.exists() for q in d.rglob("*")
                       if q.is_file() and "__pycache__" not in q.parts))
    unc = uncommitted(inputs)
    files = {}
    for p in sorted(list(OUT.rglob("*")) + (list(spec_out.rglob("*")) if spec_out.exists() else [])):
        if p.is_file() and p.name != "manifest.json":
            files[str(p.relative_to(APP))] = sha256(p)
    summary = json.loads((OUT / "summary.json").read_text())[0]
    dump("manifest", [{"run": summary["run"], "run_label": summary["run_label"],
                       "uk_data_to": summary["uk_data_to"], "source_commit": commit, "source_dirty": bool(unc),
                       "fdcore_commit": fdcore_commit,
                       "uncommitted_inputs": unc, "files": files}])
    if unc:
        print("warning: these inputs are not committed as they are, so the manifest marks the build dirty: " + ", ".join(unc))
    print(f"wrote {len(files) + 1} files to {APP.relative_to(ROOT)} ({variant}, {summary['corridors']} corridors)")


if __name__ == "__main__":
    main()
