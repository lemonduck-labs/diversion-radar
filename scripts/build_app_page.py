"""Inline the shared JavaScript modules into the workspace page (app/index.html).

The page is published as one file, so the memory core's screens (fd-core's fdcore/memory.mjs,
as the global FdMemory), the navigation the tools share (fd-core's fdcore/shell.mjs, as the
global FdShell), the screen it shares with the hosted drafting function (app/src/screen.js) and
the page's own script (app/src/page.js) are copied into it between markers:

    /* BEGIN fd-core/memory.mjs */ ... /* END fd-core/memory.mjs */
    /* BEGIN fd-core/shell.mjs */ ... /* END fd-core/shell.mjs */
    /* BEGIN src/screen.js */ ... /* END src/screen.js */
    /* BEGIN src/page.js */ ... /* END src/page.js */

fd-core is read from beside this repo (../fd-core), or from FD_CORE; each file's SHA-256 goes
in its copy, so the page says which version of fd-core's code it runs.

It also writes the brand (brand/brand.css, with its fonts as data: URIs, by fd-core's
fdcore.brand) into app/index.html and the dashboard (demo/radar/index.html), between
/* BEGIN brand */ and /* END brand */, so neither page loads anything from elsewhere.

Run after editing app/src/*.js or brand/. tests/test_app_page.py fails when a page and its
source differ, so the copy never drifts.

Usage:  python scripts/build_app_page.py [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "app" / "index.html"
DEMO_PAGE = ROOT / "demo" / "radar" / "index.html"
BRAND = ROOT / "brand"
MODULES = ["fd-core/memory.mjs", "fd-core/shell.mjs", "src/screen.js", "src/page.js"]
FD_GLOBALS = {"fd-core/memory.mjs": "FdMemory", "fd-core/shell.mjs": "FdShell"}
FDCORE = Path(os.environ.get("FD_CORE") or ROOT.parent / "fd-core")


def as_global(src: str, name: str, rel: str = "fdcore/memory.mjs") -> str:
    """An ES module made only of 'export function' and 'export const' declarations, as one
    global object, so a page without modules can use it."""
    names = re.findall(r"^export (?:async )?(?:function|const) ([A-Za-z_$][\w$]*)", src, re.M)
    if not names or re.search(r"^\s*(?:import\b|export (?!(?:async )?(?:function|const) ))", src, re.M):
        raise SystemExit(f"{name}: only 'export function' and 'export const' declarations can be inlined")
    body = re.sub(r"^export ", "", src, flags=re.M).rstrip("\n")
    digest = hashlib.sha256(src.encode("utf-8")).hexdigest()
    return (f"// fd-core {rel}, SHA-256 {digest}, as the global {name}\n"
            f"window.{name} = (() => {{\n{body}\nreturn {{ {', '.join(names)} }};\n}})();")


def source(rel: str) -> str:
    if rel in FD_GLOBALS:
        name = rel.split("/", 1)[1]
        path = FDCORE / "fdcore" / name
        if not path.exists():
            raise SystemExit(f"{path} not found: put fd-core beside this repo or set FD_CORE")
        return as_global(path.read_text(encoding="utf-8"), FD_GLOBALS[rel], "fdcore/" + name)
    return (ROOT / "app" / rel).read_text(encoding="utf-8").rstrip("\n")


def fdbrand():
    """fd-core's brand module, from beside this repo or FD_CORE."""
    if str(FDCORE) not in sys.path:
        sys.path.insert(0, str(FDCORE))
    from fdcore import brand
    return brand


def inline(page: str) -> str:
    page = fdbrand().apply(page, BRAND, "app/index.html")
    for rel in MODULES:
        src = source(rel)
        begin, end = f"/* BEGIN {rel} */", f"/* END {rel} */"
        pat = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
        if not pat.search(page):
            raise SystemExit(f"markers for {rel} not found in {PAGE.name}")
        page = pat.sub(lambda _m: f"{begin}\n{src}\n{end}", page, count=1)
    return page


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the page is out of date")
    args = ap.parse_args()
    pages = [(PAGE, inline)] + [(DEMO_PAGE, lambda t: fdbrand().apply(t, BRAND, "demo/radar/index.html"))]
    stale = []
    for path, make in pages:
        page = path.read_text(encoding="utf-8")
        new = make(page)
        if new == page:
            if not args.check:
                print(f"{path.relative_to(ROOT)} already up to date")
            continue
        stale.append(path)
        if not args.check:
            path.write_text(new, encoding="utf-8")
            print(f"updated {path.relative_to(ROOT)}")
    if args.check:
        sys.exit(1 if stale else 0)


if __name__ == "__main__":
    main()
