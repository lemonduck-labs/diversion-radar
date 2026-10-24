# Hosting the radar workspace on Supabase and Netlify

The kit for moving the radar's analyst workspace (app/) from the pilot inside Claude to a site of
its own: Supabase Postgres in London for the shared store, sign-in and the drafting function, and
Netlify for the page. It is built and tested on this machine. **Nothing is deployed**: no Supabase
project, no Netlify site, no secret and no API key exists for it yet. Everything below is for the
owner to do, in order.

A file in the workspace is one corridor and one goods code at one run: aggregates, never an
exporter. The restricted layer's cases are synthetic, and the database refuses any case that is not
SYN-CASE-001 to SYN-CASE-999. Briefs and outcomes are leads for a person to check, never findings.
A rise in exports is a lead, not evidence of a breach.

The hosted version has no lessons yet: the Lessons view says so, and the database refuses a brief
or a decision that carries one. Nor does it record triage outcomes or checks: the Reports view reads
each synthetic report against the radar as in the pilot, and says the hosted version records no
outcomes yet, as the database takes lead and case files only. Both run in the artifact and demo
builds.

## What runs where

| Part | Inside Claude (the pilot) | Hosted (this kit) |
|---|---|---|
| Page | `app/index.html`, published as an artifact with its data files | `app/dist-hosted` on Netlify: the same page, unchanged, after the Supabase client and `app/src/hosted.js` |
| Shared store | The artifact's database, with its path rules | Supabase Postgres (London), with row-level security and triggers (`supabase/migrations/`) |
| Sign-in and roles | The artifact's sharing levels | Supabase Auth (an emailed code, invited people only), roles in `public.members` |
| Drafting | Claude on the viewer's own usage | The `draft-brief` Edge Function, with the owner's Anthropic key, screening every draft with the private deny list |
| Audit log | Written by the page under each person's path | Written by the database from triggers; no member can change or delete it |
| Downloads | The artifact's downloads | A browser download |

## What is in the kit

| Path | What it is |
|---|---|
| `supabase/migrations/20261022000000_radar_workspace.sql` | Tables, roles, row-level security, and the triggers that set who and when, check four-eyes and fingerprints, and write the audit log |
| `supabase/functions/draft-brief/index.ts` | The drafting function for Supabase (Deno); `core.mjs` holds its logic |
| `supabase/functions/draft-brief/_bundle/` | Written by the build, not in git: `app/src/screen.js` unchanged, each file's facts, the prompt, the screen rules, fd-core's guardrails patterns, and the private deny list |
| `app/src/hosted.js` | The page's `claude.use(...)` over Supabase, and the sign-in bar |
| `scripts/build_hosted.py` | Writes `app/dist-hosted/` (not in git) and the function's bundle |
| `tests/test_hosted_db.py`, `tests/test_hosted_js.py` | The tests (see the last sections) |

How the page's records map to tables is set out at the top of the migration and of `hosted.js`.

## Before you start

- A Supabase account and organisation, a Netlify account, and an Anthropic Console account where
  you can create an API key and set a spend limit.
- This repo with its tools: Python with the repo's dependencies and fd-core (`pip install -e
  ../fd-core`, with fd-core beside this repo or `FD_CORE` set to it), and node. The Supabase and
  Netlify command-line tools run through npx at pinned versions, so nothing needs installing
  globally. Set the versions once in your shell:
  ```
  SUPABASE_CLI=2.120.0
  NETLIFY_CLI=27.11.2
  ```
- The private deny list in `config/deny_list.txt` on the machine that builds (it is in
  `.gitignore`; copy `config/deny_list.example.txt` to start one). The build puts it in the
  function's bundle, never in git or the page.
- The list of people and the role each should have (see step 9).
- A decision on who holds the Anthropic key and pays for it. The key never goes in the repo, the
  page or a message: only into the Supabase dashboard.

## Step 1. Create the Supabase project in London

1. In the Supabase dashboard, create a project in your organisation. Choose the **specific region
   London (eu-west-2)**, not a general "Europe" grouping, which can also mean another country
   [Likely: the label in the dashboard].
2. Set a strong database password and keep it in your password manager.
3. Note the project's URL (`https://<project-ref>.supabase.co`) and, under the API keys settings,
   its **publishable key** (`sb_publishable_...`). The publishable key is the only key that ever
   goes into the page. Never copy the secret key (`sb_secret_...`) or the legacy service-role key
   anywhere.

## Step 2. Run the migration

Either way works; use one.

- **Dashboard**: open the SQL Editor, paste the whole of
  `supabase/migrations/20261022000000_radar_workspace.sql` and run it once.
