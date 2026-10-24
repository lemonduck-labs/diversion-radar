"""Build the hosted workspace: the site for Netlify and the drafting function's bundle.

The workspace page (app/index.html) runs inside Claude for the pilot. This script builds the
copy that runs on Supabase and Netlify instead (hosted/README.md). Nothing here deploys anything.

1. Checks that app/index.html holds app/src as it is (scripts/build_app_page.py) and that every
   file app/data/manifest.json lists matches its SHA-256, so the hosted page is the page in git
   and its data the reviewed data.
2. Writes app/dist-hosted/ (gitignored), the folder deployed to Netlify:
   - index.html: app/index.html as a full document that loads the Supabase client (supabase-js,
     its UMD build from jsDelivr at a pinned version, checked by its SHA-384), the project's URL
     and publishable key, app/src/hosted.js (a stand-in for claude.use over Supabase), then the
     page's own scripts, unchanged;
   - data/ and spec/: the files app/data/manifest.json lists, unchanged, and the manifest;
   - _headers: a Content-Security-Policy that allows only those scripts (the inline ones by
     SHA-256), the page's styles by SHA-256 and the project's own API; robots.txt; and
     hosted.json, the build record.
3. Writes the draft-brief function's bundle, supabase/functions/draft-brief/_bundle/
   (gitignored): screen.js (app/src/screen.js unchanged), data.mjs (each file's facts, the
   prompt, the screen rules and schema, fd-core's guardrails patterns and the build record) and
   deny.mjs (the private deny list, read from config/deny_list.txt, or --deny-list, as
   radar/brief/screen.py reads it). The deny list never goes in git or the page.

The URL and the key come from --supabase-url and --publishable-key (or DR_SUPABASE_URL and
DR_SUPABASE_PUBLISHABLE_KEY); without them the build writes placeholders and the page says it
has no project settings. Only a publishable (anon) key is taken: a secret or service-role key
is refused.

Usage:  python scripts/build_hosted.py [--supabase-url URL --publishable-key KEY] [--deny-list FILE] [--clean]

Outputs are leads for a person, never findings. A rise in exports is a lead, not evidence of a
breach.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
APP = ROOT / "app"
PAGE = APP / "index.html"
PAGE_JS = "app/src/page.js"
HOSTED_JS = "app/src/hosted.js"
SCREEN_JS = "app/src/screen.js"
FUNCTION = ROOT / "supabase" / "functions" / "draft-brief"
HOSTED = APP / "dist-hosted"
BUNDLE = FUNCTION / "_bundle"
DENY_FILE = ROOT / "config" / "deny_list.txt"
INPUTS = ["app/index.html", PAGE_JS, SCREEN_JS, HOSTED_JS, "supabase/functions/draft-brief/core.mjs",
          "supabase/functions/draft-brief/index.ts", "scripts/build_hosted.py"]
# The Supabase client: its UMD build at an exact version, with the SHA-384 of that file as npm
# publishes it (dist/umd/supabase.js in the package), which jsDelivr serves unchanged.
SUPABASE_JS_VERSION = "2.117.2"
SUPABASE_JS = {
    "version": SUPABASE_JS_VERSION,
    "url": f"https://cdn.jsdelivr.net/npm/@supabase/supabase-js@{SUPABASE_JS_VERSION}/dist/umd/supabase.js",
    "integrity": "sha384-Rj26LVGvoeRVR6+mwQmFfcR3QOBEwT+ZmuCWpuiqeTzJpCs0ER4ITAWGb4Hiy3Ok",
}
URL_PLACEHOLDER = "https://YOUR-PROJECT-REF.supabase.co"
KEY_PLACEHOLDER = "YOUR-PUBLISHABLE-KEY"
MODULES_SCRIPT = "<script>\n/* BEGIN fd-core/memory.mjs */"
# The small reset the artifact skeleton adds at publish time (as scripts/build_site.py's RESET),
# then the sign-in bar of app/src/hosted.js, in the page's own colours.
RESET_CSS = """/* The reset the artifact skeleton adds at publish time, and the hosted workspace's sign-in bar
   (app/src/hosted.js). */
