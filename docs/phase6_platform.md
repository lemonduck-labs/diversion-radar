# Phase 6: how platforms like this are built and run, and where the radar goes next

Written 22 October 2026 for the owner. The sources are listed at the end. Each claim carries [Certain], [Likely] or [Guessing]; anything not from a source is marked as judgement.

## 1. Who would use it, and what they need now

The Office of Trade Sanctions Implementation (OTSI) published its annual review for 2025-26 in 2026 [Certain]:

- **Cases.** It received 178 suspected breach reports or referrals; 156 of the cases received were under the Russia regime. About 6% of the cases it opened were started proactively. It says it wants to "increase significantly" its intelligence-led work, and it set up a dedicated intelligence function during the year [Certain].
- **Outcomes.** It closed 104 cases. Of these, 41 found no breach and 40 went to HMRC. It had not yet imposed a civil penalty [Certain].
- **Systems.** It is building a new case management system, with online services using GOV.UK One Login, and plans to keep "investing in digital tools and AI" [Certain].
- **Partners.** It works with HMRC (an enforcement partnership), the NCA and the FCA, and closely with ECJU, OFSI and DfT's Centre for Transport Sanctions; it has memoranda of understanding with a number of government departments and regulators [Certain].

Since 13 May 2026, Sanctions End-Use Controls let the Secretary of State inform an exporter that a specific export to a non-sanctioned country is at risk of diversion to a sanctioned destination. The guidance says the notice comes through HMRC's National Clearance Hub or by direct contact, including from OTSI. Once informed, the exporter needs a licence (SI 2026/443, regulation 1(2) gives 13 May 2026; DBT and OTSI guidance of 22 April 2026) [Certain].

**What this means for the radar [Likely].** A proactive team needs a ranked list of routes and goods to look at before reports arrive. That is what a lead is. The end-use controls give such a list a direct use: deciding where to look before informing an exporter. The radar must stay a source of questions. A lead is never the basis for a notice on its own.

## 2. How platforms in this space are built

What the vendors and government listings describe:

| Layer | What it does | Examples | Sources |
|---|---|---|---|
| Data integration | Pulls many sources into one model, kept up to date | Palantir: HDFS, JDBC, SQL and flat files, federated sources. Sayari: corporate records from 250+ jurisdictions linked to shipment data at HS code level | G-Cloud 14 listing; Sayari export controls page [Certain] |
| Entity model | Objects and links: companies, routes, shipments, cases | Sayari Graph (ownership networks), Sayari Map (re-export chains) | Sayari [Certain] |
| Monitoring and alerts | Watches for new relationships or changes and raises an alert | Sayari Signal: continuous monitoring of a counterparty base for new relationships, with alerts | Sayari [Certain] |
| Workflow | Cases, tasks, approvals, reports to partners | Palantir lists sharing investigative reports with partner agencies; OTSI is building a case management system | G-Cloud listing; OTSI review [Certain] |
| Access control | Roles (discretionary) plus mandatory markings; access granted per purpose, with a recorded rationale | Foundry: markings are all-or-nothing, cannot be overridden by a role, and carry over to derived data. Purpose-based access records why each person may see each dataset | Palantir docs and blog [Certain] |
| Audit | Every action and every change to data, traceable | Palantir: "comprehensive auditing of all user activity" and lineage of data changes | G-Cloud listing [Certain] |
| APIs | Screening, alerts and risk scores pushed into the customer's own systems | Sayari real-time screening API; Kharon risk-score API | Sayari; Kharon [Certain] |

### Where the radar stands against that

| Layer | The radar after phase 6 | Gap |
|---|---|---|
| Data integration | HMRC and UN Comtrade, with checksums and an ingest log | One kind of source. No company, shipping or registry data [Certain] |
| Entity model | Files by corridor and code; synthetic declaration cases with a link graph | No real entities, by design: aggregates only in the demo [Certain] |
| Monitoring | Monthly reruns; "since the last run" on the overview | No alerting between runs, and no monitoring of news [Certain] |
| Workflow | Briefs, four-eyes approval, checks, and now follow-ups with owners and due dates | No partner referral flow beyond the evidence pack [Certain] |
| Access control | Viewer, contributor, editor and owner (hosted: row-level security in Postgres) | No markings and no purpose-based access. A government deployment would need both [Likely] |
| Audit | Hosted: a database-written audit log, including follow-ups. Inside Claude: each person's log under their own path | Covered in the hosted version; inside Claude the owner can still write anywhere [Certain] |
| APIs | None outward; add-ons show what they would send | Connectors wait for sign-off [Certain] |

## 3. What phase 6 added

All built and tested in this repository [Certain].

- **Sign-in portal.** Synthetic people at every role the hosted version has. Switching person keeps the page. The hosted version keeps its invite-only sign-in by emailed code.
- **Record layout.** A file is now one record:
  - a header with the next step for the person looking at it;
  - sections that fold away and stay folded;
  - a rail with properties, follow-ups, official references, add-ons, connected records and activity.
- **Drill-through.** On a file, the breadcrumb runs from the inbox to its corridor; the header links to the corridor's page and the goods code's page. Each lists every file the workspace shows there, and search finds them [Certain].
- **Follow-ups.**
  - Each file gets a to-do list with owners, due dates and one-click templates, for example "Recheck after HMRC adds September 2026 on 12 November 2026".
  - A "Follow-ups" page shows every open step, overdue first.
  - The hosted version has a new table with its own triggers and audit entries, and tests run on a real Postgres.
- **References.** Official pages for each file: HMRC trade data, UN Comtrade, the Common High Priority Items List, the exporter guidance and the end-use controls guidance. Each shows the date it was read.
- **Add-ons.** Task tracker, calendar, email or Teams, and case management. Each shows what it would send; nothing is connected.
- **Team and access.** A page listing who holds which role and what each role can do.

