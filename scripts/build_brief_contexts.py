"""Write one brief context per series flagged at a run that passes the display rule, for the
radar page to ship as data files: demo/radar/briefs/<slug>.json, plus index.json listing them.

Each file is radar.brief.build_context(run, series): the only facts a drafted brief may use.
Series that are flagged but not shown under the display rule get no file; they are counted,
never shown. The files hold the official, case-level outcomes of the linked cases from the
case register and the titles of the official guidance behind the questions to check.

The run is the workspace's current one by default: run 3, 18 corridors on run 2's rule
(scripts/build_demo_data.CURRENT); --variant run2 builds run 2's nine corridors.

Usage:  python scripts/build_brief_contexts.py [--run 2026-10] [--variant run3] [--out demo/radar/briefs]
(run scripts/run_live_run3.py, or scripts/run_live.py for run2, for the same run first)

A rise in exports is a lead, not evidence of a breach.
Contains public sector information licensed under the Open Government Licence v3.0.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from radar.brief import build_context, flagged_shown  # noqa: E402
from radar.brief.context import HOUSE_LINE, OGL_LINE, _period  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
from build_demo_data import CURRENT, VARIANTS  # noqa: E402


def latest_run(variant: str = CURRENT) -> str:
    """The latest month with a live table for the variant (live_<YYYY-MM>.csv for run2,
    live_<YYYY-MM>_run3.csv for run3)."""
    suffix = "_run3" if variant == "run3" else ""
    pat = re.compile(r"live_(\d{4}-\d{2})" + re.escape(suffix) + r"\.csv")
    runs = sorted(m.group(1) for p in (ROOT / "data" / "processed").glob("live_*.csv") if (m := pat.fullmatch(p.name)))
    if not runs:
        raise SystemExit(f"no {variant} live table in data/processed; run the live run first")
    return runs[-1]


def build(run: str, variant: str = CURRENT) -> dict[str, dict]:
    """File name -> content, for every series flagged at the run that passes the display rule."""
    files, index = {}, []
    for series in flagged_shown(run, variant=variant):
        ctx = build_context(run, series, variant=variant)
        name = f"{ctx['slug']}.json"
        files[name] = ctx
        index.append({"series": ctx["series"], "slug": ctx["slug"], "status": ctx["status"], "file": name})
    p = _period(run)
    files["index.json"] = {"schema": "radar-brief-index/1", "run": p.strftime("%Y-%m"),
                           "run_label": p.strftime("%B %Y"), "house_line": HOUSE_LINE, "ogl_line": OGL_LINE,
                           "series": index}
    return files


def text(obj: dict) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None, help="YYYY-MM; default: the latest live table")
    ap.add_argument("--variant", default=CURRENT, choices=list(VARIANTS),
                    help=f"which live run (default {CURRENT}, the workspace's current run)")
    ap.add_argument("--out", default=str(ROOT / "demo" / "radar" / "briefs"))
    a = ap.parse_args(argv)
    run = a.run or latest_run(a.variant)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    files = build(run, a.variant)
    for name, obj in files.items():
        (out / name).write_text(text(obj), encoding="utf-8")
    stale = sorted(p.name for p in out.glob("*.json") if p.name not in files)
    print(f"{out}: {len(files) - 1} brief contexts and index.json for the {run} run ({a.variant})")
    if stale:
        print(f"not from this run, left in place: {', '.join(stale)}")
    print(HOUSE_LINE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
