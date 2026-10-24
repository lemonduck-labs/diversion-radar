"""Paths and loaders for the files in config/."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
PROCESSED = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"


def read_rows(path: Path) -> list[dict]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def codes(path: Path = CONFIG / "codes.csv") -> list[dict]:
    """The nine goods codes, with their 8-digit ranges for HMRC."""
    return read_rows(path)


def countries(path: Path = CONFIG / "countries.csv") -> list[dict]:
    """Corridor countries, Russia (target) and the UK (origin)."""
    return read_rows(path)


def corridors(rows: list[dict]) -> list[dict]:
    return [c for c in rows if c["role"] == "corridor"]
