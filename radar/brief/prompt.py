"""The drafting prompt for an analyst brief, filled from spec/prompt.md.

build_prompt(context, review=None, lessons=None) -> {"system": str, "user": str}. A page or a
Deno function fills the same template the same way (the notes at the top of spec/prompt.md);
what the model sends back is parsed and screened (radar/brief/screen.py) before anyone sees it.

review is the list of reviewer notes that passed the note checks (screen.usable_notes), oldest
first; lessons is the list of lessons recalled for the series ({id, applies_to, text}: a second
person approved each, and fd-core's recall screen passed it). Both go in the user turn apart
from the context, each in its own block, and the model is told they are data.

The model may use only what the context holds: its facts, limits, cases and red flags.
Anything else, a figure, a name, a date or a source, fails the screen and is never shown.

A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from radar.brief import screen

SPEC = Path(__file__).resolve().parent / "spec"
SECTION = re.compile(r"^=== (system|user) ===$", re.M)
PLACEHOLDER = re.compile(r"\{\{([a-z_]+)\}\}")


def template() -> dict[str, str]:
    """The system and user sections of spec/prompt.md, unfilled."""
    text = (SPEC / "prompt.md").read_text(encoding="utf-8")
    marks = list(SECTION.finditer(text))
    if [m.group(1) for m in marks] != ["system", "user"]:
        raise ValueError("spec/prompt.md needs one '=== system ===' line and then one '=== user ===' line")
    return {"system": text[marks[0].end():marks[1].start()].strip("\n"),
            "user": text[marks[1].end():].strip("\n")}


def values(context: dict, review: list | None = None, lessons: list | None = None) -> dict[str, str]:
    r = screen.rules()
    return {"house_line": r["house_line"], "ogl_line": r["ogl_line"],
            "headline_phrase": r["headline_must_contain"],
            "blocked_words": ", ".join(r["prompt_word_examples"]),
            "schema": json.dumps(screen.brief_schema(), indent=1, ensure_ascii=False),
            "context": json.dumps(context, indent=1, ensure_ascii=False),
            "review": json.dumps(list(review or []), indent=1, ensure_ascii=False),
            "lessons": json.dumps(list(lessons or []), indent=1, ensure_ascii=False)}


def build_prompt(context: dict, review: list | None = None, lessons: list | None = None) -> dict[str, str]:
    """The filled prompt for one context, the reviewer notes that passed the note checks and the
    lessons recalled for it."""
    vals = values(context, review, lessons)
    out = {}
    for part, text in template().items():
        names = set(PLACEHOLDER.findall(text))
        unknown = names - set(vals)
        if unknown:
            raise ValueError(f"spec/prompt.md has unknown placeholders: {', '.join(sorted(unknown))}")
        # Fill in one pass so that text inside a value is never read as a placeholder.
        out[part] = PLACEHOLDER.sub(lambda m: vals[m.group(1)], text)
    return out
