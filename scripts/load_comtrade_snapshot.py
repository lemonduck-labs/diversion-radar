"""Convert the browser snapshot of UN Comtrade records into data/processed/comtrade_annual.csv,
refusing to write unless the row count and value checksum in the header match."""
import io
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
src = ROOT / "data" / "raw" / "comtrade_annual_browser_2026-10-21.txt"
text = src.read_text()
header = text.splitlines()[0]
want_rows = int(re.search(r"rows (\d+)", header).group(1))
want_value = int(re.search(r"sumValue (\d+)", header).group(1))
body = "\n".join(l for l in text.splitlines() if not l.startswith("#"))
df = pd.read_csv(io.StringIO(body), dtype={"code": str})
got = (len(df), int(df.value_usd.sum()))
print("rows/value got ", got)
print("rows/value want", (want_rows, want_value))
if got != (want_rows, want_value):
    sys.exit("Checksum mismatch: snapshot was not transcribed exactly")
df.to_csv(ROOT / "data" / "processed" / "comtrade_annual.csv", index=False)
print("wrote", len(df), "rows")
