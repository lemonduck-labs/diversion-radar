# Analyst workspace: user walkthrough script

A 30-minute usability session with one trade or sanctions analyst, run by the owner. The
workspace runs on the demo site in demo mode: the October 2026 run's leads from published trade
statistics, made-up shipments and declarations, no sign-in, no AI drafting, nothing sent
anywhere.

## 1. Purpose and what we want to learn

We want to see whether an analyst can use the workspace for their own work without help, and
where it gets in their way. We are testing the tool, not the analyst.

Research questions:

1. Can an analyst find the lead they would look at first and say why, from what the inbox and
   the file show?
2. Can they read a file's UK and onward figures, and its link to past enforcement cases, without
   reading more into them than is there: a lead, not evidence of a breach?
3. Do they trust a first draft of a brief enough to edit it rather than rewrite it, and do they
   understand why the screen stops a figure that is not in the evidence: that the screen is a
   net and they decide?
4. Does four-eyes review, where a second person approves or returns every brief, fit how their
   team works, and is the audit log a record they would rely on?
5. Can they use the exporter screen on the made-up sample and say what its order of checks means,
   and what it does not mean?

The session is not for showing the tool off, training anyone or collecting case information.
The participant brings nothing and types or uploads nothing from their work.

## 2. Before the session (for the owner)

**The link.** The demo site's workspace page: `<demo site address>/workspace/`. Nothing to
install, no sign-in. Open the workspace itself, not the site's front page, so the session starts
on the inbox. The site is not published yet (`site/README.md` lists the steps): put the address
here once it is. Until then, an in-person session can run from a local copy on your own laptop:
build the site (`python scripts/build_site.py`, with ta-market beside this repo; add `--clean`
for the copy you publish), serve it with `python -m http.server 8000 --directory site/dist`, and
open `http://localhost:8000/workspace/` on the same laptop.

**Who to invite.** A trade or sanctions analyst: someone who works with trade data, export
controls or sanctions compliance, in government, in a firm's compliance team or in research. No
technical knowledge needed. They should not have seen the workspace or its walkthrough video.

**What to tell them beforehand.** It takes 30 minutes. If remote, they need a laptop or desktop
with a recent browser (a phone works, but editing a brief is easier on a bigger screen). They
bring nothing: no files, case notes or shipment data.

**Synthetic records only.** The leads come from published trade statistics, totals by country and
goods code, and name no exporter. The shipments in the exporter screen and the declarations are
made up, every reference starting SYN-. Never ask the participant to bring, type or upload case
data, names of people or firms, or files of their own. If they start to, stop them and steer back
to the made-up sample. If they mention a firm, a person or a case aloud, don't write it down.

**Nothing they type is kept after the tab closes.** The demo has no shared store: briefs, notes,
checks and the audit log live in the browser tab, go when it closes, and are never sent anywhere.
A shipments file is read in the browser and never uploaded or stored. One catch: in an ordinary
window the browser remembers who you are acting as, the inbox filter and the last page shown,
until its site data is cleared. So always open the link in a new private window and close it at
the end; then nothing at all is kept.

**Consent.** Ask before you start; the welcome below has the words. Notes need their yes. Record
only if they agree, and then only the screen and your voices; keep the recording in the same
private place as the log, never in a repo, and delete it by the date you give them.

**Checklist**

- [ ] The site is built from the pages you mean to test: rebuild `site/dist` before the first
      session and check that `site/dist/site.json` names the commits you expect, with no
      uncommitted changes. On 22 October 2026 at 02:37 the copy there was built with `--clean`
      from diversion-radar 33ca4fb, ta-market 98c745a and fd-core 72ead08.
- [ ] The link opens on the device and network the participant will use. Government and company
      networks often block new sites: check a day ahead, and have your own laptop ready.
- [ ] You have run every task yourself on the build you will test, in a private window, and
      corrected the crib below if anything has moved. The page was still changing when this
      script was written.
- [ ] A new private window is open on the inbox, acting as the analyst, with no filter set. Open
      it in the minutes before the session; never reuse one from a rehearsal or an earlier
      participant.
- [ ] You won't reload the page or press back during the session: in demo mode that clears the
      briefs made so far.
- [ ] The log (section 4) is ready in a private document or on paper, with a clock to hand.
- [ ] You have the fallback line for task 3 ready: "UK exports rose by 300% on the 2019-21
      average."
- [ ] You have not sent the walkthrough video or screenshots: finding things is part of what we
      test.
- [ ] You have asked whether they use screen magnification, a screen reader or other settings,
      and set the device up to match.
