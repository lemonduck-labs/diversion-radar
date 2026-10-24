"""Append-only log of every data pull: what was fetched, from where, when,
under which licence, and a hash of what came back. Every number the radar
shows should trace back to an entry here."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "ingest_log.jsonl"

LICENCES = {
    "hmrc": "Open Government Licence v3.0",
    "comtrade": "UN Comtrade data use policy and re-dissemination guidance (see data/SOURCES.md)",
    "uk_sanctions_list": "Open Government Licence v3.0",
    "boe": "Bank of England database terms (check before republishing)",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def log_pull(source: str, url: str, payload: bytes, rows: int, out_file: str | None = None,
             method: str = "python", note: str | None = None) -> dict:
    """Record one pull. Returns the entry written."""
    entry = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "licence": LICENCES.get(source, "unknown"),
        "url": url,
        "rows": rows,
        "sha256": sha256_bytes(payload),
        "out_file": out_file,
        "method": method,
    }
    if note:
        entry["note"] = note
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry
