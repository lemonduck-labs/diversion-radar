# Data sources

| Source | Publisher | What we use | Licence | Access |
|---|---|---|---|---|
| Overseas trade statistics (OTS) via the uktradeinfo API | HMRC | UK non-EU exports (FlowTypeId 4) by 8-digit goods code, country and month, summed on the server | Open Government Licence v3.0 | `https://api.uktradeinfo.com/OTS`, no key, 60 requests a minute |
| UN Comtrade | UN Statistics Division | Corridor countries' annual exports to Russia (partner 643) and imports from the UK (partner 826), by 6-digit code; monthly exports to Russia for the seven corridors that report monthly, with each month's first release date (run 2 snapshot, `raw/comtrade_run2_browser_2026-10-21.txt`), and the same for the nine corridors run 3 adds (`raw/comtrade_run3_browser_2026-10-21.txt`); headline records only (partner2 0, customs C00, transport 0) | UN Comtrade re-dissemination guidance: limited tables and charts, and transformed data, need no permission (see below) | Preview endpoint, no key, one period per call (several reporters per call in run 2), rate limited |
| Common High Priority List | US BIS with the EU, UK and Japan | Tier 1 and 2 goods codes | Public guidance | Transcribed from https://www.bis.gov/licensing/country-guidance/common-high-priority-items-list-chpl (page dated 23 February 2024) |
| Annual average exchange rates | Bank of England | Series XUAAUSS, annual average spot rate, US $ into sterling, 2019 to 2025, to convert HMRC values for the mirror check (`config/fx_usd_per_gbp.csv`) | Bank of England database terms; check before republishing | https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp?html.x=yes&SeriesCodes=XUAAUSS&UsingCodes=Y&CSVF=TN&Datefrom=01/Jan/2019&Dateto=31/Dec/2025 |
| Country codes | UN Statistics Division | M49 codes, used as UN Comtrade reporter and partner codes in `config/countries.csv` | Public reference | https://unstats.un.org/unsd/methodology/m49/overview/ |

Attribution for HMRC data, required wherever it is shown:
"Contains public sector information licensed under the Open Government Licence v3.0."
Licence text: https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/

## Phase 0 snapshot (21 October 2026)

The build workspace could not reach either API, so the phase 0 pulls ran through a
browser, using the same queries the scripts make:

- `raw/hmrc_monthly_browser_2026-10-21.txt`: 54 server-side aggregates (6 countries by 9
  codes), January 2019 to August 2026. Checksums in its header (1,645 monthly rows,
  sum of values £765,142,573, sum of net mass 2,673,567 kg) are verified by
  `scripts/load_browser_snapshot.py` before anything is written.
- `raw/comtrade_annual_browser_2026-10-21.txt`: annual Comtrade records, 2019 to 2025,
  with a row count and value checksum in its header.

Running `scripts/pull_spike.py` on a machine with internet access reproduces both.

## Phase 1 inputs (21 October 2026)

`scripts/analyse.py` reads `processed/hmrc_monthly_phase1.csv` and
`processed/comtrade_annual_phase1.csv` (falling back to the phase 0 tables if they are
absent). Each is the phase 0 snapshot plus a second browser snapshot:

- `raw/hmrc_monthly_browser_2026-10-21b.txt`: Turkey, Uzbekistan, Azerbaijan and
  Tajikistan, 1,118 monthly rows; its header checksums match (sum of values
  £247,430,688, sum of net mass 895,053 kg). With phase 0: 2,763 rows.
- `raw/comtrade_annual_browser_2026-10-21b.txt`: 338 records (value checksum
  285,127,312) adding exports to Russia for the four new corridors and imports from the
  UK for all nine. With phase 0: 575 records.

Both phase 1 tables were re-derived from the two raw snapshots and matched row for row.
`scripts/build_phase1_tables.py` rebuilds them from the raw snapshots and checks them;
`scripts/pull.py` rebuilds them from the APIs on a machine with internet access.

Comtrade years with no records in the phase 1 table: Kazakhstan imports from the UK,
2020 to 2022; the UAE and Tajikistan, both flows after 2023; Uzbekistan, both flows
after 2024; Georgia's exports to Russia, 2020, 2023 and 2025; Azerbaijan's exports to
Russia, 2019.

## Reference codes and rates

- **Country codes.** The UN M49 overview lists Türkiye 792, Uzbekistan 860, Azerbaijan
  031 and Tajikistan 762 (read 21 October 2026); `config/countries.csv` holds them as
  integers. HMRC country ids (Turkey 52, Uzbekistan 81, Azerbaijan 78, Tajikistan 82)
  were verified separately before the phase 1 pull. Comtrade's own reporter
  list is served from comtradeapi.un.org, which the build workspace cannot reach, so it
  was not checked directly; Comtrade returned records for all four codes in the
  phase 1 pull.
