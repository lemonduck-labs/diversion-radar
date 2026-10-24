"""Client for UN Comtrade.

The public preview endpoint needs no key, returns up to 500 records a call,
accepts ONE period per call and is rate limited (it answers 429 with
"Try again in N seconds"). With a free subscription key (set COMTRADE_KEY),
the data endpoint takes several periods per call and returns far more.

Check Comtrade's terms before republishing its figures.
"""

from __future__ import annotations

import json
import os
import re
import time

import requests

from .ingest_log import log_pull

PREVIEW = "https://comtradeapi.un.org/public/v1/preview/C/{freq}/HS"
KEYED = "https://comtradeapi.un.org/data/v1/get/C/{freq}/HS"
PAUSE = 4.0  # seconds between preview calls


def query_url(reporter: int, partner: int, codes: list[str], period: str,
              flow: str = "X", freq: str = "A", keyed: bool = False) -> str:
    base = (KEYED if keyed else PREVIEW).format(freq=freq)
    return (f"{base}?reporterCode={reporter}&partnerCode={partner}"
            f"&cmdCode={','.join(codes)}&period={period}&flowCode={flow}")


def _get(url: str, headers: dict) -> requests.Response:
    for _ in range(6):
        resp = requests.get(url, headers=headers, timeout=60)
        if resp.status_code == 429:
            m = re.search(r"again in (\d+) second", resp.text)
            time.sleep(int(m.group(1)) + 3 if m else 8)
            continue
        resp.raise_for_status()
        return resp
    raise RuntimeError(f"Rate limited too many times: {url}")


def is_total(row: dict) -> bool:
    """Keep only the headline record: no second partner, all customs procedures,
    all modes of transport."""
    return row.get("partner2Code") == 0 and row.get("customsCode") == "C00" and row.get("motCode") == 0


def pull(reporter: int, partner: int, codes: list[str], periods: list[str], out_dir,
         flow: str = "X", freq: str = "A") -> list[dict]:
    key = os.environ.get("COMTRADE_KEY")
    headers = {"Ocp-Apim-Subscription-Key": key} if key else {}
    rows: list[dict] = []
    for period in periods:
        url = query_url(reporter, partner, codes, period, flow, freq, keyed=bool(key))
        resp = _get(url, headers)
        body = resp.json()
        data = body.get("data", []) or []
        if not key and len(data) >= 500:
            raise RuntimeError("Preview cap of 500 records reached; split the query or use a key")
        out = out_dir / f"comtrade_{reporter}_{partner}_{flow}_{freq}_{period}.json"
        out.write_text(json.dumps({"url": url, "rows": data}, indent=1))
        log_pull("comtrade", url, resp.content, len(data), str(out))
        rows.extend(r for r in data if is_total(r))
        time.sleep(PAUSE)
    return rows
