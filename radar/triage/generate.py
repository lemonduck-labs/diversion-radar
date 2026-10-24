"""A seeded set of synthetic reports and a synthetic list in the UK Sanctions List's format.

The reports are shaped like what OTSI's online service asks for (Report a suspected breach of
trade sanctions): which sanctions and what goods or services, the people and businesses
involved, details and documents, and the reporter's professional relationship to them. Here
every party is a pseudonymous id: the exporters, consignees and forwarders of the restricted
layer's synthetic declarations (radar/declarations), or PTY- ids for parties outside UK customs.
No report has a name, address, email or phone number.

The list has the 58 headings of the UK Sanctions List, in order (FCDO's format guide), with
synthetic entities only: every Name 6 is a coded label, every registration number starts SYN-,
and Other Information says the entry is made up. It holds no individuals and no ships.

Only Rng (radar/declarations/generate.py), built on random.Random(seed).random(), is drawn on,
so one seed gives the same reports on any Python 3.

SYNTHETIC. A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from radar.declarations.generate import Rng

SEED = 20261022
ROOT = Path(__file__).resolve().parent.parent.parent
DECL = ROOT / "demo" / "radar" / "declarations"

#: The UK Sanctions List's headings, in the order the format guide gives them.
LIST_HEADINGS = (
    ["Last Updated", "Unique ID", "OFSI Group ID", "UN Reference Number", "Name 6"]
    + [f"Name {i}" for i in range(1, 6)]
    + ["Name type", "Alias strength", "Title", "Name non-latin script", "Non-latin script type",
       "Non-latin script language", "Regime Name", "Individual, Entity, Ship", "Designation source",
       "Sanctions Imposed", "Other Information", "UK Statement of Reasons"]
    + [f"Address Line {i}" for i in range(1, 7)]
    + ["Address Postal Code", "Address Country", "Phone number", "Website", "Email address", "Date Designated",
       "D.O.B", "Nationality(/ies)", "National Identifier number", "National Identifier additional information",
       "Passport number", "Passport additional information", "Position", "Gender", "Town of birth",
       "Country of birth", "Type of entity", "Subsidiaries", "Parent Company", "Business registration number (s)",
       "IMO number", "Current owner/operator (s)", "Previous owner/operator (s)", "Current believed flag of ship",
       "Previous flags", "Type of ship", "Tonnage of ship", "Length of ship", "Year Built",
       "Hull identification number (HIN)"]
)
assert len(LIST_HEADINGS) == 58

#: How a report reached the service, as the service's routes allow.
CHANNELS = {
    "someone_else": "Online service: report someone else",
    "self": "Online service: report yourself (voluntary disclosure)",
    "mandatory_financial": "Mandatory report: a financial services firm",
    "mandatory_legal": "Mandatory report: a legal services firm",
    "whistleblower": "Whistleblowing report (anonymous)",
    "referral": "Referral from another public body",
}
#: The reporter's professional relationship to the business reported, in the service's terms
#: as far as they were readable; the service's own options were not readable [Certain].
RELATIONSHIPS = {
    "customer": "A customer of the business", "supplier": "A supplier to the business",
    "competitor": "A competitor", "employee": "An employee or former employee",
    "bank": "Its bank or payment provider", "adviser": "Its legal or compliance adviser",
    "self": "The business itself", "none": "No relationship given", "public_body": "A public body",
}
#: What the report is about, which decides the body that handles it (match.BODIES).
NEXUS = {
    "uk_export": "Goods exported from the UK",
    "uk_technology": "Technology transferred from the UK",
    "outside_uk_goods": "Goods moved, made available or acquired outside the UK by a UK business",
    "services": "Services: brokering, technical help, finance or other services from a UK business",
    "payments": "Payments or funds",
    "oil_cap": "Shipping or other services for oil above the price cap",
    "internet": "Internet services",
}
VALUE_BANDS = ["under £100,000", "£100,000 to £1m", "over £1m", "not given"]

#: What a reporter says, as statement ids; match.STATEMENTS maps each to red flags and factors.
UK_EXPORT_SAYS = ["third_country_payer", "forwarder_destination", "documents_no_end_user", "route_complex",
                  "new_buyer_since_2022", "orders_rose", "price_above_market", "split_invoices", "different_code",
                  "buyer_russia_office", "no_checks_made"]
SELF_SAYS = ["found_in_own_checks", "stopped_and_fixed"]

#: Goods as a reporter might describe them, by the code they point to; the match table is the same.
GOODS_WORDS = {
    "854231": ["processors", "microcontrollers"],
    "854232": ["memory chips", "flash memory modules"],
    "854233": ["amplifier chips"],
    "854239": ["programmable logic chips"],
    "851762": ["network switches", "routers", "radio modems"],
    "852691": ["satellite navigation modules", "navigation receivers"],
    "853221": ["tantalum capacitors"],
    "853224": ["multilayer ceramic capacitors"],
    "8548": ["electronic spare parts"],
}
VAGUE_GOODS = ["integrated circuits", "capacitors", "telecoms kit"]
ORDINARY_GOODS = ["office furniture", "agricultural machinery", "industrial pumps", "printed books"]
ORDINARY_DESTINATIONS = ["FR", "DE", "NL", "IE", "US", "NO"]
SERVICES = ["brokering the sale", "technical help installing the goods", "arranging finance for the deal",
            "insurance for the shipment"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September"]


def _load(name: str) -> dict:
    return json.loads((DECL / f"{name}.json").read_text(encoding="utf-8"))


class _Ids:
    """Coded ids for parties outside the synthetic declarations, and registration numbers that
    differ from each other in at least three characters, so that a number one character from a
    listed one is near that one only."""

    ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    def __init__(self, r: Rng):
        self.r = r
        self.party = 0
        self.regs: list[str] = []

    def pty(self) -> str:
        self.party += 1
        return f"PTY-{9000 + self.party:04d}"

    def registration(self) -> str:
        while True:
            body = "".join(self.r.choice(self.ALPHABET) for _ in range(6))
            if all(sum(x != y for x, y in zip(body, other[8:])) >= 3 for other in self.regs):
                self.regs.append("SYN-REG-" + body)
                return self.regs[-1]


def _period(r: Rng) -> str:
    a = r.randint(0, len(MONTHS) - 3)
    b = a + r.randint(1, 2)
    return f"{MONTHS[a]} to {MONTHS[b]} 2026"


def _received(r: Rng) -> str:
    return (date(2026, 4, 1) + timedelta(days=r.randint(0, 182))).isoformat()


def _goods(r: Rng, code: str, hs_share: float = 0.35) -> dict:
    words = r.choice(GOODS_WORDS[code])
    return {"words": words, "hs_given": code if r.chance(hs_share) else None}


def _channel(r: Rng) -> tuple[str, str]:
    ch = r.weighted(["someone_else", "mandatory_financial", "mandatory_legal", "whistleblower", "referral"], [10, 6, 2, 3, 2])
    rel = {"someone_else": r.choice(["customer", "supplier", "competitor", "employee"]), "mandatory_financial": "bank",
           "mandatory_legal": "adviser", "whistleblower": "none", "referral": "public_body"}[ch]
    return ch, rel


def _documents(r: Rng, channel: str) -> list[str]:
    if channel == "whistleblower":
        return []      # the service tells whistleblowers not to send supporting information
    pool = ["commercial invoice", "packing list", "emails with the buyer", "bill of lading", "sale contract",
            "end-user statement", "bank payment record"]
    return sorted(r.sample(pool, r.randint(1, 3)))


def build_list(r: Rng, ids: _Ids, n: int = 24) -> list[dict]:
    """Synthetic entries in the UK Sanctions List's format: entities only, coded labels."""
    countries = ["Russia", "Russia", "Russia", "Belarus", "United Arab Emirates", "Turkey", "Kazakhstan", "Armenia",
                 "Kyrgyz Republic", "Uzbekistan", "Hong Kong", "China"]
    rows = []
    for i in range(1, n + 1):
        row = {h: "" for h in LIST_HEADINGS}
        designated = date(2022, 3, 1) + timedelta(days=r.randint(0, 1500))
        updated = designated + timedelta(days=r.randint(0, 200))
        row.update({
            "Last Updated": updated.strftime("%d/%m/%Y"), "Unique ID": f"SYN-RUS-{i:04d}",
            "Name 6": f"Synthetic listed entity {i:02d}", "Name type": "Primary name",
            "Regime Name": "Russia", "Individual, Entity, Ship": "Entity", "Designation source": "UK",
            "Sanctions Imposed": r.choice(["Asset freeze", "Asset freeze|Trust services sanctions"]),
            "Other Information": "SYNTHETIC. Made up for the radar's triage view; not a designation.",
            "Address Country": r.choice(countries), "Date Designated": designated.strftime("%d/%m/%Y"),
            "Type of entity": r.choice(["Business", "Business", "Trading company", "Manufacturer"]),
            "Business registration number (s)": ids.registration(),
        })
        rows.append(row)
    return rows