### Phase 6.5: closing the loop

Built after the strategy review of 22 October 2026 [Certain]:

- **Outcomes.** Every decided file records what happened, from a fixed list. This is the start of the measure a buyer will ask for: how often a lead was worth a look.
- **Referral pack.** Follows the headings of OTSI's guidance on reporting where a lead can fill them. The UK link, any parties and the narrative are left to the analyst, since trade statistics identify no exporter.
- **End-use controls decision record.** A proposal counts as put forward only with every check, information beyond the trade statistics among them, and the approval of an editor who wrote none of it.
- **Lessons from the published cases**, on the track record.
- **Pilot timings.** Three tasks, timed in the browser.
- **The console.** The overview opens on a turning globe of the run's leads and routes.

## 4. An extension model: what a new "situation" plugs into

The core stays the same: published flows, a rule, a display rule, a file, a person's check, and an audit trail. A new situation supplies six things (a design, not yet built) [Likely]:

1. **Source adapters.** Each pulls data with checksums and an ingest log entry (fd-core already does this).
2. **A rule** that turns the data into leads, written down and backtested before it is trusted.
3. **A display rule** that keeps small or identifying flows out of view.
4. **A file type.** This sets which figures, factors and limits a file shows, and which questions come from official guidance.
5. **Follow-up templates and references** for that situation.
6. **Add-ons**: where the file's work can go.

Candidates, ordered by how closely they fit the core today (judgement, [Likely]):

| Situation | Fit | What it needs | Main risk |
|---|---|---|---|
| Other sanctioned destinations (Belarus, Iran) on the same trade data | Close | New destination codes and corridors; a backtest per destination | Fewer published cases to test against |
| End-use controls support: a shortlist of routes and goods for OTSI or HMRC to look at before informing an exporter | Close | A view and export built for that decision; a stricter display rule | A lead must never be the sole basis for a notice |
| Bank and trade finance: invoices or letters of credit checked against corridor and code leads | Close (the exporter check already does this for exporters' own files) | A batch screen API; bank-side roles | Personal data in customer files; must run inside the bank |
| Dual-use and controlled goods, beyond the Common High Priority Items List | Medium | Code lists from the control lists; different guidance | Codes map poorly to control-list entries |
| Shipping and transshipment (vessel tracking, port calls) | Further | Paid data; a vessel entity model | Cost; licence terms |
| Company and ownership links | Further | Registry data; entity resolution | Personal data; the "no names" rule holds in the demo only |
| Open-source monitoring (phase 7, the "brain") | Separate layer | See section 5 | Lawful sourcing, cost, reliability |

## 5. Phase 7, for sign-off: the monitoring "brain"

Proposed design, not built; each point is a proposal for sign-off [Likely] unless tagged:

- **Sources.** Lawful, public and logged: regulators' notices, customs and statistics releases in the corridors' own languages, company and tender registries where their terms allow, and trade press. Each source is listed with its terms before use.
- **Cadence.** A scheduled run per source, with cost capped per run.
- **Matching.** Items are matched to files by corridor, code and heading, never by guesswork about named parties.
- **Translation.** The original text is kept beside the translation, with the language and the tool recorded.
- **Grading.** Each item is graded for source reliability and information credibility on the six-by-six scale used in intelligence work. The analyst sets or confirms the grade.
- **Output.** A sourced note on a file, waiting for a person. An analyst accepts or rejects it, the decision is audited, and nothing reaches a brief unaccepted.
- **Not by default.** No VPN or hidden identity: many sites' terms forbid it, and paying a sanctioned-country service could itself be a breach. A government customer that needs this would run it on its own network, under its own authority [Likely].
- **Personal data.** A deployment needs a lawful basis (UK GDPR, or Part 3 of the Data Protection Act 2018 for law enforcement) before it collects news about named firms or people. The demo stays on aggregates [Certain].
- **Cost.** Search and translation APIs cost money, so the spend waits for sign-off.

## 6. Move forward (formerly Move-on)

The same portal, follow-ups, references and add-ons apply to the Move forward planner:

- **Roles.** Caseworker, team manager, finance and a read-only partner.
- **Follow-ups.** Steps on a household's plan, such as chasing a landlord, booking a viewing or reviewing a placement.
- **Add-ons.** The housing management system, calendar and email.

This is next after the radar, as asked. The fit is judgement [Likely].

## Sources

- [OTSI Annual Review FY 2025-26](https://assets.publishing.service.gov.uk/media/6a900a6b01bbff0bf8f97aa1/OTSI_Annual_Review_FY_25-26.pdf)
- [The Sanctions (EU Exit) (Miscellaneous Amendments) Regulations 2026, regulation 1](https://www.legislation.gov.uk/uksi/2026/443/regulation/1/made)
- [Sanctions End-Use Controls: guidance for businesses (DBT and OTSI)](https://www.gov.uk/government/publications/sanctions-end-use-controls-guidance-for-businesses/sanctions-end-use-controls-guidance-for-businesses)
- [Palantir Platform: Gotham, G-Cloud 14 listing](https://www.applytosupply.digitalmarketplace.service.gov.uk/g-cloud-14/services/801146272055049)
- [Palantir Foundry documentation: markings](https://www.palantir.com/docs/foundry/security/markings)
- [Palantir blog: purpose-based access controls](https://blog.palantir.com/purpose-based-access-controls-at-palantir-f419faa400b3)
- [Sayari: export controls for government](https://sayari.com/government/export-controls/)
- [Kharon: risk exposure score API](https://www.kharon.com/resources/company-update/compliance/kharon-unveils-api-for-seamless-integration-of-dynamic-risk-exposure-scores)
