"""The screen every drafted brief must pass before anyone sees it.

This is the reference implementation of spec/screen_rules.json: a JavaScript page or a Deno
function loads the same rules and must give the same results on spec/screen_cases.json.
On top of the shared rules, this module runs the repository screen (fd-core) over every
string of the draft with the private deny list of names, which never leaves the server.

screen_draft(draft, context, review=None) -> (ok, problems). A draft with any problem is never
shown. Each problem is {"code", "path", "detail"}; codes are listed in screen_rules.json.

Reviewer notes (screen_rules.json, review) come in apart from the context: usable_notes()
holds back any note that fails the note checks (wording, names, words that read as
instructions to the model, length), and the screen then needs one answer per usable note in
responds_to_review, citing it. A note never extends the context: its words are not allowed
names and its figures are not citable.

What it checks: the schema; the series, run, house line and licence line; the headline
says the lead is not a finding; company names (by legal form, including the forms used on
the corridors), email addresses, postcodes, em dashes and judging or accusing words in every
field; possible names of people or firms (a capitalised word in mid-sentence, or a word in
capitals, that neither the context nor the allow list holds); every figure in every claim
comes from the items the claim cites; every cited id, case and red flag is in the context;
no claim is more certain than what it cites. It is a net, not a guarantee: it checks figures
and wording, not meaning, a name that starts a sentence or is written in lower case gets
through, and a person still reads every brief.

A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

import functools
import json
import re
from dataclasses import dataclass
from pathlib import Path

SPEC = Path(__file__).resolve().parent / "spec"
ROOT = Path(__file__).resolve().parents[2]
DENY_FILE = ROOT / "config" / "deny_list.txt"

#: fd-core finding kinds as problem codes.
FDCORE_CODES = {"company name": "company_name", "email address": "email", "UK postcode": "postcode",
                "phone number": "phone", "deny-list name": "deny_list_name", "accusing language": "accusing_language"}


def _rx(pattern: str, flags: str = "") -> re.Pattern:
    return re.compile(pattern, re.ASCII | (re.I if "i" in flags else 0))


@functools.lru_cache(maxsize=1)
def rules() -> dict:
    return json.loads((SPEC / "screen_rules.json").read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=1)
def brief_schema() -> dict:
    return json.loads((SPEC / "brief.schema.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Rules:
    raw: dict
    company: re.Pattern
    email: re.Pattern
    email_allow: frozenset
    postcode: re.Pattern
    postcode_skip: str
    accusing: tuple
    hedges: tuple
    hedge_before: int
    hedge_after: int
    clause: re.Pattern
    token: re.Pattern
    stray: re.Pattern
    forbidden: tuple
    rank: dict
    company_extra: re.Pattern
    cap_word: re.Pattern
    acronym: re.Pattern
    context_word: re.Pattern
    name_endings: tuple
    skip_back: str
    starts: str
    name_allow: frozenset
    instruction: re.Pattern
    note_id: re.Pattern
    number_words: re.Pattern
    number_values: dict
    multiples: re.Pattern


@functools.lru_cache(maxsize=1)
def compiled() -> Rules:
    r = rules()
    p, a, f = r["patterns"], r["accusing"], r["figures"]
    return Rules(
        raw=r,
        company=_rx(p["company_name"]["pattern"], p["company_name"]["flags"]),
        email=_rx(p["email"]["pattern"], p["email"]["flags"]),
        email_allow=frozenset(x.lower() for x in p["email"]["allow"]),
        postcode=_rx(p["postcode"]["pattern"], p["postcode"]["flags"]),
        postcode_skip=p["postcode"]["skip_if_preceded_by"],
        accusing=(_rx(a["pattern"], a["flags"]), _rx(a["extra_pattern"], a["extra_flags"])),
        hedges=tuple(h.lower() for h in a["hedges"]),
        hedge_before=int(a["hedge_before"]), hedge_after=int(a["hedge_after"]),
        clause=_rx(a["clause_break"]["pattern"], a["clause_break"]["flags"]),
        token=_rx(f["token"]["pattern"], f["token"]["flags"]),
        stray=_rx(f["stray"]["pattern"], f["stray"]["flags"]),
        forbidden=tuple((x["code"], x["text"]) for x in r["forbidden_text"]),
        rank={c: i for i, c in enumerate(r["confidence_order"])},
        company_extra=_rx(p["company_name_extra"]["pattern"], p["company_name_extra"]["flags"]),
        cap_word=_rx(r["names"]["capitalised"]["pattern"], r["names"]["capitalised"]["flags"]),
        acronym=_rx(r["names"]["acronym"]["pattern"], r["names"]["acronym"]["flags"]),
        context_word=_rx(r["names"]["context_word"]["pattern"], r["names"]["context_word"]["flags"]),
        name_endings=tuple(r["names"]["endings_removed"]),
        skip_back=r["names"]["skip_back"], starts=r["names"]["starts"],
        name_allow=frozenset(r["names"]["allow"]),
        instruction=_rx(r["review"]["instruction"]["pattern"], r["review"]["instruction"]["flags"]),
        note_id=_rx(r["review"]["note_id"]["pattern"], r["review"]["note_id"]["flags"]),
        number_words=_rx(f["number_words"]["pattern"], f["number_words"]["flags"]),
        number_values=dict(f["number_words"]["values"]),
        multiples=_rx(f["multiples"]["pattern"], f["multiples"]["flags"]),
    )


def problem(code: str, path: str, detail: str = "") -> dict:
    return {"code": code, "path": path, "detail": detail}


def walk_strings(obj, path: str = ""):
    """Every string in obj with its path: keys joined by '.', list positions as [n]."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def _hedged(line: str, start: int, end: int, R: Rules) -> bool:
    lo = max(0, start - R.hedge_before)
    for b in R.clause.finditer(line[:start], lo):
        lo = b.end()
    hi = min(len(line), end + R.hedge_after)
    nxt = R.clause.search(line[:hi], end)
    if nxt:
        hi = nxt.start()
    window = line[lo:hi].lower()
    return any(h in window for h in R.hedges)


