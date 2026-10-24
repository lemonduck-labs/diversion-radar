"""Cases and the link graph for the radar's restricted layer.

A case groups the signals that touch the same exporter-route (an exporter and a destination)
or the same consignee, so a person reads related questions together. Parties are named by
pseudonymous id only. A case raised by two or more detectors is listed as "check first",
any other as "check". A case carries questions, the facts behind them and a link graph; it
carries no score and is never a finding.

The graph has four kinds of node (exporter, consignee, forwarder, route: a corridor and one
of the radar's codes) and is cut to each case's parties plus one hop, with at most
NEIGHBOUR_CAP neighbours kept for each party in a case.

A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

from . import scope
from .scope import CORRIDORS, code6, is_radar

NEIGHBOUR_CAP = 25
KIND_ORDER = {"exporter-route": 0, "consignee cluster": 1, "forwarder cluster": 2}
DATA_CANNOT_SHOW = ("Declarations show who sent what to whom, through whom, and when. They do not show who paid, who "
                    "ends up with the goods, where the goods go after the destination, or why [Certain].")


def _cluster(signals: list[dict]) -> list[list[dict]]:
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for s in signals:
        for k in s["keys"]:
            find(k)
        for k in s["keys"][1:]:
            a, b = find(s["keys"][0]), find(k)
            if a != b:
                parent[max(a, b)] = min(a, b)
    groups: dict[str, list[dict]] = {}
    for s in signals:
        groups.setdefault(find(s["keys"][0]), []).append(s)
    return list(groups.values())


def _focus(signals: list[dict]) -> dict:
    """The parties the case is built around: the ones in the signals' keys and units."""
    exporters, consignees, forwarders, routes = set(), set(), set(), set()
    for s in signals:
        for k in s["keys"] + [s["unit"]]:
            kind, _, rest = k.partition(":")
            parts = rest.split("|")
            if kind in ("ED", "E", "R", "P", "S"):
                exporters.add(parts[0])
            if kind == "C":
                consignees.add(parts[0])
            if kind in ("P", "S"):
                consignees.add(parts[1])
            if kind == "F":
                forwarders.add(parts[0])
            if kind == "R":
                routes.add(f"{parts[1]}-{parts[2]}")
        if s["detector"] in ("D1", "D4", "D5", "D6", "D7"):
            routes.update(s["entities"].get("routes", []))
    return {"exporters": sorted(exporters), "consignees": sorted(consignees), "forwarders": sorted(forwarders),
            "routes": sorted(routes)}


def _title(kind: str, focus: dict, countries: dict) -> str:
    if kind == "exporter-route":
        dests = sorted({countries[c] for c in focus["consignees"] if c in countries})
        names = scope.listed([scope.country_in(d) for d in dests]) if dests else "a corridor"
        lead = focus["exporters"][0] + (f" and {len(focus['exporters']) - 1} more" if len(focus["exporters"]) > 1 else "")
        return f"{lead} to {names}"
    if kind == "consignee cluster":
        c = focus["consignees"][0]
        more = f" and {len(focus['consignees']) - 1} more" if len(focus["consignees"]) > 1 else ""
        return f"{c} in {scope.country_in(countries.get(c, ''))}{more}"
    return f"{focus['forwarders'][0]}, a forwarder"


def build_cases(signals: list[dict], redflags: dict, countries: dict) -> list[dict]:
    """Group signals into cases. redflags: red-flag id -> question (radar/brief/spec/redflags.json);
    countries: consignee id -> destination."""
    order = {rid: n for n, rid in enumerate(redflags)}
    cases = []
    for sigs in _cluster(signals):
        sigs = sorted(sigs, key=lambda s: s["id"])
        dets = sorted({s["detector"] for s in sigs})
        keys = {k for s in sigs for k in s["keys"]}
        kind = ("exporter-route" if any(k.startswith("ED:") for k in keys)
                else "consignee cluster" if any(k.startswith("C:") for k in keys) else "forwarder cluster")
        focus = _focus(sigs)
        parties = {k: sorted(set().union(*[set(s["entities"].get(k, [])) for s in sigs]) | set(focus[k]))
                   for k in ("exporters", "consignees", "forwarders", "routes")}
        then = sorted({rf for s in sigs for rf in s["then_check"]} - {rf for s in sigs for rf in s["implements"]},
                      key=lambda rf: order.get(rf, 999))
        questions = [{"from": s["id"], "detector": s["detector"], "question": s["question"], "basis": s["basis"],
                      "red_flags": s["implements"]} for s in sigs]
        questions += [{"from": "red-flag list", "red_flag": rf, "question": redflags[rf]} for rf in then]
        cases.append({
            "kind": kind, "title": _title(kind, focus, countries),
            "check_order": "check first" if len(dets) >= 2 else "check", "detectors": dets,
            "focus": focus, "parties": parties, "signals": [s["id"] for s in sigs], "questions": questions,
        })
    cases.sort(key=lambda c: (c["check_order"] != "check first", -len(c["detectors"]), KIND_ORDER[c["kind"]],
                              c["signals"][0]))
    for n, c in enumerate(cases, start=1):
        c["id"] = f"SYN-CASE-{n:03d}"
    return [{"id": c.pop("id"), **c} for c in cases]


