# The demo site

Four demos as static pages, for a link that opens on a phone with no sign-in: Diversion Radar's
dashboard and analyst workspace, and Move forward's market picture and planner. Built by
`scripts/build_site.py` into `site/dist/` (not in git). **Nothing is deployed.** Publishing is
the owner's decision, and each step that publishes is listed below for the owner to take.

A rise in exports is a lead, not evidence of a breach.

## What is in it

| Path | What | From |
|---|---|---|
| `/` | The landing page, neutral in graphite: what each demo is, what data it uses, what is switched off, and a link to each How it works guide | `site/index.html`, its figures filled from the radar's datasets |
| `/radar/` | Diversion Radar's dashboard | `demo/radar/index.html` and the eight datasets it reads |
| `/workspace/` | The analyst workspace, in demo mode | `app/index.html` and every file in its manifest |
| `/ta/` | Move forward's market picture | ta-market's `demo/ta/index.html` and the nine datasets it reads |
| `/planner/` | Move forward's planner, in demo mode | ta-market's `app/dist`, built by its `scripts/build_app.py` |
| `/assets/` | The site's styles, icon and `dash.js`; the two brands' marks, the landing page's font (IBM Plex Sans) and the fonts' licence (`assets/fonts/OFL.txt`) | `site/assets/`; each repo's `brand/` |
| `/vendor/` | d3 v7.9.0, with its ISC licence | `site/vendor/`, checked against its SHA-256 on every build |
| `/_headers` | Netlify headers: each page's Content-Security-Policy, and noindex | generated |
| `/site.json` | The three commits, and every file's SHA-256 | generated |
| `/videos/` | One captioned walkthrough per demo, with a poster, captions and a transcript | `--media site/media`, recorded by `tests/site/walkthrough.mjs` |