def text_problems(text: str, path: str, R: Rules | None = None) -> list[dict]:
    """The wording checks of screen_rules.json on one string, line by line."""
    R = R or compiled()
    out = []
    for line in text.replace("\r", "").split("\n"):
        for code, bad in R.forbidden:
            if bad in line:
                out.append(problem(code, path, repr(bad)))
        for m in R.company.finditer(line):
            out.append(problem("company_name", path, m.group(0)))
        for m in R.company_extra.finditer(line):
            out.append(problem("company_name", path, m.group(0)))
        for m in R.email.finditer(line):
            if m.group(0).lower() not in R.email_allow:
                out.append(problem("email", path, m.group(0)))
        for m in R.postcode.finditer(line):
            if m.start() > 0 and line[m.start() - 1] == R.postcode_skip:
                continue
            out.append(problem("postcode", path, m.group(0)))
        for rx in R.accusing:
            for m in rx.finditer(line):
                if not _hedged(line, m.start(), m.end(), R):
                    out.append(problem("accusing_language", path, m.group(0)))
    return out


def _name_root(word: str, R: Rules) -> str:
    for ending in R.name_endings:
        if word.endswith(ending):
            word = word[: -len(ending)]
    return word


def _starts_sentence(line: str, i: int, R: Rules) -> bool:
    j = i - 1
    while j >= 0 and line[j] in R.skip_back:
        j -= 1
    return j < 0 or line[j] in R.starts


def names_allowed(context: dict, R: Rules | None = None) -> frozenset:
    """The words a draft may write with capitals (screen_rules.json, names): the allow list and
    every word of the context, endings removed."""
    R = R or compiled()
    words = set(R.name_allow)
    for _, s in walk_strings(context):
        for m in R.context_word.finditer(s):
            words.add(_name_root(m.group(0), R))
    return frozenset(words)


def name_problems(text: str, path: str, allowed: frozenset, R: Rules | None = None) -> list[dict]:
    """possible_name problems in one string (screen_rules.json, names), line by line."""
    R = R or compiled()
    out = []
    for line in text.replace("\r", "").split("\n"):
        for m in R.cap_word.finditer(line):
            word = _name_root(m.group(0), R)
            if word in allowed or _starts_sentence(line, m.start(), R):
                continue
            out.append(problem("possible_name", path, word))
        for m in R.acronym.finditer(line):
            if m.group(0) not in allowed:
                out.append(problem("possible_name", path, m.group(0)))
    return out


def figure_tokens(text: str, R: Rules | None = None) -> list[str]:
    """The figure tokens of a text (screen_rules.json, figures): every token match, then
    every digit run left over, so no digit goes unchecked, then the value of every count
    written in words (figures.number_words)."""
    R = R or compiled()
    out, rest = [], list(text)
    for m in R.token.finditer(text):
        cur, num, unit, tail = (g or "" for g in m.groups())
        out.append(cur + num.replace(",", "") + unit.lower() + tail.lower())
        rest[m.start():m.end()] = " " * (m.end() - m.start())
    out += [m.group(0) for m in R.stray.finditer("".join(rest))]
    out += [R.number_values[m.group(0).lower()] for m in R.number_words.finditer(text)]
    return out


def _tokens_of(obj, R: Rules) -> set[str]:
    return {t for _, s in walk_strings(obj) for t in figure_tokens(s, R)}


