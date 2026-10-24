"""Build the public demo site: Diversion Radar's dashboard and analyst workspace, and Move forward's
market picture and planner, as static pages for Netlify (site/README.md).

    python scripts/build_site.py [--ta ../ta-market] [--fdcore ../fd-core] [--out site/dist] [--clean]
    python scripts/build_site.py --check      builds into a temporary folder and runs the checks only

What goes in, and only this:
- radar/      demo/radar/index.html, the dashboard written for Claude's Dashboard artifact type,
              in a page of its own with site/assets/dash.js standing in for the runtime, and the
              datasets the page reads (demo/radar/<id>.json).
- workspace/  app/index.html, unchanged inside a document skeleton, with the files in its
              manifest (app/data, app/spec), so every file still matches its SHA-256.
- ta/         ta-market's demo/ta/index.html and the datasets it reads, the same way as radar/.
              The synthetic caseload beside them is not read by the page and is left out.
- planner/    ta-market's app/dist, built by its scripts/build_app.py, unchanged inside a
              document skeleton.
- the landing page (site/index.html, its figures filled from the datasets), site/assets/, the
  two brands' marks and the landing page's font from each repo's brand/ folder, with the fonts'
  licence (assets/fonts/OFL.txt),
  site/vendor/ (d3 v7.9.0, checked by SHA-256, with its licence), 404.html, _headers and
  site.json (the three commits and every file's SHA-256).
- with --media DIR, videos/: the captioned walkthroughs tests/site/walkthrough.mjs records from
  a build of this site (<demo>.mp4, a poster, the captions as WebVTT and as a transcript), each
  linked from its demo's card on the landing page. They are not in git; site.json lists them.

Every page loads files from the site only; the tools and dashboards carry their brand's fonts
inline as data: URIs, so font-src allows 'self' and data: only. _headers gives each page a Content-Security-Policy
that allows scripts from the site and the page's own inline scripts, by their SHA-256, and
nothing from any other site. The pages make no AI calls and send nothing anywhere: the workspace
and the planner run in demo mode, with changes kept in the tab and drafting from the template.

Checks, all of which must pass before anything is written:
- fd-core's screen over every text file, with both repos' private deny lists. The two checks
  that can be switched off are switched off only where the source repo's own policy does it for
  the file the site copies, or where site/guardrails_policy.txt does it for a generated file;
- no council named (names from ta-market's processed MHCLG tables);
- no series held back by the display rule at any live run is named beside its code, or carries
  a UK figure or status, and no backtest test under the display rule carries a result;
- no script, style, image, frame or font from another site, no inline event handler;
- the Open Government Licence line and link on every page that shows HMRC or MHCLG data;
- no Global Fishing Watch or OpenSanctions data;
- every link and asset inside the site resolves.

--clean refuses to build unless all three repos are committed as they are, so that site.json
names the exact code. Publishing is the owner's decision: this script never deploys.

A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import html as htmlmod
import json
import re
import shutil
import subprocess
import sys
import tempfile
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
sys.path.insert(0, str(ROOT / "scripts"))

D3 = ("vendor/d3-7.9.0.min.js", "f2094bbf6141b359722c4fe454eb6c4b0f0e42cc10cc7af921fc158fceb86539")
D3_LICENSE = "vendor/d3-LICENSE.txt"
#: Third-party files identified by their SHA-256 rather than screened: the screen is for this
#: project's own outputs, and a pinned library is known byte for byte.
PINNED = {D3[0]: D3[1]}
DASH_CALLS = {"colors", "data", "onData", "params", "setParams", "resetParams", "setLink"}
OGL_TEXT = "Open Government Licence"
OGL_URL = "nationalarchives.gov.uk/doc/open-government-licence/version/3/"
TEXT_SUFFIXES = {".html", ".js", ".mjs", ".css", ".json", ".md", ".txt", ".csv", ".svg", ".vtt", ""}
#: The walkthrough videos tests/site/walkthrough.mjs records from the built site, one per demo.
WALKTHROUGHS = ("radar", "workspace", "ta", "planner")
MEDIA_SUFFIXES = (".mp4", ".jpg", ".vtt", ".txt")
NEVER = re.compile(r"opensanctions|global\s*fishing\s*watch|globalfishingwatch", re.I)
#: Phrases that hold a council's name but are not about a council: a US court's district in the
#: case register ("Eastern District of New York").
NOT_COUNCILS = ("New York",)

# If a page is opened without its trailing slash (/radar rather than /radar/), its relative
# links would point one folder up, so it reloads itself with the slash first.
SLASH_FIX = "if(!/\\/$|\\.html$/.test(location.pathname))location.replace(location.pathname+'/'+location.search+location.hash);"
# The small reset the artifact skeleton adds at publish time, for the two pages written as
# artifacts and served here unchanged.
RESET = (":root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
         "body{margin:0;font:14px system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}img{max-width:100%}[hidden]{display:none!important}")
COMMON_HEADERS = [
    ("X-Robots-Tag", "noindex, nofollow"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Permissions-Policy", "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"),
    ("Cross-Origin-Opener-Policy", "same-origin"),
]

NOT_FOUND = """<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex">
<title>Page not found</title>
<link rel="icon" href="/assets/icon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/site.css">
</head>
<body>
<header class="site-bar"><div class="site-bar-in"><a href="/">All demos</a></div></header>
<main class="site-main home"><section class="home-head">
<h1>Nothing here</h1>
<p class="lede">This address is not one of the demos. The four are listed on the <a href="/">first page</a>.</p>
</section></main>
</body>
</html>
"""


class SiteError(SystemExit):
    pass


# ------------------------------------------------------------------ repos

def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def repo_state(repo: Path) -> dict:
    return {"commit": git(repo, "rev-parse", "--short=7", "HEAD"),
            "date": git(repo, "log", "-1", "--format=%cI"),
            "dirty": bool(git(repo, "status", "--porcelain", "--untracked-files=no"))}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def long_date(iso: str) -> str:
    d = dt.datetime.fromisoformat(iso)
    return f"{d.day} {d:%B %Y}"


def comtrade_read_on(radar: Path) -> str:
    """The day of the latest UN Comtrade pull in the ingest log: the onward figures are UN Comtrade's
    as released by then."""
    days = [json.loads(line).get("retrieved_at", "")[:10]
            for line in (radar / "data" / "ingest_log.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip() and json.loads(line).get("source") == "comtrade"]
    if not days:
        raise SiteError("data/ingest_log.jsonl has no UN Comtrade entry")
    return long_date(max(days))


# ------------------------------------------------------------------ pages

def datasets_read(fragment: str, name: str) -> list[str]:
    calls = set(re.findall(r"\bdash\.([A-Za-z_]+)", fragment))
    if calls - DASH_CALLS:
        raise SiteError(f"{name} calls dash.{', dash.'.join(sorted(calls - DASH_CALLS))}, which site/assets/dash.js does not provide")
    ids = sorted(set(re.findall(r"\brows\('([a-z0-9_]+)'\)", fragment)))
    if not ids:
        raise SiteError(f"{name}: no datasets found (rows('<id>') calls)")
    return ids


def dashboard_page(fragment: str, title: str, description: str, here: str, sources: list[str], note: str, icon: str = "icon.svg") -> str:
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex">
<title>{htmlmod.escape(title)}</title>
<meta name="description" content="{htmlmod.escape(description)}">
<link rel="icon" href="../assets/{icon}" type="image/svg+xml">
<link rel="stylesheet" href="../assets/site.css">
<script>{SLASH_FIX}</script>
<script src="../{D3[0]}"></script>
<script src="../assets/dash.js" data-sources="{','.join(sources)}"></script>
</head>
<body>
<header class="site-bar"><div class="site-bar-in"><a href="../">All demos</a><span class="here">{htmlmod.escape(here)}</span><span class="note">{htmlmod.escape(note)}</span></div></header>
<main class="site-main">
<div class="site-notice" id="site-notice" role="alert" hidden></div>
<div id="dash-root">
{fragment}
</div>
</main>
</body>
</html>
"""