- **Command line** [Likely: CLI behaviour not run here]:
  ```
  npx supabase@$SUPABASE_CLI login
  npx supabase@$SUPABASE_CLI init                       # once, if supabase/config.toml does not exist
  npx supabase@$SUPABASE_CLI link --project-ref <project-ref>
  npx supabase@$SUPABASE_CLI db push
  ```

Then check, in the Table Editor, that the ten tables exist with row-level security on (members,
briefs, decisions, files, checks, config, events, drafts, private_drafts and audit), and in
Database, Publications, that `supabase_realtime` includes members, briefs, decisions, files,
checks, config and audit.

## Step 3. Make yourself the owner

1. In Authentication, Users, add yourself (send an invitation or create the user).
2. In the SQL Editor, give yourself the owner role. The name is what colleagues will see in the
   audit log and in evidence packs:
   ```sql
   insert into public.members (user_id, role, display_name)
   select id, 'owner', '<your name as colleagues know it>' from auth.users where email = '<your work email>';
   ```

## Step 4. Close sign-up and set up the sign-in email

1. In the Authentication settings, turn off new sign-ups, so that only people you invite can sign
   in [Likely: the setting's label]. The page also asks Supabase never to create an account.
2. In Authentication, Email Templates, edit the **Magic Link** template so that it shows the code:
   add `{{ .Token }}`, for example "Your sign-in code for the radar workspace is {{ .Token }}". The
   page asks for that code.
3. Supabase's built-in email sender has low rate limits; for more than a handful of people, set up
   your own SMTP sender in the Authentication settings [Likely].

## Step 5. Build the hosted folder

```
python scripts/build_app_page.py        # if app/src has changed since app/index.html was built
python scripts/build_hosted.py --supabase-url https://<project-ref>.supabase.co --publishable-key sb_publishable_...
```

This writes `app/dist-hosted/` and `supabase/functions/draft-brief/_bundle/` from the same build.
The build refuses a page that does not hold `app/src` as it is, data files that do not match
`app/data/manifest.json`, a secret or service-role key, and a URL that is not https. Without the
two settings it writes placeholders, and the page says it has no project settings. Add `--clean`
to refuse to build from files that are not committed, so `hosted.json` names a commit you can
find. Without `config/deny_list.txt` (or `--deny-list FILE`) the bundle holds no deny list, the
build says so, and the function will not draft until one is bundled or set as the `DENY_LIST`
secret.

## Step 6. Set the function's secrets and deploy it

1. In the Anthropic Console, create an API key for this project only, and set a monthly spend
   limit on its workspace.
2. In Supabase, Edge Functions, Secrets, add:

   | Secret | Value |
   |---|---|
   | `ANTHROPIC_API_KEY` | The key from 1 (required) |
   | `ALLOWED_ORIGINS` | The Netlify site's address, once you have it (step 8) |
   | `DENY_LIST` | Optional: more deny-list terms, one per line, added to the bundled list without a new build |
   | `ANTHROPIC_MODEL` | Optional; the function uses `claude-sonnet-5-5` without it |
   | `DRAFTS_PER_HOUR` | Optional cap per person; 30 without it |

   Supabase gives every function its URL and server key itself.
3. Deploy the function from the folder the build wrote, with JWT checking at the gateway off,
   because the function checks the caller's session itself and Supabase's gateway check does not
   take the new key types [Likely: CLI behaviour not run here]:
   ```
   npx supabase@$SUPABASE_CLI functions deploy draft-brief --no-verify-jwt --project-ref <project-ref>
   ```

The deployed function carries the deny list in its code, so anyone who can open the project's
functions can read it [Likely: how Supabase shows a deployed bundle]. Keep that group to the people
who may see the list.

The function drafts only for a signed-in member at Contributor or above, only for a file whose
facts are in its own bundle, only when the page's prompt is the one it builds itself (otherwise it
answers that the builds differ), and never more than the hourly cap. It builds the prompt with the
page's own code (`app/src/screen.js`, `buildPrompt`, with no lessons), sending the system section
as the system prompt and the user section as the user turn, as `spec/prompt.md` says. It reads the
file's reviewer notes from `public.decisions` itself, never from the caller, with the brief each
decision names and the four-eyes setting, so it starts the notes again after the same approval
the page counts; a note the private deny list would hold back stops the draft (`note_blocked`)
instead of reaching Claude. It screens every reply as `radar/brief/screen.py` does: the shared
rules of `screen.js`, then fd-core's guardrails over every string with the deny list (company
names, email addresses, postcodes, phone numbers, deny-list names and judging words). Every draft
is recorded in `public.drafts` (who, which file, passed or not, which rules, token counts, never
the text) before anything is returned. A draft that fails the screen is never returned.

