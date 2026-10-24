# Workflow

Each stage has an owner and a gate. A stage is done only when its gate passes.

| Stage | Owner | What happens | Gate |
|---|---|---|---|
| 1. Pull | trade-data-engineer | HMRC and Comtrade data for every corridor in config/countries.csv | Row counts and checksums match; gaps logged |
| 2. Leads | sanctions-analyst | Baseline, persistence, onward check, mirror gaps; leads table and report | Unit tests pass; every lead shows the rule it passed |
| 3. Backtest | case-researcher, backtest-analyst | Closed cases in, as-of reruns, hits and misses | No hindsight data used; misses reported as fully as hits |
| 4. Draft (phase 2) | case-note-drafter | A case-opening note per lead into the approval queue | Every number traced; no names; no accusations |
| 5. Decide | A person | Approve or reject each note, with a reason | Only a person can decide (enforced in fdcore.decisions) |
| 6. Review | fact-checker, guardrails-reviewer | Independent checks on anything to be shared | Both pass |
| 7. Ship | The person | Push, link, demo | /ship checklist passes |

## Phases

| Phase | Radar | Backtest |
|---|---|---|
| 0 | Done 21 Oct 2026: six leads, £18.0m above baseline | Done 21 Oct 2026: 22 concluded cases, 4 testable |
| 1 | Done 21 Oct 2026: five leads, £17.8m above baseline; mirror check; nine corridors | Run 1 done 21 Oct 2026: three of four cases hit before the first public action (backtest/reports/run1.md) |
| 2 | Case-note drafter, approval screen, memory core | Run 2: monthly onward data; peacetime placebo; more cases |
| 3 | Evals (Inspect), poisoning test, decision records | Write-up |
| 4 | Design, wayfinding and walkthrough films | |

Figures in the phase table come from HMRC data. Contains public sector information licensed under the Open Government Licence v3.0.
