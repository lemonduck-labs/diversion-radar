"""Write the restricted layer's synthetic data files to demo/radar/declarations/ from one seed
(radar/declarations). Tests fail if a file differs from what this writes.

Usage:  python scripts/build_declarations.py [--check] [--seed N]
        (--check: write nothing, exit 1 if a file is out of date)

SYNTHETIC. A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from radar.declarations import export  # noqa: E402
from radar.declarations.generate import SEED  # noqa: E402

OUT = ROOT / "demo" / "radar" / "declarations"


def outputs(seed: int = SEED) -> dict[Path, str]:
    return {OUT / name: text for name, text in export.build(seed).items()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args(argv)
    stale = []
    files = outputs(a.seed)
    if not a.check:
        OUT.mkdir(parents=True, exist_ok=True)
    for path, text in files.items():
        if path.exists() and path.read_text(encoding="utf-8") == text:
            continue
        stale.append(path)
        if not a.check:
            path.write_text(text, encoding="utf-8")
    for path in stale:
        print(f"{'out of date' if a.check else 'wrote'}: {path.relative_to(ROOT)}")
    total = sum(len(t.encode("utf-8")) for t in files.values())
    print(f"{len(files)} files, {total / 1e6:.2f} MB")
    return 1 if a.check and stale else 0


if __name__ == "__main__":
    sys.exit(main())
