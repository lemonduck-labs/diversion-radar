"""Readers for the compact browser snapshots in data/raw.

The build workspace cannot reach the HMRC or UN Comtrade APIs, so some pulls ran in
a browser using the same queries as radar/hmrc.py and radar/comtrade.py. Each
snapshot carries checksums computed in the browser. These readers refuse to return
anything unless the checksums match, so a transcription error cannot reach the
analysis.
"""

from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

import pandas as pd


class SnapshotMismatch(ValueError):
    pass


def read_hmrc(path: str | Path) -> pd.DataFrame:
    """HMRC monthly aggregates. Header: rows N; sumValue V; sumMass M.
    Body lines: country_id,code:YYMM=value/mass;YYMM=value/mass;..."""
    lines = Path(path).read_text().splitlines()
    header = lines[0]
    want = tuple(int(re.search(p, header).group(1))
                 for p in (r"rows (\d+)", r"sumValue (\d+)", r"sumMass (\d+)"))
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
    if got != want:
        raise SnapshotMismatch(f"{path}: rows/value/mass {got} against header {want}")
    return df.sort_values(["country_id", "code", "month"]).reset_index(drop=True)


def read_comtrade(path: str | Path) -> pd.DataFrame:
    """UN Comtrade annual records. Header: rows N; sumValue V. Body: a CSV."""
    text = Path(path).read_text()
    header = text.splitlines()[0]
    want = (int(re.search(r"rows (\d+)", header).group(1)),
            int(re.search(r"sumValue (\d+)", header).group(1)))
    body = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
    df = pd.read_csv(io.StringIO(body), dtype={"code": str})
    got = (len(df), int(df.value_usd.sum()))
    if got != want:
        raise SnapshotMismatch(f"{path}: rows/value {got} against header {want}")
    return df


def read_availability(path: str | Path, sha256: str) -> dict[str, pd.DataFrame]:
    """UN Comtrade data availability (getDA): when each reporter's data for each
    period was first and last released. The browser computed a SHA-256 of the text;
    it must match exactly.

    Returns {"annual": ..., "monthly": ..., "monthly_summary": ...}.
    """
    raw = Path(path).read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != sha256:
        raise SnapshotMismatch(f"{path}: sha256 {got} against {sha256}")
    lines = raw.decode().splitlines()
    want_rows = int(re.match(r"ROWS (\d+)", lines[0]).group(1))
    body = [line.split("|") for line in lines[1:] if line.strip()]
    if len(body) != want_rows:
        raise SnapshotMismatch(f"{path}: {len(body)} rows against header {want_rows}")
    annual = pd.DataFrame(
        [r[1:] for r in body if r[0] == "A"],
        columns=["reporter", "year", "classification", "is_original_classification",
                 "first_released", "last_released", "total_records", "dataset_checksum"])
    monthly = pd.DataFrame([r[1:] for r in body if r[0] == "M"],
                           columns=["reporter", "period", "classification",
                                    "first_released", "last_released"])
    summary = pd.DataFrame([r[1:] for r in body if r[0] == "MSUM"],
                           columns=["reporter", "monthly_periods", "first_period", "last_period"])
    for df, cols in ((annual, ["reporter", "year", "total_records"]),
                     (monthly, ["reporter", "period"]),
                     (summary, ["reporter", "monthly_periods"])):
        for c in cols:
            df[c] = df[c].astype(int)
    for df in (annual, monthly):
        for c in ("first_released", "last_released"):
            df[c] = pd.to_datetime(df[c])
    return {"annual": annual, "monthly": monthly, "monthly_summary": summary}


RUN2_SECTIONS = ("DA_A", "DA_M", "ANN", "MON", "CALLS")
ANN_COLUMNS = ["reporter", "partner", "flow", "code", "year", "value_usd", "net_wgt_kg",
               "is_reported", "classification"]


