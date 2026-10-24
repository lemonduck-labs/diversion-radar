# 1. Python first

Date: 21 October 2026. Status: accepted (default from the build plan; the owner can overturn it).

## Context

The radar may one day run on a commercial data platform, but code built on a platform lives there.

## Decision

Build version 1 in plain Python (pandas, DuckDB, Streamlit), with its objects designed up front so
they map one to one onto an ontology-style platform if a deployment calls for one.

## Consequences

- The code is ours, runs anywhere and can be sold or shown without platform access.
- The ontology is designed up front so the mapping stays one to one.
