"""The workspace page stays in step with its shared JavaScript and passes the shared cases."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_page_inlines_the_current_shared_screen():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_app_page.py"), "--check"])
    assert r.returncode == 0, "run scripts/build_app_page.py"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.skipif(not (ROOT / "radar" / "brief" / "spec" / "screen_cases.json").exists(), reason="no shared cases yet")
def test_javascript_screen_passes_the_shared_cases():
    r = subprocess.run(["node", str(ROOT / "tests" / "screen_js.test.mjs")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_page_builds_the_same_prompt_as_python(tmp_path):
    import json
    sys.path.insert(0, str(ROOT))
    from radar.brief.prompt import build_prompt
    ctx = json.loads(next(p for p in sorted((ROOT / "app" / "data" / "briefs").glob("*.json")) if p.name != "index.json").read_text(encoding="utf-8"))
    review = [{"id": "review-1", "kind": "returned", "at": "2026-10-21", "text": "Say which onward check carries the lead."}]
    lessons = [{"id": "lesson-1", "applies_to": "this goods code on every corridor", "text": "Check re-exports before the onward check."}]
    for r, ls in (([], []), (review, []), (review, lessons), ([], lessons)):
        f = tmp_path / "in.json"
        f.write_text(json.dumps({"context": ctx, "review": r, "lessons": ls}), encoding="utf-8")
        out = subprocess.run(["node", str(ROOT / "tests" / "prompt_js_run.mjs"), str(f)], capture_output=True, text=True, check=True)
        assert json.loads(out.stdout) == build_prompt(ctx, r, ls)
    assert "<lessons>\n[]\n</lessons>" in build_prompt(ctx)["user"]
