# Monitoring runbook (phase 7)

How a collection run works, whether a person or a scheduled Claude session does it. The layer
reads; it never decides. Every item waits on the workspace's Monitor page for a person to accept
it, setting its grade, or reject it.

## Before a run

1. See which sources are due: `python -m fdcore.monitor due --register monitor/sources.json --items monitor/items.jsonl`.
2. Read only the sources in `monitor/sources.json`, and only through their public pages, as a
   person would. Never sign in, never use a VPN or a hidden identity, never pay a service, and
   never read a site whose terms forbid it. A new source goes into the register first, with its
   terms page read and noted, and the owner's yes.

## For each item

- Write one candidate per notice, release or page into `monitor/inbox/<date>.json` (a list), with
  the fields fd-core's monitor module needs: `source`, `url` (on the source's own site),
  `published` (the date the page gives), `retrieved_at`, `language`, `title_original`,
  `excerpt_original` (the source's own words, quoted exactly, at most 600 characters and
  better under 300), `title` and
  `summary` in English, `translated_by` (who translated, with the date; "not translated" for
  English), `tags`, and `grade_proposed`.
- **No names.** Never put the name of a person or firm in any field. A notice that designates
  parties is summarised by counts, countries of address and kinds of goods; the excerpt is chosen
  from text that names no one.
- **Tags** come from `monitor/vocab.json`: the corridors (ISO codes), goods codes and headings
  the radar knows, and topics (enforcement, licensing, reporting, designations, release,
  guidance, end_use). An item tagged with a corridor shows on that corridor's files.
- **The grade** is proposed on the six-by-six scale: the source's reliability (A to F, never above
  its standing grade in the register) and the information's credibility (1 to 6). The person who
  accepts the item sets it.
- **Translation:** keep the original beside the English. Say who translated it. When a figure
  matters, quote it in the excerpt as well as the summary.
- **Every figure in the summary is on the cited page itself**, not a document it links to; cite
  the linked document as its own item instead. No "provisional" or similar unless the page says
  so, and an inference is tagged [Likely].
- **Grades:** credibility 1 (confirmed by other sources) only when an independent second source
  is cited; otherwise 2 at best.
- **What the summary says:** what was published, the figures that matter to the radar's routes
  or goods, and what it does not cover (for example a release with no trade by goods code).
  Never a judgement about a party, and never "evidence".

## Correcting an item

There is no amend path in the tool: a filed item is corrected by editing `monitor/items.jsonl` by
hand (never its `id`, `url`, `published`, `title_original` or `excerpt_original`, which fix its
identity and checksum), checking it again with fd-core's `validate`, and saying why in the commit.

## Filing

1. `python scripts/monitor_ingest.py` checks every candidate (fd-core's monitor module and its
   guardrails screen, with the private deny list when present), files the good ones into
   `monitor/items.jsonl` with an ingest-log entry each, and lists refusals with their reasons in
   `monitor/refused.jsonl`. Fix and re-run, or drop the candidate.
2. `python scripts/build_app_data.py` copies the items into `app/data/monitor.json` for the
   workspace, with the manifest's SHA-256.
3. Commit the inputs, then the manifest, as for any data change; republish the workspace when the
   owner wants the new items in front of the team.

## Cost

Reading public pages costs nothing beyond the session. Paid search, translation or data services
are not used, and wait for the owner's sign-off and a spend cap.