- [ ] Remote: they open the link in a private window and share their screen. If it won't open on
      their network, share yours and let them tell you what to do; note that in the log.

**Owner's crib for today's build** (for you only: never read it out or point to it)

Checked on 22 October 2026 against the page at commit 8ddadc8 (the counts, links and messages
below against its committed code and data); they still hold at 9c91283, which adds a triage view
that this session does not use. 69e40c1 moved the page's navigation into a sidebar, and rows 1,
4, 5 and 6 were brought up to date against the demo site built at 02:37 from 33ca4fb [Certain,
from the built page]. The layout will change; the task wording should not.

| Task | Where it is today | What the tool shows when it works |
|---|---|---|
| 1 | Inbox: 23 files, grouped by what each needs next, so at the start "Leads with no brief yet" (7) and then "Watch items with no brief yet" (16). The sidebar lists queues named for the job (Needs my review, Returned to me, Assigned to me), then Leads and Watch items; the search at the top (Ctrl or Cmd + K) finds a file by country or code. There is no sort, and the list does not show which files touch a past case. A line under the list counts the 12 series held back by the display rule. In demo mode the workspace first opens on a sign-in screen; signing in as "Analyst (demo)", a Contributor, shows that person at the foot of the sidebar (since phase 6; before it, an "Acting as" menu). | A file opens with its reference (DR-2026-10-...), Lead or Watch, and its state. |
| 2 | The file's left column: "What rose" (UK exports in pounds, the corridor's exports to Russia in dollars, runs as a lead), a chart of UK exports at each run, a chart of the corridor's exports to Russia by year, "Linked enforcement cases" on files that touch one, and "Limits of this lead". Leads that touch a past case in the October 2026 run: Kazakhstan 8517.62 (EU-01), India 8542.31 (US-01), China 8532.21 and both United Arab Emirates leads (EU-05 and US-01). | They say what rose, against what, and what a linked case does and does not mean. |
| 3 | "Analyst brief" card: "Start from the template" is the only way to start, as AI drafting is off in the demo. Then "Edit": lines can be reworded or removed, not added, and the questions can't be reworded. "Done editing" works only when the brief passes; then "Save draft". The questions to check appear once a version is saved. | "Not yet: fix these before saving." and "A figure that appears nowhere in the context.", with the figure and "Done editing" off. Once saved: "Drafting", "Version 1 of 1, saved (time) by Analyst (demo) (you)". |
| 4 | "Submit for approval". As the analyst they then see "Awaiting approval by an editor." and nothing to press. To play the second person they press "Switch user", at the foot of the sidebar, and sign in as "Reviewer (demo)", an Editor: Approve, "Return with a note" and Reject are then open. The return form has a box, "Keep this note as a lesson for later drafts", whose lesson waits on the Lessons page for someone other than the person who kept it: "Lead reviewer (demo)", the third demo person and also an Editor, can approve it with a reason. | "Returned by Reviewer (demo)" with the note. Back as the analyst: "This version was saved before the brief was returned. Draft a new version: it must answer the reviewer's note, then submit it." |
| 5 | Exporter check, in the sidebar under Tools: "Try the synthetic sample". | 362 rows and 12 destination and code pairs: 3 "Check first" (Kazakhstan 8517.62 at the top), 4 "Check", 4 "Not shown (display rule)", 1 "No radar signal". "Questions" opens the questions to ask for a row. No row goes to Russia or Belarus. |
| 6 | Audit log, in the sidebar under Reference, newest first; each file also has its own "Activity" list. | Entries for saving, submitting, returning, keeping a lesson and screening the shipments file, under "Analyst (demo)" and "Reviewer (demo)". |

Switched off in the demo: AI drafting, and every download (evidence pack, exporter results,
audit export). If they reach one, ask what they expected it to do.

What the screen does on today's build, checked on 22 October 2026, so you can log what you see:

- A rise written in words is stopped: "tripled" or "more than doubled" gets "A multiple or
  fraction in words (doubled, tripled, twice, halved): give the figure the cited items write
  instead." A count from two to twelve written in words is read as a figure and must be in the
  items the line cites. Both since commit f63245d.
- A figure the participant works out (a percentage change, say) is stopped even when the sum is
  right, because every figure must come from the file's evidence. Log their reaction; it is the
  screen working as built.
- A figure from the evidence is stopped when the line does not cite it, for example the onward
  figure written into a line about the UK figures: "A figure that is in the context but not in
  the items the claim cites."
- A return note with two capitalised words in a row can be stopped as a possible name.

## 3. Script: 30 minutes

| Clock | Block | Minutes |
|---|---|---|
| 0:00 | Welcome, ground rules and consent | 3 |
| 3:00 | Warm-up: how they do this work today | 3 |
| 6:00 | Task 1: find the lead to look at first | 3 |
| 9:00 | Task 2: what rose, and the case routes it touches | 3 |
| 12:00 | Task 3: a first brief, edited | 4 |
| 16:00 | Task 4: send it back with a note | 3 |
| 19:00 | Task 5: an exporter's shipments | 3 |
| 22:00 | Task 6: the record of what was done | 2 |
| 24:00 | Closing questions | 5 |
| 29:00 | Thanks and close the window | 1 |

Running late: at 16:00, if no brief is saved yet, help them save one so task 4 can follow, and
mark task 3 "with help". If you are more than three minutes behind at 22:00, ask task 6 as a
question in the closing block instead. Never cut the closing questions.

How to run the tasks:

- Read each task as written. Don't name a page, button or menu, and don't point. Finding the way
  is part of the test.
- Let silence run. If they go quiet, ask "What are you thinking?"
- If they ask you something, turn it back: "What do you think it does?" Note the question.
- If they are stuck, wait about a minute, then ask "What would you try next?" If they are still
  stuck when the task's time is up, show them and mark the task "with help".
- Note the clock when each task starts and ends.

### 0:00 Welcome, ground rules and consent (3 minutes)

Say:

> Thank you for giving me half an hour. I'm going to show you a tool that looks in published
> trade figures for places where UK exports of high-priority goods to a country rose, and that
> country's own exports of the same goods to Russia rose too. I'll ask you to try a few things
> with it.
>
> We are testing the tool, not you. If something is hard to find or doesn't make sense, that's a
> problem with the tool, and it's what I most need to hear. There are no wrong answers.
>
> Please think aloud as you go: what you're looking for, what you expect to happen, and anything
> that surprises or annoys you. If you go quiet, I may ask what you're thinking.
>
> I won't help much while you work, because I want to see what you'd do on your own. If you ask
> me something, I may ask what you think first. I'll answer anything at the end. I'll keep us to
> time, so I may move us on before you've finished something, and that's fine.
>
> The trade figures are published totals by country and goods code; no exporter is named. The
> shipments and declarations in the tool are made up. Please don't type or upload anything from
> your own work: no names of people or firms, no case details, no files of your own. If you need
> an example, make one up.
>
> This is a demo. It runs in this browser window, sends nothing anywhere, and keeps nothing once
> the window is closed. A few things are switched off, such as downloads. If you reach one, tell
> me what you'd expect it to do.
>
> The screens are going to be redesigned, so anything that doesn't work for you is the most
> useful thing you can tell me.
>
> I'd like to take notes. They won't have your name or your employer on them, and I keep them
> privately. Is that all right?

Wait for the answer. If you would like a recording, ask:

> Would you be happy for me to record the screen and our voices, so I can check my notes? I'd
> delete it by [date]. It's fine to say no.

Then:

> You can stop at any time, or skip anything. Any questions before we start?

### 3:00 Warm-up (3 minutes)

Say:

> Before we look at the tool: tell me how you look into a rise in exports of sensitive goods to a
> country today. Think of the last time you did, and keep it general: no names of people or
> firms, and no case details.

Follow-ups, as time allows:

- "Where do you start, and which figures do you trust?"
- "How do you write it up, and who checks it?"
- "What makes you drop a lead, and where is that recorded?"
- "Do you ever help exporters check their own shipments?"

