"""The analyst brief engine: the AI-in-the-loop step of the radar, independent of hosting.

    build_context(run, series_key) -> dict           radar.brief.context
    build_prompt(context) -> {"system", "user"}      radar.brief.prompt
    screen_draft(draft, context) -> (ok, problems)   radar.brief.screen
    draft_brief(context, llm) -> BriefResult         radar.brief.pipeline
    FakeLLM, fake_draft                              radar.brief.fake_llm
    RED_FLAGS, export()                              radar.brief.redflags

The language-neutral contract a page or a Deno function loads unchanged is in spec/:
prompt.md, brief.schema.json, context.schema.json, screen_rules.json, redflags.json and
screen_cases.json. See README.md.

A rise in exports is a lead, not evidence of a breach.
"""
from radar.brief.context import BriefRefused, build_context, flagged_shown, slug
from radar.brief.fake_llm import FakeLLM, fake_draft
from radar.brief.pipeline import BriefResult, draft_brief
from radar.brief.prompt import build_prompt
from radar.brief.screen import parse_reply, screen_draft

__all__ = ["BriefRefused", "BriefResult", "FakeLLM", "build_context", "build_prompt", "draft_brief",
           "fake_draft", "flagged_shown", "parse_reply", "screen_draft", "slug"]