def claims(draft: dict):
    """Every claim in a draft that matches the schema, with its path."""
    yield "headline", draft["headline"]
    for part in ("uk", "onward"):
        for i, c in enumerate(draft["what_rose"][part]):
            yield f"what_rose.{part}[{i}]", c
    for i, c in enumerate(draft["why_it_may_be_ordinary"]):
        yield f"why_it_may_be_ordinary[{i}]", c
    yield "linked_cases.note", draft["linked_cases"]["note"]
    for i, q in enumerate(draft["questions_to_check"]):
        if "why_here" in q:
            yield f"questions_to_check[{i}].why_here", q["why_here"]
    for i, a in enumerate(draft.get("responds_to_review", [])):
        yield f"responds_to_review[{i}].change", a["change"]


def note_problems(text: str, context: dict, path: str = "note", R: Rules | None = None) -> list[dict]:
    """The note checks (screen_rules.json, review) on one reviewer note: the wording checks,
    the names rule against the context, words that read as instructions to the model, and
    the length limit. A note with any problem is held back from the prompt."""
    R = R or compiled()
    text = str(text)
    out = text_problems(text, path, R) + name_problems(text, path, names_allowed(context, R), R)
    for line in text.replace("\r", "").split("\n"):
        m = R.instruction.search(line)
        if m:
            out.append(problem("planted_instruction", path, m.group(0)[:80]))
            break
    if len(text) > int(R.raw["review"]["max_note_length"]):
        out.append(problem("note_too_long", path, str(len(text))))
    return _dedupe(out)


