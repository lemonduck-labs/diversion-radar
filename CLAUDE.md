# Diversion radar: project rules for Claude

This repo holds two builds on one data model:

1. **The radar**: monthly leads where UK exports of high-priority goods to a corridor
   country rose and that country's own exports of the same goods to Russia rose too.
2. **The enforcement backtest** (backtest/): whether the radar would have flagged the
   goods and routes in concluded, published enforcement cases before the action.

## Hard rules

- No names of people or firms, anywhere: code, data, reports, charts, commits.
  Official case references are fine. This is about the subjects of the work (exporters,
  defendants, parties); data publishers may appear as citation domains, and tools by name.
- Source links: the private case register may cite URLs of official records of concluded
  cases, and secondary reports only where no official record was found, if the URL holds no
  party name. Never copy names or per-person details (sentences, nationality, residence,
  arrest or court dates of individuals) from those pages. Anything public cites the official
  reference only, with no URLs. Cases that did not end in a settlement, penalty, plea or
  conviction are counted, never referenced.
- The deny list lives outside git (config/deny_list.txt is gitignored; the tracked file is
  config/deny_list.example.txt). Filling a tracked file would put names in the repo.
- Before anything is public: a minimum size for any series shown as a lead, so a small flow
  cannot point at an identifiable exporter; and the licence checks in data/SOURCES.md.
- Aggregates only. No personal data.
- Outputs are leads for a person, never findings. House line: "A rise in exports is a
  lead, not evidence of a breach."
- Every number traces to a row in data/processed and an entry in data/ingest_log.jsonl.
- Data that arrives by a side route is used only after its checksums match.
- Every inference carries [Certain], [Likely] or [Guessing].
- Contains public sector information licensed under the Open Government Licence v3.0:
  this line goes on every screen and report that shows HMRC data.
- Nothing leaves the repo until the fact-checker and guardrails-reviewer agents pass it
  (/review, then /ship).
- British English. No em dashes.

## Team (.claude/agents)

| Agent | Owns |
|---|---|
| trade-data-engineer | HMRC and Comtrade pulls, snapshots, checksums, ingest log |
| sanctions-analyst | Lead rules, leads table, radar reports |
| case-note-drafter | Phase 2: drafted case notes into the approval queue |
| case-researcher | Backtest: closed cases, official references only |
| backtest-analyst | Backtest: as-of reruns, hits, misses, lead times |
| fact-checker | Re-derives every number before sharing |
| guardrails-reviewer | Blocks names, personal data, accusations, licence problems |

Commands: /pull, /leads, /backtest, /review, /ship. The workflow is in WORKFLOW.md.

## Shared core

fd-core (../fd-core) provides the ingest log, snapshot checks, guardrails screen and
decision log. Install with pip install -e ../fd-core.