def wrapped_page(page: str, icon: str = "icon.svg") -> str:
    """An artifact page in the skeleton the Artifact tool adds at publish time."""
    return ('<!doctype html><html lang="en-GB"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<meta name="robots" content="noindex"><link rel="icon" href="../assets/{icon}" type="image/svg+xml">'
            f'<style>{RESET}</style><script>{SLASH_FIX}</script></head><body>'
            + page + "</body></html>\n")


def fill(template: str, values: dict[str, object]) -> str:
    out = template
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", htmlmod.escape(str(v)))
    left = sorted(set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", out)))
    if left:
        raise SiteError(f"site/index.html: placeholders not filled: {', '.join(left)}")
    return out


def watch_links(template: str, media: dict[str, dict]) -> str:
    """Put a link to each demo's walkthrough beside its Open button, where the video exists."""
    for name in WALKTHROUGHS:
        mark = f"<!--watch:{name}-->"
        if template.count(mark) != 1:
            raise SiteError(f"site/index.html: {mark} must appear once")
        m = media.get(name)
        link = (f' <a class="watch" href="videos/{name}.mp4">Watch the walkthrough, {m["length"]}</a>'
                f' <a class="watch-t" href="videos/{name}.txt">transcript</a>') if m else ""
        template = template.replace(mark, link)
    return template


def mp4_seconds(data: bytes) -> float:
    """A film's length, from the movie header ('mvhd') of an MP4 file."""
    i = data.find(b"mvhd")
    if i < 4:
        raise SiteError("not an MP4 file: no movie header")
    v = data[i + 4]
    if v == 1:
        scale, length = int.from_bytes(data[i + 24:i + 28], "big"), int.from_bytes(data[i + 28:i + 36], "big")
    else:
        scale, length = int.from_bytes(data[i + 16:i + 20], "big"), int.from_bytes(data[i + 20:i + 24], "big")
    return length / scale


def read_media(media_dir: Path | None) -> tuple[dict[str, bytes], dict[str, dict]]:
    """The walkthroughs in media_dir: every one needs all four files; its length is read from the
    film itself."""
    files: dict[str, bytes] = {}
    found: dict[str, dict] = {}
    if media_dir is None:
        return files, found
    if not media_dir.is_dir():
        raise SiteError(f"--media {media_dir}: no such folder")
    for name in WALKTHROUGHS:
        have = [s for s in MEDIA_SUFFIXES if (media_dir / f"{name}{s}").exists()]
        if not have:
            continue
        if len(have) != len(MEDIA_SUFFIXES):
            raise SiteError(f"--media: {name} has only {', '.join(have)}; record it again with tests/site/walkthrough.mjs")
        if "-->" not in (media_dir / f"{name}.vtt").read_text(encoding="utf-8"):
            raise SiteError(f"--media: {name}.vtt has no captions")
        secs = round(mp4_seconds((media_dir / f"{name}.mp4").read_bytes()))
        found[name] = {"length": f"{secs // 60}:{secs % 60:02d}", "seconds": secs}
        for suf in MEDIA_SUFFIXES:
            files[f"videos/{name}{suf}"] = (media_dir / f"{name}{suf}").read_bytes()
    return files, found


#: How each README names a walkthrough, beside its length in brackets.
README_WALKTHROUGHS = {"dashboard": "radar", "analyst workspace": "workspace", "market picture": "ta",
                       "Move forward planner": "planner"}


def readme_lengths(readmes: dict[str, Path], media: dict[str, dict]) -> None:
    """A length a README gives for a walkthrough, as "the dashboard (1:53)", must be the film's own.
    Checked only when the films are given (--media), as they are not in git."""
    bad = []
    pat = re.compile(r"\b(" + "|".join(map(re.escape, README_WALKTHROUGHS)) + r") \((\d+:\d\d)\)")
    for repo, path in readmes.items():
        for label, length in pat.findall(path.read_text(encoding="utf-8")):
            name = README_WALKTHROUGHS[label]
            if name in media and media[name]["length"] != length:
                bad.append(f"{repo}/README.md gives the {label} walkthrough as {length}; the film runs {media[name]['length']}")
    if bad:
        raise SiteError("walkthrough lengths:\n  " + "\n  ".join(bad))


def landing_values(radar: Path, ta_dist: Path, states: dict) -> dict[str, object]:
    s = json.loads((radar / "demo" / "radar" / "summary.json").read_text(encoding="utf-8"))[0]
    cost = {r["measure"]: r for r in json.loads((radar / "demo" / "radar" / "cost.json").read_text(encoding="utf-8"))}
    cases = cost["Cases with a lead before the first public action"]
    ever = cost["Series a lead at some run, Jan 2022 to Aug 2026"]
    caseload = json.loads((ta_dist / "data" / "caseload.json").read_text(encoding="utf-8"))
    tests = json.loads((radar / "demo" / "radar" / "tests.json").read_text(encoding="utf-8"))
    # Hits shown whose lead had stopped by the day of the action, as the walkthrough counts them.
    stopped = sum(1 for t in tests if t.get("shown") is not False and str(t.get("run2_on_the_day") or "").startswith("no, stopped"))
    fmt = lambda n: f"{int(n):,}"  # noqa: E731
    words = lambda n: ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"][n] if n < 10 else fmt(n)  # noqa: E731
    commit = lambda k: states[k]["commit"] + (", with uncommitted changes" if states[k]["dirty"] else "")  # noqa: E731
    return {
        "RUN_LABEL": s["run_label"], "UK_DATA_TO": s["uk_data_to"], "LEADS": fmt(s["leads"]), "WATCH": fmt(s["watch"]),
        "SERIES": fmt(s["series"]), "CORRIDORS": fmt(s["corridors"]), "CODES": fmt(s["codes"]),
        "LEADS_SHOWN": fmt(s["leads_shown"]), "LEADS_HELD": fmt(s["leads_held"]),
        "DISPLAY_MIN_GBP": fmt(s["display_min_gbp"]), "DISPLAY_MIN_MONTHS": fmt(s["display_min_months"]),
        "CASES_HIT": fmt(cases["run2"]), "CASES": fmt(cases["of"]), "CASES_HIT_RUN1": fmt(cases["run1"]),
        "CASES_STOPPED": words(stopped),
        "EVER_LEAD": fmt(ever["run2"]), "EVER_OF": fmt(ever["of"]), "EVER_LEAD_RUN1": fmt(ever["run1"]),
        "CASELOAD": fmt(len(caseload["records"])),
        "BUILT_ON": long_date(max(v["date"] for v in states.values())),
        "RADAR_COMMIT": commit("diversion-radar"), "TA_COMMIT": commit("ta-market"), "FDCORE_COMMIT": commit("fd-core"),
    }


# ------------------------------------------------------------------ CSP and headers

SCRIPT = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.S | re.I)