## Step 7. Deploy the site to Netlify

Deploy the built folder, not the repo: the build needs fd-core and writes files that stay out of git.

- **Dashboard**: add a new site, deploy manually, and drop the `app/dist-hosted` folder.
- **Command line** [Likely: CLI behaviour not run here]:
  ```
  npx netlify-cli@$NETLIFY_CLI deploy --dir app/dist-hosted --prod
  ```

The folder carries a `_headers` file: a Content-Security-Policy that lets the page run only its own
inline code and styles (by SHA-256, the style element fd-core's shared navigation adds when it
mounts included), its few fixed style attributes (by SHA-256), the pinned Supabase client
and calls to your project, with no framing and no referrer. It also carries `robots.txt` and a
`noindex` header, which ask search engines to keep out, and `hosted.json`, the build record.

## Step 8. Point Supabase and the function at the site

1. In Authentication, URL Configuration, set the Site URL and the redirect URL to the Netlify address.
2. Set the function's `ALLOWED_ORIGINS` secret to the same address (comma-separated if there is
   more than one). No redeploy is needed for secrets [Likely].

## Step 9. Invite colleagues by role

| Role | Can |
|---|---|
| viewer | Read everything shared; export evidence packs, the audit log and their own exporter screen results |
| contributor | Also take files, draft briefs (with Claude or the template), save and submit them, work the checks, and propose outcomes on synthetic cases |
| editor | Also approve, return, reject and reopen briefs and outcomes, and turn four-eyes on or off |
| owner | Also add members and change their roles (from the SQL Editor or the API) |

For each person: add them in Authentication, Users (send an invitation), then in the SQL Editor:

```sql
insert into public.members (user_id, role, display_name)
select id, 'contributor', '<their name as colleagues know it>' from auth.users where email = '<their work email>';
```

To change a role, `update public.members set role = 'editor' where user_id = '<their id>';`. To
remove access, `update public.members set active = false where user_id = '<their id>';`. Their
records keep their name. Deleting the account of anyone in `public.members` is refused, by design,
so that no record loses its author.

## Step 10. What to check first

Use two colleagues, or two accounts of your own: one at Contributor and one at Editor, besides
yours as owner. The owner meets every level, so the owner alone cannot test the roles.

1. **Sign-in.** Open the site. Sign in as the Contributor with the emailed code. The bar says
   "Signed in as ..., contributor" and the store chip says "Shared store". An account that is
   signed in but not in `public.members` sees that it has not been given access, and nothing else.
2. **A brief through the workflow.** As the Contributor, open a file, start from the template,
   save and submit. The Contributor is not offered Approve. As the Editor, open the file and
   approve, then export the evidence pack. The audit log shows each step under the right name.
3. **Four-eyes.** As the Editor, save and submit a brief on another file, then look for Approve: it
   is not offered for your own brief. The database refuses it too, whatever the page does. To see
   that, run this in the SQL Editor with the Editor's id and, from `public.briefs`, the `key`,
   `lead`, `run` and `sha256` of a brief they saved; it rolls back either way [Likely: that the SQL
   Editor lets you take the authenticated role like this]:
   ```sql
   begin;
   set local role authenticated;
   set local request.jwt.claims to '{"sub": "<editor user id>", "role": "authenticated"}';
   insert into public.decisions (id, lead, run, series, decision, brief_id, brief_sha256)
   values ('check~four-eyes', '<lead>', '<run>', 'check', 'approved', '<key>', '<sha256>');
   rollback;
   ```
   Expected: "four-eyes is on: the person who saved this brief cannot approve it". The same with
   the Contributor's id gives "only an Editor or the owner can record a decision".
4. **The audit log cannot be changed.** In the SQL Editor, `update public.audit set detail = 'x'
   where id = 1;` is refused ("audit is insert-only"), and so is a delete, even for you.
5. **Drafting.** As the Contributor, draft with Claude once. A row appears in `public.drafts`, the
   function's logs show the file id and the rules only, and a brief appears in the page for the
   analyst to read. If a draft is stopped by the screen, the bar says what the screen found and
   the page says the draft did not arrive; draft again or start from the template.
6. **The restricted layer.** As the Contributor, open a synthetic case under Declarations and
   propose an outcome; as the Editor, approve it. Both rows carry the case's SYN-CASE id.
7. **Lessons and triage.** The Lessons view says the hosted version has no lessons yet, and
   returning a brief offers no lesson. A report under Reports shows its reading, and its Outcome
   card says the hosted version records no triage outcomes yet.
