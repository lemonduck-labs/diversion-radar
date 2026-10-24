"""Detectors for the radar's restricted layer: one per pattern, each citing the red flags in
radar/brief/spec/redflags.json that it implements. What a detector puts out is a signal: a
question for a person to check, with the facts from the declarations that raised it. A
signal is never a finding; most will have an ordinary explanation.

"implements" lists the red flags whose indicator the detector tests in the declaration data.
"then_check" lists the red flags a person checks next, which declarations cannot answer.
The thresholds are ours, set on synthetic data [Guessing]; a deployment would set them with
the customer on its own data.

A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import median

from . import scope
from .scope import CORRIDORS, NEIGHBOURS, code6, is_radar

CHPL = "the Common High Priority Items List"

DETECTORS = [
    {"id": "D1", "name": "new-corridor-consignee", "pattern": "G1",
     "title": "New consignee in a corridor buying the radar's goods",
     "implements": ["new-chpl-trader", "transit-edd-country"],
     "then_check": ["chpl-end-destination", "new-customer-dual-use", "sanctions-list-check", "web-presence",
                    "end-user-certificate"],
     "mapping": "new-chpl-trader [Likely]: the declarations show a consignee new to receiving these goods from "
                "UK exporters, not new to importing them from anywhere. transit-edd-country [Certain] where the "
                "destination is one the UK guidance names; Georgia, Azerbaijan and Tajikistan are not named, so for "
                "them the detector cites only new-chpl-trader.",
     "unit": "consignee",
     "thresholds": {"window": list(scope.WINDOW), "min_value_gbp": 50000},
     "question": "Is {consignee} in {country} new to buying goods on " + CHPL + ", and what checks show that "
                 "their end destination is not Russia?",
     "basis": "First seen in a UK export declaration on {first_seen}. In the last 12 months: {value} of the radar's "
              "goods in {shipments} shipments from {exporters}."},
    {"id": "D2", "name": "route-volume-jump", "pattern": "G2",
     "title": "An exporter's exports jumping on a route the public radar shows",
     "implements": ["order-volume-rise"],
     "then_check": ["chpl-end-destination", "end-use-details", "line-of-business", "destination-clear"],
     "mapping": "order-volume-rise [Likely]: the guidance speaks of an existing customer's orders; the detector sees "
                "one exporter's declared exports on one route and names the consignees behind the rise.",
     "unit": "exporter-route",
     "thresholds": {"window": list(scope.WINDOW), "prior": list(scope.PRIOR), "min_ratio": 3.0,
                    "min_increase_gbp": 100000, "min_prior_gbp": 10000,
                    "routes": "routes the public radar shows as a lead or a watch item"},
     "question": "Have {exporter}'s exports of {code} ({code_desc}) to {country} risen beyond their usual pattern, "
                 "and is there a business reason for the rise?",
     "basis": "{value_w} in the last 12 months against {value_p} in the 12 before ({ratio} times), on a route the "
              "public radar shows as {status}. {consignees} behind the rise, {new} of them first seen in the last "
              "12 months."},
    {"id": "D3", "name": "shared-party", "pattern": "G3",
     "title": "A consignee or forwarder shared by unrelated exporters",
     "implements": ["consignee-uses-goods", "shared-address"],
     "then_check": ["forwarder-as-destination", "web-presence", "line-of-business", "route-complex"],
     "mapping": "consignee-uses-goods [Likely]: a consignee supplied by many unrelated exporters may be a forwarder "
                "or logistics firm rather than a user of the goods. shared-address [Guessing]: the guidance's "
                "indicator is an address shared by many businesses; the declarations' nearest parallel is one party "
                "shared by many exporters. A deployment holding the consignee's name and address (DE 3/9) could "
                "test the address itself; the synthetic records hold no addresses.",
     "unit": "consignee or forwarder",
     "thresholds": {"period": list(scope.SHARED_PERIOD), "min_exporter_groups": 4, "min_consignee_shipments": 6,
                    "min_forwarder_share": 0.4, "min_forwarder_items": 10},
     "question": "Is {party} in {country} a business that would use these goods, rather than a forwarder or "
                 "logistics firm, and why do exporters in {groups} different ownership groups send it goods on "
                 + CHPL + "?",
     "question_forwarder": "Why do exporters in {groups} different ownership groups send goods on " + CHPL + " to "
                           "{countries} through {party}, and is a forwarder named as the final destination on "
                           "any of these shipments?",
     "basis": "In the last 24 months: {shipments} shipments of the radar's goods from {exporters} in {groups} "
              "ownership groups. First seen in a UK export declaration on {first_seen}.",
     "basis_forwarder": "In the last 24 months: {items} goods items of the radar's goods to corridor countries "
                        "through {party}, {share} of everything declared with it, from {exporters} in {groups} "
                        "ownership groups. First declared on {first_seen}."},
    {"id": "D4", "name": "unit-value", "pattern": "G4",
     "title": "Declared values per kilogram far out of line for the code",
     "implements": ["price-and-invoices", "hs-code-check"],
     "then_check": ["end-use-details", "line-of-business"],
     "mapping": "price-and-invoices [Likely]: a value per kilogram far above the code's norm is one way a price well "
                "above the market shows in declarations. hs-code-check [Likely]: a value per kilogram far from the "
                "norm can mean the goods are not what the code describes.",
     "unit": "exporter, consignee and code",
     "thresholds": {"min_code_items": 30, "robust_z": 3.5, "min_outlier_items": 3,
                    "scope": "corridor destinations; the norm for each code is taken over every destination"},
     "question": "Why is the declared value per kilogram of {code} ({code_desc}) from {exporter} to {consignee} in "
                 "{country} {factor} the usual for the code, and are the goods recorded under the correct code and "
                 "at the market price?",
     "basis": "{outliers} of {items} goods items are more than 3.5 robust deviations from the code's median of "
              "{norm} per kg; this pair's median is {pair} per kg."},
    {"id": "D5", "name": "code-switch", "pattern": "G5",
     "title": "A code switching to a neighbouring code outside the radar's nine",
     "implements": ["hs-code-check"],
     "then_check": ["line-of-business", "end-use-details", "chpl-end-destination"],
     "mapping": "hs-code-check [Likely]: the guidance lists goods recorded under a code that is not subject to "
                "controls; the detector sees the same flow move to a neighbouring code at a similar value per "
                "kilogram. Whether the neighbouring code is controlled is not modelled.",
     "unit": "exporter and consignee",
     "thresholds": {"min_items_each_code": 3, "max_overlap_days": 92, "value_per_kg_ratio": [0.5, 2.0]},
     "question": "Why did {exporter}'s shipments to {consignee} in {country} move from {code_a} to {code_b} at a "
                 "similar value per kilogram, and are the goods recorded under the correct code on every document?",
     "basis": "{n_a} goods items under {code_a} ({desc_a}) up to {last_a}; {n_b} under {code_b} ({desc_b}) from "
              "{first_b}. Median value per kg {uv_a}, then {uv_b}."},
    {"id": "D6", "name": "russia-switch", "pattern": "G6",
     "title": "Exports to Russia stopping after 24 February 2022 and moving to a corridor",
     "implements": ["chpl-orders-since-2022", "transit-edd-country"],
     "then_check": ["transport-changed", "russia-ties", "chpl-end-destination", "end-user-certificate"],
     "mapping": "chpl-orders-since-2022 [Likely]: the indicator is a customer that started receiving these goods only "
                "after 24 February 2022; the detector tests that for the consignees that took the place of the "
                "exporter's Russia trade. transit-edd-country [Certain] where a destination is one the UK guidance "
                "names.",
     "unit": "exporter",
     "thresholds": {"before": list(scope.BEFORE_INVASION), "after": list(scope.AFTER_INVASION),
                    "min_russia_value_gbp": 100000, "min_replaced_share": 0.5},
     "question": "Did {exporter}'s customers in {countries} start receiving these goods only after 24 February 2022, "
                 "when its exports of them to Russia stopped, and has the way the goods are shipped changed?",
     "basis": "{ru_value} of the radar's goods to Russia from January 2021 to 23 February 2022; {corr_value} in the "
              "two years from March 2022 to {consignees} in {countries} first seen after 24 February 2022. Codes in "
              "common: {codes}."},
    {"id": "D7", "name": "small-frequent", "pattern": "G7",
     "title": "Small, frequent shipments to one consignee",
     "implements": ["small-frequent-shipments"],
     "then_check": ["price-and-invoices", "consignee-uses-goods", "delivery-vague"],
     "mapping": "small-frequent-shipments [Certain]: the indicator names small, frequent shipments to a central "
                "location; what counts as small and frequent is ours [Guessing].",
     "unit": "consignee",
     "thresholds": {"window": list(scope.WINDOW), "min_shipments": 20, "max_median_value_gbp": 2000,
                    "max_median_net_mass_kg": 2.0},
     "question": "Are the goods going to {consignee} in {country} in small, frequent shipments to one central "
                 "location, and are orders or invoices being split to stay under a limit?",
     "basis": "{shipments} shipments of the radar's goods in the last 12 months, median {value} and {mass} kg, "
              "from {exporters}."},
]
BY_ID = {d["id"]: d for d in DETECTORS}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


@dataclass
class Context:
    """What the detectors need besides the records."""
    groups: dict = field(default_factory=dict)  # exporter id -> ownership group id
    flagged_routes: dict = field(default_factory=lambda: dict(scope.FLAGGED_ROUTES))
    window: tuple = scope.WINDOW
    prior: tuple = scope.PRIOR
    shared_period: tuple = scope.SHARED_PERIOD
    before: tuple = scope.BEFORE_INVASION
    after: tuple = scope.AFTER_INVASION

    def group(self, exporter: str) -> str:
        return self.groups.get(exporter, exporter)


def gbp(v: float) -> str:
    return f"£{round(v):,}"


def day(s: str) -> str:
    d = date.fromisoformat(s)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def count(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _in(s: str, period: tuple) -> bool:
    return period[0] <= s <= period[1]


def _edd(countries) -> bool:
    return any(c in scope.EDD_COUNTRIES for c in countries)


def _signal(det: str, unit: str, keys: list, entities: dict, question: str, basis: str, facts: dict,
            implements: list | None = None) -> dict:
    d = BY_ID[det]
    return {"detector": det, "name": d["name"], "unit": unit, "keys": keys,
            "entities": {k: sorted(set(v)) for k, v in entities.items()}, "question": question, "basis": basis,
            "facts": facts, "implements": implements if implements is not None else list(d["implements"]),
            "then_check": list(d["then_check"])}


def _decls(records) -> dict:
    """Declarations: ref -> {date, exporter, consignee, destination, forwarder, items}."""
    out = {}
    for r in records:
        d = out.get(r["declaration_ref"])
        if d is None:
            d = out[r["declaration_ref"]] = {"ref": r["declaration_ref"], "date": r["acceptance_date"],
                                             "exporter": r["exporter_id"], "consignee": r["consignee_id"],
                                             "destination": r["destination"], "forwarder": r["forwarder_id"],
                                             "items": []}
        d["items"].append(r)
    return out


def _first_seen(records, radar_only: bool = False) -> dict:
    first = {}
    for r in records:
        if radar_only and not is_radar(r["commodity_code"]):
            continue
        c, s = r["consignee_id"], r["acceptance_date"]
        if c not in first or s < first[c]:
            first[c] = s
    return first


# -- D1 ---------------------------------------------------------------------------------------

def d1_new_corridor_consignee(records, ctx: Context) -> list[dict]:
    t = BY_ID["D1"]["thresholds"]
    first = _first_seen(records)
    agg = {}
    for r in records:
        if r["destination"] in CORRIDORS and is_radar(r["commodity_code"]) and _in(r["acceptance_date"], ctx.window):
            a = agg.setdefault(r["consignee_id"], {"value": 0, "decls": set(), "exporters": set(), "codes": set(),
                                                   "forwarders": set(), "country": r["destination"]})
            a["value"] += r["statistical_value_gbp"]
            a["decls"].add(r["declaration_ref"])
            a["exporters"].add(r["exporter_id"])
            a["codes"].add(code6(r["commodity_code"]))
            if r["forwarder_id"]:
                a["forwarders"].add(r["forwarder_id"])
    out = []
    for c in sorted(agg):
        a = agg[c]
        if first[c] < ctx.window[0] or a["value"] < t["min_value_gbp"]:
            continue
        cc = a["country"]
        implements = ["new-chpl-trader"] + (["transit-edd-country"] if _edd([cc]) else [])
        facts = {"first_seen": first[c], "value_gbp": a["value"], "shipments": len(a["decls"]),
                 "exporters": sorted(a["exporters"]), "codes": sorted(a["codes"]), "country": cc}
        out.append(_signal(
            "D1", f"C:{c}", [f"C:{c}"],
            {"consignees": [c], "exporters": a["exporters"], "forwarders": a["forwarders"],
             "routes": [f"{cc}-{x}" for x in a["codes"]]},
            BY_ID["D1"]["question"].format(consignee=c, country=scope.country_in(cc)),
            BY_ID["D1"]["basis"].format(first_seen=day(first[c]), value=gbp(a["value"]), shipments=len(a["decls"]),
                                        exporters=count(len(a["exporters"]), "exporter")),
            facts, implements))
    return out


# -- D2 ---------------------------------------------------------------------------------------

def d2_route_volume_jump(records, ctx: Context) -> list[dict]:
    t = BY_ID["D2"]["thresholds"]
    first = _first_seen(records)
    agg = {}
    for r in records:
        key = (r["destination"], code6(r["commodity_code"]))
        if key not in ctx.flagged_routes or not is_radar(r["commodity_code"]):
            continue
        s = r["acceptance_date"]
        side = "w" if _in(s, ctx.window) else "p" if _in(s, ctx.prior) else None
        if side is None:
            continue
        a = agg.setdefault((r["exporter_id"],) + key, {"w": 0, "p": 0, "cons": {}, "forwarders": set()})
        a[side] += r["statistical_value_gbp"]
        c = a["cons"].setdefault(r["consignee_id"], {"w": 0, "p": 0})
        c[side] += r["statistical_value_gbp"]
        if r["forwarder_id"]:
            a["forwarders"].add(r["forwarder_id"])
    out = []
    for key in sorted(agg):
        a = agg[key]
        if a["p"] < t["min_prior_gbp"] or a["w"] < t["min_ratio"] * a["p"] or a["w"] - a["p"] < t["min_increase_gbp"]:
            continue
        exp, cc, c6 = key
        rising = sorted(((v["w"] - v["p"], c) for c, v in a["cons"].items() if v["w"] > v["p"]), reverse=True)
        top = [c for _, c in rising[:3]]
        new = [c for c in top if first[c] >= ctx.window[0]]
        status = ctx.flagged_routes[(cc, c6)]
        facts = {"value_window_gbp": a["w"], "value_prior_gbp": a["p"], "ratio": round(a["w"] / a["p"], 1),
                 "public_status": status, "rising_consignees": top, "new_consignees": new}
        out.append(_signal(
            "D2", f"R:{exp}|{cc}|{c6}", [f"ED:{exp}|{cc}"] + [f"C:{c}" for c in top],
            {"exporters": [exp], "consignees": top, "forwarders": a["forwarders"], "routes": [f"{cc}-{c6}"]},
            BY_ID["D2"]["question"].format(exporter=exp, code=c6, code_desc=scope.RADAR_CODES[c6].lower(),
                                           country=scope.country_in(cc)),
            BY_ID["D2"]["basis"].format(value_w=gbp(a["w"]), value_p=gbp(a["p"]), ratio=f"{a['w'] / a['p']:.1f}",
                                        status="a lead" if status == "lead" else "a watch item",
                                        consignees=count(len(top), "consignee"), new=len(new)),
            facts))
    return out


# -- D3 ---------------------------------------------------------------------------------------

def d3_shared_party(records, ctx: Context) -> list[dict]:
    t = BY_ID["D3"]["thresholds"]
    cons, fwds = {}, {}
    first_c = _first_seen(records)
    first_f = {}
    for r in records:
        f = r["forwarder_id"]
        if f and (f not in first_f or r["acceptance_date"] < first_f[f]):
            first_f[f] = r["acceptance_date"]
        if not _in(r["acceptance_date"], ctx.shared_period):
            continue
        hit = r["destination"] in CORRIDORS and is_radar(r["commodity_code"])
        if r["forwarder_id"]:
            f = fwds.setdefault(r["forwarder_id"], {"all": 0, "hit": 0, "exporters": set(), "countries": set(),
                                                    "consignees": set()})
            f["all"] += 1
            if hit:
                f["hit"] += 1
                f["exporters"].add(r["exporter_id"])
                f["countries"].add(r["destination"])
                f["consignees"].add(r["consignee_id"])
        if hit:
            c = cons.setdefault(r["consignee_id"], {"decls": set(), "exporters": set(),
                                                    "country": r["destination"], "forwarders": set(), "codes": set()})
            c["decls"].add(r["declaration_ref"])
            c["exporters"].add(r["exporter_id"])
            c["codes"].add(code6(r["commodity_code"]))
            if r["forwarder_id"]:
                c["forwarders"].add(r["forwarder_id"])
    out = []
    for cid in sorted(cons):
        c = cons[cid]
        groups = {ctx.group(e) for e in c["exporters"]}
        if len(groups) < t["min_exporter_groups"] or len(c["decls"]) < t["min_consignee_shipments"]:
            continue
        facts = {"shipments": len(c["decls"]), "exporters": sorted(c["exporters"]), "groups": len(groups),
                 "first_seen": first_c[cid], "country": c["country"], "party_type": "consignee"}
        out.append(_signal(
            "D3", f"C:{cid}", [f"C:{cid}"],
            {"consignees": [cid], "exporters": c["exporters"], "forwarders": c["forwarders"],
             "routes": [f"{c['country']}-{x}" for x in c["codes"]]},
            BY_ID["D3"]["question"].format(party=cid, country=scope.country_in(c["country"]), groups=len(groups)),
            BY_ID["D3"]["basis"].format(shipments=len(c["decls"]), exporters=count(len(c["exporters"]), "exporter"),
                                        groups=len(groups), first_seen=day(first_c[cid])),
            facts, ["consignee-uses-goods", "shared-address"]))
    for fid in sorted(fwds):
        f = fwds[fid]
        groups = {ctx.group(e) for e in f["exporters"]}
        share = f["hit"] / f["all"] if f["all"] else 0.0
        if (len(groups) < t["min_exporter_groups"] or share < t["min_forwarder_share"]
                or f["hit"] < t["min_forwarder_items"]):
            continue
        countries = sorted(f["countries"])
        facts = {"items": f["hit"], "items_all": f["all"], "share": round(share, 3), "exporters": sorted(f["exporters"]),
                 "groups": len(groups), "countries": countries, "first_seen": first_f[fid], "party_type": "forwarder"}
        listed = scope.listed([scope.country_in(c) for c in countries])
        out.append(_signal(
            "D3", f"F:{fid}", [f"F:{fid}"],
            {"forwarders": [fid], "exporters": f["exporters"], "consignees": f["consignees"], "routes": []},
            BY_ID["D3"]["question_forwarder"].format(party=fid, countries=listed, groups=len(groups)),
            BY_ID["D3"]["basis_forwarder"].format(items=f["hit"], party=fid, share=f"{share:.0%}",
                                                  exporters=count(len(f["exporters"]), "exporter"), groups=len(groups),
                                                  first_seen=day(first_f[fid])),
            facts, ["shared-address"]))
    return out


# -- D4 ---------------------------------------------------------------------------------------

def code_norms(records, min_items: int) -> dict:
    """For each eight-digit code with enough items: the median and the robust scale (1.4826 times the
    median absolute deviation) of log value per kilogram, over every destination."""
    logs = {}
    for r in records:
        if r["net_mass_kg"] > 0 and r["statistical_value_gbp"] > 0:
            logs.setdefault(r["commodity_code"], []).append(math.log(r["statistical_value_gbp"] / r["net_mass_kg"]))
    norms = {}
    for code in sorted(logs):
        xs = logs[code]
        if len(xs) < min_items:
            continue
        m = median(xs)
        scale = 1.4826 * median(abs(x - m) for x in xs)
        if scale > 0:
            norms[code] = (m, scale, len(xs))
    return norms


def d4_unit_value(records, ctx: Context) -> list[dict]:
    t = BY_ID["D4"]["thresholds"]
    norms = code_norms(records, t["min_code_items"])
    pairs = {}
    for r in records:
        code = r["commodity_code"]
        if r["destination"] not in CORRIDORS or code not in norms or r["net_mass_kg"] <= 0:
            continue
        if not (is_radar(code) or code in NEIGHBOURS.values()):
            continue
        m, scale, _ = norms[code]
        x = math.log(r["statistical_value_gbp"] / r["net_mass_kg"])
        p = pairs.setdefault((r["exporter_id"], r["consignee_id"], code), {"xs": [], "z": [], "country": r["destination"],
                                                                          "forwarders": set()})
        p["xs"].append(x)
        p["z"].append((x - m) / scale)
        if r["forwarder_id"]:
            p["forwarders"].add(r["forwarder_id"])
    out = []
    for key in sorted(pairs):
        p = pairs[key]
        outliers = [z for z in p["z"] if abs(z) > t["robust_z"]]
        if len(outliers) < t["min_outlier_items"]:
            continue
        exp, con, code = key
        m = norms[code][0]
        pair_uv = math.exp(median(p["xs"]))
        ratio = math.exp(median([x for x, z in zip(p["xs"], p["z"]) if abs(z) > t["robust_z"]]) - m)
        factor = f"about {ratio:.0f} times" if ratio >= 1 else f"about {ratio:.0%} of"
        facts = {"items": len(p["z"]), "outliers": len(outliers), "code_median_gbp_per_kg": round(math.exp(m), 2),
                 "pair_median_gbp_per_kg": round(pair_uv, 2), "outlier_ratio": round(ratio, 2),
                 "direction": "above" if ratio >= 1 else "below", "country": p["country"]}
        out.append(_signal(
            "D4", f"P:{exp}|{con}|{code}", [f"ED:{exp}|{p['country']}", f"C:{con}"],
            {"exporters": [exp], "consignees": [con], "forwarders": p["forwarders"],
             "routes": [f"{p['country']}-{code6(code)}"] if is_radar(code) else []},
            BY_ID["D4"]["question"].format(code=code, code_desc=scope.GOODS[code].lower(), exporter=exp, consignee=con,
                                           country=scope.country_in(p["country"]), factor=factor),
            BY_ID["D4"]["basis"].format(outliers=len(outliers), items=len(p["z"]), norm=gbp(math.exp(m)),
                                        pair=gbp(pair_uv)),
            facts))
    return out


# -- D5 ---------------------------------------------------------------------------------------

def d5_code_switch(records, ctx: Context) -> list[dict]:
    t = BY_ID["D5"]["thresholds"]
    pairs = {}
    for r in records:
        if r["destination"] not in CORRIDORS or r["net_mass_kg"] <= 0:
            continue
        p = pairs.setdefault((r["exporter_id"], r["consignee_id"]), {"codes": {}, "country": r["destination"],
                                                                     "forwarders": set()})
        p["codes"].setdefault(r["commodity_code"], []).append(
            (r["acceptance_date"], r["statistical_value_gbp"] / r["net_mass_kg"]))
        if r["forwarder_id"]:
            p["forwarders"].add(r["forwarder_id"])
    lo, hi = t["value_per_kg_ratio"]
    out = []
    for key in sorted(pairs):
        p = pairs[key]
        for a in sorted(p["codes"]):
            b = NEIGHBOURS.get(a)
            if b is None or b not in p["codes"]:
                continue
            xa, xb = sorted(p["codes"][a]), sorted(p["codes"][b])
            if len(xa) < t["min_items_each_code"] or len(xb) < t["min_items_each_code"]:
                continue
            first_b, last_a = date.fromisoformat(xb[0][0]), date.fromisoformat(xa[-1][0])
            if xa[0][0] >= xb[0][0] or last_a > first_b + timedelta(days=t["max_overlap_days"]):
                continue
            uva, uvb = median(v for _, v in xa), median(v for _, v in xb)
            if not lo <= uvb / uva <= hi:
                continue
            exp, con = key
            facts = {"code_a": a, "code_b": b, "items_a": len(xa), "items_b": len(xb), "last_a": xa[-1][0],
                     "first_b": xb[0][0], "median_gbp_per_kg_a": round(uva, 2), "median_gbp_per_kg_b": round(uvb, 2),
                     "country": p["country"]}
            out.append(_signal(
                "D5", f"S:{exp}|{con}|{a}|{b}", [f"ED:{exp}|{p['country']}", f"C:{con}"],
                {"exporters": [exp], "consignees": [con], "forwarders": p["forwarders"],
                 "routes": [f"{p['country']}-{code6(a)}"]},
                BY_ID["D5"]["question"].format(exporter=exp, consignee=con, country=scope.country_in(p["country"]),
                                               code_a=a, code_b=b),
                BY_ID["D5"]["basis"].format(n_a=len(xa), code_a=a, desc_a=scope.GOODS[a].lower(), last_a=day(xa[-1][0]),
                                            n_b=len(xb), code_b=b, desc_b=scope.GOODS[b].lower(), first_b=day(xb[0][0]),
                                            uv_a=gbp(uva), uv_b=gbp(uvb)),
                facts))
    return out


# -- D6 ---------------------------------------------------------------------------------------

def d6_russia_switch(records, ctx: Context) -> list[dict]:
    t = BY_ID["D6"]["thresholds"]
    first_radar = _first_seen(records, radar_only=True)
    invasion = scope.INVASION.isoformat()
    ru, corr = {}, {}
    for r in records:
        if not is_radar(r["commodity_code"]):
            continue
        s, e = r["acceptance_date"], r["exporter_id"]
        if r["destination"] == "RU" and _in(s, ctx.before):
            a = ru.setdefault(e, {"value": 0, "codes": set()})
            a["value"] += r["statistical_value_gbp"]
            a["codes"].add(code6(r["commodity_code"]))
        elif (r["destination"] in CORRIDORS and _in(s, ctx.after) and first_radar[r["consignee_id"]] >= invasion):
            a = corr.setdefault(e, {"value": 0, "codes": set(), "consignees": set(), "countries": set(),
                                    "forwarders": set()})
            a["value"] += r["statistical_value_gbp"]
            a["codes"].add(code6(r["commodity_code"]))
            a["consignees"].add(r["consignee_id"])
            a["countries"].add(r["destination"])
            if r["forwarder_id"]:
                a["forwarders"].add(r["forwarder_id"])
    years_before = ((date.fromisoformat(ctx.before[1]) - date.fromisoformat(ctx.before[0])).days + 1) / 365.25
    years_after = ((date.fromisoformat(ctx.after[1]) - date.fromisoformat(ctx.after[0])).days + 1) / 365.25
    out = []
    for e in sorted(ru):
        a, c = ru[e], corr.get(e)
        if a["value"] < t["min_russia_value_gbp"] or c is None:
            continue
        common = sorted(a["codes"] & c["codes"])
        if not common or c["value"] / years_after < t["min_replaced_share"] * a["value"] / years_before:
            continue
        countries = sorted(c["countries"])
        listed = scope.listed([scope.country_in(x) for x in countries])
        implements = ["chpl-orders-since-2022"] + (["transit-edd-country"] if _edd(countries) else [])
        facts = {"russia_value_gbp": a["value"], "corridor_value_gbp": c["value"],
                 "replaced_share": round((c["value"] / years_after) / (a["value"] / years_before), 2),
                 "new_consignees": sorted(c["consignees"]), "countries": countries, "codes_in_common": common}
        out.append(_signal(
            "D6", f"E:{e}", [f"ED:{e}|{x}" for x in countries] + [f"C:{x}" for x in sorted(c["consignees"])],
            {"exporters": [e], "consignees": c["consignees"], "forwarders": c["forwarders"],
             "routes": [f"{x}-{k}" for x in countries for k in common]},
            BY_ID["D6"]["question"].format(exporter=e, countries=listed),
            BY_ID["D6"]["basis"].format(ru_value=gbp(a["value"]), corr_value=gbp(c["value"]), countries=listed,
                                        consignees=count(len(c["consignees"]), "consignee"), codes=", ".join(common)),
            facts, implements))
    return out


# -- D7 ---------------------------------------------------------------------------------------

def d7_small_frequent(records, ctx: Context) -> list[dict]:
    t = BY_ID["D7"]["thresholds"]
    per = {}
    for d in _decls(records).values():
        if d["destination"] not in CORRIDORS or not _in(d["date"], ctx.window):
            continue
        items = [i for i in d["items"] if is_radar(i["commodity_code"])]
        if not items:
            continue
        p = per.setdefault(d["consignee"], {"values": [], "masses": [], "exporters": set(), "country": d["destination"],
                                            "forwarders": set(), "codes": set()})
        p["values"].append(sum(i["statistical_value_gbp"] for i in items))
        p["masses"].append(sum(i["net_mass_kg"] for i in items))
        p["exporters"].add(d["exporter"])
        p["codes"].update(code6(i["commodity_code"]) for i in items)
        if d["forwarder"]:
            p["forwarders"].add(d["forwarder"])
    out = []
    for c in sorted(per):
        p = per[c]
        n, mv, mm = len(p["values"]), median(p["values"]), median(p["masses"])
        if n < t["min_shipments"] or mv >= t["max_median_value_gbp"] or mm >= t["max_median_net_mass_kg"]:
            continue
        facts = {"shipments": n, "median_value_gbp": round(mv), "median_net_mass_kg": round(mm, 1),
                 "exporters": sorted(p["exporters"]), "country": p["country"]}
        out.append(_signal(
            "D7", f"C:{c}", [f"C:{c}"],
            {"consignees": [c], "exporters": p["exporters"], "forwarders": p["forwarders"],
             "routes": [f"{p['country']}-{x}" for x in p["codes"]]},
            BY_ID["D7"]["question"].format(consignee=c, country=scope.country_in(p["country"])),
            BY_ID["D7"]["basis"].format(shipments=n, value=gbp(mv), mass=f"{mm:.1f}",
                                        exporters=count(len(p["exporters"]), "exporter")),
            facts))
    return out


RUNNERS = {"D1": d1_new_corridor_consignee, "D2": d2_route_volume_jump, "D3": d3_shared_party,
           "D4": d4_unit_value, "D5": d5_code_switch, "D6": d6_russia_switch, "D7": d7_small_frequent}


def run_all(records, ctx: Context) -> list[dict]:
    """Every detector over the records, with signal ids SIG-0001 upwards in detector order."""
    out = []
    for det in sorted(RUNNERS):
        out.extend(RUNNERS[det](records, ctx))
    for n, s in enumerate(out, start=1):
        s["id"] = f"SIG-{n:04d}"
    return [{"id": s.pop("id"), **s} for s in out]