- **Run 3 country codes** (read in a browser on 21 October 2026, before any run 3 figures
  were pulled; `config/countries_run3.csv`). HMRC country ids from the uktradeinfo API's
  country list (`https://api.uktradeinfo.com/Country`, 263 entries): China 720, Hong Kong
  740, Macao 743, India 664, Israel 624, Malaysia 701, Serbia 98, Thailand 680, Vietnam 690.
  HMRC gives Serbia the alpha code XS and lists Serbia and Montenegro (94) and Kosovo (95)
  apart. UN Comtrade codes from its own reference lists of reporters and partners
  (`https://comtradeapi.un.org/files/v1/app/reference/Reporters.json` and
  `partnerAreas.json`, read through the browser): China 156, China Hong Kong SAR 344, China
  Macao SAR 446, India 699, Israel 376, Malaysia 458, Serbia 688 (from 2006), Thailand 764,
  Viet Nam 704; Russian Federation 643 and United Kingdom 826 as partners. The UN M49
  overview (248 rows) gives the same codes except India, 356: UN Comtrade keeps 356 for
  "India (...1974)" and reports India from 1975 as 699, so 699 is used. The ISO2 code for
  Serbia in the config is RS, not HMRC's XS.
- **Exchange rates.** The seven XUAAUSS values were read from the Bank of England
  database on 21 October 2026, twice, with the same result. As an independent check,
  HMRC's yearly average rates for the years to 31 December agree within 0.3%: 1.2432
  (2023), 1.2787 (2024) and 1.3156 (2025), at
  https://trade-tariff.service.gov.uk/exchange_rates/view/2023-12?type=average (and the
  2024-12 and 2025-12 pages). That service lists no year to December 2019 average, so
  the Bank of England series is used for every year. A third reading on 21 October 2026
  matched; the seven rows are saved in `raw/boe_xuaauss_browser_2026-10-21.txt`, with a
  SHA-256 checked against the browser and an ingest log entry. The Bank's CSV link
  downloads a file rather than showing it, so the HTML table was read. A blank rate in the
  file makes the mirror check skip that year.

## UN Comtrade release dates (21 October 2026)

`raw/comtrade_availability_browser_2026-10-21.txt` holds UN Comtrade's data availability
records (first and last release dates) for the nine corridors, annual and monthly, from its
public `getDA` service. The browser computed a SHA-256 of the text; `radar/snapshots.py`
refuses to read the file unless it matches. `scripts/build_phase1_tables.py` writes the
tables the backtest uses into `backtest/data/`. Where a dataset was replaced, the first
release date shown is the replacement's.

## Run 3 inputs: nine corridors added (21 October 2026)

Pre-registered in `backtest/RESEARCH_LOG.md` (entry R3, commit 5447f08) before any of these
figures were pulled. Pulled in a browser from the public endpoints, with no key; no other
customs sites were used.

- `raw/hmrc_monthly_run3_browser_2026-10-21.txt`: HMRC non-EU exports (FlowTypeId 4) of
  the nine code ranges to China (720), Hong Kong (740), Macao (743), India (664), Israel
  (624), Malaysia (701), Serbia (98), Thailand (680) and Vietnam (690), by month, January
  2016 to August 2026 (the latest published), summed on the server: 81 queries, 7,589
  monthly rows, sum of values £6,423,821,855, sum of net mass 30,804,512 kg (header
  checksums), SHA-256 e6dc508b... The 81 calls, with the time and row count of each, are in
  `raw/hmrc_monthly_run3_calls_browser_2026-10-21.txt` (SHA-256 8ba610c9...); their URLs
  are the ones `radar/hmrc.monthly_exports_url` builds.
- `raw/comtrade_run3_browser_2026-10-21.txt` (SHA-256 73db5d9b...): UN Comtrade for
  reporters 156, 344, 446, 699, 376, 458, 688, 764 and 704. Data availability (getDA), every
  dataset listed: 290 annual and 1,750 monthly. Annual exports to Russia and imports from
  the UK, 2019 to 2025: 799 headline records (sum USD 15,850,160,952.06). Monthly exports to
  Russia, every month from January 2019 with a dataset: 2,524 records (sum USD
  9,965,608,927.52) over 770 corridor-months. 124 calls (18 availability, 14 annual, 92
  monthly, one per month with every corridor that had a dataset), each listed in the file
  with its time and record count. No call hit the 500-record cap or the rate limit.
- How the files left the browser: each snapshot was written onto a page in the browser,
  read back whole by the browser tool, which saved the page text to a file in the
  workspace, and checked against the SHA-256 the browser had computed. Nothing was copied
  by hand.
- `scripts/build_run3_tables.py` writes the run 3 tables, each run 2's table byte for byte
  followed by the new corridors' rows, and checks that (`backtest/data/run3_inputs_report.json`).
  205 ingest entries in `ingest_log.jsonl`.

## Monitoring sources (phase 7, 22 October 2026)

