Use the trade-data-engineer agent to pull fresh data for every corridor in config/countries.csv:
run python scripts/pull.py (or scripts/pull_spike.py), check row counts and checksums, and report any
reporter that has not published the latest year. If this machine cannot reach the APIs, say so and stop.