def inline_scripts(page: str) -> list[str]:
    out = []
    for m in SCRIPT.finditer(page):
        attrs, body = m.group(1), m.group(2)
        if re.search(r"\bsrc\s*=", attrs, re.I):
            if body.strip():
                raise SiteError("a script with src also has inline code")
            continue
        typ = re.search(r"""\btype\s*=\s*["']?([^"'\s>]+)""", attrs, re.I)
        if typ and typ.group(1).lower() not in ("text/javascript", "application/javascript", "module"):
            continue                    # a data block, which never runs
        out.append(body)
    return out


def csp_for(page: str) -> str:
    bodies = inline_scripts(page)
    has_src = any(re.search(r"\bsrc\s*=", m.group(1), re.I) for m in SCRIPT.finditer(page))
    hashes = sorted({"'sha256-" + base64.b64encode(hashlib.sha256(b.encode("utf-8")).digest()).decode() + "'" for b in bodies})
    script = " ".join((["'self'"] if has_src else []) + hashes) or "'none'"
    return ("default-src 'self'; script-src " + script + "; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def headers_file(csp: dict[str, str]) -> str:
    lines = ["# Written by scripts/build_site.py. One rule matches every path; each page's own rule adds its",
             "# Content-Security-Policy, so no header is set by two rules for the same path.", "/*"]
    lines += [f"  {k}: {v}" for k, v in COMMON_HEADERS]
    for path in sorted(csp):
        lines += [path, f"  Content-Security-Policy: {csp[path]}"]
    return "\n".join(lines) + "\n"


def parse_headers(text: str) -> list[tuple[str, list[tuple[str, str]]]]:
    rules: list[tuple[str, list[tuple[str, str]]]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw.startswith((" ", "\t")):
            rules.append((raw.strip(), []))
        else:
            k, _, v = raw.strip().partition(":")
            rules[-1][1].append((k.strip(), v.strip()))
    return rules


def headers_for(rules, path: str) -> dict[str, str]:
    """The headers Netlify would send for a path, raising if two matching rules set the same one."""
    out: dict[str, str] = {}
    for pat, hs in rules:
        if pat == path or (pat.endswith("/*") and (path + "/").startswith(pat[:-1])) or pat == "/*":
            for k, v in hs:
                if k in out:
                    raise SiteError(f"_headers: {k} is set twice for {path}")
                out[k] = v
    return out


# ------------------------------------------------------------------ checks

def text_files(files: dict[str, bytes]) -> dict[str, str]:
    out = {}
    for rel, data in files.items():
        if Path(rel).suffix.lower() in TEXT_SUFFIXES and b"\x00" not in data[:8192]:
            out[rel] = data.decode("utf-8")
    return out


def council_names(ta: Path) -> set[str]:
    import pandas as pd
    p1, p2 = ta / "data" / "processed" / "ta1_wide.csv", ta / "data" / "processed" / "ro4_wide.csv"
    if not (p1.exists() and p2.exists()):
        raise SiteError("ta-market's processed tables (data/processed/ta1_wide.csv, ro4_wide.csv) are missing, so the council check cannot run")
    ta1, ro4 = pd.read_csv(p1), pd.read_csv(p2)
    return {n for n in set(ta1[ta1.level == "council"].name.dropna()) | set(ro4.la_name.dropna()) if len(n) > 3}


def check_external(rel: str, text: str) -> list[str]:
    bad = []
    if rel.endswith(".html"):
        for tag, attr in (("script", "src"), ("img", "src"), ("source", "src"), ("audio", "src"), ("video", "src")):
            for m in re.finditer(rf"<{tag}\b[^>]*\b{attr}\s*=\s*[\"']?([^\"'\s>]+)", text, re.I):
                if re.match(r"[a-z][a-z0-9+.-]*:|//", m.group(1), re.I) and not m.group(1).startswith("data:"):
                    bad.append(f"{rel}: <{tag}> from another site ({m.group(1)})")
        for m in re.finditer(r"<link\b[^>]*>", text, re.I):
            href = re.search(r"""\bhref\s*=\s*["']?([^"'\s>]+)""", m.group(0), re.I)
            if href and re.match(r"[a-z][a-z0-9+.-]*:|//", href.group(1), re.I):
                bad.append(f"{rel}: <link> to another site ({href.group(1)})")
        for tag in ("iframe", "object", "embed", "frame"):
            if re.search(rf"<{tag}\b", text, re.I):
                bad.append(f"{rel}: <{tag}>")
        outside = SCRIPT.sub("", text)
        for m in re.finditer(r"<[a-zA-Z][^>]*\son[a-z]+\s*=", outside):
            bad.append(f"{rel}: an inline event handler, which the CSP would block ({m.group(0)[:60]})")
        if re.search(r"""href\s*=\s*["']?\s*javascript:""", outside, re.I):
            bad.append(f"{rel}: a javascript: link")
    if rel.endswith((".css", ".html")):
        for m in re.finditer(r"""@import\s+(?:url\()?["']?([^"')\s;]+)|url\(\s*["']?((?:https?:)?//[^"')\s]+)""", text, re.I):
            u = m.group(1) or m.group(2)
            if u and re.match(r"(?:https?:)?//", u, re.I):
                bad.append(f"{rel}: CSS from another site ({u})")
    if rel.endswith((".js", ".mjs", ".html")):
        for m in re.finditer(r"""\b(?:fetch|import|EventSource|WebSocket|sendBeacon)\s*\(\s*["'`]((?:https?:|wss?:)?//[^"'`]+)""", text):
            bad.append(f"{rel}: a request to another site ({m.group(1)})")
    return bad


def check_display_rule(files: dict[str, str]) -> list[str]:
    import build_share as B
    held = B.held_back_series(ROOT)
    out = []
    pats = B.series_patterns(held)
    for rel, text in files.items():
        if not rel.startswith(("radar/", "workspace/")) or rel in PINNED:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for what, p in pats:
                if p.search(line):
                    out.append(f"{rel}:{i}: names a series the display rule holds back ({what})")

    def rows(rel):
        return json.loads(files[rel]) if rel in files else []

    for rel in ("radar/data/leads.json", "workspace/data/leads.json"):
        for r in rows(rel):
            if (r["country"], str(r["code"])) in held:
                out.append(f"{rel}: a held-back series is listed ({r['series']})")
    for rel in ("radar/data/history.json", "workspace/data/history.json"):
        for r in rows(rel):
            if tuple(r["series"].rsplit(" ", 1)) in held:
                out.append(f"{rel}: a held-back series has a history ({r['series']})")
            if not r["shown"] and r.get("uk_trailing12_gbp") is not None:
                out.append(f"{rel}: a run not shown carries a UK figure ({r['series']} {r['run']})")
    for r in rows("workspace/data/signals.json"):
        if (r["country"], str(r["code"])) in held and set(r.get("uk") or {}) - {"shown", "status"}:
            out.append(f"workspace/data/signals.json: a held-back series carries UK figures ({r['country']} {r['code']})")
        if (r.get("uk") or {}).get("shown") is False and set(r["uk"]) - {"shown", "status"}:
            out.append(f"workspace/data/signals.json: a series not shown carries UK figures ({r['country']} {r['code']})")
        # A series not shown carries nothing from the radar on either side, so a held-back lead
        # cannot be told apart from the other series not shown on any field (N7).
        if (r.get("uk") or {}).get("shown") is False and (r.get("onward") or {}) != {"shown": False, "status": "not shown (display rule)"}:
            out.append(f"workspace/data/signals.json: a series not shown carries onward data ({r['country']} {r['code']})")
        extra = set(r) - {"country", "iso2", "code", "description", "uk_data_to", "uk", "onward"}
        if extra:
            out.append(f"workspace/data/signals.json: unexpected fields {sorted(extra)} ({r['country']} {r['code']})")
    for rel in ("radar/data/summary.json", "workspace/data/summary.json"):
        for r in rows(rel):
            # Splitting the leads by which onward check carries them, beside the display rule's
            # counts, can single out a held-back lead (N7).
            if any("run1_rule" in k or "monthly_only" in k or "annual_only" in k for k in r):
                out.append(f"{rel}: the summary splits the leads by onward check")
    for rel in ("radar/data/tests.json", "workspace/data/tests.json"):
        for t in rows(rel):
            if t.get("shown") is False and t.get("corridor"):
                out.append(f"{rel}: a test under the display rule gives its route ({t['test_id']})")
            if t.get("shown") is False:
                if any(t.get(f"{k}_first_lead") for k in ("run1", "run2")) or any(t.get(f"{k}_lead_time_months") is not None for k in ("run1", "run2")) \
                        or any(t.get(f"{k}_outcome") in ("hit", "miss", "watch only") for k in ("run1", "run2")) or t.get("run2_on_the_day") not in (None, "", "n/a"):
                    out.append(f"{rel}: a test under the display rule carries a result ({t['test_id']})")
    for rel, text in files.items():
        if rel.startswith("workspace/data/briefs/") and rel.endswith(".json") and not rel.endswith("index.json"):
            b = json.loads(text)
            key = (b.get("country") or (b.get("lead") or {}).get("country"), str(b.get("code") or (b.get("lead") or {}).get("code")))
            if key in held:
                out.append(f"{rel}: a brief for a held-back series")
    return out


def screen(files: dict[str, str], sources: dict[str, tuple[str, str]], policies: dict[str, list], site_policy: list, deny: list[str]) -> list[str]:
    from fdcore.guardrails import scan_text
    out = []
    for rel, text in sorted(files.items()):
        if rel in PINNED:
            continue
        skip: set[str] = set()
        if rel in sources:
            repo, src = sources[rel]
            for g, c in policies.get(repo, []):
                if fnmatch(src, g):
                    skip |= c
        for g, c in site_policy:
            if fnmatch(rel, g):
                skip |= c
        for f in scan_text(text, rel, deny, skip):
            out.append(f"{rel}:{f.line}: fd-core screen: {f.kind}")
    return out


def check_links(files: dict[str, bytes]) -> list[str]:
    out = []
    names = set(files)
    for rel, data in files.items():
        if not rel.endswith(".html"):
            continue
        text = data.decode("utf-8")
        base = Path(rel).parent
        for m in re.finditer(r"""<(?:a|link|script)\b[^>]*\b(?:href|src)\s*=\s*["']([^"'#?]*)""", SCRIPT.sub(lambda s: s.group(0) if re.search(r"\bsrc\s*=", s.group(1)) else "", text), re.I):
            u = m.group(1)
            if not u or re.match(r"[a-z][a-z0-9+.-]*:|//", u, re.I):
                continue
            target = (Path(u.lstrip("/")) if u.startswith("/") else base / u)
            parts = []
            for p in target.as_posix().split("/"):
                if p == "..":
                    if parts:
                        parts.pop()
                elif p not in ("", "."):
                    parts.append(p)
            t = "/".join(parts)
            if u.endswith("/") or t == "":
                t = (t + "/index.html").lstrip("/")
            if t not in names:
                out.append(f"{rel}: a link to {u}, which is not in the site")
    return out


def check_ogl(files: dict[str, bytes]) -> list[str]:
    out = []
    for rel in ("index.html", "radar/index.html", "workspace/index.html", "ta/index.html", "planner/index.html"):
        text = files[rel].decode("utf-8")
        if OGL_TEXT not in text or OGL_URL not in text:
            out.append(f"{rel}: no Open Government Licence line and link")
    return out


# ------------------------------------------------------------------ monitoring items

OPEN_TERMS = "Open Government Licence"
# The terms pages known to put their content under the Open Government Licence: the licence itself,
# GOV.UK's terms and legislation.gov.uk's. A source counts as open only when its note says so and
# its terms page is one of these, so free text alone cannot pass an item.
OPEN_TERMS_PAGES = ("https://www.nationalarchives.gov.uk/doc/open-government-licence/",
                    "https://www.gov.uk/help/terms-conditions",
                    "https://www.legislation.gov.uk/help")
MONITOR = "data/monitor.json"


def open_licence_only(items: bytes, sources: bytes) -> tuple[bytes, int]:
    """The monitoring items a public site may carry: those whose source is under the Open Government
    Licence. Items from sources whose terms reserve all rights or forbid commercial use stay in the
    workspace for internal monitoring and are left off the site until permission is recorded
    (data/SOURCES.md). Returns the kept items and how many were left off."""
    open_ids = {s["id"] for s in json.loads(sources)["sources"]
                if str(s.get("terms_note", "")).startswith(OPEN_TERMS) and str(s.get("terms_url", "")).startswith(OPEN_TERMS_PAGES)}
    every = json.loads(items)
    keep = [i for i in every if i["source"] in open_ids]
    return (json.dumps(keep, ensure_ascii=False, indent=1) + "\n").encode("utf-8"), len(every) - len(keep)


def patched_manifest(raw: bytes, patched: dict[str, str], left_off: int) -> bytes:
    """The manifest copy for the site: the same, with the hash of each file the site changed."""
    doc = json.loads(raw)
    m = doc[0] if isinstance(doc, list) else doc
    for rel, h in patched.items():
        m["files"][rel] = h
    if patched:
        m["site_copy"] = {"changed": sorted(patched), "monitor_items_left_off": left_off,
                          "why": "their sources have no open licence, so they stay internal"}
    return (json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


# ------------------------------------------------------------------ build

def build(radar: Path, ta: Path, fdcore: Path, clean: bool, media_dir: Path | None = None) -> tuple[dict[str, bytes], dict]:
    states = {"diversion-radar": repo_state(radar), "ta-market": repo_state(ta), "fd-core": repo_state(fdcore)}
    if clean and any(v["dirty"] for v in states.values()):
        raise SiteError("--clean: these repos have uncommitted changes: " + ", ".join(k for k, v in states.items() if v["dirty"]))

    # The planner, built by ta-market's own script from its committed page.
    py = sys.executable
    r = subprocess.run([py, "scripts/build_app.py", "--check"], cwd=ta, capture_output=True, text=True)
    if r.returncode:
        raise SiteError("ta-market: " + (r.stdout + r.stderr).strip())
    r = subprocess.run([py, "scripts/build_app.py"] + (["--clean"] if clean else []), cwd=ta, capture_output=True, text=True)
    if r.returncode:
        raise SiteError("ta-market: " + (r.stdout + r.stderr).strip())
    ta_dist = ta / "app" / "dist"
    ta_manifest = json.loads((ta_dist / "data" / "manifest.json").read_text(encoding="utf-8"))
    if clean and (ta_manifest["source_dirty"] or ta_manifest["source_commit"] != states["ta-market"]["commit"]):
        raise SiteError("ta-market: app/dist was not built from its committed HEAD")
    if ta_manifest.get("fdcore_commit") != states["fd-core"]["commit"]:
        raise SiteError(f"ta-market: the planner's screen patterns come from fd-core {ta_manifest.get('fdcore_commit')}, not {states['fd-core']['commit']}")

    # The workspace, as built and committed in this repo.
    r = subprocess.run([py, "scripts/build_app_page.py", "--check"], cwd=radar, capture_output=True, text=True)
    if r.returncode:
        raise SiteError("diversion-radar: " + (r.stdout + r.stderr).strip())
    ws_manifest = json.loads((radar / "app" / "data" / "manifest.json").read_text(encoding="utf-8"))[0]
    if clean and ws_manifest["source_dirty"]:
        raise SiteError("diversion-radar: app/data was built from inputs that were not committed")

    files: dict[str, bytes] = {}
    sources: dict[str, tuple[str, str]] = {}      # site path -> (repo, path in that repo), for the screen's policies
    pages: dict[str, dict] = {}

    def put(rel: str, data: bytes, repo: str | None = None, src: str | None = None) -> None:
        if rel in files:
            raise SiteError(f"{rel} written twice")
        files[rel] = data
        if repo:
            sources[rel] = (repo, src)

    # Landing page, assets, vendor, and the walkthroughs if given.
    media_files, media = read_media(media_dir)
    readme_lengths({"diversion-radar": radar / "README.md", "ta-market": ta / "README.md"}, media)
    template = watch_links((SITE / "index.html").read_text(encoding="utf-8"), media)
    put("index.html", fill(template, landing_values(radar, ta_dist, states)).encode("utf-8"))
    for rel, data in media_files.items():
        put(rel, data)
    put("404.html", NOT_FOUND.encode("utf-8"))
    # Kept out of search by noindex, in every page's head and in _headers. Crawling stays allowed:
    # a crawler that robots.txt turns away never sees the noindex, and a page linked from elsewhere
    # can then still be listed (Google Search Central, "Block Search indexing with noindex").
    put("robots.txt", b"User-agent: *\nAllow: /\n")
    for name in ("assets/site.css", "assets/dash.js", "assets/icon.svg", D3_LICENSE):
        put(name, (SITE / name).read_bytes(), "diversion-radar", f"site/{name}")
    put("favicon.ico", (SITE / "assets" / "favicon.ico").read_bytes(), "diversion-radar", "site/assets/favicon.ico")
    # The two brands' marks, and the fonts the landing page uses, from each repo's brand/ folder;
    # the tools and dashboards carry their brand inline (fdcore.brand).
    put("assets/radar-mark.svg", (radar / "brand" / "mark.svg").read_bytes(), "diversion-radar", "brand/mark.svg")
    put("assets/moveon-mark.svg", (ta / "brand" / "mark.svg").read_bytes(), "ta-market", "brand/mark.svg")
    plex = "ibm-plex-sans-latin-wght-normal.woff2"
    put(f"assets/fonts/{plex}", (radar / "brand" / "fonts" / plex).read_bytes(), "diversion-radar", f"brand/fonts/{plex}")
    put("assets/fonts/OFL.txt", ((radar / "brand" / "fonts" / "OFL.txt").read_text(encoding="utf-8") + "\n\n"
                                 + (ta / "brand" / "fonts" / "OFL.txt").read_text(encoding="utf-8")).encode("utf-8"))
    d3 = (SITE / D3[0]).read_bytes()
    if sha256(d3) != D3[1]:
        raise SiteError(f"site/{D3[0]} does not match its pinned SHA-256")
    put(D3[0], d3, "diversion-radar", f"site/{D3[0]}")
    pages["/"] = {"from": "site/index.html"}

    # The two dashboards.
    for slug, repo, root, frag_rel, title, desc, here, icon in (
        ("radar", "diversion-radar", radar, "demo/radar", "Diversion Radar",
         "Monthly leads where UK exports and onward trade to Russia rose together, with a backtest against published enforcement cases.", "Diversion Radar: dashboard", "radar-mark.svg"),
        ("ta", "ta-market", ta, "demo/ta", "Move forward: market picture",
         "Temporary accommodation in England, council by council, from MHCLG's published statistics. No council is named.", "Move forward: market picture", "moveon-mark.svg"),
    ):
        fragment = (root / frag_rel / "index.html").read_text(encoding="utf-8")
        ids = datasets_read(fragment, f"{repo}/{frag_rel}/index.html")
        note = (f"Static copy: HMRC data to {json.loads((root / frag_rel / 'summary.json').read_text())[0]['uk_data_to']}, "
                f"UN Comtrade as released by {comtrade_read_on(root)}") if slug == "radar" else "Static copy, data as published"
        put(f"{slug}/index.html", dashboard_page(fragment, title, desc, here, ids, note, icon).encode("utf-8"), repo, f"{frag_rel}/index.html")
        for i in ids:
            put(f"{slug}/data/{i}.json", (root / frag_rel / f"{i}.json").read_bytes(), repo, f"{frag_rel}/{i}.json")
        pages[f"/{slug}/"] = {"from": f"{repo}/{frag_rel}/index.html", "datasets": ids}

    # The workspace, unchanged, with every file in its manifest.
    app = radar / "app"
    put("workspace/index.html", wrapped_page((app / "index.html").read_text(encoding="utf-8"), "radar-mark.svg").encode("utf-8"), "diversion-radar", "app/index.html")
    ws_patched, ws_off = {}, 0
    for rel, want in sorted(ws_manifest["files"].items()):
        data = (app / rel).read_bytes()
        if sha256(data) != want:
            raise SiteError(f"diversion-radar: app/{rel} does not match its manifest")
        if rel == MONITOR:
            data, ws_off = open_licence_only(data, (app / "spec" / "monitor_sources.json").read_bytes())
            ws_patched[rel] = sha256(data)
        put(f"workspace/{rel}", data, "diversion-radar", f"app/{rel}")
    put("workspace/data/manifest.json", patched_manifest((app / "data" / "manifest.json").read_bytes(), ws_patched, ws_off),
        "diversion-radar", "app/data/manifest.json")
    pages["/workspace/"] = {"from": "diversion-radar/app/index.html", "manifest_commit": ws_manifest["source_commit"],
                            "monitor_items_left_off": ws_off}

    # The planner, unchanged, with every file in its manifest.
    put("planner/index.html", wrapped_page((ta_dist / "index.html").read_text(encoding="utf-8"), "moveon-mark.svg").encode("utf-8"), "ta-market", "app/index.html")
    ta_patched, ta_off = {}, 0
    for rel, want in sorted(ta_manifest["files"].items()):
        data = (ta_dist / rel).read_bytes()
        if sha256(data) != want:
            raise SiteError(f"ta-market: app/dist/{rel} does not match its manifest")
        if rel == MONITOR:
            data, ta_off = open_licence_only(data, (ta_dist / "spec" / "monitor_sources.json").read_bytes())
            ta_patched[rel] = sha256(data)
        put(f"planner/{rel}", data)
    put("planner/data/manifest.json", patched_manifest((ta_dist / "data" / "manifest.json").read_bytes(), ta_patched, ta_off))
    pages["/planner/"] = {"from": "ta-market/app/dist/index.html", "manifest_commit": ta_manifest["source_commit"],
                          "monitor_items_left_off": ta_off}

    # Headers: each page's CSP, by the SHA-256 of its inline scripts.
    csp = {}
    for path, rel in (("/", "index.html"), ("/index.html", "index.html"), ("/radar/*", "radar/index.html"), ("/ta/*", "ta/index.html"),
                      ("/workspace/*", "workspace/index.html"), ("/planner/*", "planner/index.html")):
        csp[path] = csp_for(files[rel].decode("utf-8"))
    put("_headers", headers_file(csp).encode("utf-8"))

    meta = {"built_by": "scripts/build_site.py", "built_on": long_date(max(v["date"] for v in states.values())), "clean": clean,
            "repos": states, "pages": pages,
            "walkthroughs": {k: dict(v, recorded_by="tests/site/walkthrough.mjs", in_git=False) for k, v in media.items()},
            "files": {k: sha256(v) for k, v in sorted(files.items())},
            "note": "A static demo: no sign-in, no AI calls, nothing sent anywhere. A rise in exports is a lead, not evidence of a breach."}
    put("site.json", (json.dumps(meta, indent=1) + "\n").encode("utf-8"))
    return files, {"sources": sources, "states": states}


def problems(files: dict[str, bytes], sources: dict[str, tuple[str, str]], ta: Path) -> list[str]:
    from fdcore.guardrails import read_policy
    texts = text_files(files)
    out = []
    policies = {"diversion-radar": read_policy(str(ROOT / "config" / "guardrails_policy.txt")),
                "ta-market": read_policy(str(ta / "config" / "guardrails_policy.txt"))}
    site_policy = read_policy(str(SITE / "guardrails_policy.txt"))
    deny = []
    for p in (ROOT / "config" / "deny_list.txt", ta / "config" / "deny_list.txt"):
        if p.exists():
            deny += p.read_text(encoding="utf-8").splitlines()
    out += screen(texts, sources, policies, site_policy, deny)
    names = council_names(ta)
    rx = re.compile(r"(?<![A-Za-z])(?:" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")(?![A-Za-z])")
    for rel, text in texts.items():
        if rel in PINNED:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for phrase in NOT_COUNCILS:
                line = line.replace(phrase, "")
            for m in rx.finditer(line):
                out.append(f"{rel}:{i}: names a council ({m.group(0)})")
    out += check_display_rule(texts)
    for rel, text in texts.items():
        if rel not in PINNED:
            out += check_external(rel, text)
            if NEVER.search(text):
                out.append(f"{rel}: mentions Global Fishing Watch or OpenSanctions")
    out += check_links(files)
    out += check_ogl(files)
    rules = parse_headers(files["_headers"].decode("utf-8"))
    for rel in files:
        path = "/" + rel
        for p in ([path] + ([path[: -len("index.html")]] if path.endswith("index.html") else [])):
            try:
                hs = headers_for(rules, p)
            except SiteError as e:
                out.append(str(e))
                continue
            if rel.endswith(".html") and rel != "404.html" and "Content-Security-Policy" not in hs:
                out.append(f"_headers: no Content-Security-Policy for {p}")
    return out


def write(files: dict[str, bytes], out: Path) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="site-", dir=out.parent))
    try:
        for rel, data in files.items():
            p = tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        if out.exists():
            shutil.rmtree(out)
        tmp.rename(out)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ta", type=Path, default=ROOT.parent / "ta-market", help="the ta-market repo (default ../ta-market)")
    ap.add_argument("--fdcore", type=Path, default=ROOT.parent / "fd-core", help="the fd-core repo (default ../fd-core)")
    ap.add_argument("--out", type=Path, default=SITE / "dist", help="where to write the site (default site/dist, not in git)")
    ap.add_argument("--clean", action="store_true", help="refuse to build unless all three repos are committed as they are")
    ap.add_argument("--check", action="store_true", help="build and run the checks, but write nothing")
    ap.add_argument("--media", type=Path, help="a folder of walkthroughs recorded by tests/site/walkthrough.mjs, to serve under videos/")
    a = ap.parse_args(argv)
    ta, fdcore = a.ta.resolve(), a.fdcore.resolve()
    files, info = build(ROOT, ta, fdcore, a.clean, a.media.resolve() if a.media else None)
    bad = problems(files, info["sources"], ta)
    if bad:
        print("the site would not pass its checks:\n  " + "\n  ".join(bad[:200]) + (f"\n  ... and {len(bad) - 200} more" if len(bad) > 200 else ""))
        return 1
    size = sum(len(v) for v in files.values())
    st = info["states"]
    summary = ", ".join(f"{k} {v['commit']}{' (uncommitted changes)' if v['dirty'] else ''}" for k, v in st.items())
    if a.check:
        print(f"site checks passed: {len(files)} files, {size / 1e6:.1f} MB, from {summary}")
        return 0
    out = a.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    write(files, out)
    rel = out.relative_to(ROOT).as_posix() if out.is_relative_to(ROOT) else str(out)
    print(f"wrote {rel}: {len(files)} files, {size / 1e6:.1f} MB, from {summary}")
    print("Nothing is deployed. Publishing is the owner's decision (site/README.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
