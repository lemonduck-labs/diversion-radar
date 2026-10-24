"""The hosted workspace's code outside the database: the drafting function, the page's stand-in for
claude.use over Supabase, and the hosted build.

- The draft-brief function's logic (supabase/functions/draft-brief/core.mjs), with Claude and the
  database mocked: a passing draft is screened, recorded and returned with the page's SHA-256; a
  draft that fails is recorded and never returned, and a deny-list name never comes back; only a
  signed-in Contributor or above drafts, only a file of its own build, within the hourly cap, with
  a deny list and the same prompt as the page; the reviewer notes are the page's own, from the
  database; the key goes only to the Messages API.
- fd-core's screen as the function runs it: the same findings as fd-core's own scan_text.
- app/src/hosted.js, with a fake Supabase client, driven through the page's own store code
  (app/src/page.js): every record path maps to its table; nothing the page sends as an author,
  actor or time reaches the database; reads come back in the page's shapes and time format;
  errors come back as the codes the page knows; drafting goes to the function; lessons are refused.
- scripts/build_hosted.py: the site holds the page unchanged, loads only the pinned, hash-checked
  Supabase client, has a Content-Security-Policy that allows exactly its own inline code, holds
  the reviewed data files, takes only a publishable key, and comes with a function bundle of the
  same build, whose prompt for every file is the page's, and whose deny list never reaches the site.
- With Deno installed, index.ts is type-checked and runs end to end against a faked project and a
  faked Claude.
- With Playwright, its Chromium and a copy of the pinned Supabase client (DR_SUPABASE_UMD or
  TA_SUPABASE_UMD), the hosted site runs in a real browser under its own Content-Security-Policy
  against a faked project: two people sign in with an emailed code and take a brief through the
  template, a Claude draft, a stopped draft, submission, approval and an export
  (tests/hosted_browser_check.mjs).

The JavaScript tests need node and are skipped without it. A rise in exports is a lead, not
evidence of a breach.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from radar.brief.fake_llm import FAKE_ANSWER, fake_draft

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
DENO = os.environ.get("DR_DENO") or shutil.which("deno")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")
APP = ROOT / "app"
URL = "https://abcdefghijklmnopqrst.supabase.co"
KEY = "sb_publishable_" + "k" * 32
DENY_TERM = "zzq" + "placeholder"
NOTE = {"id": "review-1", "kind": "returned", "at": "2026-10-21", "text": "Say which onward check carries the lead."}

_spec = importlib.util.spec_from_file_location("build_hosted", ROOT / "scripts" / "build_hosted.py")
build_hosted = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_hosted)

SUITE = [
    "function: a passing draft is screened, recorded and returned",
    "function: a draft with judging wording is refused and never returned",
    "function: a deny-list name is caught, from the bundle and from the secret, and never echoed",
    "function: the screen is the reference screen, the shared rules and then fd-core",
    "function: a reply that is not one JSON object, is cut off or is declined fails",
    "function: the caller must be a signed-in Contributor or above",
    "function: only a file in its own build is drafted, and the page must prove its prompt",
    "function: it stops before calling Claude without a key, over the hourly cap, without a deny list or on a different build",
    "function: Claude's errors become retry or set-up answers, and an unrecorded draft is not returned",
    "function: CORS and methods",
    "function: its canon, safe details and words are the page's",
    "function: reviewer notes come from the database, reach Claude apart from the facts, and the draft must answer them",
    "function: an approval that counts starts the notes again, as the page's own reviewNotes decides",
    "function: a note the deny list would hold back is not sent, and notes that cannot be read stop the draft",
    "hosted: every page path maps to its table, and others are refused",
    "hosted: the user capability gives each role what the page expects",
    "hosted: nobody outside the members table gets a store",
    "hosted: the page's own store code saves a brief, moves the pointer and records an export through the tables",
    "hosted: decisions, checks, the setting and private drafts go to their tables with no who or when",
    "hosted: follow-ups go to public.tasks with no who or when, and read back in the page's shape",
    "hosted: outcomes and end-use records go to their tables with no who or when; an approval is a flag",
    "hosted: a monitoring decision goes to its table with no who or when, grade or reason by the decision",
    "hosted: a case outcome and its decision go to the same tables, in the page's shapes",
    "hosted: lessons are refused, since the hosted version has none yet",
    "hosted: the audit log is read per person, newest first, in the page's words",
    "hosted: long tables are read past the 1,000-row page",
    "hosted: errors reach the page as the codes it knows",
    "hosted: one live channel, and a change refreshes only the watches it touches",
    "hosted: drafting goes to the function with the file's slug and the prompt's SHA-256",
    "hosted: the page's prompt for every file reaches the function's own logic as the same prompt",
    "hosted: downloads hand the page's file to the browser",
    "hosted: the build's placeholders are not taken for a project",
]


def _contexts() -> dict:
    out = {}
    for e in json.loads((APP / "data" / "briefs" / "index.json").read_text(encoding="utf-8"))["series"]:
        out[e["slug"]] = json.loads((APP / "data" / "briefs" / e["file"]).read_text(encoding="utf-8"))
    return out


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory) -> Path:
    """What the node suite needs from Python: fd-core's patterns, and the page's template brief for
    every file (radar/brief/fake_llm.py's fake_draft), without notes and answering one note."""
    ctxs = _contexts()
    p = tmp_path_factory.mktemp("fixtures") / "fixtures.json"
    p.write_text(json.dumps({"fdcore": build_hosted.fdcore_patterns(), "deny_term": DENY_TERM,
                             "drafts": {s: fake_draft(c) for s, c in ctxs.items()},
                             "answered": {s: fake_draft(c, [NOTE], FAKE_ANSWER) for s, c in ctxs.items()}}), encoding="utf-8")
    return p


@pytest.fixture(scope="module")
def suite(fixtures):
    out = subprocess.run([NODE, str(ROOT / "tests" / "hosted_js_run.mjs"), "suite", str(ROOT), str(fixtures)], capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-3000:]
    return {r["name"]: r for r in json.loads(out.stdout)["results"]}


@needs_node
@pytest.mark.parametrize("name", SUITE)
def test_node_suite(suite, name):
    assert name in suite, f"the check did not run: {name}"
    assert suite[name]["ok"], suite[name].get("error")


@needs_node
def test_the_suite_has_no_check_this_file_does_not_list(suite):
    assert sorted(suite) == sorted(SUITE)


# ============================================================== fd-core's screen, as the function runs it

def _awkward_texts() -> list[str]:
    """Text that tests fd-core's screen. It is put together here so that the repository's own
    screen, which reads this file, never sees a phone number, an address or a judging word."""
    j = "".join
    phone, intl = j(["020", " 7946", " 0958"]), j(["+44", " 20", " 7946", " 0958"])
    email, allowed = "@".join(["ops", "zzq-test.example"]), "@".join(["noreply", "anthropic.com"])
    firm, firm2, firm3 = j(["Zzq Holdings ", "Ltd"]), j(["Zzqvel ", "OOO"]), j(["Zzq & Sons ", "Co."])
    pc = j(["SW1A", " 1AA"])
    w = {k: j(v) for k, v in {"div": ["di", "verted"], "eva": ["eva", "ded"], "smu": ["smug", "gled"], "fai": ["fail", "ing"],
                              "mis": ["misman", "aged"], "bre": ["breach", "ed"]}.items()}
    arabic = j(chr(0x660 + int(c)) for c in "0207" + "9460958")
    wide = j(chr(0xFF10 + int(c)) for c in "12345" + "678901")
    nbsp, smile, ls = chr(0xA0), chr(0x1F600), chr(0x2028)
    return [
        f"Call {phone} or {intl} today.",
        "Ref 1086532.3333333333 and SHA a0427129176 and 3528945012.5",
        f"Write to {email} or {allowed}.",
        f"Ship to {firm} and {firm2}; also {firm3} now",
        f"Postcode {pc} and #e4e3df colour and {pc.lower().replace(' ', '')}",
        f"The goods were {w['div']} and the buyer {w['eva']} checks.",
        f"This is not evidence of a breach; it was {w['div']}, but they {w['smu']} nothing.",
        "A rise in exports is a lead, not evidence of a breach.",
        f"Ask {DENY_TERM.upper()} about it, and {DENY_TERM} and the a.b+c desk too.",
        f"Digits {arabic} in Arabic-Indic, and full width {wide}.",
        j([chr(0xD6), "lmaz Trading ", "Ltd und Stra", chr(0xDF), "e M", chr(0xFC), "ller ", "GmbH"]),
        f"Caf{chr(233)} SW1A{nbsp}1AA and 020{nbsp}7946{nbsp}0958 with spaces that do not break",
        f"{smile * 2} they {w['bre']} the rules, {smile} possible breach noted",
        f"line one{ls}{w['eva']} line two{chr(0x1C)}not evidence of a breach {w['eva']}",
        f"worst case, the {w['fai']} route was {w['mis']} badly",
        " ".join(["1986", "2020", "19998887776", "2099887766", j(["12345", "67890"])]),
        " ".join(["values", "854231", "854232", "and", "8542.31"]),
    ]


@needs_node
def test_the_functions_port_of_fd_core_finds_what_fd_core_finds(tmp_path):
    """core.mjs runs fd-core's guardrails screen in JavaScript, as radar/brief/screen.py runs it in
    Python, with Python's Unicode reading of the patterns: the same findings on every text. For
    judging words the port reports the word, never the line, which fd-core quotes."""
    from fdcore.guardrails import scan_text
    texts = _awkward_texts()
    deny = [DENY_TERM, "  Zzqvel Trading  ", "# a comment", "a.b+c"]
    src = tmp_path / "cases.json"
    src.write_text(json.dumps({"fdcore": build_hosted.fdcore_patterns(), "texts": texts, "deny": deny}), encoding="utf-8")
    out = subprocess.run([NODE, str(ROOT / "tests" / "hosted_js_run.mjs"), "fdcore", str(ROOT), str(src)], capture_output=True, text=True, check=True)
    got = json.loads(out.stdout)
    word = lambda kind, text: re.match(r"^'(.*?)' in:", text).group(1) if kind == "accusing language" else text  # noqa: E731
    want = [[[f.kind, word(f.kind, f.text)] for f in scan_text(t, "x", deny)] for t in texts]
    assert got == want
    kinds = {k for row in want for k, _ in row}
    assert kinds == {"company name", "email address", "UK postcode", "phone number", "deny-list name", "accusing language"}


# ============================================================== the hosted build

@pytest.fixture(scope="module")
def deny_file(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("deny") / "deny_list.txt"
    p.write_text(f"# test list\n{DENY_TERM}\n\n", encoding="utf-8")
    return p


@pytest.fixture(scope="module")
def hosted(tmp_path_factory, deny_file):
    base = tmp_path_factory.mktemp("hosted")
    site, bundle = base / "site", base / "fn" / "_bundle"
    assert build_hosted.main(["--supabase-url", URL + "/", "--publishable-key", KEY, "--out", str(site), "--bundle-out", str(bundle),
                              "--deny-list", str(deny_file)]) == 0
    return site, bundle


def _script(html: str, name: str) -> str:
    begin, end = f"/* BEGIN {name} */", f"/* END {name} */"
    return html[html.index(begin): html.index(end) + len(end)]


def test_the_hosted_site_holds_the_page_unchanged(hosted):
    site, _ = hosted
    html = (site / "index.html").read_text(encoding="utf-8")
    page = (APP / "index.html").read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>\n<html lang=\"en-GB\">")
    for name in ["fd-core/memory.mjs", "fd-core/shell.mjs", "src/screen.js", "src/page.js"]:
        assert _script(html, name) == _script(page, name), name
    style = re.search(r"<style>.*?</style>", page, re.S).group(0)
    body = page[page.index("</style>") + len("</style>"):page.index("<script>")].strip("\n")
    assert style in html and body in html and html.index(style) < html.index("</head>") < html.index(body)
    assert (APP / "src" / "hosted.js").read_text(encoding="utf-8").rstrip() in html
    config = json.loads(re.search(r"window\.DR_HOSTED_CONFIG = (\{.*?\});", html).group(1))
    assert config == {"url": URL, "anonKey": KEY}
    # One script from another site: the Supabase client at its exact version, checked by its hash.
    srcs = re.findall(r"<script\b[^>]*\bsrc=\"([^\"]+)\"[^>]*>", html)
    assert srcs == [build_hosted.SUPABASE_JS["url"]]
    assert re.fullmatch(r"https://cdn\.jsdelivr\.net/npm/@supabase/supabase-js@\d+\.\d+\.\d+/dist/umd/supabase\.js", srcs[0])
    assert f'integrity="{build_hosted.SUPABASE_JS["integrity"]}" crossorigin="anonymous"' in html
    assert re.fullmatch(r"sha384-[A-Za-z0-9+/]{64}", build_hosted.SUPABASE_JS["integrity"])
    assert not re.search(r"<link\b|@import|url\(\s*['\"]?\s*https?:", html, re.I)
    # In order: the client, the settings, the stand-in, then the page's own code.
    order = [html.index(srcs[0]), html.index("window.DR_HOSTED_CONFIG"), html.index("/* app/src/hosted.js */"),
             html.index("/* BEGIN fd-core/memory.mjs */"), html.index("/* BEGIN src/page.js */")]
    assert order == sorted(order)
    assert html.count("<title>") == 1 and html.index("<title>") < html.index("</head>")


def test_the_hosted_site_holds_the_reviewed_data(hosted):
    site, _ = hosted
    m = json.loads((APP / "data" / "manifest.json").read_text(encoding="utf-8"))[0]
    for path, sha in m["files"].items():
        assert hashlib.sha256((site / path).read_bytes()).hexdigest() == sha, path
    assert (site / "data" / "manifest.json").read_bytes() == (APP / "data" / "manifest.json").read_bytes()
    served = sorted(p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file())
    assert served == sorted([*m["files"], "data/manifest.json", "index.html", "_headers", "robots.txt", "hosted.json"])
    # Every file the page asks for is there.
    src = (APP / "src" / "page.js").read_text(encoding="utf-8")
    names = re.search(r"const names = \[([^\]]*)\]", src).group(1)
    for n in re.findall(r"'([a-z_]+)'", names):
        assert (site / "data" / f"{n}.json").is_file(), n
    for p in re.findall(r"get(?:Text|JSON)\('((?:spec|data)/[^']+)'\)", src):
        assert (site / p).is_file(), p
    rec = json.loads((site / "hosted.json").read_text())
    assert (rec["target"], rec["configured"], rec["supabase_url"], rec["supabase_js"]) == ("hosted", True, URL, build_hosted.SUPABASE_JS)
    assert rec["hosted_page_sha256"] == hashlib.sha256((site / "index.html").read_bytes()).hexdigest()
    assert rec["data_commit"] == m["source_commit"] and rec["run"] == m["run"]
    assert (site / "robots.txt").read_text() == "User-agent: *\nDisallow: /\n"


def test_the_content_security_policy_allows_exactly_the_pages_own_code(hosted):
    site, _ = hosted
    html = (site / "index.html").read_text(encoding="utf-8")
    headers = (site / "_headers").read_text(encoding="utf-8")
    csp = re.search(r"Content-Security-Policy: (.*)", headers).group(1)
    d = {part.split()[0]: part.split()[1:] for part in (p.strip() for p in csp.split(";")) if part}
    h = lambda t: "'sha256-" + base64.b64encode(hashlib.sha256(t.encode("utf-8")).digest()).decode() + "'"  # noqa: E731
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    styles = re.findall(r"<style>(.*?)</style>", html, re.S)
    assert len(scripts) == 4 and len(styles) == 2
    assert d["script-src"] == [h(t) for t in scripts] + [build_hosted.SUPABASE_JS["url"]]
    # The page's fixed style attributes, by hash, and nothing else inline.
    attrs = sorted(set(re.findall(r"\bstyle: '([^']*)'", (APP / "src" / "page.js").read_text(encoding="utf-8"))))
    assert len(attrs) >= 1
    # The one style element fd-core's shell adds when it mounts, by the hash of its exact text.
    shell = build_hosted.shell_css(html)
    assert shell.lstrip().startswith(".fs {") and "fd-shell-css" in html
    assert d["style-src"] == [h(t) for t in styles] + [h(shell)] + ["'unsafe-hashes'"] + [h(t) for t in attrs]
    host = URL.split("://")[1]
    assert d["connect-src"] == ["'self'", f"https://{host}", f"wss://{host}"]
    assert d["default-src"] == ["'none'"] and d["frame-ancestors"] == ["'none'"] and d["base-uri"] == ["'none'"] and d["object-src"] == ["'none'"]
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    assert "X-Content-Type-Options: nosniff" in headers and "Referrer-Policy: no-referrer" in headers and "X-Robots-Tag: noindex, nofollow" in headers


def test_without_settings_the_build_writes_placeholders(tmp_path, deny_file):
    site = tmp_path / "site"
    assert build_hosted.main(["--supabase-url", "", "--publishable-key", "", "--out", str(site), "--bundle-out", str(tmp_path / "b"),
                              "--deny-list", str(deny_file)]) == 0
    html = (site / "index.html").read_text(encoding="utf-8")
    config = json.loads(re.search(r"window\.DR_HOSTED_CONFIG = (\{.*?\});", html).group(1))
    assert config == {"url": build_hosted.URL_PLACEHOLDER, "anonKey": build_hosted.KEY_PLACEHOLDER}
    assert json.loads((site / "hosted.json").read_text())["configured"] is False


def _jwt(payload: dict) -> str:
    seg = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()  # noqa: E731
    return f"{seg({'alg': 'HS256', 'typ': 'JWT'})}.{seg(payload)}.{'s' * 43}"


def test_the_build_takes_only_a_publishable_key_and_an_https_project_url(tmp_path):
    bad_keys = ["sb_secret_" + "k" * 32, _jwt({"role": "service_role", "iss": "supabase"}), _jwt({"role": "authenticated"}), "not-a-key"]
    for i, key in enumerate(bad_keys):
        with pytest.raises(SystemExit) as e:
            build_hosted.main(["--supabase-url", URL, "--publishable-key", key, "--out", str(tmp_path / f"s{i}"), "--bundle-out", str(tmp_path / f"b{i}")])
        assert "publishable" in str(e.value), key
        assert not (tmp_path / f"s{i}").exists()
    for i, url in enumerate(["http://abcdefghijklmnopqrst.supabase.co", URL + "/rest/v1", "abcdefghijklmnopqrst.supabase.co"]):
        with pytest.raises(SystemExit, match="https URL"):
            build_hosted.main(["--supabase-url", url, "--publishable-key", KEY, "--out", str(tmp_path / f"u{i}"), "--bundle-out", str(tmp_path / f"v{i}")])
    assert build_hosted.check_public_key(_jwt({"role": "anon", "iss": "supabase"})).count(".") == 2
    assert build_hosted.check_public_key(KEY) == KEY


def test_the_build_never_clears_a_folder_it_did_not_write(tmp_path):
    mine = tmp_path / "mine"
    mine.mkdir()
    (mine / "notes.txt").write_text("keep me")
    with pytest.raises(SystemExit, match="left alone"):
        build_hosted.main(["--out", str(mine), "--bundle-out", str(tmp_path / "b")])
    assert (mine / "notes.txt").read_text() == "keep me"


def test_the_build_refuses_a_page_or_data_out_of_step(tmp_path, monkeypatch):
    page = (APP / "index.html").read_text(encoding="utf-8")
    stale = tmp_path / "index.html"
    stale.write_text(page.replace("/* BEGIN src/page.js */\n", "/* BEGIN src/page.js */\n// an old copy\n", 1), encoding="utf-8")
    monkeypatch.setattr(build_hosted, "PAGE", stale)
    with pytest.raises(SystemExit, match="build_app_page"):
        build_hosted.page_is_current()
    app = tmp_path / "app"
    shutil.copytree(APP / "data", app / "data")
    shutil.copytree(APP / "spec", app / "spec")
    (app / "data" / "summary.json").write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(build_hosted, "APP", app)
    with pytest.raises(SystemExit, match="summary.json"):
        build_hosted.data_manifest()


def _bundle_data(bundle: Path, name: str = "data.mjs", const: str = "DATA") -> object:
    text = (bundle / name).read_text(encoding="utf-8")
    return json.loads(text[text.index(f"export const {const} = ") + len(f"export const {const} = "): text.rstrip().rindex(";")])


@needs_node
def test_the_function_bundle_is_the_same_build_as_the_site(hosted):
    site, bundle = hosted
    data = _bundle_data(bundle)
    ctxs = _contexts()
    assert data["contexts"] == ctxs
    assert sorted(data["files"]) == sorted(ctxs)
    assert all(re.fullmatch(r"\d{4}-\d{2}_[A-Z]{2}-\d{4,8}", f["lead"]) for f in data["files"].values())
    assert data["files"]["kazakhstan-851762"] == {"lead": "2026-10_KZ-851762", "series": "Kazakhstan 851762", "run": "2026-10"}
    assert data["prompt"] == (APP / "spec" / "prompt.md").read_text(encoding="utf-8")
    assert data["spec"]["rules"] == json.loads((APP / "spec" / "screen_rules.json").read_text())
    assert data["spec"]["schema"] == json.loads((APP / "spec" / "brief.schema.json").read_text())
    assert data["fdcore"] == json.loads(json.dumps(build_hosted.fdcore_patterns()))
    rec = json.loads((site / "hosted.json").read_text())
    assert data["build"]["source_commit"] == rec["source_commit"] and data["build"]["data_commit"] == rec["data_commit"]
    assert (bundle / "screen.js").read_bytes() == (APP / "src" / "screen.js").read_bytes()
    assert rec["bundle"] == {n: hashlib.sha256((bundle / n).read_bytes()).hexdigest() for n in ["data.mjs", "screen.js"]}
    out = subprocess.run([NODE, str(ROOT / "tests" / "hosted_js_run.mjs"), "bundle", str(ROOT), str(site), str(bundle)],
                         capture_output=True, text=True, check=True)
    n = len(ctxs)
    assert json.loads(out.stdout) == {"files": n, "same": n, "ids": n, "fn_files": n}


def test_the_deny_list_goes_to_the_function_and_never_to_the_site(hosted, deny_file, tmp_path):
    site, bundle = hosted
    assert _bundle_data(bundle, "deny.mjs", "DENY") == [DENY_TERM]
    assert DENY_TERM not in (bundle / "data.mjs").read_text(encoding="utf-8")
    for p in site.rglob("*"):
        if p.is_file():
            assert DENY_TERM.encode() not in p.read_bytes().lower(), p
    # Without a deny list the bundle holds none, and the function then refuses to draft.
    assert build_hosted.main(["--out", str(tmp_path / "s"), "--bundle-out", str(tmp_path / "b"), "--deny-list", str(tmp_path / "missing.txt")]) == 0
    assert _bundle_data(tmp_path / "b", "deny.mjs", "DENY") == []
    assert build_hosted.DENY_FILE == ROOT / "config" / "deny_list.txt"


def test_the_hosted_outputs_and_local_secrets_stay_out_of_git():
    for p in ["app/dist-hosted/index.html", "app/dist-hosted/_headers", "supabase/functions/draft-brief/_bundle/data.mjs",
              "supabase/functions/draft-brief/_bundle/deny.mjs", "supabase/functions/draft-brief/_bundle/screen.js",
              "supabase/.temp/project-ref", "supabase/functions/.env", "supabase/.env", "config/deny_list.txt"]:
        assert subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", p]).returncode == 0, p
    for p in ["supabase/functions/draft-brief/index.ts", "supabase/functions/draft-brief/core.mjs", "app/src/hosted.js", "hosted/README.md",
              "scripts/build_hosted.py", "supabase/migrations/20261022000000_radar_workspace.sql"]:
        assert subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", p]).returncode == 1, p


def test_the_hosted_code_passes_the_repository_screen_and_has_no_long_dashes():
    from fdcore.guardrails import scan_text
    from radar.brief.screen import load_deny
    deny = load_deny()
    files = [ROOT / "app" / "src" / "hosted.js", ROOT / "hosted" / "README.md", ROOT / "scripts" / "build_hosted.py",
             *sorted((ROOT / "supabase").rglob("*.sql")), *[p for p in sorted((ROOT / "supabase" / "functions").rglob("*")) if p.is_file() and "_bundle" not in p.parts],
             *sorted((ROOT / "tests").glob("*hosted*"))]
    assert len(files) >= 11
    for f in files:
        text = f.read_text(encoding="utf-8")
        assert chr(0x2014) not in text and chr(0x2013) not in text, f
        assert scan_text(text, f.name, deny) == [], f


# ============================================================== index.ts under Deno

@pytest.mark.skipif(DENO is None or NODE is None, reason="Deno (and node) are not installed")
def test_the_function_runs_under_deno_against_a_faked_project(hosted, tmp_path):
    _, bundle = hosted
    fn = tmp_path / "draft-brief"
    fn.mkdir()
    for name in ["index.ts", "core.mjs"]:
        shutil.copyfile(ROOT / "supabase" / "functions" / "draft-brief" / name, fn / name)
    shutil.copytree(bundle, fn / "_bundle")
    env = dict(os.environ, DENO_NO_UPDATE_CHECK="1")
    check = subprocess.run([DENO, "check", "--no-lock", str(fn / "index.ts")], capture_output=True, text=True, timeout=300, env=env)
    assert check.returncode == 0, check.stderr[-3000:]
    reply = tmp_path / "reply.txt"
    # The fake project holds one returned note for the file, so the reply answers it.
    reply.write_text(json.dumps(fake_draft(_contexts()["kazakhstan-851762"], [NOTE], FAKE_ANSWER)), encoding="utf-8")
    r = subprocess.run([DENO, "run", "--no-lock", "--allow-read", "--allow-env", "--allow-net=127.0.0.1", str(ROOT / "tests" / "hosted_deno_smoke.ts"),
                        str(reply), str(fn), json.dumps(NOTE)], capture_output=True, text=True, timeout=300, env=env)
    assert r.returncode == 0, r.stderr[-3000:]
    out = json.loads([line for line in r.stdout.splitlines() if line.startswith("{")][-1])
    assert out["ok"]["status"] == 200 and out["ok"]["body"]["passed"] is True, out["ok"]
    assert out["ok"]["body"]["draft"]["series"] == "Kazakhstan 851762"
    assert out["stale"] == {"status": 401, "body": {"error": "not_signed_in"}}
    assert out["mismatch"]["status"] == 409 and out["mismatch"]["body"]["error"] == "build_mismatch"
    assert [c["key"] for c in out["sentToClaude"]] == ["test-key-not-real"]
    assert out["sentToClaude"][0]["version"] == "2023-06-01"
    assert out["sentToClaude"][0]["system"] is True and out["sentToClaude"][0]["notes"] == [NOTE]
    row = out["recorded"][0]
    assert (row["lead"], row["passed"], row["rules"]) == ("2026-10_KZ-851762", True, [])
    assert any(s.startswith("POST api.anthropic.com/v1/messages") for s in out["seen"])
    assert any(s.startswith("POST project.invalid/rest/v1/drafts") for s in out["seen"])
    # The session goes only to Auth's user endpoint; the REST calls carry the secret key on the
    # apikey header only, as Supabase asks for its new secret keys.
    for k in out["keys"]:
        want = ("secret", "user") if k["path"] == "/auth/v1/user" else ("secret", "none")
        assert (k["apikey"], k["authorization"]) == want, k
    assert {k["path"] for k in out["keys"]} == {"/auth/v1/user", "/rest/v1/members", "/rest/v1/drafts", "/rest/v1/decisions", "/rest/v1/config"}
    # The reviewer notes are read from the file's decisions, each with the brief it names.
    q = next(s for s in out["seen"] if s.startswith("GET project.invalid/rest/v1/decisions"))
    assert "lead=eq.2026-10_KZ-851762" in q and "brief%3Abriefs%28author%2Csha256%2Clead%29" in q


# ============================================================== the site in a real browser

def _playwright() -> str | None:
    cand = os.environ.get("DR_PLAYWRIGHT") or str(ROOT / "tests" / "browser" / "node_modules" / "playwright" / "index.mjs")
    return cand if cand and Path(cand).exists() else None


def _umd() -> str | None:
    for path in [os.environ.get("DR_SUPABASE_UMD"), os.environ.get("TA_SUPABASE_UMD")]:
        if path and Path(path).exists():
            digest = base64.b64encode(hashlib.sha384(Path(path).read_bytes()).digest()).decode()
            if "sha384-" + digest == build_hosted.SUPABASE_JS["integrity"]:
                return path
    return None


@pytest.mark.skipif(NODE is None or _playwright() is None or _umd() is None,
                    reason="needs node, Playwright with its Chromium, and DR_SUPABASE_UMD (or TA_SUPABASE_UMD) set to the pinned dist/umd/supabase.js")
def test_the_hosted_site_works_in_a_real_browser(hosted, tmp_path):
    site, _ = hosted
    replies = tmp_path / "replies.json"
    replies.write_text(json.dumps({s: fake_draft(c) for s, c in _contexts().items()}), encoding="utf-8")
    # DR_HOSTED_SHOTS names a folder for a few screenshots, for a person to look at.
    shots = [os.environ["DR_HOSTED_SHOTS"]] if os.environ.get("DR_HOSTED_SHOTS") else []
    r = subprocess.run([NODE, str(ROOT / "tests" / "hosted_browser_check.mjs"), _playwright(), str(site), _umd(), str(replies), *shots],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-3000:]
    out = json.loads(r.stdout)
    if any("Executable doesn't exist" in e or "browserType.launch" in e for e in out["errors"]):
        pytest.skip("Playwright's Chromium is not installed")
    assert out["errors"] == [] and out["csp"] == [], (out["errors"], out["csp"])
    bad = [s for s in out["steps"] if not s["ok"]]
    assert bad == [], bad
    assert len(out["steps"]) == 22
