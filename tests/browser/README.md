# Browser flows for the workspace page

End-to-end flows for `app/index.html`, run in Chromium against `mock.js`, a stand-in for the
claude.ai viewer's capabilities (`db`, `user`, `sample`, `downloads`). The mock applies the
same per-path rules the page declares at publish (author-bound briefs, decisions and audit;
decisions and config at Editor level; private drafts), so these flows test the page's logic
against those rules. They do not test the platform's own enforcement, which needs a second
account on the published artifact [Certain].

Users in the mock are role labels (Owner A, Editor B, Contributor C, Viewer D), chosen with
`?role=` and `?uid=` in the URL. The store lives in the browser's localStorage as `mockdb`.

## Run

```sh
cd tests/browser
npm install                     # Playwright 1.64.1
npx playwright install chromium # once, if no Chromium is installed
sh build.sh                     # copies app/ into dev/ with the mock
(cd dev && python3 -m http.server 8765) &
node flow.mjs http://localhost:8765 shots/flow       # inbox, files, briefs, four-eyes, packs, exporter
node decl_flow.mjs http://localhost:8765 shots/decl  # the restricted layer on synthetic declarations
node lessons_flow.mjs http://localhost:8765 shots/lessons   # lessons kept from returned briefs
node triage_flow.mjs http://localhost:8765 shots/triage     # the triage view on synthetic reports
node nav_flow.mjs http://localhost:8765 shots/nav           # the navigation (fd-core's shell)
```

Each prints its steps and ends with `{"ok":true,...}` or `... flow passed`; a failed step throws.
Screenshots go to `shots/`. `tests/test_browser_flows.py` runs all five under pytest, and is
skipped when node or the pinned Playwright in `node_modules` is missing.

## What the flows cover

- Drafting from the template and from a mocked Claude reply; the screen stopping an invented
  figure, an accusing word and prose around the JSON.
- Save, submit, return and approve; four-eyes: a self-approval does not count with the setting
  on, including one whose decision claims it was off; with four-eyes off a self-approval counts
  and is marked "One person"; turning it back on stops it counting.
- Tampered and forged approvals, roles (Viewer, Contributor, Editor, Owner), demo mode with no
  store, the evidence pack and audit export, the exporter screen, narrow screens.
- The restricted layer: case list, case file, outcome proposal and approval, the evaluation view.
- Lessons: a reviewer keeps a return note as a lesson; its author cannot approve it and a second
  person does with a reason; a later draft recalls it with its provenance and sends it to Claude
  as data; a changed text stops it being used; retiring it ends it; three demo people in one tab.
- Triage: the reports in reading order; a listed registration number and the synthetic entry; a
  route linked to its lead file, and one held back under the display rule marked as such and
  nothing more; an outcome proposed and approved; a name in a reason refused; no request for more
  on an anonymous report; the audit log; narrow screens.
- The navigation (`nav_flow.mjs`), fd-core's shell as the workspace uses it: the sidebar's queues,
  views and pages with their counts (an empty work queue shows none); a view's own link; j and k
  through a list and between files, cases and reports, with each one's place in its list as
  filtered; Escape back to the row it came from; the search palette by country and by page, and
  its empty state; the shortcuts sheet, whose Escape leaves the page as it was; g then a letter; a
  view reloaded from its link; the drawer on a narrow screen.