def check_review(review) -> list[dict]:
    """The notes as given, checked for shape: a list of at most max_notes objects with a unique
    id matching note_id and a text. Raises ValueError otherwise (a fault in the caller)."""
    R = compiled()
    notes = list(review or [])
    if len(notes) > int(R.raw["review"]["max_notes"]):
        raise ValueError(f"at most {R.raw['review']['max_notes']} reviewer notes")
    ids = [n.get("id") if isinstance(n, dict) else None for n in notes]
    if any(not isinstance(i, str) or not R.note_id.fullmatch(i) for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("reviewer notes need unique ids review-1 to review-5")
    if any(not isinstance(n.get("text"), str) for n in notes):
        raise ValueError("every reviewer note needs a text")
    return notes


def usable_notes(review, context: dict) -> tuple[list[dict], list[dict]]:
    """(usable, held): the notes that pass note_problems, and the rest with their problems."""
    usable, held = [], []
    for n in check_review(review):
        probs = note_problems(n["text"], context, "note")
        if probs:
            held.append({**n, "problems": probs})
        else:
            usable.append(n)
    return usable, held


def citable(context: dict) -> dict[str, dict]:
    items = {f["id"]: f for f in context["facts"]}
    items.update({x["id"]: x for x in context["limits"]})
    items.update({c["id"]: c for c in context["cases"]})
    return items


def _schema_path(parts) -> str:
    out = ""
    for p in parts:
        out += f"[{p}]" if isinstance(p, int) else (f".{p}" if out else str(p))
    return out


def schema_problems(draft) -> list[dict]:
    import jsonschema
    v = jsonschema.Draft202012Validator(brief_schema())
    errs = sorted(v.iter_errors(draft), key=lambda e: [str(x) for x in e.absolute_path])
    return [problem("schema", _schema_path(e.absolute_path), e.message[:200]) for e in errs]


def parse_reply(reply: str):
    """A model reply as a draft (screen_rules.json, reply): one JSON object, optionally inside
    one Markdown code fence. Raises ValueError otherwise."""
    s = str(reply).strip()
    m = re.fullmatch(r"```[A-Za-z0-9_-]*[ \t]*\n(.*)\n[ \t]*```", s, re.S)
    if m:
        s = m.group(1).strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError as e:
        raise ValueError(f"the reply is not JSON ({e.msg})") from None
    if not isinstance(obj, dict):
        raise ValueError("the reply is not a JSON object")
    return obj


def load_deny(path: Path | str | None = None) -> list[str]:
    path = Path(path) if path else DENY_FILE
    if not path.exists():
        return []
    return [x.strip() for x in path.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]


def _fdcore_problems(draft: dict, deny: list[str]) -> list[dict]:
    """The repository screen (fd-core) over every string, with the private deny list."""
    from fdcore.guardrails import scan_text
    out = []
    for path, s in walk_strings(draft):
        for f in scan_text(s, path, deny):
            out.append(problem(FDCORE_CODES.get(f.kind, f.kind), path, f.text))
    return out


def _dedupe(problems: list[dict]) -> list[dict]:
    seen, out = set(), []
    for pr in problems:
        key = (pr["code"], pr["path"])
        if key not in seen:
            seen.add(key)
            out.append(pr)
    return out


def screen_shared(draft, context: dict, review=None) -> list[dict]:
    """The checks of screen_rules.json alone: what a page or Deno port runs. review is the list
    of usable reviewer notes the draft was written against (usable_notes), or None."""
    R = compiled()
    notes = check_review(review)
    note_ids = [n["id"] for n in notes]
    if not isinstance(draft, dict):
        return [problem("not_json", "", "the draft is not a JSON object")]
    errs = schema_problems(draft)
    if errs:
        return errs
    out = []
    raw = R.raw
    if draft["series"] != context["series"]:
        out.append(problem("series_mismatch", "series", draft["series"]))
    if draft["run"] != context["run"]:
        out.append(problem("run_mismatch", "run", draft["run"]))
    if draft["house_line"] != raw["house_line"]:
        out.append(problem("house_line", "house_line", draft["house_line"][:80]))
    if draft["ogl_line"] != raw["ogl_line"]:
        out.append(problem("ogl_line", "ogl_line", draft["ogl_line"][:80]))
    if raw["headline_must_contain"].lower() not in draft["headline"]["text"].lower():
        out.append(problem("headline_not_hedged", "headline.text", draft["headline"]["text"][:80]))
    allowed = names_allowed(context, R)
    for path, s in walk_strings(draft):
        out += text_problems(s, path, R)
        out += name_problems(s, path, allowed, R)

    items = citable(context)
    in_context = _tokens_of(context, R)
    free = _tokens_of([context.get(k, "") for k in raw["figures"]["free_fields"]], R)
    for path, c in claims(draft):
        cited = []
        answer = path.startswith("responds_to_review[")
        for i, cid in enumerate(c["cites"]):
            if cid in items:
                cited.append(items[cid])
            elif not (answer and cid in note_ids):
                out.append(problem("unknown_fact", f"{path}.cites[{i}]", cid))
        allowed = free | _tokens_of(cited, R)
        for tok in figure_tokens(c["text"], R):
            if tok not in allowed:
                out.append(problem("uncited_figure" if tok in in_context else "invented_figure", f"{path}.text", tok))
        for m in R.multiples.finditer(c["text"]):
            out.append(problem("figure_in_words", f"{path}.text", m.group(0)))
        if cited:
            floor = min(R.rank[x["confidence"]] for x in cited)
            if R.rank[c["confidence"]] > floor:
                out.append(problem("confidence_above_source", f"{path}.confidence",
                                   f"{c['confidence']} above {R.raw['confidence_order'][floor]}"))
    limit_ids = {x["id"] for x in context["limits"]}
    for i, lid in enumerate(draft["limits"]):
        if lid not in limit_ids:
            out.append(problem("unknown_fact", f"limits[{i}]", lid))
    case_ids = [c["case_id"] for c in context["cases"]]
    got = draft["linked_cases"]["case_ids"]
    for i, cid in enumerate(got):
        if cid not in case_ids:
            out.append(problem("unknown_case", f"linked_cases.case_ids[{i}]", cid))
    missing = [c for c in case_ids if c not in got]
    if missing:
        out.append(problem("cases_missing", "linked_cases.case_ids", ", ".join(missing)))
    flags = {f["id"]: f for f in context["red_flags"]}
    for i, q in enumerate(draft["questions_to_check"]):
        f = flags.get(q["red_flag"])
        if f is None:
            out.append(problem("unknown_red_flag", f"questions_to_check[{i}].red_flag", q["red_flag"]))
        elif q["question"] != f["question"]:
            out.append(problem("red_flag_text_changed", f"questions_to_check[{i}].question", q["red_flag"]))
    seen = set()
    for i, a in enumerate(draft.get("responds_to_review", [])):
        nid = a["note"]
        if nid not in note_ids:
            out.append(problem("review_unknown", f"responds_to_review[{i}].note", nid))
        elif nid in seen:
            out.append(problem("review_duplicate", f"responds_to_review[{i}].note", nid))
        seen.add(nid)
        if nid not in a["change"]["cites"]:
            out.append(problem("review_not_cited", f"responds_to_review[{i}].change.cites", nid))
        if a["change"]["text"].strip() == raw["review"]["placeholder"]:
            out.append(problem("review_placeholder", f"responds_to_review[{i}].change.text", nid))
    missing = [nid for nid in note_ids if nid not in seen]
    if missing:
        out.append(problem("review_unanswered", "responds_to_review", ", ".join(missing)))
    return _dedupe(out)


def screen_draft(draft, context: dict, deny: list[str] | None = None, review=None) -> tuple[bool, list[dict]]:
    """(ok, problems) for a drafted brief against the context it was drafted from and the
    usable reviewer notes it answers. deny is the private list of names (default
    config/deny_list.txt; pass [] for none). A draft that fails is never shown."""
    out = screen_shared(draft, context, review)
    if out and out[0]["code"] in ("not_json", "schema"):
        return False, out
    out = _dedupe(out + _fdcore_problems(draft, load_deny() if deny is None else list(deny)))
    return (not out), out
