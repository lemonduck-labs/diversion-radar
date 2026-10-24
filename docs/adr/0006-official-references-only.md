# 6. Official references only: no URLs and no per-person detail in anything public

Date: 21 October 2026. Status: Accepted (a rule in CLAUDE.md).

## Context

The case register draws on official records of concluded cases and, where none was found, on
published reports. Those pages can name parties and carry details about individuals. The first
register held per-person detail such as sentences; the independent reviews of the morning of
21 October 2026 had it removed and the rule written into CLAUDE.md (commit a795ab8).

## Decision

- The private register may cite URLs of official records of concluded cases, and secondary
  reports only where no official record was found, if the URL holds no party name.
- Names and per-person details (sentences, nationality, residence, arrest or court dates of
  individuals) are never copied from those pages.
- Anything public cites the official reference only, with no URLs.
- Cases that did not end in a settlement, penalty, plea or conviction are counted, never
  referenced.
- Case outcomes in the register and the demo are case-level: pleas, convictions, penalties,
  confiscation (decision log line 21).
- Brief contexts carry cases at case level only and never a URL; the URLs of the official
  guidance behind the checklist sit in `data/brief_sources.csv`, tracked in this private
  repository and copied into nothing shown (`radar/brief/redflags.py`).
- The shared copy of the register keeps official references only, and the share build stops on
  any URL other than a data publisher's (decision log line 43).

## Options ruled out

None recorded.

## Consequences

- Official URLs in the private register whose paths describe defendants (residence,
  nationality, a sentence length) are still there. CLAUDE.md allows official URLs that hold no
  party name but bars per-person details, so they must go before the repo is shared beyond the
  owner (decision log, deferred line 60).
- EU-05 is shown as convictions at first instance, finality not verified, and is not called
  concluded; US-01 is not described beyond the plea (decision log line 20; deferred lines 57
  and 58).
- Not every case has an official reference number. The fact-check of 21 October 2026 noted that
  12 of the 22 cases have none found and that the two European tested cases rest on published
  reports (items 13 and 18). Since commit dba4c51, `share/README.md` says that for those 12 the
  reference gives the court or body, the date and the announcement, and the landing page says
  the two European tested cases come from published reports [Certain, from the files].

## Where recorded

Line numbers are as at commit 1be3729.

- `CLAUDE.md` lines 15-20 (added in commit a795ab8).
- `docs/decision_log.md` lines 20, 21 and 43; deferred lines 57, 58 and 60.
- `radar/brief/README.md` lines 90-100.
- `scripts/build_share.py`; `tests/test_share.py`
  (`test_the_case_register_copy_cites_official_references_only`); `tests/test_brief.py`
  (`test_contexts_hold_no_url_and_no_per_person_detail`).
- `share/README.md` lines 12-19.
- Commits a795ab8, fe90ade, 15525c3, f3c5331 and dba4c51.