def _route(r: dict) -> str | None:
    if r["destination"] in CORRIDORS and is_radar(r["commodity_code"]):
        return f"{r['destination']}-{code6(r['commodity_code'])}"
    return None


def build_graph(records: list[dict], cases: list[dict], flagged_routes: dict, window: tuple) -> dict:
    """Nodes and edges for each case's parties plus one hop, aggregated over the whole period."""
    edges: dict[tuple, dict] = {}
    countries: dict[str, str] = {}

    def add(kind, a, b, r, value=True):
        e = edges.setdefault((kind, a, b), {"items": 0, "value_gbp": 0, "value_window_gbp": 0,
                                            "first": r["acceptance_date"], "last": r["acceptance_date"]})
        e["items"] += 1
        if value:
            e["value_gbp"] += r["statistical_value_gbp"]
            if window[0] <= r["acceptance_date"] <= window[1]:
                e["value_window_gbp"] += r["statistical_value_gbp"]
        e["first"] = min(e["first"], r["acceptance_date"])
        e["last"] = max(e["last"], r["acceptance_date"])

    for r in records:
        exp, con, fwd = f"E:{r['exporter_id']}", f"C:{r['consignee_id']}", r["forwarder_id"]
        countries[r["consignee_id"]] = r["destination"]
        add("shipped_to", exp, con, r)
        if fwd:
            add("used_forwarder", exp, f"F:{fwd}", r, value=False)
            add("carried_to", f"F:{fwd}", con, r, value=False)
        route = _route(r)
        if route:
            add("on_route", exp, f"R:{route}", r)
            add("on_route", con, f"R:{route}", r)

    neighbours: dict[str, list[tuple]] = {}
    for (kind, a, b), e in edges.items():
        w = e["value_gbp"] or e["items"]
        neighbours.setdefault(a, []).append((w, b))
        neighbours.setdefault(b, []).append((w, a))

    case_nodes, selected = {}, set()
    for c in cases:
        f = c["focus"]
        focus = ([f"E:{x}" for x in f["exporters"]] + [f"C:{x}" for x in f["consignees"]]
                 + [f"F:{x}" for x in f["forwarders"]] + [f"R:{x}" for x in f["routes"]])
        nodes = set(focus)
        for n in focus:
            ranked = sorted(neighbours.get(n, []), key=lambda t: (-t[0], t[1]))
            nodes.update(b for _, b in ranked[:NEIGHBOUR_CAP])
        case_nodes[c["id"]] = {"focus": sorted(focus), "nodes": sorted(nodes),
                               "neighbours_cut": sorted(n for n in focus if len(neighbours.get(n, [])) > NEIGHBOUR_CAP)}
        selected |= nodes

    def node(n: str) -> dict:
        kind, _, rest = n.partition(":")
        if kind == "E":
            return {"id": n, "type": "exporter"}
        if kind == "C":
            return {"id": n, "type": "consignee", "country": countries.get(rest)}
        if kind == "F":
            return {"id": n, "type": "forwarder"}
        cc, c6 = rest.split("-")
        return {"id": n, "type": "route", "country": cc, "code": c6,
                "public_status": flagged_routes.get((cc, c6), "not shown")}

    out_edges = []
    for (kind, a, b) in sorted(edges):
        if a in selected and b in selected:
            e = edges[(kind, a, b)]
            row = {"source": a, "target": b, "type": kind, "items": e["items"], "first": e["first"], "last": e["last"]}
            if kind in ("shipped_to", "on_route"):
                row["value_gbp"] = e["value_gbp"]
                row["value_window_gbp"] = e["value_window_gbp"]
            out_edges.append(row)
    return {"nodes": [node(n) for n in sorted(selected)], "edges": out_edges, "cases": case_nodes}
