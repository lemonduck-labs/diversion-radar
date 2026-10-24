"""File the monitoring items a collection run left in monitor/inbox/ (phase 7).

Writes monitor/vocab.json (the corridors and goods codes the radar knows, from app/data, and
the topics), then runs fd-core's monitor ingest: every candidate is checked against
monitor/sources.json and the vocabulary, screened by fd-core's guardrails (with the private deny
list when it is present), and either appended to monitor/items.jsonl with an entry in
data/ingest_log.jsonl, or refused into monitor/refused.jsonl with its reasons. An item already
held is skipped. Then run scripts/build_app_data.py, which copies the items to
app/data/monitor.json for the workspace. How a collection run works: monitor/RUNBOOK.md.

Usage:  python scripts/monitor_ingest.py [--today YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from fdcore import monitor
from fdcore.ingest_log import IngestLog

ROOT = Path(__file__).resolve().parent.parent
M = ROOT / "monitor"
TOPICS = ["enforcement", "licensing", "reporting", "designations", "release", "guidance", "end_use"]


def vocab() -> dict[str, list[str]]:
    corridors = json.loads((ROOT / "app" / "data" / "corridors.json").read_text(encoding="utf-8"))[0]["corridors"]
    codes = [str(c["code"]) for c in json.loads((ROOT / "app" / "data" / "codes.json").read_text(encoding="utf-8"))]
    return {"corridors": sorted(c["iso2"] for c in corridors), "codes": sorted(codes),
            "headings": sorted({c[:4] for c in codes}), "topics": TOPICS}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--today")
    a = ap.parse_args(argv)
    v = vocab()
    (M / "vocab.json").write_text(json.dumps(v, indent=1) + "\n", encoding="utf-8")
    deny_file = ROOT / "config" / "deny_list.txt"
    deny = deny_file.read_text(encoding="utf-8").splitlines() if deny_file.exists() else None
    # Paths relative to the repository, so the ingest log never records where a checkout happens to be.
    os.chdir(ROOT)
    rep = monitor.ingest(Path("monitor/inbox"), Path("monitor/items.jsonl"), monitor.load_register("monitor/sources.json"), IngestLog("data/ingest_log.jsonl"),
                         v, deny, today=date.fromisoformat(a.today) if a.today else None, refusals_path=Path("monitor/refused.jsonl"))
    print(json.dumps({k: len(x) for k, x in rep.items()}))
    for r in rep["refused"]:
        print(f"refused {r['url']}: " + "; ".join(r["problems"]), file=sys.stderr)
    return 1 if rep["refused"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