8. **The browser console.** No Content-Security-Policy errors, and no integrity error for the
   Supabase script. If the Supabase script is blocked, check that the file jsDelivr serves still
   has the SHA-384 in `scripts/build_hosted.py` (`curl -s <the URL> | openssl dgst -sha384 -binary | openssl base64 -A`).
9. **Live updates.** With two browsers open, a change in one shows in the other within seconds.

## Changing things later

- After any change to the data, the spec, the page, `screen.js`, `hosted.js` or the deny list:
  build with `scripts/build_hosted.py` again, then deploy both the function (step 6.3) and the site
  (step 7). The function refuses to draft for a page from a different build.
- A schema change is a new file in `supabase/migrations/`; never edit one that has been run.
- A new run needs nothing in the database: its files have new ids, and earlier runs' records stay.
- To rotate the Anthropic key, create a new one, replace the secret, then revoke the old one.

## Running the tests

`python -m pytest -q` runs everything that needs only Python, node and Postgres (with fd-core
beside this repo, or `FD_CORE` set to it). Two checks run only when their tools are there:

- the drafting function under Deno (type-checked, then run against a faked project and a faked
  Claude): put Deno on the path, or set `DR_DENO` to it;
- the site in a real browser: Playwright with its Chromium (the copy in `tests/browser`, or
  `DR_PLAYWRIGHT` set to its `index.mjs`), and a copy of the pinned Supabase client:
  ```
  SUPABASE_JS=2.117.2
  npm pack "@supabase/supabase-js@$SUPABASE_JS"
  tar -xzf "supabase-supabase-js-$SUPABASE_JS.tgz" package/dist/umd/supabase.js
  export DR_SUPABASE_UMD="$PWD/package/dist/umd/supabase.js"
  ```
  The test skips unless the file has the SHA-384 the page checks. `TA_SUPABASE_UMD`, as the
  planner's tests name it, works too.

## What the database guarantees, and what it does not