`monitor/sources.json` lists each source the monitoring layer reads, with its terms as read on
22 October 2026: the OTSI blog and GOV.UK's sanctions news and notices (Open Government Licence
v3.0) [Certain]; the Ministry of Trade of Türkiye (footer: all rights reserved, no reuse terms
stated; items keep a short excerpt with the link for internal monitoring, and anything shared
wider needs permission [Likely]); the National Statistical Committee of the Kyrgyz Republic
(footer: users must cite the source; its licensing page, read on 22 October 2026, puts the
site's content under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 [Certain], so no
commercial use without permission, and a paid deployment is commercial [Likely]). Every item
filed has an entry in `data/ingest_log.jsonl` with the SHA-256 of its excerpt.

The public demo site copies only the items whose source is under the Open Government Licence
(`scripts/build_site.py`, `open_licence_only`); items from the two foreign sources stay in the
workspace for internal monitoring until permission is recorded here.

## Land outlines for the workspace globe (22 October 2026)

- Natural Earth 1:110m land and country outlines, version 4.1.0, by way of the world-atlas npm
  package (2.0.2, ISC licence), thinned to about half a degree into `radar/geo/land.json`.
  Natural Earth is in the public domain (https://www.naturalearthdata.com/about/terms-of-use/)
  [Certain]. The outlines place nothing: the globe's marks sit on capitals and every figure comes
  from the run's data.

## Terms to check before anything is public

- UN Comtrade (both pages read in a browser, 21 October 2026). Its "Policy on Comtrade
  Data Use" (https://uncomtrade.org/docs/policy-on-comtrade-data-use/) says the data "are
  provided for internal use only and may not be re-disseminated in any form without UNSD's
  permission", with exemptions on its "Re-dissemination of data" page
  (https://uncomtrade.org/docs/re-dissemination-of-data/), and that use stays subject to
  the on-line usage agreement of 7 August 2012
  (https://comtrade.un.org/licenseagreement.html) and to the disclaimer in its "Read Me
  First". Uses that need no permission or licence: publication of limited amounts "in a
  few tables, graphs, visualization", for profit or not; free-of-charge visualisation or
  analytics applications; free extraction applications of up to 100,000 records; internal
  use. Transformed data (new indicators, growth rates, derived metrics, aggregations, or
  data combined with other datasets) needs no licence, as UN Comtrade "does not copyright
  transformed data". A licence to distribute applies to original data at 100,000 records
  or more in a product, or when charging for access to it. Citation: "UN Comtrade".
  [Certain, as the pages state it] Reading for this repo: the demo and reports show
  derived ratios and a few tables and charts from far fewer than 100,000 records, combined
  with HMRC data, so no permission is needed [Likely]. The snapshots in `raw/` are
  original data, under 100,000 records, so within the limited-amount exemption if the repo
  is ever public [Likely]; this public copy leaves them out. Before
  charging for anything built on Comtrade data, confirm with the UN Comtrade team (contact
  on the re-dissemination page). Pulls use the public API, paced within its quota, as the
  policy's fair-usage section asks (no scraping of the web interface).
- Bank of England: the Bank's legal page places its database under the Open Government
  Licence but excludes selected exchange-rate series [Likely, read through a summarising
  fetch]. Confirm for XUAAUSS, or switch to HMRC's published rates, before republishing a
  converted figure.

## Known gaps

- HMRC suppresses some figures to protect traders; suppressed records do not show
  under the country they went to, so totals can understate.
- Some HMRC records sit at chapter level (code 85) with no 8-digit code; they are
  outside the code ranges used here.
- Heading 8548 changed in HS 2022 (8548.10 and 8548.90 became 8548.00); the whole
  heading is used for a consistent series.
- Russia stopped publishing detailed trade data in 2022, so the onward check relies
  on what each corridor country reports to Comtrade.
- Values are nominal. Net mass is used as a rough volume check.

Run 3 corridors (pulled 21 October 2026):

- HMRC: no UK exports recorded to Macao in 8542.33, 8532.21 or 8532.24 from January 2016
  to August 2026.
- UN Comtrade annual: Vietnam has released no annual data after 2023, so both its flows
  end in 2023. Macao's exports to Russia have records only for 2023 and 2024 (none for
  2019-22 or 2025, though those datasets are released), so it has no 2019-21 baseline and
  no annual onward signal. Serbia has no records of these codes going to Russia in 2024,
  although its 2024 dataset is released. Every other corridor holds both flows for each
  year from 2019 to 2025. China's 2025 annual data were first released on 22 September
  2026.
- UN Comtrade monthly: China's monthly data end in December 2024 (none for 2025 or 2026 by
  21 October 2026), Vietnam's in December 2023 and Thailand's in May 2026; Hong Kong,
  Macao and India reach July 2026, and Israel, Malaysia and Serbia August 2026. Macao has
  one monthly record of these codes going to Russia from 2019 (August 2024). The August 2026
  call (Israel, Malaysia, Serbia) returned no records.
- 2016-18 annual onward data were not pulled for the new corridors: the live rule does not
  use them, but a peacetime placebo on these routes would need them.
- Hong Kong's reported exports include re-exports [Likely]; its onward figures are not
  goods made there.
- Release times: getDA gives them to a fraction of a second; the run 3 release tables cut
  them to the second, as the phase 1 and run 2 tables did. getDA listed no dataset twice and
  none outside the original classification for the new corridors.
