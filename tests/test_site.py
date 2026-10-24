"""The demo site (scripts/build_site.py) builds, passes its checks, and the checks catch what they
are for. The browser smoke test (tests/site/smoke.mjs) runs when node, Playwright and Chromium are
installed. Synthetic records and published aggregates only."""
import base64
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TA = ROOT.parent / "ta-market"
FDCORE = ROOT.parent / "fd-core"
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as S  # noqa: E402

needs_repos = pytest.mark.skipif(not (TA / "scripts" / "build_app.py").exists() or not (FDCORE / "fdcore").exists(),
                                 reason="ta-market and fd-core are not beside this repo")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    if not (TA / "scripts" / "build_app.py").exists() or not (FDCORE / "fdcore").exists():
        pytest.skip("ta-market and fd-core are not beside this repo")
    out = tmp_path_factory.mktemp("site") / "dist"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_site.py"), "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return out


def test_the_site_builds_and_passes_its_checks(built):
    for rel in ("index.html", "radar/index.html", "workspace/index.html", "ta/index.html", "planner/index.html",
                "_headers", "site.json", "404.html", "favicon.ico", S.D3[0], S.D3_LICENSE):
        assert (built / rel).exists(), rel
    assert not (built / "ta" / "data" / "synthetic_caseload.json").exists()
    assert "{{" not in (built / "index.html").read_text(encoding="utf-8")
    assert (built / "robots.txt").read_text(encoding="utf-8") == "User-agent: *\nAllow: /\n"


def test_every_page_has_a_policy_that_allows_only_its_own_scripts(built):
    rules = S.parse_headers((built / "_headers").read_text(encoding="utf-8"))
    for rel in ("index.html", "radar/index.html", "workspace/index.html", "ta/index.html", "planner/index.html"):
        page = (built / rel).read_text(encoding="utf-8")
        csp = S.headers_for(rules, "/" + rel)["Content-Security-Policy"]
        assert "https:" not in csp and "*" not in csp and "'unsafe-eval'" not in csp
        for body in S.inline_scripts(page):
            h = "'sha256-" + base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode() + "'"
            assert h in csp, rel
        assert S.headers_for(rules, "/" + rel)["X-Robots-Tag"].startswith("noindex")


@pytest.mark.parametrize("snippet, why", [
    ('<script src="https://cdn.example.org/x.js"></script>', "from another site"),
    ('<link rel="stylesheet" href="//fonts.example.org/a.css">', "to another site"),
    ('<img src="http://example.org/a.png">', "from another site"),
    ('<button onclick="go()">Go</button>', "inline event handler"),
    ("<iframe src=\"x.html\"></iframe>", "<iframe>"),
    ("<script>fetch('https://example.org/collect')</script>", "request to another site"),
])
def test_the_external_check_catches(snippet, why):
    assert any(why in p for p in S.check_external("x.html", snippet)), snippet


def test_the_external_check_passes_local_files_and_outbound_links():
    page = ('<link rel="stylesheet" href="../assets/site.css"><script src="../vendor/d3.js"></script>'
            '<a href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/">OGL</a>'
            "<script>fetch('data/x.json')</script>")
    assert S.check_external("x.html", page) == []


def test_a_header_set_twice_for_a_path_stops_the_build():
    rules = S.parse_headers("/*\n  X-A: 1\n/radar/*\n  X-A: 2\n")
    with pytest.raises(S.SiteError, match="set twice"):
        S.headers_for(rules, "/radar/index.html")


def test_a_placeholder_left_unfilled_stops_the_build():
    with pytest.raises(S.SiteError, match="NOT_SET"):
        S.fill("<p>{{SET}} and {{NOT_SET}}</p>", {"SET": "x"})


def test_a_dashboard_call_the_stand_in_lacks_stops_the_build():
    with pytest.raises(S.SiteError, match="dash.ask"):
        S.datasets_read("rows('a'); dash.ask('x')", "page")


def test_the_display_rule_check_catches_a_held_back_series():
    import build_share as B
    country, code = sorted(B.held_back_series())[0]
    found = S.check_display_rule({"radar/index.html": f"<p>{country} {code} rose.</p>"})
    assert any("holds back" in p for p in found)


def test_a_hidden_test_with_a_result_is_caught():
    import json
    t = {"test_id": "T9", "shown": False, "run1_outcome": "hit", "run2_outcome": "not shown (display rule)",
         "run1_first_lead": "", "run2_first_lead": "", "run1_lead_time_months": None, "run2_lead_time_months": None, "run2_on_the_day": "n/a"}
    found = S.check_display_rule({"radar/data/tests.json": json.dumps([t])})
    assert any("carries a result" in p for p in found)