Listen for what they start from, what review looks like where they work (one reviewer, a panel,
none), and how they record why a lead was dropped. Note tools by type ("spreadsheet", "case
system"), never by product or supplier. You will come back to these in tasks 1, 4 and 6.

### 6:00 Task 1: find the lead to look at first (3 minutes)

Say:

> Here's the latest run. Find the lead you would look at first, and tell me why.

**Success looks like:** they open one file and give a reason drawn from what the tool shows: the
size of the UK rise, the onward rise, how long it has been a lead, how recent the onward figures
are, or a link to a past case.

**Watch for:**

- Whether they tell leads from watch items, and what they take a watch item to be.
- Whether they read the line about series held back, and what they make of it.
- What they weigh, and anything they look for that isn't there, such as a sort, a filter by
  corridor or goods, or a score.
- Whether they notice the line that a rise in exports is a lead, not evidence of a breach.

**Prompts:**

- "What made you choose that one?"
- "What would you want this list to show that it doesn't?"
- "What does 'watch' mean to you here?"

### 9:00 Task 2: what rose, and the case routes it touches (3 minutes)

Say:

> For this lead, tell me what rose, in the UK figures and in the country's own exports to Russia,
> and whether it connects to any past enforcement case.

If their lead touches no past case, ask:

> Is there a lead in this run that does connect to a past case? How would you find out?

Give it a minute, then show them one and mark the task "with help".

**Success looks like:** they say what rose on each side, by how much and against what (the
2019-21 average), and what a linked case does and does not mean: the route and goods match a past
enforcement case, which named no UK goods or UK party, so it says nothing about who sent these
exports.

**Watch for:**

- Pounds (UK) and dollars (onward) mixed up, or a ratio read as a total.
- Whether they notice which year the onward figures rest on; some rest on 2023.
- Whether they read the limits of the lead.
- Whether they treat the case link as evidence about this lead.
- Whether they can tell from the list which leads touch a past case. Today they can't.
- Whether the charts help them or slow them down.

**Prompts:**

- "How would you explain that rise to a colleague?"
- "What does the link to that case tell you, and what doesn't it?"
- "How sure would you be about these figures?"

### 12:00 Task 3: a first brief, edited (4 minutes)

Say:

> Write this lead up for a colleague. Get a first draft of the brief, then change one line so it
> says what you'd want them to take from the figures, in your own words, with a figure in it.

If the screen lets their figure through (it came from the evidence), ask "Did you expect it to
accept that?", then:

> Could you also try this exact sentence in place of one of the lines about the UK figures: "UK
> exports rose by 300% on the 2019-21 average."

**Success looks like:** they start a brief (in the demo the template is the only way), change at
least one line, see the screen stop a figure that is not in the file's evidence, say why in their
own words, and save a version that passes.

**Watch for:**

- Their first reaction to the draft: its length, its wording, its order.
- Whether they edit a line or two or want to rewrite it all (research question 3).
- Whether they try to add a line of their own. Today they can only reword or remove.
- What they make of the word "context" in the screen's message.
- Whether they work out a percentage themselves and are surprised when it is refused.
- Whether finishing an edit feels like saving it. Today the brief is not kept as a version until
  it is saved: note whether they notice.
- Whether they cancel an edit and lose their changes.

**Prompts:**

- "What is the tool telling you there?"
- "What did you expect to happen?"
- "Where would that figure need to come from?"
- "Would you send this brief as it is, edit it, or start again?"

### 16:00 Task 4: send it back with a note (3 minutes)

Say:

> Now send the brief on for a second person to check. Then play that second person: you're not
> happy with it yet. Send it back to its author with a note saying what needs to change. Keep the
> note general: no names of people or firms. Then tell me what you expect to happen next.

**Success looks like:** the brief waits for approval, then goes back to its author with their
note, and they can say what happens next: the author sees the note, the next version must answer
it, and someone other than the author approves it.

**Watch for:**

- Whether they work out how to become the second person, and how long it takes.
- Whether they try to approve the brief as its author, and their reaction when they can't.
- Their reaction to the note being screened.
- Whether sending back feels different from rejecting.
- Whether they expect the author to be told. The demo sends no message: ask how they would let
  the author know.
- If they keep the note as a lesson for later drafts: what they expect it to do, and who they
  think must approve it.
- Whether this matches how work is reviewed in their team.

**Prompts:**

- "What happens now?"
- "Who sees your note?"
- "What does the author have to do before it can be approved?"
- "How does this compare with how briefs are reviewed where you work?"

### 19:00 Task 5: an exporter's shipments (3 minutes)

Say:

> An exporter's compliance team has asked which of its shipments it should look into first. Use
> the tool to answer them, with the made-up sample of shipments it comes with. Please don't use a
> file of your own.

If they reach for a file of their own: "Please use the made-up sample only."

**Success looks like:** they run the screen on the sample, name the destination and goods to
check first and why, open the questions to ask for it, and say that the order sets priorities for
the exporter's own checks and finds nothing about any customer.

**Watch for:**

- Whether "Check first" reads to them as a finding about a customer.
- Whether they understand the rows not shown under the display rule, and the shipments outside
  the radar.
- Whether they find the questions to ask.
- Whether they would trust a file of their own to stay in the browser. Ask; don't test it.

**Prompts:**

- "What would you tell the exporter?"
- "What does 'Check first' mean here?"
- "Would you put your own file into this? Why or why not?"

### 22:00 Task 6: the record of what was done (2 minutes)

Say:

> Find a record of what's been done in the tool today, and tell me whether it's a record you'd
> rely on.

**Success looks like:** they find the log for the whole workspace, not only one file's activity,
say who did what and when, and say whether it would be enough for their work.

**Watch for:**

- Whether they stop at one file's own activity list or go on to the full log.
- How they read the two people in the log, both of them played by the participant in the demo.
- Whether they expect lines the screen stopped to be listed. They aren't.
- What they would want added, and whether they want to export it (off in the demo).

**Prompts:**

- "Is anything missing from that record?"
- "Who would look at this, and when?"
- "If someone asked you in six months why a lead was dropped, would this be enough?"

### 24:00 Closing questions (5 minutes)

Say:

> Thank you. A few last questions.

1. "How did that feel to use, overall?"
2. "On a scale of 1 to 5, where 1 is 'I would not feel confident using this' and 5 is 'I would
   feel confident using it every day', how confident would you feel using it day to day?" Then:
   "What makes it that number and not one higher?"
3. "What would stop you using it?"
4. "If you could change one thing first, what would it be?"
5. "Was there anything you expected to find that wasn't there?"
6. "Is there anything you'd like to ask me?"

Answer their questions now, including any you turned back during the tasks.

### 29:00 Thanks and close (1 minute)

Say:

> Thank you, that's given me a lot to work on. I'll close the window now, which clears
> everything you typed.

Close the private window. Note the end time.

## 4. Log template

Copy this for each session and fill it in during the session or straight after.

Rules for the log:

- Write quotes without the participant's name or employer, and without the name of their team
  or any firm they mention.
- Write tools by type ("spreadsheet"), never by product or supplier.
- Keep the log in a private place, such as a private folder or document, not in the repo. It
  goes in the repo only if the participant has agreed and it holds no names.
- If they typed or said anything from a live case, don't copy it: note only that it happened.

**Session**

| Field | Entry |
|---|---|
| Session id | P1, P2 and so on |
| Date | |
| Participant's role, in general terms | for example "sanctions analyst, government" or "compliance analyst, exporter" |
| In person or remote; device and browser | |
| Notes agreed | yes / no |
| Recording agreed; where kept; delete by | yes / no |
| Build tested | the commit shown at the foot of the page |

**Tasks**

| Task | Completed (yes / with help / no) | Time taken | What they said, in their own words | What went wrong | Severity (blocks / slows / annoys) | Change they asked for |
|---|---|---|---|---|---|---|
| Warm-up | n/a | | | | | |
| 1. Find the lead to look at first | | | | | | |
| 2. What rose, and the case routes | | | | | | |
| 3. A first brief, edited | | | | | | |
| 4. Send it back with a note | | | | | | |
| 5. An exporter's shipments | | | | | | |
| 6. The record of what was done | | | | | | |

Severity:

- **blocks**: they could not finish without help, or they misread something in a way that would
  lead to a wrong action at work, such as taking a lead or a "Check first" row for evidence of a
  breach.
- **slows**: they finished, but with wrong turns, hesitation or a question.
- **annoys**: they finished without trouble but disliked something.

**Closing answers**

| Question | Answer |
|---|---|
| Confidence, 1 to 5, and why | |
| What would stop them using it | |
| One thing to change first | |
| Expected but not there | |
| Their questions | |

**Summary** (straight after the session)

- Top three problems, with task numbers:
  1.
  2.
  3.
- Top three things that worked:
  1.
  2.
  3.
- Quotes worth keeping (no name, employer or firm):
- Changes to make:
- What this session says about each research question (1 to 5):
- Screen: figures or wording it let through that it should have stopped, or lines it stopped
  wrongly (reworded, nothing from a live case):

## 5. After the session

1. Finish the log within the hour, while it is fresh. Allow 10 minutes after each session.
2. Delete any recording by the date you promised.
3. After every three to five sessions, merge the logs into one list of problems. For each, note
   the tasks, the sessions it was seen in and its highest severity.
4. Rank the list by severity first (blocks, then slows, then annoys), then by how many sessions
   it was seen in. A block seen in two or more sessions comes first. A research question that
   came out "no" points to the next ones. Annoyances go on a list for the redesign.
5. Turn each problem into one change with one owner (a role, not a name), a date, and the session
   and task ids it came from. Keep each change small: one problem, one change.
6. A screen finding (a figure or wording it let through, or a line it stopped wrongly) becomes a
   new case in `radar/brief/spec/screen_cases.json`, written fresh as a made-up example, never in
   the participant's words if they could point to anyone. Then change the rules until the Python
   screen and the page's JavaScript port both pass it; the evals run the same cases.
7. Record each change and why in `docs/decision_log.md`, citing session ids only.
8. Re-test: after a change, run the same task, worded the same way, with at least two new
   participants. Close the change when neither hits the problem; if one does, look again.
9. After the redesign, update the owner's crib and run the same six tasks unchanged, so the
   results compare.
