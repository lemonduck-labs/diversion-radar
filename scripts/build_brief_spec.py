"""Write the generated parts of the brief spec: radar/brief/spec/redflags.json (from
radar/brief/redflags.py) and radar/brief/spec/screen_cases.json (from
radar/brief/shared_cases.py). Tests fail if either file differs from what this writes.

Usage:  python scripts/build_brief_spec.py [--check]
        (--check: write nothing, exit 1 if a file is out of date)

A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from radar.brief import redflags, shared_cases  # noqa: E402

SPEC = ROOT / "radar" / "brief" / "spec"


def outputs() -> dict[Path, str]:
    return {SPEC / "redflags.json": redflags.export_text(),
            SPEC / "screen_cases.json": shared_cases.to_json_text(shared_cases.build())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    stale = []
    for path, text in outputs().items():
        if path.exists() and path.read_text(encoding="utf-8") == text:
            continue
        stale.append(path)
        if not a.check:
            path.write_text(text, encoding="utf-8")
    for path in stale:
        print(f"{'out of date' if a.check else 'wrote'}: {path.relative_to(ROOT)}")
    return 1 if a.check and stale else 0


if __name__ == "__main__":
    sys.exit(main())
