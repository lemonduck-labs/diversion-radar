# The restricted layer (synthetic)

The public radar works from published trade statistics: totals by country and code, which
cannot show who exported what to whom. This layer is what a deployment inside government
would run on export declarations, which can. It is designed here and run only on synthetic
records: every record, id and party in `demo/radar/declarations/` is made up by a seeded
generator, and every file says so.

A rise in exports is a lead, not evidence of a breach. Every output of this layer is a
question for a person to check, with the facts from the declarations that raised it. None
is a finding.

The layer covers the radar's original nine corridors (run 2's), not the nine run 3 added:
its corridors, the routes it is pointed at and the synthetic world are those of run 2, whose
shown routes run 3 left as they were. `tests/test_declarations.py` compares the routes with
the radar's shown routes on those nine corridors only.

## What is here

| File | What it does |
|---|---|
| `schema.py` | The record, field by field, against HMRC's CDS export data elements |
| `scope.py` | The corridors, codes, routes the public radar shows, and the review windows |
| `generate.py` | A seeded world of synthetic declarations, with injected patterns and look-alikes recorded as ground truth |
| `signals.py` | Seven detectors, one per pattern, each citing the red flags it implements |
| `cases.py` | Signals grouped into cases, and the link graph |
| `evaluate.py` | Precision and recall against the ground truth, on synthetic data only |
| `export.py` | The data files for the workspace page |

`python scripts/build_declarations.py` writes the files to `demo/radar/declarations/`;
`--check` writes nothing and fails if a file is out of date. `tests/test_declarations.py`
covers the schema, the generator, each detector on hand-built records, the cases, the
evaluation and the files.

## The data model

One record is one goods item of one export declaration. The fields are the few the
questions in `radar/brief/spec/redflags.json` need; a real declaration carries many more.
Each mirrors a data element in HM Revenue & Customs, *CDS Declaration Completion
Instructions for Exports* (first published 23 Oct 2019, last updated 6 Oct 2026), in the
group pages and appendices listed under Sources. The official links are in the private file
`data/declaration_sources.csv`.

