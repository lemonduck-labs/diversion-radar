"""The evals run as CI runs them, and the planted notes reach the prompt they are meant to test.

The live eval (a real model, with a key) is not run here: it costs money and has no bar.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytest.importorskip("inspect_ai")
sys.path.insert(0, str(ROOT / "evals"))
import run as R  # noqa: E402
import brief_evals as B  # noqa: E402
from radar.brief import screen as S  # noqa: E402


def test_every_planted_note_passes_the_note_checks():
    planted = [s for s in B.live_samples() if s.metadata["review"]]
    assert len(planted) == len(B.PLANTED) == 6
    for s in planted:
        usable, _ = S.usable_notes(s.metadata["review"], B.ctx_for(s.metadata["slug"]))
        assert usable, s.id


@pytest.mark.parametrize("which", ["screen", "pipeline"])
def test_the_offline_evals_pass_their_bar(which, tmp_path):
    assert R.main([which, "--log-dir", str(tmp_path)]) == 0