def read_comtrade_run2(path: str | Path, sha256: str) -> dict[str, pd.DataFrame]:
    """The UN Comtrade snapshot for backtest run 2, pulled in a browser.

    Sections, each opened by '#SECTION <name>|rows <n>' (ANN and MON add '|sumValue <v>'):
    DA_A  annual data availability: reporter|year|classification|first_released|last_released
    DA_M  monthly data availability: reporter|period|classification|first_released|last_released
    ANN   annual exports to Russia, 2016-18: a CSV with a header line (not counted in rows)
    MON   monthly exports to Russia: reporter|period|code|value_usd
    CALLS the monthly calls made: reporter|period (one per corridor and month)
    MULTI optional: calls that asked for several corridors at once: period|reporter,reporter,...
          (reporters in the order they were sent)

    The browser computed a SHA-256 of the whole text; it must match exactly, and every
    section's row count and value sum must match its header.
    """
    raw = Path(path).read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != sha256:
        raise SnapshotMismatch(f"{path}: sha256 {got} against {sha256}")
    sections: dict[str, dict] = {}
    current = None
    for line in raw.decode().splitlines():
        if line.startswith("#SECTION "):
            parts = line[len("#SECTION "):].split("|")
            current = parts[0]
            meta = dict(p.split(" ", 1) for p in parts[1:])
            sections[current] = {"rows": int(meta["rows"]), "sum": float(meta["sumValue"]) if "sumValue" in meta else None,
                                 "lines": []}
        elif line.startswith("#") or not line.strip():
            continue
        elif current is not None:
            sections[current]["lines"].append(line)
    missing = [s for s in RUN2_SECTIONS if s not in sections]
    if missing:
        raise SnapshotMismatch(f"{path}: missing sections {missing}")

    def pipe(name, cols):
        return pd.DataFrame([l.split("|") for l in sections[name]["lines"]], columns=cols)

    out = {
        "multi": (pd.DataFrame([l.split("|") for l in sections["MULTI"]["lines"]], columns=["period", "reporters"])
                  if "MULTI" in sections else pd.DataFrame(columns=["period", "reporters"])),
        "annual_availability": pipe("DA_A", ["reporter", "year", "classification", "first_released", "last_released"]),
        "monthly_availability": pipe("DA_M", ["reporter", "period", "classification", "first_released", "last_released"]),
        "monthly": pipe("MON", ["reporter", "period", "code", "value_usd"]),
        "calls": pipe("CALLS", ["reporter", "period"]),
    }
    ann_lines = sections["ANN"]["lines"]
    if ann_lines and ann_lines[0].split(",")[0] == "reporter":
        ann_lines = ann_lines[1:]
    out["annual"] = pd.read_csv(io.StringIO("\n".join([",".join(ANN_COLUMNS), *ann_lines])), dtype={"code": str})
    counts = {"DA_A": "annual_availability", "DA_M": "monthly_availability", "ANN": "annual",
              "MON": "monthly", "CALLS": "calls"}
    if "MULTI" in sections:
        counts["MULTI"] = "multi"
    for sec, key in counts.items():
        if len(out[key]) != sections[sec]["rows"]:
            raise SnapshotMismatch(f"{path}: {sec} has {len(out[key])} rows against header {sections[sec]['rows']}")
    for df, cols in ((out["annual_availability"], ["reporter", "year"]),
                     (out["monthly_availability"], ["reporter", "period"]),
                     (out["monthly"], ["reporter", "period"]), (out["calls"], ["reporter", "period"])):
        for c in cols:
            df[c] = df[c].astype(int)
    out["monthly"]["value_usd"] = out["monthly"]["value_usd"].astype(float)
    for df in (out["annual_availability"], out["monthly_availability"]):
        for c in ("first_released", "last_released"):
            df[c] = pd.to_datetime(df[c], format="ISO8601")
    for sec, key, col in (("ANN", "annual", "value_usd"), ("MON", "monthly", "value_usd")):
        want = sections[sec]["sum"]
        if want is not None and abs(round(float(out[key][col].sum()), 2) - want) > 0.011:
            raise SnapshotMismatch(f"{path}: {sec} value sum {out[key][col].sum():.2f} against header {want}")
    return out


RUN3_SECTIONS = ("DA_A", "DA_M", "ANN", "MON", "CALLS")
RUN3_DA_A = ["reporter", "year", "classification", "is_original_classification",
             "first_released", "last_released", "total_records", "dataset_checksum"]
RUN3_DA_M = ["reporter", "period", "classification", "is_original_classification",
             "first_released", "last_released"]


