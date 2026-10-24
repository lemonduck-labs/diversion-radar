# How this was built

One person set the problem, the rules and every decision. Claude Code did the building,
directed through a team of agents, each with its own brief in `.claude/agents/`. The rules
come first and stay fixed: no names of people or firms, aggregates only, a display rule so
that a small flow cannot point at one exporter, and outputs that are leads for a person, never
findings (`CLAUDE.md`).

## The team

| Agent | Owns |
|---|---|
| trade-data-engineer | HMRC and UN Comtrade pulls, snapshots, checksums, the ingest log |
| sanctions-analyst | The lead rules, the leads table, the radar's reports |
| case-note-drafter | Briefs drafted from a file's facts into the approval queue |
| case-researcher | The backtest's closed cases, by official reference only |
| backtest-analyst | As-of reruns, hits, misses and lead times |
| fact-checker | Re-derives every number before anything is shared |
| guardrails-reviewer | Blocks names, personal data, accusations and licence problems |

Commands: `/pull`, `/leads`, `/backtest`, `/review`, `/ship` (`WORKFLOW.md`).

## The gates

- Nothing leaves the repository until the fact-checker has re-derived every number from
  `data/processed` and the ingest log, and the guardrails reviewer has passed it (`/review`,
  then `/ship`).
- After each phase, a reviewer that did not write the work (a fresh agent given the code and
  the sources, not the builder's account of them) checks it against the law, the sources and
  the rules, and lists blocking and non-blocking points, each marked [Certain], [Likely] or
  [Guessing]. Blocking points are fixed before the work is shared or signed off, and the
  decision log records each one.
- The backtest was pre-registered before it was run (`backtest/preregistration.md`), and every
  run, superseded ones included, is kept in a research log.
- Tests run in Python, as browser flows in Chromium, and against the hosted database on Postgres.
- Every inference carries its confidence. The decisions, the defaults set in the owner's absence
  and the checks left for later are in `docs/decision_log.md`.

## What the reviews caught

A few of the points the independent reviews raised, each fixed once found:

- An outcome put a route forward for an end-use controls decision before its decision record
  was approved. It now counts as a step only once a second editor, who wrote none of the
  record, approves it.
- The referral pack described a watch item as if its onward exports had risen; a watch item is
  a UK rise only.
- A monitoring item called OTSI's 2025-26 annual review its "first". The cited post never says
  so, and OTSI had published a review for 2024-25.
- The shared copies gave a held-back test's case and code, which with the case's corridors let a
  reader work out its route. The held-back tests now keep only their id and that case is shared
  without its corridors; the case's published reports still name them, so what the public copies
  and the demo site hold back is each test's result and any UK figure on its route in the case's
  window (decision log, 24 Oct 2026).

A rise in exports is a lead, not evidence of a breach.
