# Radar workspace (phase 2)

The working tool on top of the radar: an inbox of this run's leads, a file per lead with an
AI-drafted analyst brief that a second person approves, a checklist of questions from
official guidance, an audit log, an evidence pack, and an exporter screen that checks an
exporter's own shipments against the radar's corridor signals.

A rise in exports is a lead, not evidence of a breach.

## What runs where

| Part | Inside Claude (the pilot) | Hosted (built and tested here, not deployed: hosted/README.md) |
|---|---|---|
| Page | `app/index.html`, published as an artifact with its data files | `app/dist-hosted` on Netlify: the same page, after the Supabase client and `app/src/hosted.js` |
| Shared store | The artifact's database (`db`) | Supabase Postgres, London region, with row-level security |
| Sign-in and roles | The artifact's sharing levels (`user`) | Supabase Auth, roles in a members table |
| Drafting | Claude on the viewer's own usage (`sample`) | The `draft-brief` Edge Function, with the owner's Anthropic key and the private deny list |
| Downloads | The artifact's `downloads` | A browser download |

The page reaches all four through `claude.use(name)`. The hosted build provides objects with the
same calls (`app/src/hosted.js`), so the page does not change, apart from saying which version it
is. The pilot works without any of them:
with no store it runs in demo mode (changes stay in the tab), with no drafting it offers
the template, with no downloads it hides the export buttons.

## Getting around

The page runs fd-core's shared shell (`fdcore/shell.mjs`, inlined as `FdShell`). The sidebar
lists queues named for the job, with counts: Needs my review (submitted briefs this person may
approve, which with four-eyes on leaves out a version they saved), Returned to me (returned
briefs whose returned version they saved) and Assigned to me; then Leads and Watch items; the
synthetic Declarations and Reports; the exporter check and Lessons; and Track record, Method
and the audit log. A file opens with its place in the queue it came from ("3 of 7"), the
previous and next file a key away, and a line saying where its brief stands; a case and a report
open the same way, with their place in their list as filtered. The top bar shows
where you are. Ctrl or Cmd + K, or /, searches files, cases, reports and pages; j and k move
through a list, or between records on a record; g then a letter goes to a page; ? lists the
keys. Below 900 pixels wide the sidebar becomes a drawer.

Each queue and page has its own link, the artifact's link plus `#review`, `#returned`, `#mine`,
`#leads`, `#watch`, `#inbox`, `#declarations`, `#reports`, `#exporter`, `#lessons`, `#track`,
`#method`, `#audit`, `#tasks` (Follow-ups) or `#team`; a file is `#file-<key>`, a case
`#case-SYN-CASE-nnn`, a report `#report-RPT-SYN-nnn`, a corridor `#corridor-<ISO2>` and a goods
code `#code-<six digits>`.

## Sign-in, the record page and follow-ups (phase 6)

- **Sign-in.** In demo mode the page opens on a sign-in screen: synthetic people at each of the
  hosted version's roles (analyst as Contributor, two editors so four-eyes can be tried in one
  tab, a partner liaison as Viewer, and the owner). "Switch user" in the sidebar brings it back
  and keeps the page. Inside Claude, who you are comes from the artifact; "Try the demo roles"
  moves that tab to a store of its own. The hosted version keeps its own sign-in.
- **A file is one record.** The header gives the next step for the person looking (start, continue
  or revise the brief, review and decide, export the evidence pack). The main column's sections
  fold away and stay folded on that browser. The rail holds the file's properties, follow-ups,
  references (`spec/references.json`: each publisher's own page with the date it was read, never
  a case record), add-ons, connected records and activity.
- **Follow-ups** (`tasks/<id>`, a shared record any Contributor writes). Each has text, a due date,
  an owner and done or not, with one-click templates (recheck after HMRC's next release, the
  Common High Priority Items List, the corridor's mirror figures, the exporter check, a partner
  agency). Every change is audited. The Follow-ups page lists open ones by due date, mine or
  everyone's. Hosted: `public.tasks` (migration `20261022130000_radar_followups.sql`).
- **Add-ons** (task tracker, calendar, email or Teams, case management) connect nothing and send
  nothing in this version: each shows the text it would send.
- **Corridor and goods-code pages** list every file the workspace shows on that corridor or code,
  from the breadcrumb, a file's header or the search; held-back series are not counted.

## The console and closing the loop (phase 6.5)