The two dashboards were written for Claude's Dashboard artifact type. `assets/dash.js` stands in
for that runtime with the calls the two pages make (`dash.data`, `dash.onData`, `dash.colors`,
`dash.params`, `dash.setParams`, `dash.resetParams`, `dash.setLink`), over JSON files beside
each page; the build stops if a page calls anything else. The workspace and the planner are the
pages published as artifacts, unchanged, inside a copy of the skeleton the Artifact tool wraps a
page in, as the tool's own description gives it (a charset and viewport meta and a small reset)
[Likely: the tool's wrapper is not in this repo to compare]. With no
Claude runtime they run in demo mode: changes stay in the tab, and briefs and plans start from
the template, as drafting with Claude needs the page inside Claude.

## What the site does not do

- No sign-in, no AI calls, no cookies, no analytics, nothing sent anywhere. Every page loads
  files from the site only, and its Content-Security-Policy allows nothing else (scripts from the
  site and the page's own inline scripts, by SHA-256; `connect-src 'self'`; fonts from the site
  or, for the brand fonts each tool and dashboard carries inline, data: URIs).
- No household-level or personal data. The planner's 200 households and the workspace's
  declarations and shipments are synthetic, made up from seeds.
- No council named and no exporter named. Series the display rule holds back are counted, never
  shown by corridor or code; a series not shown carries nothing from the radar on either side,
  so a held-back lead looks like any other series not shown; and the two backtest tests under
  the rule are listed by id only, with no case, route, codes or result.
- Not indexed by search engines by default: `X-Robots-Tag: noindex, nofollow` on every path and
  a robots meta tag on every page. Remove both in `scripts/build_site.py` and `site/index.html`
  if the owner wants it found.

## Build and check

From this repo, with fd-core installed (`pip install -e ../fd-core`) and ta-market beside it:

```sh
python scripts/build_site.py --check      # build in memory and run every check; writes nothing in this repo,
                                          # but rebuilds ta-market's app/dist (ignored by git) on the way;
                                          # add --media site/media to check the videos too
python scripts/build_site.py --clean      # write site/dist; refuses if any of the three repos has uncommitted changes
node tests/site/smoke.mjs site/dist shots # open every page in Chromium, desktop and phone width
```

The build checks, and stops on any failure: fd-core's screen over every text file with both
private deny lists; no council named; nothing held back by the display rule shown, a series not
shown carrying no field but its name and status, a test under the rule giving no route or
result, and no summary splitting the leads by onward check; no script,
style, image, frame or font from another site and no inline event handler; the Open Government
Licence line and link on every page with HMRC or MHCLG data; no Global Fishing Watch or
OpenSanctions data; every link inside the site resolves; no header set twice for a path. The
screen's two switchable checks are off only where the source repo's own policy turns them off
for the file copied, or `site/guardrails_policy.txt` does for a generated file.

The smoke test serves `site/dist` the way Netlify would (the headers from `_headers`, a folder's
`index.html`, `404.html` for a missing page) and fails on any console error, anything the
Content-Security-Policy blocks, failed request, request to another site, stray "null" or
"undefined" in a view, or sideways scroll at phone width. `tests/test_site.py` runs both.

## Walkthrough videos

One captioned walkthrough per demo, recorded from the built site in Chromium by
`tests/site/walkthrough.mjs`: frames from Chrome's own screencast, joined by ffmpeg into an
H.264 MP4 at 1280 by 720, with the captions drawn into the picture so they show wherever the file
plays. Each comes with a poster frame, the captions as WebVTT and a transcript, and each ends
with the Open Government Licence line, since each shows HMRC or MHCLG figures. The figures in
the captions are read from the site's datasets, and the recorder stops if a count typed into a
caption no longer matches them. The videos are not in git (`site/media/` is ignored);
`site.json` lists each one's SHA-256.

```sh
python scripts/build_site.py --clean                        # the site the videos are recorded from
node tests/site/walkthrough.mjs site/dist site/media        # or name some: ... site/media radar ta
python scripts/build_site.py --clean --media site/media     # the site again, with a link to each video
```

## Publishing (the owner's steps)

Before anything is published:

1. `/review`, then `/ship`, on the built site: the fact-checker and the guardrails-reviewer
   agents read every page and dataset (CLAUDE.md). The repos stay private either way.
2. The owner's own pre-publication checks, kept outside the repo.
3. `python scripts/build_site.py --clean`, so `site.json` names committed code only.

Then, on Netlify [Likely: Netlify's interface as of October 2026, not run here]:

1. Create a site by dragging `site/dist` onto the deploy area of the Netlify dashboard (Sites,
   then "Deploy manually"), or with the CLI at a pinned version (27.11.2, as in ta-market's
   hosted/README.md; published 6 October 2026, by the npm registry):
   ```sh
   NETLIFY_CLI=27.11.2
   npx netlify-cli@$NETLIFY_CLI deploy --dir site/dist          # a draft URL to check first
   npx netlify-cli@$NETLIFY_CLI deploy --dir site/dist --prod   # once it is checked
   ```
2. Check the headers arrived: `curl -sI https://<site>.netlify.app/radar/` shows
   `content-security-policy` and `x-robots-tag`.
3. Open each page on a phone.

Licences: HMRC and MHCLG data under the Open Government Licence v3.0, attributed on every page
that shows them. UN Comtrade's re-dissemination guidance allows limited tables and charts, and
free visualisation applications, without permission; the site shows a few tables and charts from
far fewer than 100,000 records, so no permission is needed [Likely, data/SOURCES.md]. d3 is
served under its ISC licence, whose notice must stay with it.

## Open for the owner

- Whether the landing page carries a byline. It names no person now.
- Whether the site may be indexed (noindex by default).
- Whether to show the two backtest tests under the display rule at all. Since 24 October 2026
  they are listed by id only, and the shared case register shows the case they are on without
  its corridors. Their case can still be read from the test ids and the pages, and its published
  reports name its corridors, so their routes can be inferred. What the public copies and the
  demo site hold back is each test's result and any UK figure on its route in the case's window
  (decision log, 24 Oct). Dropping the
  two rows as well stays the owner's call.