@needs_repos
def test_the_screen_runs_with_the_repos_policies_and_catches_a_name():
    firm = "Example Trading " + "Ltd"      # split, so the repo's own screen does not stop on this file
    texts = {"radar/data/extra.json": '{"exporter": "%s"}' % firm}
    found = S.screen(texts, {}, {}, [], [])
    assert any("company name" in f for f in found)


@pytest.mark.skipif(not shutil.which("node") or not (ROOT / "tests" / "browser" / "node_modules" / "playwright").exists()
                    or not Path("/opt/pw-browsers/chromium").exists(), reason="needs node, Playwright and Chromium")
def test_every_page_opens_in_a_browser(built, tmp_path):
    r = subprocess.run(["node", str(ROOT / "tests" / "site" / "smoke.mjs"), str(built), str(tmp_path / "shots")],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0 and "site smoke test passed" in r.stdout, r.stdout[-4000:] + r.stderr[-2000:]


def test_a_walkthrough_link_appears_only_where_its_video_exists():
    page = "".join(f"<p><!--watch:{n}--></p>" for n in S.WALKTHROUGHS)
    out = S.watch_links(page, {"radar": {"length": "1:33"}})
    assert 'href="videos/radar.mp4">Watch the walkthrough, 1:33</a>' in out
    assert "videos/ta.mp4" not in out and "<!--watch:" not in out


def test_the_film_length_comes_from_the_movie_header():
    head = b"\x00\x00\x00\x6cmvhd" + bytes([0, 0, 0, 0]) + (0).to_bytes(4, "big") * 2 + (1000).to_bytes(4, "big") + (92733).to_bytes(4, "big")
    assert abs(S.mp4_seconds(b"\x00" * 8 + head) - 92.733) < 1e-9
    with pytest.raises(S.SiteError, match="movie header"):
        S.mp4_seconds(b"not a film")


def test_a_walkthrough_missing_a_file_stops_the_build(tmp_path):
    (tmp_path / "radar.mp4").write_bytes(b"x")
    with pytest.raises(S.SiteError, match="radar has only"):
        S.read_media(tmp_path)



@pytest.mark.parametrize("copy, repo_app", [("workspace", ROOT / "app"), ("planner", TA / "app" / "dist")])
def test_monitoring_items_from_sources_without_an_open_licence_stay_off_the_site(built, copy, repo_app):
    """Some monitor sources reserve all rights or forbid commercial use: their items serve internal
    monitoring only, so each site copy carries the Open Government Licence items alone, and its
    manifest copy holds the hash of the file it carries and says how many it left off."""
    import json
    sources = json.loads((repo_app / "spec" / "monitor_sources.json").read_text(encoding="utf-8"))
    is_open = {s["id"]: s["terms_note"].startswith(S.OPEN_TERMS) and s["terms_url"].startswith(S.OPEN_TERMS_PAGES) for s in sources["sources"]}
    every = json.loads((repo_app / "data" / "monitor.json").read_text(encoding="utf-8"))
    site = json.loads((built / copy / "data" / "monitor.json").read_text(encoding="utf-8"))
    assert every and not all(is_open[i["source"]] for i in every), "the test needs an item that must be left off"
    assert site and all(is_open[i["source"]] for i in site)
    assert {i["id"] for i in site} == {i["id"] for i in every if is_open[i["source"]]}
    m = json.loads((built / copy / "data" / "manifest.json").read_text(encoding="utf-8"))
    m = m[0] if isinstance(m, list) else m
    assert m["files"]["data/monitor.json"] == hashlib.sha256((built / copy / "data" / "monitor.json").read_bytes()).hexdigest()
    assert m["site_copy"]["monitor_items_left_off"] == len(every) - len(site)


def test_the_open_licence_filter_keeps_only_open_items():
    import json
    src = json.dumps({"sources": [{"id": "a", "terms_note": "Open Government Licence v3.0"},
                                  {"id": "b", "terms_note": "All rights reserved"}]}).encode()
    items = json.dumps([{"id": "1", "source": "a"}, {"id": "2", "source": "b"}, {"id": "3", "source": "gone"}]).encode()
    kept, off = S.open_licence_only(items, src)
    assert not json.loads(kept) and off == 3, "a note alone, without the licence's own address, is not enough"
    src = json.dumps({"sources": [{"id": "a", "terms_note": "Open Government Licence v3.0", "terms_url": S.OPEN_TERMS_PAGES[0] + "version/3/"},
                                  {"id": "b", "terms_note": "Open Government Licence, it says", "terms_url": "https://example.org/terms"}]}).encode()
    kept, off = S.open_licence_only(items, src)
    assert [i["id"] for i in json.loads(kept)] == ["1"] and off == 2