- **The console.** The overview opens on a globe that turns and a sweep that lights each corridor
  as it passes. A blip is a corridor with series the display rule lets the workspace show (violet
  for a lead, pale blue for a watch item); every corridor on the scan has a small mark, so a quiet
  mark says nothing about what is held back, which is counted on the console and never placed.
  Routes run from the UK to each corridor with a blip and on to Russia; moving dots show the
  direction of trade, not shipments. Marks sit on capitals. Drag to turn it, hover or click a
  blip, or choose a corridor from the list (the keyboard's way in); Pause stops the motion, and a
  system set to reduce motion starts it paused. Drawn on a canvas from `spec/land.json` (Natural
  Earth, public domain; `radar/geo/README.md`), with nothing loaded from elsewhere.
- **What happened** (`outcomes/<file>`). Once a brief is approved or rejected, a Contributor
  records the outcome from a fixed list (no further action, keep on watch, guidance or outreach to
  the trade, referred on, proposed for an end-use controls decision), with an optional
  screened note; a rejected lead can only be closed or kept on watch. The overview and the track
  record count them: a count of what the team did, not a test of the rule. A proposal for an
  end-use decision counts as a step only once its decision record puts the route forward and is
  approved, and while a record puts it forward the outcome cannot be changed away from it.
- **Referral pack** (`<ref>-referral.md`, an approved file only): the goods, the dates, the rules
  that may apply, the documents behind it and whether other authorities have been told, under the
  headings of OTSI's guidance on reporting (16 December 2025) where a lead can fill them; the UK
  link, any parties and the narrative of who did what come from the analyst's own enquiries in a deployment, since trade
  statistics identify no exporter. A screened reason is required. Exported as a page event.
- **End-use controls decision record** (`enduse/<file>`, on a file proposed for one): why the route,
  six checks and a recommendation. Putting a route forward needs every check, including
  information beyond the trade statistics; a second editor, not the recorder, approves it. Nobody who
  wrote any part of it since the last approval may approve it, and any change to the content clears
  the approval.
- **Lessons from the published cases** on the track record: what the radar showed on each case
  route the display rule lets it show, and the point each makes.
- **Pilot timings** (Reference): three tasks (write a brief and send it, record an outcome,
  prepare a referral pack) timed in minutes and steps, kept in this browser only, with no file,
  text or person logged; a CSV for comparing with the same tasks done the usual way.
- Hosted: `public.outcomes` and `public.enduse_records` (migration `20261022160000_radar_outcomes.sql`).

## The monitor (phase 7)

- **Items** (`data/monitor.json`, built from `monitor/items.jsonl`): official notices,
  statistics releases and guidance read from the public pages of the sources in
  `monitor/sources.json` (copied to `spec/monitor_sources.json`), each with the original beside
  an English title and summary, who translated it, tags that match it to corridors, codes and
  topics, and a proposed grade on the six-by-six scale. Each was checked by fd-core's monitor
  module before it was filed (`scripts/monitor_ingest.py`; how a run works:
  `monitor/RUNBOOK.md`).
- **The Monitor page** (Work) lists items waiting, accepted and rejected, and the sources with
  their terms. A Contributor accepts an item, setting its grade, or rejects it with a reason
  (`monitor/<item>`, a shared record, audited). Only accepted items appear on the files they
  touch, in the rail's Monitoring card; corridors with an item waiting pulse on the console's
  globe, and a line beside the corridor list names them for anyone not looking at the globe.
  Nothing reaches a brief unless a person writes it in; drafting does not read items yet.
- **What the items touch** [Certain]: an item reaches a file when its corridor (and its code or
  heading, if tagged) matches one. An item tagged only to a corridor scanned with no lead in run 3
  shows on the Monitor page and the console, on no file; this copy holds the four items from
  sources under the Open Government Licence (`PUBLIC.md`).
- **Correcting an item:** there is no amend path in the page. A filed item is corrected in
  `monitor/items.jsonl` by hand, checked again and committed with the reason
  (`monitor/RUNBOOK.md`); a decision already recorded on it stays.
- **On the public demo site** only items from sources under the Open Government Licence are
  copied; the others serve internal monitoring until their publishers' permission is recorded
  (`scripts/build_site.py`, `data/SOURCES.md`).
- Hosted: `public.monitor_decisions` (migration `20261022170000_radar_monitor.sql`).

## Data the page loads

Built by `python scripts/build_app_data.py` from files already built and reviewed for the
dashboard, plus the files below. The run is the one `demo/radar` holds: run 3, the October
2026 run on 18 corridors with run 2's rule (`backtest/reports/run3.md`). 16 of the 18 have
monthly UN Comtrade data after 2019 and get the monthly onward check; Vietnam's onward data end in 2023 and China's monthly data in December
2024 [Certain]. A 2019-21 year counts in the annual onward baseline only when the corridor's
figures hold exports of one of the nine codes to Russia that year: Macao's hold none, so its
annual check cannot pass and its monthly check rests on the $100,000 floor, and Azerbaijan's
baseline leaves out 2019 and Georgia's 2020 (`backtest/RESEARCH_LOG.md`, R3.4) [Certain]. The track record is the backtest,
on the original nine corridors.

- `data/signals.json`: one row per corridor and code. Each corridor's onward check for all
  162 series (national totals as each corridor reports them). A UK-wide status only where
  the series passes the display rule at this run; UK figures only for series flagged and
  shown.
- `data/corridors.json`: the run's 18 corridors with the spellings an exporter's file may
  use (Viet Nam, Hong Kong SAR, Macao SAR, PRC and so on), and the stops (Russia, Belarus).
- `data/synthetic_shipments.csv`: a made-up exporter's shipments (every reference SYN-),
  with two customers on corridors run 3 added (India and Hong Kong).
- `data/briefs/`: the brief engine's facts for each file (`radar/brief`).
- `data/triage/`: the triage view's 43 synthetic reports, each with what it was read against;
  a synthetic list of 24 entities in the UK Sanctions List's format; and the view's rules
  (`radar/triage`, written to `demo/radar/triage` by `scripts/build_triage.py`).
- `spec/`: the brief engine's prompt, schema, screen rules and red flags, unchanged.
- `data/manifest.json`: the run, the source commit and a SHA-256 of every file.

`python scripts/build_app_page.py` copies `app/src/screen.js` and the page's own script,
`app/src/page.js`, into the page between their markers; `tests/test_app_data.py` and
`tests/test_app_page.py` keep both in step. The manifest names the commit the inputs came from,
and lists any input that is not committed as it is (`source_dirty`). The page loads nothing
from other sites: no fonts, no scripts.

## Records

| Path | Holds | Who can write it |
|---|---|---|
| `members/{id}` | That a person has worked in the workspace (written on their first change) | That person |
| `briefs/{id}/b/{version}` | Each brief version they saved: the draft, its screen result, its SHA-256, its source | That person, at Contributor or above |
| `decisions/{id}/d/{decision}` | Each decision they made: approved, returned, rejected or reopened, with the brief and its SHA-256 and the four-eyes setting; a return that keeps its note as a lesson carries the lesson's scope and SHA-256; a decision on a lesson names it and its SHA-256, with a reason | That person, at Editor or above |
| `audit/{id}/e/{event}` | Every action they took: when, which file, what | That person |
| `leads/{run}_{key}` | The status pointer (drafting or submitted), the current brief, who has the file | Contributors and up |
| `checks/{run}_{key}` | Each question's state (open, checked, not applicable), who and when | Contributors and up |
| `config/workflow` | Four-eyes on or off | Editors and the owner only |
| `data/users/{id}/draft_{file}` | A viewer's unsaved, screened draft | That viewer only |

The rules declared at publish:

```json
{"rules": [
  {"path": "members", "read": "view", "write": "owner"}, {"path": "members/{self}", "write": "interact"},
  {"path": "briefs", "read": "view", "write": "owner"}, {"path": "briefs/{self}", "write": "interact"},
  {"path": "decisions", "read": "view", "write": "owner"}, {"path": "decisions/{self}", "write": "admin"},
  {"path": "audit", "read": "view", "write": "owner"}, {"path": "audit/{self}", "write": "interact"},
  {"path": "config", "write": "admin"}
]}
```

So the path, not a field anyone can type, says who saved a brief, who decided and who did what.
A brief counts as approved only when a decision under an editor's path names a version whose
text still matches the SHA-256 saved with it and the SHA-256 the approver saw, and the version
was saved under someone else's path. An approval by the person who saved the version counts
only while the shared four-eyes setting is off and the decision records it as off; the file,
the inbox and the evidence pack then mark it "One person", and turning four-eyes back on stops
it counting. An approval that fails any of these does not count, and the file says why. A decided file shows the version its decision
names, never a later save, and a draft cannot be saved on a file that is awaiting approval or
decided. People are stored by id only; names are resolved for each viewer when the page draws.
Evidence packs and the audit export carry the names of the staff who acted, as the
accountability record, and never "you".

Limits of the pilot store [Certain]: the artifact's owner can write anywhere; times are set by
the writer's browser; a person can change or delete their own records; the status pointer and
the checks are shared records any Contributor can change, so the audit log is the attested
record of who did what; one view reads the records of at most 18 people (the store allows 64
live subscriptions per view) and the latest 1,000 audit entries per person, and says so when
it hits either. That the platform enforces these rules for people other than the owner is
[Likely]: it follows the capability's type definitions and needs a check with a second account.
The hosted version (hosted/README.md: built and tested here, not deployed) closes the rest in the
database: it sets every author and time, writes the audit log itself from triggers, no member can
edit or delete it, and approvals are checked against four-eyes there [Certain: tested on a
local Postgres 16, not yet on Supabase].

## The brief

Claude sees only the drafting rules, the file's facts and the output schema
(`spec/prompt.md`, `data/briefs/<file>.json`, `spec/brief.schema.json`), and, as data in their
own blocks, the reviewers' notes since the last approval and the lessons in force for the
file (below). Every draft, and
every edit a person makes, passes the screen (`spec/screen_rules.json`, `app/src/screen.js`)
before it can be saved: no firm names with a legal-form ending (including the forms used on
the corridors), no capitalised words that may be names of people or firms unless the file's
own facts or the screen's allow list hold them, no emails or postcodes, no judging or
accusing words outside a hedged clause, no figure the facts do not hold, every claim tied to
the facts it cites, the cases and questions word for word, and the house line exact. A draft
that fails is never shown or saved; the analyst sees what failed and drafts again or starts
from the template. The screen cannot catch a name written in lower case or at the start of a
sentence, so the analyst reads every brief. The private deny list of names is not in the
page; the hosted drafting function screens every draft with it (hosted/README.md).

## Lessons

fd-core's memory core runs in the page (`fdcore/memory.mjs`, inlined by
`scripts/build_app_page.py` as `window.FdMemory`, with its rules in `spec/memory_rules.json`).
An editor who returns a brief can keep the note as a lesson for the route, for the goods code
on every corridor, or for the corridor and every code. The lesson is a field on the return
decision, so the path says who kept it, with the SHA-256 of its scope and text, and the memory
core's admission check runs first (a scope, a source, no names, no instruction to a model).
The core admits a person's own reviewed note at once; here every lesson waits for a second
person, who is not its author, to approve it with a reason, because a note can carry text
pasted from elsewhere (fd-core's `research/POISONING_LOG.md`, P1.1, where three held-out
attacks reached the prompt this way) [Certain]. A lesson in force is recalled into every later
draft on its route, code or corridor, at most five, after the core's recall screen (planted
instructions again) and a check of its text against its SHA-256; a lesson that fails is held
back and the file says why. It is shown with its provenance (who kept it, from which file, who
approved it, when and why), sent to Claude as data with no names or dates, and recorded with
each version saved; the evidence pack lists it. Editors can retire a lesson with a reason.
Whether a model follows an instruction hidden in an approved lesson is the poisoning test's
model run (P2), not yet run [Certain]. The hosted build has no lessons yet.

