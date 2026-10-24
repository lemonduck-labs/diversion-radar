"""Convert the compact browser snapshot of HMRC data into data/processed/hmrc_monthly.csv.

The snapshot holds the same server-side aggregates that radar/hmrc.py requests
(monthly sums of Value and NetMass per country and goods-code range). It was
pulled through a browser because the build workspace could not reach the API.
The header line carries row and value checksums computed in the browser; this
script refuses to write the CSV unless they match.
"""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
src = ROOT / "data" / "raw" / "hmrc_monthly_browser_2026-10-21.txt"
lines = src.read_text().splitlines()
header = lines[0]
want_rows = int(re.search(r"rows (\d+)", header).group(1))
want_value = int(re.search(r"sumValue (\d+)", header).group(1))
want_mass = int(re.search(r"sumMass (\d+)", header).group(1))

records = []
for line in lines[1:]:
    if not line.strip():
        continue
    key, _, body = line.partition(":")
    country, code = key.split(",")
    for item in filter(None, body.split(";")):
        ym, _, vm = item.partition("=")
        v, _, m = vm.partition("/")
        records.append({"country_id": int(country), "code": code, "month": 200000 + int(ym),
                        "value_gbp": int(v), "net_mass_kg": int(m)})

df = pd.DataFrame(records)
got = (len(df), int(df.value_gbp.sum()), int(df.net_mass_kg.sum()))
print("rows/value/mass got ", got)
print("rows/value/mass want", (want_rows, want_value, want_mass))
if got != (want_rows, want_value, want_mass):
    sys.exit("Checksum mismatch: snapshot was not transcribed exactly")
out = ROOT / "data" / "processed" / "hmrc_monthly.csv"
df.sort_values(["country_id", "code", "month"]).to_csv(out, index=False)
print("wrote", out, len(df), "rows")