| Field | Data element | Synthetic value |
|---|---|---|
| `declaration_ref` | DE 2/5 LRN (the declarant's reference) | `SYN-DEC-` and six digits |
| `goods_item` | DE 1/6 Goods Item Number | 1, or 2 and 3 on multi-item declarations |
| `acceptance_date` | none: the date the declaration is accepted [Likely] | 2021 to June 2026 |
| `declaration_type` | DE 1/1 Declaration Type | always `EX` |
| `additional_declaration_type` | DE 1/2 Additional Declaration Type | always `A` |
| `procedure_code` | DE 1/10 Procedure (Appendix 1) | `1040` permanent export; `3171` re-export from customs warehousing |
| `exporter_id` | DE 3/2 Exporter Identification Number (EORI) | `EXP-` and four digits |
| `consignee_id` | DE 3/10 Consignee Identification Number, or DE 3/9 name and address | `CON-` and four digits |
| `representative_id`, `representative_status` | DE 3/20 and DE 3/21 (2 direct, 3 indirect, blank for self-representation) | `REP-` and four digits |
| `forwarder_id` | DE 3/37 Additional Supply Chain Actor(s), role code FW | `FWD-` and four digits, or none |
| `destination` | DE 5/8 Country of Destination Code | two-letter code |
| `routing` | DE 5/18 Country of Routing Codes | GB, any transit countries, the destination |
| `commodity_code` | DE 6/14 Commodity Code (first 8 digits) | the radar's six-digit codes padded with 00 |
| `description` | DE 6/8 Description of Goods (an..280) | the code's description |
| `net_mass_kg` | DE 6/1 Net Mass | to 0.1 kg |
| `supplementary_units` | DE 6/2 Supplementary Units | an item count for the radar's codes, none otherwise |
| `statistical_value_gbp` | DE 8/6 Statistical Value | whole pounds |
| `mode_border`, `mode_inland` | DE 7/4 and DE 7/5 (1 sea, 2 rail, 3 road, 4 air, 5 post and so on) | air for most of the radar's goods |
| `documents` | DE 2/3 Documents, certificates and authorisations | made-up codes `SYN1` to `SYN3` on a few items |

Every record also carries `record_type` ("synthetic export declaration item") and
`synthetic: true`. Ids look nothing like EORI numbers, and there are no names, addresses or
postcodes anywhere. `declarations.schema.json` holds the JSON Schema, the field table with
each source, and the compact columnar format the page loads.

Simplifications [Certain]: padding a six-digit code with 00 does not always give a code that
exists in the tariff; which codes call for supplementary units is not modelled; the document
codes are not real licence codes (export licence codes are listed in Appendix 5C of the
guidance); and the world does not model which goods need a licence.

## The synthetic world

Seed 20261021. 32,597 goods items on 30,028 declarations, 298 exporters, 3,034 consignees,
40 forwarders and 12 customs agents, January 2021 to June 2026. Most of it is ordinary
trade: steady customers in non-corridor countries, ordinary codes such as whisky, books and
medicaments, customers coming and going, and Russia trade that stops on 24 February 2022.
The corridors and codes in the patterns are the radar's nine of each.

Put into it and recorded in `ground_truth.json`:

| Pattern | What was injected | Count | Built for |
|---|---|---|---|
| G1 | A new consignee in a corridor buying goods on the Common High Priority Items List | 6 | D1 |
| G2 | One exporter's exports jumping on a route the public radar shows | 3 | D2 |
| G3 | One consignee or forwarder shared by unrelated exporters (two consignees, one forwarder) | 3 | D3 |
| G4 | Values per kilogram far out of line for the code (two high, two low) | 4 | D4 |
| G5 | A code switching to a neighbouring code outside the radar's nine | 3 | D5 |
| G6 | Shipments to Russia stopping after 24 February 2022 and moving to a corridor | 4 | D6 |
| G7 | Small, frequent shipments to one consignee | 3 | D7 |

Two injections also carry a second pattern by construction (G2-1 includes a new consignee
for D1; G6-2's new consignee also gets small, frequent shipments for D7), so that some cases
are raised by two detectors. Four injections are near misses, built to sit just outside a
threshold: G1-6 stays under D1's value floor, G4-4 has only two values out of line, G6-4
moves its Russia volume to a consignee first seen before 2022, and G7-3 spreads its
shipments so fewer than 20 fall in the window.

Look-alikes are ordinary trade built to resemble a pattern, so the detectors have false
positives to show: new distributors in a corridor (L1, 4), ordinary growth on a shown route
(L2, 3), established distributors and forwarders specialising in corridor routes (L3, 5),
premium product lines (L4, 3), reclassifications (L5, 2), exporters that lost Russia
customers and found new ones in a corridor (L6, 3) and spare-parts subscriptions (L7, 3).
At the level of the declarations an injection and its look-alike can be identical; only the
questions a person then asks can tell them apart [Certain].

Ids are issued in order of first appearance, so an id says nothing about whether a party was
injected.

## Detectors

Each detector cites the red flags in `radar/brief/spec/redflags.json` it implements (the
indicator it tests in the data) and the ones a person checks next, which declarations
cannot answer. `signals_spec.json` holds the full wording, thresholds and mappings. The
thresholds are ours, set on synthetic data [Guessing]. In the wording, "the radar's goods"
means goods under the radar's nine codes.

| Detector | Asks | Implements | Thresholds |
|---|---|---|---|
| D1 new corridor consignee | Is this consignee new to buying these goods, and what checks show their end destination is not Russia? | new-chpl-trader [Likely], transit-edd-country [Certain] where the destination is named in the UK guidance | first seen in the last 12 months, at least 50,000 pounds of the radar's goods |
| D2 route volume jump | Have this exporter's exports on this route risen beyond their usual pattern, and is there a business reason? | order-volume-rise [Likely] | routes the public radar shows only; at least 3 times the 12 months before and 100,000 pounds more |
| D3 shared party | Is this consignee a user of the goods, and why do so many unrelated exporters send it goods? Or, for a forwarder, why do they route these goods through it? | consignee-uses-goods [Likely], shared-address [Guessing] | 4 or more ownership groups in 24 months; a forwarder also needs 40% of its traffic to be the radar's goods to corridors |
| D4 unit value | Why is the value per kilogram so far from the usual for the code, and are the goods under the correct code and at the market price? | price-and-invoices [Likely], hs-code-check [Likely] | 3 or more items more than 3.5 robust deviations from the code's median |
| D5 code switch | Why did this flow move to a neighbouring code at a similar value per kilogram? | hs-code-check [Likely] | 3 or more items under each code, a clean switch, value per kilogram within a factor of 2 |
| D6 Russia switch | Did these customers start receiving the goods only after 24 February 2022, when the exporter's Russia trade stopped? | chpl-orders-since-2022 [Likely], transit-edd-country [Certain] where named | at least 100,000 pounds to Russia before; corridor consignees first seen after 24 February 2022 taking, a year, at least half the Russia trade's yearly value |
| D7 small frequent | Are the goods going in small, frequent shipments to one central location? | small-frequent-shipments [Certain] | 20 or more shipments in 12 months, median under 2,000 pounds and under 2 kg |

The public layer's research signals in `radar/signals` look for three of the same patterns
in aggregate (price per kilogram, code shift, displacement from Russia). This layer looks for
them per declaration, which only declaration data allows.

## Cases and the graph

Signals that share an exporter and destination, or a consignee, go into one case, so a
person reads related questions together. A case raised by two or more detectors is listed
as "check first"; any other as "check". No case carries a score. Each case lists its
questions: the detectors' questions with their basis, then the follow-up questions from the
red-flag list. `graph.json` holds a link graph of exporters, consignees, forwarders and
routes (a corridor and one of the radar's codes), cut to each case's parties plus one hop,
with at most 25 neighbours per party.

## Evaluation

Performance on synthetic data. The patterns were put in by the same people who wrote the
detectors, so these figures show how the machinery behaves, not how well it would find
anything in real declarations. They say nothing about real-world performance [Certain].

| Detector | Fired | Built to find | Found | False positives | Missed | Precision | Recall |
|---|---|---|---|---|---|---|---|
| D1 | 13 | 7 | 6 | 7 | 1 | 0.462 | 0.857 |
| D2 | 7 | 3 | 3 | 4 | 0 | 0.429 | 1.0 |
| D3 | 8 | 3 | 3 | 5 | 0 | 0.375 | 1.0 |
| D4 | 6 | 4 | 3 | 3 | 1 | 0.5 | 0.75 |
| D5 | 4 | 3 | 3 | 1 | 0 | 0.75 | 1.0 |
| D6 | 6 | 4 | 3 | 3 | 1 | 0.5 | 0.75 |
| D7 | 6 | 4 | 3 | 3 | 1 | 0.5 | 0.75 |

Of the 26 false positives, 22 are look-alikes and 4 are ordinary background trade. Every
miss is a near miss built to show a threshold's edge. 50 signals make 48 cases, 2 of them
"check first". `evaluation.json` lists every unit and case behind these counts.

## How a real deployment would plug in

The detectors are plain code over the fields above, with no AI model in the loop. A
deployment would run them inside the customer's own environment, on the customer's own
data, under the customer's own legal basis. Nothing here asserts what that basis is.

### Mapping the fields

- At ingest, a data steward maps each declaration to the fields above and replaces each
  EORI (DE 3/2, DE 3/20, DE 3/37) with a pseudonymous id from a keyed hash whose key only
  the steward holds.
- Consignees in the corridors will mostly have no GB, EU or XI EORI, so the guidance puts
  their name and address in DE 3/9 instead of an id in DE 3/10 [Likely]. A deployment needs
  entity resolution on names and addresses to give each consignee a stable id; how well that
  works decides how well D1, D3, D6 and D7 work. The synthetic data does not exercise it.
- The forwarder comes from DE 3/37 with role code FW, which the guidance says is optional.
  How often real declarations carry it was not checked; where it is blank, D3 sees only the
  consignee side.
- Ownership groups (for "unrelated exporters" in D3) and sectors come from records outside
  the declarations; which ones the customer may link is for the customer to confirm.
- The routes D2 looks at come from the public radar's current run, never from series it
  holds back.

### What the customer's lawyers must confirm

These are questions, not answers:

1. Which body holds the declarations, and which of its own functions this processing
   serves.
2. The gateway that lets the data be used for this purpose, and, if data or outputs move
   between bodies, the gateway for each movement and any limit on onward disclosure.
3. Whether any of the data is personal data (a sole trader exporter, a consignee who is an
   individual), which data protection rules apply (general processing or law enforcement
   processing), the lawful basis, whether an impact assessment is needed, and how long data
   and outputs may be kept.
4. Whether flagging a party by an automated rule needs safeguards beyond the person who
   reviews every case.
5. What duties of confidence apply to the declarations, and what disclosure duties would
   apply to a case's records if it led to proceedings.
6. Who may re-identify a pseudonymous id, on whose approval, and how that is recorded.
7. Where the data may be processed and stored, at what security classification, and with
   what vetting for staff and suppliers.
8. Whether any external service, including an AI model, may see declaration data or
   case content at all. The layer itself does not need one.

### Who would see what

| Role | Sees | Does not see |
|---|---|---|
| Data steward | The declarations and the key that maps ids back to EORIs and names | Case triage |
| Analyst | Cases, signals, figures and the graph, by pseudonymous id | Names, EORIs, addresses |
| Approver (a second person) | The same as the analyst, plus re-identification requests to approve | Anything not in a case they are asked to approve |
| Investigator, after referral | The identified case pack, in the customer's own case system | Cases not referred |
| Auditor | The log of who saw, re-identified, approved or referred what | Declaration content beyond references |
| Platform administrator | The running system | Declaration data in clear, and the key [Likely]: to be confirmed with the customer's security team |
| Exporters and the public | Nothing from this layer; the public radar stays aggregate | Everything here |

## What the layer cannot do

- Show intent. Every signal has ordinary explanations, and the look-alikes show that at the
  level of the declarations they can be identical to the patterns [Certain].
- See payments, end users beyond the declared consignee, or where goods go after they reach
  the destination. Declarations show only the UK export.
- See goods declared under an unrelated code, or at values that look ordinary. D5 sees only
  moves to a neighbouring code; D4 only values far from the code's norm.
- See goods that leave without a declaration of the kind modelled here [Likely].
- Check licences. The synthetic world does not model which goods need one, so no detector
  compares licence references with goods; that rule would need the customer's licensing
  data and was not built.
- Say how it would do on real declarations. Its thresholds were set on synthetic data and
  its precision and recall above are synthetic. A pilot would measure them against cases the
  customer has already closed, before anyone relies on them.

## Sources

All HM Revenue & Customs, *CDS Declaration Completion Instructions for Exports*:

- Group 1: Message Information (including Procedure Codes), last updated 1 Jul 2026
- Group 2: References of Messages, Document, Certificates and Authorisations, last updated 1 Jul 2026
- Group 3: Parties, last updated 6 Oct 2026
- Group 5: Dates, Times, Periods, Places, Countries and Regions, last updated 1 Jul 2026
- Group 6: Goods Identification, last updated 6 Oct 2026
- Group 7: Transport Information (Modes, Means and Equipment), last updated 1 Jul 2026
- Group 8: Other Data Elements (Statistical Data, Guarantees and Tariff Related Data), last updated 7 Sep 2026
- Appendix 1: DE 1/10: Requested and Previous Procedure Codes, last updated 13 Jul 2026
- Data Element 2/3: Document and Other Reference Codes: Licence Types (imports and exports) of
  the Customs Declaration Service (CDS), last updated 4 Sep 2026

The red flags and their official sources are in `radar/brief/spec/redflags.json`.