Guaranteed by the database, whatever any page or script sends [Certain: tested on Postgres 16,
with a stand-in for Supabase's auth schema and roles]:

- Every author, actor and time is set by the database from the signed-in caller and its clock.
- Every active member reads; a signed-in account that is not a member reads nothing; nobody reads
  without signing in. Only Contributors and up save briefs and outcomes, move the status pointer
  and work the checks; only Editors and the owner record decisions and change four-eyes; only the
  owner manages members, and cannot change their own role or remove the last owner.
- An approval is refused when four-eyes is on and the approver saved the brief, when the SHA-256
  it names is not the brief's, when the brief is not the one submitted, or when the file has not
  been submitted again since the last decision. A brief or an outcome is refused unless its SHA-256
  is the SHA-256 of its draft in the page's canonical JSON, which the tests check against the
  page's own code for the template brief of every file and an outcome on every case.
- A brief must be a `radar-brief/1` draft for its file's series and run, list the reviewer notes
  it answers and answer each once; an outcome must be for its own synthetic case, with one of the
  three outcomes and a note; file ids are a run's corridor and code, or a SYN-CASE id, on every
  table; a decided file takes no new brief, no pointer move and no check until it is reopened.
- No brief or decision carries a lesson.
- Follow-ups (`public.tasks`, migration `20261022130000_radar_followups.sql`): only Contributors
  and up add one, tick it off or change its text, date or owner; who added and who finished each
  are set by the database; a new owner must be an active member; a follow-up's id and file never
  change; nobody deletes one, and every change writes an audit row. Unlike the checks, follow-ups
  can still change on a decided file.
- Monitoring decisions (migration `20261022170000_radar_monitor.sql`): accepted with a grade on
  the six-by-six scale, or rejected with a reason from a fixed list; who and when are set by the
  database; nobody deletes one; every change writes an audit row. The items are files built
  with the page, not rows.
- Outcomes and end-use decision records (migration `20261022160000_radar_outcomes.sql`): an
  outcome needs a decided brief, and a rejected lead takes only "no further action" or "keep on
  watch"; who recorded it and when are set by the database. A decision record needs the outcome
  "put forward", every check before it can recommend putting a route forward (a table
  constraint), and an editor other than the recorder to approve it; any change to its content
  clears the approval. Nobody deletes either, and every change writes an audit row. A referral
  pack's export is a page event (`referral_exported`).
- Nobody, the dashboard included, changes or deletes briefs, decisions, drafts, page events or
  the audit log, and no audited table can be truncated. Every insert, update or delete of the
  shared tables writes an audit row, with the person, the database role and the change. Private
  drafts are left out, so the shared log never holds them.

Not guaranteed:

- Notes, reasons and follow-up text are screened for names in the page only. A Contributor who
  writes to the database's API directly can store text the page would refuse [Certain]; the audit
  log records who did.

- The table owner (the dashboard's SQL Editor) can still change the status pointer, the checks,
  the setting and members; each change is in the audit log with no person and the database role
  [Certain]. The owner could also drop the triggers [Certain]: the audit log is as trustworthy as
  the people who hold the database password.
- The page still trusts itself for what a brief says: the database checks its fingerprint and its
  shape, not its words. The screen runs in the page and in the function; the database does not run
  it, so a person who edits a brief past the page could save words the screen would stop [Certain].
- A file id is checked for its shape, not for being a file the run publishes [Certain].
- Page events (exports, the exporter screen) are reported by the page; the database sets who and
  when, not whether the file was really saved, and keeps the page's detail to 200 characters
  [Certain]. The exporter's own file never leaves the browser; its event holds counts only.

## What is not built or not tested

- Nothing is deployed, and nothing here has run against a real Supabase project, Netlify or the
  Anthropic API [Certain].
- Lessons are not in the hosted version [Certain]. Moving them needs their records in the database
  and a recall step in the drafting function.
- Triage outcomes and checks are not in the hosted version [Certain]. Moving them needs report
  files (`report_RPT-SYN-nnn`) in the tables' id checks and an outcome branch like the restricted
  layer's in the briefs and decisions triggers, with the triage view's five outcomes.
- The migration is tested on a local Postgres 16 with a stand-in for Supabase's `auth.uid()`,
  roles and default grants (`tests/hosted_supabase_stub.sql`). That it behaves the same on
  Supabase is [Likely]; the stand-in copies how Supabase sets `request.jwt.claims` but is not
  Supabase.
- `hosted.js` is tested in node with a fake Supabase client, through the page's own store code,
  and in headless Chromium with the real supabase-js 2.117.2 (loaded past its SHA-384 check) under
  the site's Content-Security-Policy, against a fake of the project's Auth, REST and function
  endpoints: a Contributor and an Editor sign in with an emailed code and take briefs through the
  template, a Claude draft, a draft stopped by the screen, submission, approval and an evidence
  pack export, then open the Lessons view and a triage report, with nothing blocked by the policy
  and no page error [Certain: run in this session].
  It has not run against a real project, and live updates over Supabase Realtime are untested: the
  check closes the socket, so the page falls back to polling every 20 seconds [Certain]. That the
  real services behave like the fakes is [Likely]. Real email delivery of the code is untested
  [Certain].
- The restricted layer's outcomes are tested in the database and through `hosted.js` against the
  fake client, not in the browser check [Certain].
- `index.ts` is type-checked and run end to end under Deno 2.9 against a faked project and a faked
  Claude [Certain: run in this session]; the test repeats this only where Deno is installed. It
  imports nothing from outside its folder, but Supabase's Edge Runtime is not Deno 2.9 itself, so
  that it deploys and runs unchanged is [Likely]. Its calls to the project (Auth's user endpoint
  and four REST calls) follow Supabase's documented headers for the new secret key and the legacy
  service-role key [Likely until run on a project].
- The function's port of fd-core's screen gives the same findings as fd-core on the tests' text,
  including digits and spaces outside ASCII [Certain]. Where Python and JavaScript fold case or
  count characters differently in other text, they could differ [Guessing: no case found].
- The SHA-384 of the Supabase client was computed from the npm package; that jsDelivr serves the
  same bytes is [Likely] (check 8 above).
- The Content-Security-Policy's hashes are tested to match the page, and Chromium runs the page
  under it with nothing blocked [Certain]. It allows the page's fixed style attributes with
  `'unsafe-hashes'`; a browser without that keyword would drop those few styles, not the page
  [Likely]. Other browsers [Likely] until check 8.
- The Method view, the audit log and the brief panel tell the two versions apart by whether
  `app/src/hosted.js` has loaded (`window.RadarHosted`) [Certain, from the code and the browser
  check; not yet seen on a deployed site].
- The page's own limits stay: it reads the records of at most 18 people and the latest 1,000 audit
  entries per person [Certain].
- When a draft fails the screen, the page says the draft did not arrive, because it cannot show
  the function's list of problems without a change to the page; the bar shows the list [Certain].
- The dashboard labels named above, the CLI commands and the region label may differ from what
  Supabase and Netlify show today [Likely].
- Staff names and emails are personal data, in `auth.users`, `public.members`, the audit log and
  the evidence packs. The data protection officer should agree where the project is hosted, who
  can open the dashboard and how long the log is kept, before anyone outside a test uses it
  [Likely].
