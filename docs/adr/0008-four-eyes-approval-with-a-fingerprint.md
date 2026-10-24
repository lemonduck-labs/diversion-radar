# 8. Four-eyes approval, bound to a SHA-256 fingerprint and to the author's own path

Date: 21 October 2026. Status: Accepted (a default, open to the owner).

## Context

Analyst briefs in the workspace are drafted by Claude or start from a template, and WORKFLOW.md
leaves the decision to a person. In the workspace's first store, who saved a brief was a field
in a shared collection that any Contributor could write, and so was the audit log (`app/README.md`
before commit 93d0484). The independent review of the workspace (its finding 3) asked for the
store itself to say who saved and who approved.

## Decision

- Contributors draft, check and submit; editors and the owner approve, return or reject.
  Four-eyes is on by default: the person who saved a version cannot approve it. A draft that
  fails the screen is never shown or saved (decision log line 28).
- Briefs, decisions and the audit log sit under each person's own path, so the path, not a
  field anyone can type, says who saved, who approved and who did what; decisions need Editor
  level (decision log line 32). That the platform enforces these rules for people other than
  the owner is [Likely] (Consequences).
- An approval counts only when the brief text still matches the SHA-256 saved with it and the
  SHA-256 the approver saw, and, with four-eyes on, someone else saved it. A decided file shows
  the version its decision names, never a later save (decision log lines 32 and 33).
- The decision's own four-eyes field is written by the approver, so it never decides alone:
  with the shared setting on, a self-approval does not count; with it off, it counts and is
  marked "One person", and turning four-eyes back on stops it counting (commit 14e7090).

## Options ruled out

- The first store, with the author as a field in shared collections: replaced in 93d0484 after
  review finding 3.
- Trusting the four-eyes field the approver writes on the decision: replaced in 14e7090.
- No other option is recorded as ruled out.

## Consequences

- That the platform enforces the path rules for people other than the owner is [Likely] until
  checked with two more accounts, one at Contributor and one at Editor (decision log line 32;
  deferred line 65). The browser flows test the page against a mock that applies the same rules,
  not the platform's own enforcement (`tests/browser/README.md`).
- In the pilot the artifact's owner can write anywhere, times come from the writer's browser,
  and a person can change or delete their own records (`app/README.md` lines 92-98).
- Four-eyes is a setting that Editors and the owner can turn off, and in demo mode any visitor
  can. The fact-check of 21 October 2026 found public wording ("a second person approves each
  brief") that left this out (item 3). Since commit dba4c51 the README says approval is by a
  second person while four-eyes is on, as it is by default, and that with it off one person may
  approve and the file says so (`README.md` lines 79-81).
- No hosted version exists to check four-eyes in a database for this workspace
  (`app/README.md` lines 99-101) [Certain].
- Since commit 1be3729 (22 October 2026) lessons follow the same pattern, with no setting to
  turn off: a reviewer's note kept as a lesson for later drafts is a field on the return
  decision, with the SHA-256 of its scope and text, and it is in force only once someone other
  than its author approves it with a reason for that SHA-256. fd-core's core alone would admit
  a person's own note at once; the workspace does not, because a note can carry pasted text
  (fd-core's P1.1; `app/README.md` lines 120-141; `app/src/page.js` lines 1764-1776) [Certain,
  from the code].

## Where recorded

Line numbers are as at commit 1be3729.

- `WORKFLOW.md` line 11.
- `docs/decision_log.md` lines 28, 32 and 33; deferred line 65.
- `app/README.md` lines 55-101, 120-141 and 143-150.
- `app/src/page.js` lines 301-309 (`approvalCheck`) and 1764-1776 (a lesson's status).
- `tests/browser/README.md` lines 28-37.
- Commits 46af934, 93d0484, 14e7090, dba4c51 and 1be3729.
