"""Draft one brief and keep it only if it passes the screen.

draft_brief(context, llm, review=None) builds the prompt, asks the drafter, parses the reply
and screens it. BriefResult.draft is None whenever anything fails, so a draft that fails can
never be shown; the problems say why. Reviewer notes that fail the note checks are held back
from the prompt and listed in BriefResult.held; the draft must answer the rest. The drafter
is anything with complete(system, user) -> str: FakeLLM here, the page's in-page model call
or a Deno function in the hosted versions.

A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from radar.brief.prompt import build_prompt
from radar.brief.screen import parse_reply, problem, screen_draft, usable_notes


@dataclass
class BriefResult:
    ok: bool
    draft: dict | None
    problems: list[dict] = field(default_factory=list)
    reply: str = ""
    held: list[dict] = field(default_factory=list)


def draft_brief(context: dict, llm, deny: list[str] | None = None, review: list | None = None) -> BriefResult:
    usable, held = usable_notes(review, context)
    p = build_prompt(context, usable)
    reply = llm.complete(p["system"], p["user"])
    try:
        draft = parse_reply(reply)
    except ValueError as e:
        return BriefResult(False, None, [problem("not_json", "", str(e))], reply, held)
    ok, problems = screen_draft(draft, context, deny, usable)
    return BriefResult(ok, draft if ok else None, problems, reply, held)