:root { color-scheme: light; padding-top: env(safe-area-inset-top, 0px); padding-bottom: env(safe-area-inset-bottom, 0px); }
body { margin: 0; font: 14px system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif; }
img { max-width: 100%; }
[hidden] { display: none !important; }
.hs-bar { background: var(--panel); border-bottom: 1px solid var(--line); font-size: 0.8125rem; color: var(--fg-2); }
.hs-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; padding-block: 8px; }
.hs-form { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.hs-bar input { font: inherit; color: var(--fg); background: var(--panel); border: 1px solid var(--line-strong); border-radius: var(--r-sm); padding: 5px 8px; width: 16rem; max-width: 100%; min-width: 0; }
.hs-notice { padding-block: 0 8px; }
.hs-notice-in { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
"""
# The page sets a few style attributes from fixed strings (h(..., { style: '...' })). The
# Content-Security-Policy allows exactly those, by SHA-256 with 'unsafe-hashes'.
STYLE_ATTR = re.compile(r"\bstyle: '([^'\\]*)'")
STYLE_ANY = re.compile(r"\bstyle:")


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()


def uncommitted(paths: list[str]) -> list[str]:
    """Inputs that are not in HEAD as they are on disk (untracked, or changed since)."""
    out = []
    for p in paths:
        tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", p], capture_output=True).returncode == 0
        same = tracked and subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "HEAD", "--", p], capture_output=True).returncode == 0
        if not same:
            out.append(p)
    return out


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clear(dest: Path, marker: str) -> None:
    """Empty a folder this script wrote before (it holds `marker`), and never any other folder."""
    if dest.exists():
        if any(dest.iterdir()) and not (dest / marker).exists():
            raise SystemExit(f"{dest} is not empty and was not written by this script, so it is left alone")
        shutil.rmtree(dest)


# ---------------------------------------------------------------- checks on the inputs

def page_is_current() -> None:
    spec = importlib.util.spec_from_file_location("build_app_page", ROOT / "scripts" / "build_app_page.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    page = PAGE.read_text(encoding="utf-8")
    if mod.inline(page) != page:
        raise SystemExit("app/index.html does not hold app/src as it is: run python scripts/build_app_page.py first")


def data_manifest() -> dict:
    """app/data/manifest.json, after checking that every file it lists is on disk as listed."""
    m = json.loads((APP / "data" / "manifest.json").read_text(encoding="utf-8"))[0]
    bad = [p for p, h in m["files"].items() if not (APP / p).is_file() or sha256((APP / p).read_bytes()) != h]
    if bad:
        raise SystemExit("these files do not match app/data/manifest.json: " + ", ".join(bad) + ". Run python scripts/build_app_data.py.")
    return m


def check_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not re.fullmatch(r"https://[a-z0-9-]+(?:\.[a-z0-9-]+)+", url):
        raise SystemExit(f"--supabase-url must be the project's https URL with no path, for example {URL_PLACEHOLDER}")
    return url


def check_public_key(key: str) -> str:
    """Only a key that is safe in a browser: a publishable key, or a legacy anon key. A secret or
    service-role key would give anyone who opens the page the whole database."""
    key = key.strip()
    if key.startswith("sb_secret_"):
        raise SystemExit("that is a secret key: the page takes only the publishable key. Revoke the secret key if it was shared.")
    if re.fullmatch(r"sb_publishable_[A-Za-z0-9_-]{8,}", key):
        return key
    parts = key.split(".")
    if len(parts) == 3:
        try:
            claims = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
        except ValueError:
            claims = {}
        if claims.get("role") == "anon":
            return key
        raise SystemExit(f"that key's role is {claims.get('role')!r}: the page takes only the publishable (anon) key")
    raise SystemExit("--publishable-key must be the project's publishable key (sb_publishable_...) or its legacy anon key")


# ---------------------------------------------------------------- the site

def csp_hash(text: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii") + "'"


def inline_blocks(html: str, tag: str) -> list[str]:
    """The text of every inline <script> (no src) or <style> block, exactly as a browser hashes it."""
    pat = r"<script>(.*?)</script>" if tag == "script" else r"<style>(.*?)</style>"
    return re.findall(pat, html, re.S)


def style_attributes() -> list[str]:
    """The fixed style attributes app/src/page.js sets, refusing any it builds at run time."""
    src = (ROOT / PAGE_JS).read_text(encoding="utf-8")
    fixed = STYLE_ATTR.findall(src)
    if len(fixed) != len(STYLE_ANY.findall(src)):
        raise SystemExit(f"{PAGE_JS} sets a style attribute that is not a fixed string, so the Content-Security-Policy cannot allow it by hash")
    return sorted(set(fixed))


def hosted_page(page: str, url: str, key: str) -> str:
    """The page as a full document, with the Supabase client, the project settings and
    app/src/hosted.js ahead of the page's own scripts. The page's code is not changed."""
    end = page.find("</style>")
    if not page.startswith("<title>") or end < 0:
        raise SystemExit("app/index.html: expected <title>, <meta> and <style>, then the page's body")
    cut = end + len("</style>")
    head, body = page[:cut], page[cut:].lstrip("\n")
    at = body.find(MODULES_SCRIPT)
    if at < 0:
        raise SystemExit("app/index.html: the script with the shared modules is missing")
    config = json.dumps({"url": url, "anonKey": key}).replace("</", "<\\/")
    hosted_js = (ROOT / HOSTED_JS).read_text(encoding="utf-8").rstrip() + "\n"
    if "</script" in hosted_js.lower():
        raise SystemExit(f"{HOSTED_JS}: the code holds a closing script tag")
    s = SUPABASE_JS
    inject = (f'<script src="{s["url"]}" integrity="{s["integrity"]}" crossorigin="anonymous" referrerpolicy="no-referrer"></script>\n'
              f"<script>\nwindow.DR_HOSTED_CONFIG = {config};\n</script>\n"
              f"<script>\n/* {HOSTED_JS} */\n{hosted_js}</script>\n")
    return ("<!doctype html>\n<html lang=\"en-GB\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
            "<meta name=\"referrer\" content=\"no-referrer\">\n<meta name=\"robots\" content=\"noindex, nofollow\">\n"
            f"<style>\n{RESET_CSS}</style>\n{head}\n</head>\n<body>\n{body[:at]}{inject}{body[at:]}</body>\n</html>\n")


def shell_css(page: str) -> str:
    """The text of the one <style> element fd-core's shell adds when it mounts (fdcore/shell.mjs,
    SHELL_CSS), as the page inlines it, so the policy can allow it by its SHA-256."""
    m = re.search(r"^const SHELL_CSS = `(.*?)`;$", page, re.M | re.S)
    if not m or "\\" in m.group(1) or "${" in m.group(1):
        raise SystemExit("app/index.html: fd-core's shell styles (SHELL_CSS) are missing or not plain text")
    return m.group(1)


def netlify_headers(html: str, url: str, attrs: list[str]) -> str:
    host = url.split("://", 1)[1]
    scripts = " ".join(csp_hash(t) for t in inline_blocks(html, "script"))
    styles = " ".join(csp_hash(t) for t in [*inline_blocks(html, "style"), shell_css(html)])
    attr = (" 'unsafe-hashes' " + " ".join(csp_hash(t) for t in attrs)) if attrs else ""
    csp = (f"default-src 'none'; script-src {scripts} {SUPABASE_JS['url']}; style-src {styles}{attr}; "
           f"connect-src 'self' https://{host} wss://{host}; img-src 'self' data:; font-src data:; base-uri 'none'; "
           "form-action 'none'; frame-ancestors 'none'; object-src 'none'")
    return ("# Written by scripts/build_hosted.py. The page's inline scripts and styles, and the style element\n"
            "# fd-core's shell adds, are allowed by their SHA-256, its fixed style attributes by theirs, and the\n"
            "# Supabase client by its exact URL (and its SHA-384 in the page).\n"
            "/*\n"
            f"  Content-Security-Policy: {csp}\n"
            "  X-Content-Type-Options: nosniff\n"
            "  Referrer-Policy: no-referrer\n"
            "  X-Frame-Options: DENY\n"
            "  X-Robots-Tag: noindex, nofollow\n"
            "  Cross-Origin-Opener-Policy: same-origin\n"
            "  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()\n"
            "/data/*\n  Cache-Control: no-cache\n"
            "/spec/*\n  Cache-Control: no-cache\n")


# ---------------------------------------------------------------- the function's bundle

def fdcore_patterns() -> dict:
    """fd-core's guardrails patterns, for the function's port of its screen (core.mjs, fdcoreScan).
    The bundle stays out of git: it lists the words the screen blocks."""
    from fdcore import guardrails as G

    def rx(p: re.Pattern) -> dict:
        return {"pattern": p.pattern, "flags": "i" if p.flags & re.IGNORECASE else ""}

    return {
        "generated_from": "fdcore.guardrails", "fdcore_sha256": sha256(Path(G.__file__).read_bytes()),
        "kinds": G.KINDS,
        "patterns": {"company": rx(G.COMPANY), "email": rx(G.EMAIL), "phone": rx(G.PHONE), "postcode": rx(G.UK_POSTCODE),
                     "accusing": rx(G.ACCUSING), "clause_break": rx(G.CLAUSE_BREAK)},
        "hedges": list(G.HEDGES), "hedge_before": G.HEDGE_BEFORE, "hedge_after": G.HEDGE_AFTER,
        "email_allow": sorted(G.EMAIL_ALLOW),
    }


def files_and_contexts() -> tuple[dict, dict]:
    """Each file the page can draft for, by its facts' slug: the file id the page writes
    (app/src/page.js, buildFiles: <run>_<corridor>-<code>), its series and run, and its facts."""
    load = lambda p: json.loads((APP / "data" / p).read_text(encoding="utf-8"))  # noqa: E731
    run = load("summary.json")[0]["run"]
    iso = {c["name"]: c["iso2"] for c in load("corridors.json")[0]["corridors"]}
    lead_of = {l["series"]: f"{run}_{iso[l['country']]}-{l['code']}" for l in load("leads.json")}  # noqa: E741
    files, contexts = {}, {}
    for e in load("briefs/index.json")["series"]:
        ctx = load(f"briefs/{e['file']}")
        if ctx["slug"] != e["slug"] or ctx["series"] != e["series"] or ctx["run"] != run or e["series"] not in lead_of:
            raise SystemExit(f"app/data/briefs/{e['file']} is not a file of this run")
        files[e["slug"]] = {"lead": lead_of[e["series"]], "series": e["series"], "run": run}
        contexts[e["slug"]] = ctx
    return files, contexts


def deny_terms(path: Path | None) -> list[str]:
    from radar.brief.screen import load_deny
    return load_deny(path) if path and path.exists() else []


def build_bundle(dest: Path, record: dict, deny_path: Path | None) -> int:
    clear(dest, "data.mjs")
    dest.mkdir(parents=True)
    shutil.copyfile(ROOT / SCREEN_JS, dest / "screen.js")
    files, contexts = files_and_contexts()
    spec = lambda n: json.loads((APP / "spec" / n).read_text(encoding="utf-8"))  # noqa: E731
    data = {
        "files": files, "contexts": contexts,
        "prompt": (APP / "spec" / "prompt.md").read_text(encoding="utf-8"),
        "spec": {"rules": spec("screen_rules.json"), "schema": spec("brief.schema.json")},
        "fdcore": fdcore_patterns(),
        "build": record,
    }
    (dest / "data.mjs").write_text(
        "// Written by scripts/build_hosted.py, with the hosted page of the same build. Not in git: it holds\n"
        "// fd-core's word lists. A rise in exports is a lead, not evidence of a breach.\n"
        f"export const DATA = {json.dumps(data, indent=1, ensure_ascii=False)};\n", encoding="utf-8")
    deny = deny_terms(deny_path)
    (dest / "deny.mjs").write_text(
        "// Written by scripts/build_hosted.py from the private deny list. Never commit it, never send it to a page.\n"
        f"export const DENY = {json.dumps(deny, ensure_ascii=False)};\n", encoding="utf-8")
    return len(deny)


def build_hosted(url: str | None, key: str | None, dest: Path = HOSTED, bundle: Path = BUNDLE, deny_path: Path | None = DENY_FILE) -> dict:
    url = check_url(url) if url else URL_PLACEHOLDER
    key = check_public_key(key) if key else KEY_PLACEHOLDER
    page_is_current()
    manifest = data_manifest()
    attrs = style_attributes()
    unc = uncommitted(INPUTS + sorted(f"app/{p}" for p in manifest["files"]) + ["app/data/manifest.json"])
    record = {"built_by": "scripts/build_hosted.py", "source_commit": git("rev-parse", "--short", "HEAD"), "source_dirty": bool(unc),
              "uncommitted_inputs": unc, "data_commit": manifest["source_commit"], "run": manifest["run"]}
    clear(dest, "hosted.json")
    dest.mkdir(parents=True)
    for p in [*manifest["files"], "data/manifest.json"]:
        (dest / p).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(APP / p, dest / p)
    html = hosted_page(PAGE.read_text(encoding="utf-8"), url, key)
    (dest / "index.html").write_text(html, encoding="utf-8")
    (dest / "_headers").write_text(netlify_headers(html, url, attrs), encoding="utf-8")
    (dest / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    terms = build_bundle(bundle, record, deny_path)
    out = dict(record, target="hosted", supabase_url=url, configured=url != URL_PLACEHOLDER and key != KEY_PLACEHOLDER,
               supabase_js=SUPABASE_JS, hosted_page_sha256=sha256((dest / "index.html").read_bytes()),
               bundle={n: sha256((bundle / n).read_bytes()) for n in ["data.mjs", "screen.js"]})
    (dest / "hosted.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return dict(out, deny_terms=terms)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--supabase-url", default=os.environ.get("DR_SUPABASE_URL"), help="the project's URL")
    ap.add_argument("--publishable-key", "--anon-key", dest="key", default=os.environ.get("DR_SUPABASE_PUBLISHABLE_KEY"),
                    help="the project's publishable (anon) key, never a secret key")
    ap.add_argument("--deny-list", type=Path, default=DENY_FILE, help="the private deny list (default config/deny_list.txt)")
    ap.add_argument("--clean", action="store_true", help="refuse to build from inputs that are not committed as they are")
    ap.add_argument("--out", type=Path, default=HOSTED, help="the site folder (default app/dist-hosted)")
    ap.add_argument("--bundle-out", type=Path, default=BUNDLE, help="the function's bundle (default supabase/functions/draft-brief/_bundle)")
    args = ap.parse_args(argv)
    if args.clean:
        manifest = data_manifest()
        unc = uncommitted(INPUTS + sorted(f"app/{p}" for p in manifest["files"]) + ["app/data/manifest.json"])
        if unc:
            print("these inputs are not committed as they are: " + ", ".join(unc) + ". Commit them first.")
            return 1
    m = build_hosted(args.supabase_url, args.key, args.out, args.bundle_out, args.deny_list)
    rel = lambda q: q.resolve().relative_to(ROOT).as_posix() if q.resolve().is_relative_to(ROOT) else str(q)  # noqa: E731
    print(f"wrote {rel(args.out)} and {rel(args.bundle_out)} from {m['source_commit']}{' (uncommitted changes)' if m['source_dirty'] else ''}"
          + ("" if m["configured"] else "; no project settings yet, so the page will say so (see hosted/README.md)")
          + ("" if m["deny_terms"] else "; no deny list, so the function will not draft until one is bundled or set as DENY_LIST"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