def _sections(raw: bytes) -> dict[str, dict]:
    sections: dict[str, dict] = {}
    current = None
    for line in raw.decode().splitlines():
        if line.startswith("#SECTION "):
            parts = line[len("#SECTION "):].split("|")
            current = parts[0]
            meta = dict(p.split(" ", 1) for p in parts[1:])
            sections[current] = {"rows": int(meta["rows"]),
                                 "sum": float(meta["sumValue"]) if "sumValue" in meta else None,
                                 "lines": []}
        elif line.startswith("#") or not line.strip():
            continue
        elif current is not None:
            sections[current]["lines"].append(line)
    return sections


def read_comtrade_run3(path: str | Path, sha256: str) -> dict[str, pd.DataFrame]:
    """The UN Comtrade snapshot for run 3 (nine corridors added), pulled in a browser.

    Sections, each opened by '#SECTION <name>|rows <n>' (ANN and MON add '|sumValue <v>'):
    DA_A  annual availability, every dataset getDA listed:
          reporter|year|classification|is_original_classification|first_released|
          last_released|total_records|dataset_checksum
    DA_M  monthly availability, every dataset getDA listed:
          reporter|period|classification|is_original_classification|first_released|last_released
    ANN   annual records, exports to Russia (partner 643, flow X) and imports from the UK
          (partner 826, flow M), headline records only: a CSV with a header line (not counted)
    MON   monthly exports to Russia, headline records only: reporter|period|code|value_usd
    CALLS every call, in the order made: url|records returned|headline records|retrieved_at

    Release times are kept as getDA gave them (to a fraction of a second, no time zone).
    The browser computed a SHA-256 of the whole text; it must match exactly, and every
    section's row count and value sum must match its header.
    """
    raw = Path(path).read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != sha256:
        raise SnapshotMismatch(f"{path}: sha256 {got} against {sha256}")
    sections = _sections(raw)
    missing = [s for s in RUN3_SECTIONS if s not in sections]
    if missing:
        raise SnapshotMismatch(f"{path}: missing sections {missing}")

    def pipe(name, cols):
        rows = [l.split("|") for l in sections[name]["lines"]]
        if any(len(r) != len(cols) for r in rows):
            raise SnapshotMismatch(f"{path}: {name} has a line without {len(cols)} fields")
        return pd.DataFrame(rows, columns=cols)

    out = {
        "annual_availability": pipe("DA_A", RUN3_DA_A),
        "monthly_availability": pipe("DA_M", RUN3_DA_M),
        "monthly": pipe("MON", ["reporter", "period", "code", "value_usd"]),
        "calls": pipe("CALLS", ["url", "records", "headline", "retrieved_at"]),
    }
    ann_lines = sections["ANN"]["lines"]
    if not ann_lines or ann_lines[0] != ",".join(ANN_COLUMNS):
        raise SnapshotMismatch(f"{path}: ANN does not start with its header line")
    out["annual"] = pd.read_csv(io.StringIO("\n".join(ann_lines)), dtype={"code": str, "flow": str})
    out["annual_lines"] = pd.DataFrame({"line": ann_lines[1:]})
    out["monthly_lines"] = pd.DataFrame({"line": list(sections["MON"]["lines"])})
    for sec, key in (("DA_A", "annual_availability"), ("DA_M", "monthly_availability"), ("ANN", "annual"),
                     ("MON", "monthly"), ("CALLS", "calls")):
        if len(out[key]) != sections[sec]["rows"]:
            raise SnapshotMismatch(f"{path}: {sec} has {len(out[key])} rows against header {sections[sec]['rows']}")
    for df, cols in ((out["annual_availability"], ["reporter", "year", "total_records"]),
                     (out["monthly_availability"], ["reporter", "period"]),
                     (out["monthly"], ["reporter", "period"]), (out["calls"], ["records", "headline"])):
        for c in cols:
            df[c] = df[c].astype(int)
    out["monthly"]["value_usd"] = out["monthly"]["value_usd"].astype(float)
    for df in (out["annual_availability"], out["monthly_availability"]):
        for c in ("first_released", "last_released"):
            df[c] = pd.to_datetime(df[c], format="ISO8601")
    for sec, key, col in (("ANN", "annual", "value_usd"), ("MON", "monthly", "value_usd")):
        want = sections[sec]["sum"]
        if want is None or abs(round(float(out[key][col].sum()), 2) - want) > 0.011:
            raise SnapshotMismatch(f"{path}: {sec} value sum {out[key][col].sum():.2f} against header {want}")
    return out