In demo mode the sign-in screen picks who you are: an analyst (Contributor), two reviewers
(Editors), so four-eyes on briefs and on lessons can be tried in one tab, a partner liaison
(Viewer) and the owner.

## Workflow

New, drafting, awaiting approval, then approved or rejected; a returned brief goes back to
drafting with the approver's note. With four-eyes on, the person who saved a version cannot
approve it, and an approval by that person does not count. Editors can turn four-eyes off;
the change goes in the audit log. Approved and rejected files are locked until an editor reopens them. The
evidence pack (Markdown and JSON) carries the facts, the approved brief and its SHA-256
(checked against the approval), the checks, the file's audit trail and the data manifest.

## Reports: triage (synthetic)

Where reports of a suspected breach of trade sanctions arrive (OTSI's online service), the view
reads each one against the radar: the goods codes its words or code point to (a code given is
read as given [Certain]; words through a small phrase table [Likely], or a family of codes
[Guessing]); the radar's status for each route, looked up against the run the page shows (a
lead or watch file, shown and not flagged, held back under the display rule, or no corridor), so
a held-back series says only that; the synthetic declaration cases that hold one of its parties;
any party whose registration number is on, or one character from, a synthetic list entry. Each
report shows the body that handles that kind of report, by OTSI's published split (HMRC for UK
customs, OTSI for goods moved outside the UK and for services, OFSI, HM Treasury and Ofcom for
their measures); the factors OTSI's assessment guidance weighs that the report states, in our
words [Likely]; the questions it raises, from the red flag list; and a reading order by a rule
the page sets out (OTSI publishes no triage scoring [Certain]). A person proposes an outcome
(assess further, pass to HMRC, pass to another body, ask the reporter, or close) with a
screened reason, and an editor approves it, four-eyes as for briefs; an anonymous report cannot
be asked for more. Every report, party, list entry and identifier is made up from a seed: no
names, addresses or contact details, and no individuals or ships on the list. The hosted build
reads reports the same way but records no outcomes or checks yet (hosted/README.md).

## The exporter screen

The exporter's file is parsed in the browser and never uploaded, stored or sent to Claude.
Rows going to one of the run's 18 corridors with one of the nine codes are grouped by
destination and code, with the exporter's own last 12 months against the 12 before,
customers and new customers, each corridor's onward check and the UK-wide status. The order
of checks is: check first (onward check on, with a new customer or a rise), check (a radar
signal), no radar signal. Questions come from the red-flag list by tag. Rows straight to
Russia or Belarus are not screened: they need a sanctions check first.
