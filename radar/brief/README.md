# radar.brief: the analyst brief engine

The AI-in-the-loop step of the radar. For one series flagged at a run, it gathers the facts
a person may see, asks a drafter for a short brief built only from those facts, and screens
the draft before anyone sees it. A draft that fails the screen is never shown.

A rise in exports is a lead, not evidence of a breach.

## The contract (spec/)

A page or a server loads these files unchanged. Python here is the reference.

| File | What it is |
|---|---|
| `spec/context.schema.json` | The shape of a brief context (`radar-brief-context/1`). |
| `spec/prompt.md` | The drafting prompt: a system and a user section with `{{placeholders}}`; how to fill them is at the top of the file. |
| `spec/brief.schema.json` | The strict JSON shape of a draft (`radar-brief/1`, JSON Schema draft 2020-12). |
| `spec/screen_rules.json` | The screen: patterns, word lists, hedges, the figure rule, problem codes and the order of checks. |
| `spec/screen_cases.json` | Shared cases (draft, context, expected `ok` and problems) that every port must pass. |
| `spec/redflags.json` | The questions to check, with tags and citations; generated from `redflags.py`. |

Brief contexts for the current run (run 3: 18 corridors, 23 series shown) are data files:
`demo/radar/briefs/<slug>.json`, with `index.json`, written by `scripts/build_brief_contexts.py`. The generated spec files are
written by `scripts/build_brief_spec.py`; tests fail if either is out of date.

## Python interface

```python
from radar.brief import build_context, build_prompt, screen_draft, draft_brief, FakeLLM

ctx = build_context("2026-10", "Kazakhstan 851762")   # or the slug "kazakhstan-851762"
prompt = build_prompt(ctx)                             # {"system": ..., "user": ...}
ok, problems = screen_draft(draft, ctx)                # problems: [{"code", "path", "detail"}]
result = draft_brief(ctx, FakeLLM())                   # result.draft is None unless it passed
```

- `build_context(run, series_key, root=None, variant=None) -> dict` raises `BriefRefused`
  for a series that is not in the run, not flagged, or not shown under the display rule.
  `variant` is `"run3"` (18 corridors, the workspace's current run and the default, from
  `scripts/build_demo_data.CURRENT`) or `"run2"` (the original nine); each fact cites the
  tables of its variant. It re-checks the
  rule from the monthly table, and it stops a context with a URL, per-person detail or a
  register column that is never copied.
- `flagged_shown(run) -> list[str]` lists the series a brief may be built for.
- `screen_draft(draft, context, deny=None) -> (ok, problems)` runs the shared rules, then
  the repository screen (fd-core) over every string with the private deny list
  (`config/deny_list.txt` by default; `[]` for none).
- `draft_brief(context, llm, deny=None) -> BriefResult` builds the prompt, calls
  `llm.complete(system, user)`, parses and screens. `llm` is anything with that method.

## What a hosted service must do

For each brief: load the context file; fill `spec/prompt.md`; call the model (the page's
in-page model call now, a Deno function with the API key later); parse the reply as one JSON
object (one Markdown code fence is allowed); run every check in `spec/screen_rules.json` in
its order; show the brief only when there is no problem, and otherwise show nothing from it.
A port is correct when it gives the expected `ok` and the same (code, path) pairs on every
case in `spec/screen_cases.json`.

When the page shows a passing brief it renders, from the context and not from the draft:
the text of each listed limit, the linked cases' details (outcome, basis, first public
action), the red flags' citations, the house line and the line "Contains public sector
information licensed under the Open Government Licence v3.0."

The deny list of names is private and never ships to a browser: the page cannot run that
check. A server that holds it (the Deno function, or this Python reference) must run it
before a brief leaves for anyone other than the owner. Until then the page relies on the
company-suffix checks (fd-core's legal forms and those used on the corridors), the
possible-name check, the email, postcode, judging-word, figure and house-line checks, and
on the model having nothing but the context to draw on.

The possible-name check: a capitalised word that does not start a sentence, or a word in
capitals anywhere, fails unless it is on the allow list in `spec/screen_rules.json` (months,
countries and their adjectives, publishers, the titles of official lists and guidance, and
acronyms such as UK, HMRC and CHPL) or appears somewhere in the context the brief was drafted
from.

## What the model may and may not do

It may: write short claims about the figures in the context, each citing the ids of the
facts, limits or cases it rests on; copy figures exactly as the context writes them; pick
3 to 8 of the context's questions to check, word for word; tag each claim no more certain
than what it cites.

It may not: add any figure, date, name, source or fact the context does not hold; name a
person or firm; write an email address, postcode or phone number; judge or accuse anyone
(the word list is in `spec/screen_rules.json`); restate case outcomes; present a lead as a
finding; use an em dash. Any of these fails the screen.

## Guardrails behind the facts

- Only series that pass the display rule (radar/display.py) get a context, and only runs
  whose own 12 months pass it are in the history. On a route linked to a case, only runs
  whose 12 months start after the case's first public action are drawn.
- Cases are case level only: id, jurisdiction, outcome, what the reference rests on, first
  public action. Never sentences, nationality, residence or court dates of individuals,
  and never a URL. The cases named no UK goods or UK party.
- The questions to check come from official guidance only, cited by publisher, title and
  date; the URLs are kept privately in `data/brief_sources.csv`.
- Every fact and limit carries a source (dataset and field) and a confidence tag.

## Limits of the screen

It is a net, not a guarantee. It checks figures and wording, not meaning: a claim can cite
the right facts and still read them wrongly. Multiples and fractions in words ("doubled",
"tripled", "twice") are refused outright, and counts from two to twelve in words are read as
figures (f63245d); other figures in words, such as "a hundred" or "a third", carry no digits and
get past the figure rule. A name that starts a sentence, is written in lower case, or is
made only of words on the allow list or in the context gets past the possible-name check. A
person reads every brief before it is used.
