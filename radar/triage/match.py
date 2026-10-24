"""Reads each synthetic report against what the radar holds, for a person to triage.

For each report: the goods codes its words or code point to; the synthetic declaration cases
that hold one of its parties; any party whose registration number is on, or one character from,
the synthetic list; the body that handles that kind of report, from OTSI's published split; the
factors OTSI's assessment guidance weighs that the report states; the red flags it raises, from
the radar's red flag list; and a reading order by a rule set out in RULE_ORDER. The route's radar
status (a lead, a series shown with no lead, a series held back under the display rule, or no
corridor) is looked up by the page against the run it shows, so this module never touches the
display rule.

Everything here is what a report states, read against synthetic data. Nothing is a finding:
a report is an allegation until a person has assessed it [Certain].
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

#: The goods words a report may use, and the codes each points to, with the confidence of the
#: reading. A code given in the report is read as given [Certain]; words are read [Likely];
#: words that fit a whole family of codes point to all of them [Guessing].
PHRASES = {
    "processors": (["854231"], "Likely"), "microcontrollers": (["854231"], "Likely"),
    "memory chips": (["854232"], "Likely"), "flash memory modules": (["854232"], "Likely"),
    "amplifier chips": (["854233"], "Likely"), "programmable logic chips": (["854239"], "Likely"),
    "network switches": (["851762"], "Likely"), "routers": (["851762"], "Likely"), "radio modems": (["851762"], "Likely"),
    "satellite navigation modules": (["852691"], "Likely"), "navigation receivers": (["852691"], "Likely"),
    "tantalum capacitors": (["853221"], "Likely"), "multilayer ceramic capacitors": (["853224"], "Likely"),
    "electronic spare parts": (["8548"], "Guessing"),
    "integrated circuits": (["854231", "854232", "854233", "854239"], "Guessing"),
    "capacitors": (["853221", "853224"], "Guessing"),
}

#: OTSI's published split of who handles what (Office of Trade Sanctions Implementation, Report a
#: suspected breach of trade sanctions, last updated 27 June 2025, read 22 October 2026).
BODIES = {
    "uk_export": ("HMRC", "Export controls and trade sanctions involving UK customs, including the export of goods, are for HMRC: reports go to HMRC."),
    "uk_technology": ("HMRC", "The transfer of technology to or from the UK goes to HMRC."),
    "outside_uk_goods": ("OTSI", "Moving, making available or acquiring sanctioned goods or technology outside the UK goes to OTSI."),
    "services": ("OTSI", "Providing or procuring sanctioned services, and services ancillary to moving goods outside the UK, go to OTSI."),
    "payments": ("OFSI", "Financial sanctions are reported to the Office of Financial Sanctions Implementation, in addition to any report to OTSI."),
    "oil_cap": ("HM Treasury", "The oil price cap is enforced by HM Treasury."),
    "internet": ("Ofcom", "Internet service measures are enforced by Ofcom."),
}
BODY_SOURCE = {"publisher": "Office of Trade Sanctions Implementation", "title": "Report a suspected breach of trade sanctions",
               "date": "last updated 27 Jun 2025", "read": "22 Oct 2026"}

#: The factors OTSI's assessment guidance weighs, in our words (Office of Trade Sanctions
#: Implementation, How suspected breaches of trade sanctions are assessed by the Office of Trade
#: Sanctions Implementation (OTSI), last updated 31 July 2025, read 22 October 2026).
FACTORS = {
    "severity": {
        "culpability": "Culpability, from none or low, through negligence or recklessness, to intent or significant negligence",
        "concealment": "Extensive or sophisticated planning, such as efforts to conceal the breach",
        "harm": "Harm to the purposes of the sanctions regime",
        "value": "Financial value, where nothing else points to the severity",
    },
    "mitigating": {
        "voluntary_disclosure": "Timely voluntary disclosure by whoever is responsible",
        "cooperation": "Complying with OTSI's requests for information",
        "no_previous": "No record of breaching UK sanctions before",
        "due_diligence": "Good customer due diligence and compliance systems, for the business's size and exposure",
        "remediation": "Steps taken to deal with the causes of the breach",
    },
    "aggravating": {
        "ignored_warning": "Not responding to earlier warning letters",
        "poor_cooperation": "Poor compliance with the investigation",
        "withholding": "Withholding information or obstructing access to it, such as concealing or destroying evidence",
        "related_requirements": "Not complying with related requirements, such as recordkeeping and licensing conditions",
        "previous": "A previous breach by the same person or business, allowing for the time since",
        "inadequate_dd": "Inadequate due diligence",
        "blaming": "Trying to wrongly blame others",
    },
}
FACTOR_SOURCE = {"publisher": "Office of Trade Sanctions Implementation",
                 "title": "How suspected breaches of trade sanctions are assessed by the Office of Trade Sanctions Implementation (OTSI)",
                 "date": "last updated 31 Jul 2025", "read": "22 Oct 2026"}

#: What a reporter says, in plain words, with the red flags (radar/brief/spec/redflags.json ids)
#: and the assessment factors each one touches. Every one is as the report states it.
STATEMENTS = {
    "third_country_payer": ("Payment came from a business in another country that is not otherwise part of the deal.", ["third-country-payer"], []),
    "forwarder_destination": ("A freight forwarder is named as the final destination of the goods.", ["forwarder-as-destination"], []),
    "documents_no_end_user": ("The documents do not name the end user.", ["documents-end-user", "end-use-details"], []),
    "route_complex": ("The goods went by a long route through several countries.", ["route-complex"], []),
    "new_buyer_since_2022": ("The buyer is new and was set up after February 2022.", ["new-customer-dual-use"], []),
    "orders_rose": ("The buyer's orders rose sharply over the year.", ["order-volume-rise"], []),
    "price_above_market": ("The buyer paid well above the usual price.", ["price-and-invoices"], []),
    "split_invoices": ("Invoices were split into smaller amounts.", ["price-and-invoices"], []),
    "different_code": ("The invoice gives the goods a different commodity code from the one the reporter expected.", ["hs-code-check"], [("severity", "concealment")]),
    "buyer_russia_office": ("The buyer has an office in Russia.", ["russia-ties"], []),
    "no_checks_made": ("No checks were made on the buyer before the goods were sent.", ["sanctions-list-check", "checks-repeated"], [("aggravating", "inadequate_dd")]),
    "earlier_warning_letter": ("The business had a warning letter about earlier shipments.", [], [("aggravating", "ignored_warning")]),
    "found_in_own_checks": ("The business found the shipments in its own checks and is reporting them itself.", [], [("mitigating", "voluntary_disclosure")]),
    "stopped_and_fixed": ("The business has stopped the shipments and changed its checks.", [], [("mitigating", "remediation")]),
}

#: The reading order: this tool's rule, not OTSI's (OTSI publishes no triage scoring) [Certain].
RULE_ORDER = [
    (1, "A party's registration number is on the list"),
    (2, "Radar goods, and a party in a declaration case marked check first, or a close match to a listed number"),
    (3, "Radar goods to a radar corridor or through a country named for enhanced due diligence"),
    (4, "Everything else"),
]

#: The UK guidance's enhanced due diligence countries (radar/brief/spec/redflags.json), as codes.
EDD_ISO = {"Armenia": ["AM"], "China (including Hong Kong and Macau)": ["CN", "HK", "MO"], "India": ["IN"], "Israel": ["IL"],
           "Kazakhstan": ["KZ"], "Kyrgyzstan": ["KG"], "Malaysia": ["MY"], "Serbia": ["RS"], "Thailand": ["TH"],
           "Türkiye": ["TR"], "UAE": ["AE"], "Uzbekistan": ["UZ"], "Vietnam": ["VN"]}


def _codes() -> dict:
    with open(ROOT / "config" / "codes.csv", newline="") as f:
        return {r["code"]: {"tier": int(r["tier"]), "description": r["description"]} for r in csv.DictReader(f)}


def _corridors() -> set[str]:
    out = set()
    for name in ("countries.csv", "countries_run3.csv"):
        with open(ROOT / "config" / name, newline="") as f:
            out |= {r["iso2"] for r in csv.DictReader(f) if r["role"] == "corridor"}
    return out


def _edd() -> set[str]:
    rf = json.loads((ROOT / "radar" / "brief" / "spec" / "redflags.json").read_text(encoding="utf-8"))
    names = rf["uk_enhanced_due_diligence_countries"]["names"]
    missing = [n for n in names if n not in EDD_ISO]
    if missing:
        raise ValueError(f"no country code for {missing}")
    return {iso for n in names for iso in EDD_ISO[n]}


def one_apart(a: str, b: str) -> bool:
    """Two identifiers of the same length that differ in exactly one character."""
    return len(a) == len(b) and a != b and sum(x != y for x, y in zip(a, b)) == 1


def goods_codes(goods: dict | None, codes: dict) -> list[dict]:
    if not goods:
        return []
    if goods.get("hs_given"):
        c = goods["hs_given"]
        return [{"code": c, "how": "given in the report", "confidence": "Certain"}] if c in codes else []
    hit = PHRASES.get(goods["words"])
    if not hit:
        return []
    found, conf = hit
    return [{"code": c, "how": f"the report's words, “{goods['words']}”", "confidence": conf} for c in found]


def match_report(rep: dict, cases: list[dict], listed: list[dict], codes: dict, corridors: set[str], edd: set[str]) -> dict:
    found = goods_codes(rep.get("goods"), codes)
    for f in found:
        f["tier"] = codes[f["code"]]["tier"]
        f["description"] = codes[f["code"]]["description"]
    ids = {p["id"] for p in rep["parties"]}
    in_cases = []
    for c in cases:
        roles = [ids & set(c["parties"].get(k) or []) for k in ("exporters", "consignees", "forwarders")]
        hit = sorted(set().union(*roles))
        if hit:
            in_cases.append({"case": c["id"], "check_order": c["check_order"], "parties": hit})
    list_hits = []
    for p in rep["parties"]:
        reg = p.get("registration")
        if not reg:
            continue
        for e in listed:
            n = e["Business registration number (s)"]
            if reg == n:
                list_hits.append({"party": p["id"], "unique_id": e["Unique ID"], "strength": "same number", "registration": reg})
            elif one_apart(reg, n):
                list_hits.append({"party": p["id"], "unique_id": e["Unique ID"], "strength": "one character apart", "registration": reg,
                                  "listed_number": n})
    countries = [rep["destination"]] + list(rep.get("transit") or [])
    flags: list[str] = []
    factors = []
    for s in rep["says"]:
        _, fl, fa = STATEMENTS[s]
        flags += fl
        factors += [{"group": g, "id": f} for g, f in fa]
    if rep["channel"] == "self" and not any(f["id"] == "voluntary_disclosure" for f in factors):
        factors.append({"group": "mitigating", "id": "voluntary_disclosure"})
    if rep.get("value_band") and rep["value_band"] != "not given":
        factors.append({"group": "severity", "id": "value"})
    if found:
        flags.append("chpl-end-destination")
    if any(c in edd for c in countries) and found:
        flags.append("transit-edd-country")
    if any(h["strength"] == "same number" for h in list_hits):
        flags.append("sanctions-list-check")
    if any(h["strength"] == "one character apart" for h in list_hits):
        flags.append("listed-party-resemblance")
    flags = list(dict.fromkeys(flags))
    body, why = BODIES[rep["nexus"]]
    radar_goods = bool(found)
    corridor = rep["destination"] in corridors
    if any(h["strength"] == "same number" for h in list_hits):
        band = 1
    elif radar_goods and (any(c["check_order"] == "check first" for c in in_cases) or list_hits):
        band = 2
    elif radar_goods and (corridor or any(c in edd for c in countries)):
        band = 3
    else:
        band = 4
    routes = [f"{rep['destination']}-{f['code']}" for f in found]
    touches = bool(found or in_cases or list_hits or corridor)
    return {"codes": found, "routes": routes, "corridor": corridor, "declaration_cases": in_cases, "list": list_hits,
            "body": {"name": body, "why": why}, "factors": factors, "red_flags": flags, "order": band,
            "touches_radar": touches}


def match_all(reports: list[dict], listed: list[dict]) -> list[dict]:
    cases = json.loads((ROOT / "demo" / "radar" / "declarations" / "cases.json").read_text(encoding="utf-8"))["cases"]
    codes, corridors, edd = _codes(), _corridors(), _edd()
    return [dict(rep, matched=match_report(rep, cases, listed, codes, corridors, edd)) for rep in reports]
