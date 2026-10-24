# 7. The deny list lives outside git

Date: 21 October 2026. Status: Accepted (a rule in CLAUDE.md).

## Context

fd-core's screen checks every output against a deny list of names that must never appear. The
first deny list was a tracked file, `config/deny_list.txt`, committed in 9529aa8 with a comment
line only. A list filled in that file would have put the names into the repo and its history.

## Decision

- `config/deny_list.txt` is local and gitignored; the tracked file is the template
  `config/deny_list.example.txt` (commit a795ab8).
- The list never reaches a browser. The workspace page cannot run the deny-list check, and a
  server that holds the list must run it before a brief leaves for anyone other than the owner.
- The demo site's build screens every text file with both repos' private deny lists.

## Options ruled out

- A tracked deny list, as first committed: "Filling a tracked file would put names in the
  repo" (CLAUDE.md line 22).

## Consequences

- The list holds no names yet. It is to be filled locally with the parties named in the case
  sources before the repo is shared beyond the owner (decision log, deferred line 61). Until
  then the screen's name check matches nothing, which the guardrails review of 21 October 2026
  raised for both repos (item 6) [Certain from the files: each holds one comment line].
- People's names are caught only through this list; firm names are caught by their legal-form
  endings (`fdcore/guardrails.py`) [Certain from the code].
- The workspace's own screen relies on its other checks and on a person reading every brief
  (`app/README.md` lines 103-118).

## Where recorded

Line numbers are as at commit 1be3729.

- `CLAUDE.md` lines 21-22.
- `.gitignore` lines 9-10; `config/deny_list.example.txt`.
- `docs/decision_log.md` deferred line 61.
- `radar/brief/README.md` lines 65-70; `app/README.md` lines 117-118; `site/README.md` lines
  62-63.
- Commits 9529aa8 (the tracked file) and a795ab8 (moved out of git).
