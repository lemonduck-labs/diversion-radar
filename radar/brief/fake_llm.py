"""A deterministic stand-in for the drafting model, so the prompt, the parse and the screen
are tested end to end without an API key.

FakeLLM().complete(system, user) reads the context and any reviewer notes back out of the
user prompt and returns the brief that fake_draft() builds from them: claim texts copied
from the cited facts and limits, figures exactly as the context writes them, and each
claim's confidence set to the lowest of what it cites. It knows nothing the context does not
hold. A real model is held to the same screen.

With reviewer notes, fake_draft() is the page's template: each note gets the placeholder
answer, which the screen refuses until a person writes the answer. FakeLLM answers each note
with a fixed sentence instead, so a pipeline test can pass end to end.

A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

import json
import re

SCHEMA = "radar-brief/1"
RANK = {"Guessing": 0, "Likely": 1, "Certain": 2}
#: Which red flags to ask about first: one per tag, in this order.
QUESTION_TAGS = ("chpl", "corridor", "volume_rise", "end_use", "end_user", "payment", "routing")
WHY_HERE = {"chpl": "series.chpl_tier", "corridor": "corridor.uk_guidance", "volume_rise": "uk.ratio"}
ORDINARY = ("limit.code_breadth", "limit.corridor_totals", "limit.single_month", "limit.revisions",
            "limit.onward_age")


FAKE_ANSWER = "This draft was checked against the note; its figures and limits are as the context gives them."


def _placeholder() -> str:
    from radar.brief.screen import rules
    return rules()["review"]["placeholder"]


def fake_draft(ctx: dict, review: list | None = None, answer: str | None = None) -> dict:
    """A brief built only from the context; with reviewer notes, one answer per note: the
    placeholder (the template), or answer when given."""
    items = {x["id"]: x for x in ctx["facts"] + ctx["limits"] + ctx["cases"]}

    def claim(text: str, cites: list[str]) -> dict:
        conf = min((items[c]["confidence"] for c in cites), key=RANK.get)
        return {"text": text, "confidence": conf, "cites": list(cites)}

    def say(*ids: str, lead: str = "") -> dict:
        return claim((lead + " ".join(items[i]["text"] for i in ids)).strip(), list(ids))

    ratio = items["uk.ratio"]["display"]
    if ctx["status"] == "lead":
        head = f"{ctx['series']}: UK exports {ratio} the 2019-21 average and the onward check passed; a lead to check, not a finding"
    else:
        head = (f"{ctx['series']}: UK exports {ratio} the 2019-21 average; the onward check has not passed; "
                "a watch item to check, not a finding")
    onward = [say("onward.check")] + [say(i) for i in ("onward.annual", "onward.monthly") if i in items]
    ordinary = [say(i, lead="The rise may be ordinary trade. " if i == "limit.code_breadth" else "")
                for i in ORDINARY if i in items]

    questions, picked = [], set()
    for tag in QUESTION_TAGS:
        flag = next((f for f in ctx["red_flags"] if tag in f["tags"] and f["id"] not in picked), None)
        if flag is None:
            continue
        picked.add(flag["id"])
        q = {"red_flag": flag["id"], "question": flag["question"]}
        if WHY_HERE.get(tag) in items:
            q["why_here"] = say(WHY_HERE[tag])
        questions.append(q)

    return {
        "schema": SCHEMA,
        "series": ctx["series"],
        "run": ctx["run"],
        "headline": claim(head, ["uk.ratio", "onward.check"]),
        "what_rose": {"uk": [say("uk.trailing12", "uk.ratio"), say("uk.months", "display.rule"),
                             say("history.summary")],
                      "onward": onward},
        "why_it_may_be_ordinary": ordinary,
        "linked_cases": {"case_ids": [c["case_id"] for c in ctx["cases"]],
                         "note": claim(items["cases.summary"]["text"],
                                       ["cases.summary"] + [c["id"] for c in ctx["cases"]])},
        "questions_to_check": questions,
        "limits": [x["id"] for x in ctx["limits"]],
        **({"responds_to_review": [{"note": n["id"], "change": {"text": answer or _placeholder(), "confidence": "Certain",
                                                                "cites": [n["id"]]}} for n in review]}
           if review else {}),
        "house_line": ctx["house_line"],
        "ogl_line": ctx["ogl_line"],
    }


class FakeLLM:
    """complete(system, user) -> reply text, like a model call."""

    def __init__(self, reply: str | None = None):
        self.reply = reply  # a fixed reply, to test what happens to a bad one

    def complete(self, system: str, user: str) -> str:
        if self.reply is not None:
            return self.reply
        m = re.search(r"<context>\s*(\{.*\})\s*</context>", user, re.S)
        if not m:
            return "I could not find the context."
        n = re.search(r"<review_notes>\s*(\[.*\])\s*</review_notes>", user, re.S)
        review = json.loads(n.group(1)) if n else []
        return json.dumps(fake_draft(json.loads(m.group(1)), review, FAKE_ANSWER), indent=1, ensure_ascii=False)