def build_reports(seed: int = SEED) -> tuple[list[dict], list[dict]]:
    """The synthetic reports and the synthetic list, from one seed."""
    r = Rng(seed)
    ids = _Ids(r)
    listed = build_list(r, ids)
    cases = _load("cases")["cases"]
    route_cases = [c for c in cases if c["kind"] == "exporter-route"]
    cluster_cases = [c for c in cases if c["kind"] == "consignee cluster"]
    entities = _load("entities")
    ordinary_exporters = [e["id"] for e in entities["exporters"] if e["corridor_radar_items"] == 0]
    corridor_consignees = {}
    for c in entities["consignees"]:
        corridor_consignees.setdefault(c["country"], []).append(c["id"])
    reports: list[dict] = []

    def add(**kw):
        kw.setdefault("transit", [])
        kw.setdefault("documents", _documents(r, kw["channel"]))
        kw["anonymous"] = kw["channel"] == "whistleblower"
        kw["synthetic"] = True
        reports.append(kw)

    def says(pool, k_lo=1, k_hi=3):
        return sorted(r.sample(pool, r.randint(k_lo, k_hi)))

    # 1. UK exports by an exporter in a declaration case, on its route (14).
    for c in r.sample(route_cases, 9) + r.sample(cluster_cases, 5):
        route = r.choice(c["parties"]["routes"])
        iso, code = route.split("-")
        ch, rel = _channel(r)
        parties = [{"role": "exporter", "id": c["parties"]["exporters"][0]},
                   {"role": "consignee", "id": r.choice(c["parties"]["consignees"])}]
        if c["parties"]["forwarders"] and r.chance(0.5):
            parties.append({"role": "forwarder", "id": c["parties"]["forwarders"][0]})
        add(channel=ch, relationship=rel, nexus="uk_export", goods=_goods(r, code), destination=iso,
            transit=[r.choice(["TR", "AE", "GE"])] if r.chance(0.25) and iso not in ("TR", "AE", "GE") else [],
            value_band=r.choice(VALUE_BANDS[:3]), period=_period(r), parties=parties, says=says(UK_EXPORT_SAYS))
    # 2. UK exports by an exporter outside any case, to a corridor, on a radar code (6).
    for _ in range(6):
        code = r.choice(list(GOODS_WORDS))
        iso = r.choice(["KZ", "AE", "TR", "AM", "KG", "UZ"])
        ch, rel = _channel(r)
        add(channel=ch, relationship=rel, nexus="uk_export", goods=_goods(r, code), destination=iso,
            value_band=r.choice(VALUE_BANDS), period=_period(r),
            parties=[{"role": "exporter", "id": r.choice(ordinary_exporters)},
                     {"role": "consignee", "id": r.choice(corridor_consignees.get(iso) or [ids.pty()])}],
            says=says(UK_EXPORT_SAYS, 1, 2))
    # 3. Voluntary disclosures: an exporter reports its own shipments (3).
    for c in r.sample(route_cases, 3):
        route = r.choice(c["parties"]["routes"])
        iso, code = route.split("-")
        add(channel="self", relationship="self", nexus="uk_export", goods=_goods(r, code, 0.9), destination=iso,
            value_band=r.choice(VALUE_BANDS[:3]), period=_period(r),
            parties=[{"role": "exporter", "id": c["parties"]["exporters"][0]},
                     {"role": "consignee", "id": c["parties"]["consignees"][0]}],
            says=sorted(SELF_SAYS + r.sample(["no_checks_made", "documents_no_end_user"], 1)))
    # 4. Goods moved between third countries by a UK business (5).
    for _ in range(5):
        code = r.choice(list(GOODS_WORDS))
        iso = r.choice(["KZ", "KG", "AM", "UZ", "GE"])
        ch, rel = _channel(r)
        add(channel=ch, relationship=rel, nexus="outside_uk_goods", goods=_goods(r, code, 0.2), destination=iso,
            transit=[r.choice(["AE", "TR", "CN", "HK"])], value_band=r.choice(VALUE_BANDS), period=_period(r),
            parties=[{"role": "UK business", "id": ids.pty()}, {"role": "supplier abroad", "id": ids.pty()},
                     {"role": "buyer", "id": ids.pty()}],
            says=says(["third_country_payer", "route_complex", "buyer_russia_office", "documents_no_end_user"], 1, 2))
    # 5. Services from a UK business (4).
    for _ in range(4):
        code = r.choice(list(GOODS_WORDS))
        iso = r.choice(["AE", "TR", "KZ", "AM"])
        ch, rel = _channel(r)
        add(channel=ch, relationship=rel, nexus="services", goods=_goods(r, code, 0.2), destination=iso,
            service=r.choice(SERVICES), value_band=r.choice(VALUE_BANDS), period=_period(r),
            parties=[{"role": "UK service provider", "id": ids.pty()}, {"role": "buyer", "id": ids.pty()}],
            says=says(["buyer_russia_office", "third_country_payer", "route_complex"], 1, 2))
    # 6. Payments, the oil price cap, internet services: other bodies (4).
    add(channel="mandatory_financial", relationship="bank", nexus="payments", goods=None, destination="AE",
        value_band="£100,000 to £1m", period=_period(r),
        parties=[{"role": "payer", "id": ids.pty()}, {"role": "payee", "id": ids.pty()}], says=["third_country_payer"])
    add(channel="mandatory_financial", relationship="bank", nexus="payments", goods=None, destination="TR",
        value_band="under £100,000", period=_period(r),
        parties=[{"role": "payer", "id": ids.pty()}, {"role": "payee", "id": ids.pty()}], says=["split_invoices"])
    add(channel="someone_else", relationship="competitor", nexus="oil_cap", goods=None, destination="TR",
        value_band="over £1m", period=_period(r), parties=[{"role": "UK service provider", "id": ids.pty()}], says=[])
    add(channel="someone_else", relationship="customer", nexus="internet", goods=None, destination="AM",
        value_band="not given", period=_period(r), parties=[{"role": "UK service provider", "id": ids.pty()}], says=[])
    # 7. Words that point to no single code, or to none (3).
    for words in VAGUE_GOODS:
        iso = r.choice(["KZ", "AE", "TR"])
        ch, rel = _channel(r)
        add(channel=ch, relationship=rel, nexus="uk_export", goods={"words": words, "hs_given": None}, destination=iso,
            value_band=r.choice(VALUE_BANDS), period=_period(r),
            parties=[{"role": "exporter", "id": r.choice(ordinary_exporters)}, {"role": "consignee", "id": ids.pty()}],
            says=says(["documents_no_end_user", "new_buyer_since_2022", "orders_rose"], 1, 1))
    # 8. Ordinary goods to ordinary destinations: nothing the radar covers (4).
    for words in ORDINARY_GOODS:
        ch, rel = _channel(r)
        add(channel=ch, relationship=rel, nexus="uk_export", goods={"words": words, "hs_given": None},
            destination=r.choice(ORDINARY_DESTINATIONS), value_band=r.choice(VALUE_BANDS), period=_period(r),
            parties=[{"role": "exporter", "id": r.choice(ordinary_exporters)}, {"role": "consignee", "id": ids.pty()}],
            says=[])
    # Warning letters and earlier reports, on a few of the UK export reports.
    uk = [x for x in reports if x["nexus"] == "uk_export" and x["channel"] != "self" and x["says"]]
    for x in r.sample(uk, 3):
        x["says"] = sorted(set(x["says"]) | {"earlier_warning_letter"})
    # Listed parties: four reports name a party whose registration number is on the synthetic
    # list, and two one whose number is one character from a listed one.
    named = [x for x in reports if x["nexus"] in ("uk_export", "outside_uk_goods", "services", "payments")
             and x["channel"] != "self"]
    picks = r.sample(named, 6)
    for i, x in enumerate(picks):
        entry = listed[r.randint(0, len(listed) - 1)]
        reg = entry["Business registration number (s)"]
        if i >= 4:
            last = reg[-1]
            reg = reg[:-1] + ("A" if last != "A" else "B")
        target = next((p for p in x["parties"] if p["role"] in ("consignee", "buyer", "payee", "supplier abroad")), x["parties"][-1])
        target["registration"] = reg
    # Order by date received; ids follow that order.
    for x in reports:
        x["received"] = _received(r)
    reports.sort(key=lambda x: x["received"])
    out = []
    for i, x in enumerate(reports, 1):
        y = {"id": f"RPT-SYN-{i:03d}", "received": x["received"], "channel": x["channel"],
             "relationship": x["relationship"], "anonymous": x["anonymous"], "nexus": x["nexus"],
             "goods": x["goods"], "service": x.get("service"), "destination": x["destination"], "transit": x["transit"],
             "value_band": x["value_band"], "period": x["period"], "parties": x["parties"], "says": x["says"],
             "documents": x["documents"], "synthetic": True}
        out.append(y)
    return out, listed
