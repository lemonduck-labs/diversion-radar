"""Client for HMRC's overseas trade statistics (uktradeinfo OData API).

No key is needed. The API allows 60 requests a minute and returns at most
40,000 rows per response, with @odata.nextLink for the rest.
Data: Open Government Licence v3.0.
"""

from __future__ import annotations

import json
import time
from urllib.parse import quote

import requests

from .ingest_log import log_pull

BASE = "https://api.uktradeinfo.com"
NON_EU_EXPORTS = 4  # FlowTypeId: 1 EU imports, 2 EU exports, 3 non-EU imports, 4 non-EU exports
MIN_INTERVAL = 1.1  # seconds between calls, to stay under 60 a minute


class HMRCClient:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self._last = 0.0

    def _get(self, url: str) -> tuple[dict, bytes]:
        wait = MIN_INTERVAL - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        for attempt in range(4):
            resp = self.session.get(url, timeout=60)
            self._last = time.monotonic()
            if resp.status_code == 429:  # rate limited: the docs say wait up to a minute
                time.sleep(65)
                continue
            resp.raise_for_status()
            return resp.json(), resp.content
        raise RuntimeError(f"Rate limited too many times: {url}")

    def get_all(self, url: str) -> tuple[list[dict], bytes]:
        """Follow @odata.nextLink until every row is fetched."""
        rows: list[dict] = []
        raw = b""
        while url:
            body, content = self._get(url)
            rows.extend(body.get("value", []))
            raw += content
            url = body.get("@odata.nextLink")
        return rows, raw


def monthly_exports_url(country_id: int, cn8_from: int, cn8_to: int,
                        month_from: int = 201901, flow: int = NON_EU_EXPORTS) -> str:
    """Monthly UK exports of one goods-code range to one country, summed on the server."""
    flt = (f"CountryId eq {country_id} and FlowTypeId eq {flow} "
           f"and CommodityId ge {cn8_from} and CommodityId le {cn8_to} "
           f"and MonthId ge {month_from}")
    apply = (f"filter({flt})/groupby((MonthId),"
             f"aggregate(Value with sum as Value,NetMass with sum as NetMass))")
    return f"{BASE}/OTS?$apply={quote(apply, safe='')}"


def pull_monthly_exports(client: HMRCClient, country_id: int, code: str, cn8_from: int,
                         cn8_to: int, out_dir, month_from: int = 201901) -> list[dict]:
    url = monthly_exports_url(country_id, cn8_from, cn8_to, month_from)
    rows, raw = client.get_all(url)
    out = out_dir / f"hmrc_{country_id}_{code}.json"
    out.write_text(json.dumps({"url": url, "rows": rows}, indent=1))
    log_pull("hmrc", url, raw, len(rows), str(out))
    return rows
