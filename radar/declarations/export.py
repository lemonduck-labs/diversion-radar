"""The data files for the workspace page, built from one seed: declarations in a compact
columnar form, entities, the link graph, cases, the detectors' specification, the
evaluation, the ground truth and the record schema. Every file carries the synthetic notice.

build() returns {file name: text}; scripts/build_declarations.py writes them to
demo/radar/declarations/ and checks they are up to date.

A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

from . import scope
from .cases import DATA_CANNOT_SHOW, NEIGHBOUR_CAP, build_cases, build_graph
from .evaluate import LABEL, evaluate
from .generate import LOOKALIKES, PATTERNS, SEED, generate
from .schema import FIELDS, HOUSE_LINE, NOTICE, RECORD_TYPE, SCHEMA_ID, SOURCES, field_docs, json_schema
from .signals import DETECTORS, Context, run_all
from .scope import CORRIDORS, is_radar

ROOT = Path(__file__).resolve().parents[2]
REDFLAGS = ROOT / "radar" / "brief" / "spec" / "redflags.json"
FORMAT = "radar-declaration-columns/1"
BASE_DATE = "2021-01-01"
CONSTANTS = {"record_type": RECORD_TYPE, "synthetic": True, "declaration_type": "EX", "additional_declaration_type": "A"}
DICT_COLUMNS = ("procedure_code", "exporter_id", "consignee_id", "representative_id", "representative_status",
                "forwarder_id", "destination", "commodity_code")
INT_COLUMNS = ("goods_item", "statistical_value_gbp", "mode_border", "mode_inland")
FILE_NAMES = ("declarations.json", "declarations.schema.json", "entities.json", "graph.json", "cases.json",
              "signals_spec.json", "evaluation.json", "ground_truth.json")

ABOUT_FORMAT = (
    "Columns of equal length, one value per goods item, in order of acceptance date. To rebuild record i: "
    "constants hold the fields that are the same on every record; a dict column's value is an index into "
    "dictionaries[column]; an int column's value is the value; net_mass_kg is in tenths of a kilogram; "
    "supplementary_units holds the count or null; acceptance_date holds the days since the previous record "
    "(the first counts from base_date); declaration_ref counts up by one at every record whose goods_item is 1, "
    "written as prefix plus a six-digit number; routing is an index into dictionaries.routing; description is "
    "descriptions[commodity_code]; documents holds 0 for none or [code index, reference number, status index] "
    "into documents.codes and documents.statuses, the reference written as SYN-DOC- plus six digits.")


def redflag_questions() -> dict:
    return {i["id"]: i["question"] for i in json.loads(REDFLAGS.read_text(encoding="utf-8"))["items"]}


# -- columns ----------------------------------------------------------------------------------

def encode(records: list[dict]) -> dict:
    dicts = {c: [] for c in DICT_COLUMNS}
    index = {c: {} for c in DICT_COLUMNS}
    routes, route_index = [], {}
    doc_codes, doc_status = ["SYN1", "SYN2", "SYN3"], ["EP", "AP", "UP"]
    cols = {c: [] for c in DICT_COLUMNS + INT_COLUMNS}
    cols.update({"acceptance_date": [], "net_mass_kg": [], "supplementary_units": [], "routing": [], "documents": []})
    prev = date.fromisoformat(BASE_DATE)
    for r in records:
        for c in DICT_COLUMNS:
            v = r[c]
            if v not in index[c]:
                index[c][v] = len(dicts[c])
                dicts[c].append(v)
            cols[c].append(index[c][v])
        for c in INT_COLUMNS:
            cols[c].append(r[c])
        d = date.fromisoformat(r["acceptance_date"])
        cols["acceptance_date"].append((d - prev).days)
        prev = d
        cols["net_mass_kg"].append(int(round(r["net_mass_kg"] * 10)))
        cols["supplementary_units"].append(r["supplementary_units"])
        key = tuple(r["routing"])
        if key not in route_index:
            route_index[key] = len(routes)
            routes.append(list(key))
        cols["routing"].append(route_index[key])
        docs = r["documents"]
        cols["documents"].append(0 if not docs else [doc_codes.index(docs[0]["code"]), int(docs[0]["ref"][-6:]),
                                                     doc_status.index(docs[0]["status"])])
    dicts["routing"] = routes
    return {
        "notice": NOTICE, "house_line": HOUSE_LINE, "schema": SCHEMA_ID, "format": FORMAT, "about_format": ABOUT_FORMAT,
        "records": len(records), "base_date": BASE_DATE, "declaration_prefix": "SYN-DEC-", "constants": CONSTANTS,
        "descriptions": {c: scope.GOODS[c] for c in dicts["commodity_code"]},
        "documents": {"codes": doc_codes, "statuses": doc_status, "prefix": "SYN-DOC-"},
        "dictionaries": dicts, "columns": cols,
    }


def decode(data: dict) -> list[dict]:
    """The records in object form, from encode()'s output."""
    cols, dicts = data["columns"], data["dictionaries"]
    out, n_decl = [], 0
    day = date.fromisoformat(data["base_date"])
    for i in range(data["records"]):
        if cols["goods_item"][i] == 1:
            n_decl += 1
        day = day + timedelta(days=cols["acceptance_date"][i])
        code = dicts["commodity_code"][cols["commodity_code"][i]]
        doc = cols["documents"][i]
        rec = dict(data["constants"])
        rec.update({
            "declaration_ref": f"{data['declaration_prefix']}{n_decl:06d}", "goods_item": cols["goods_item"][i],
            "acceptance_date": day.isoformat(),
            "procedure_code": dicts["procedure_code"][cols["procedure_code"][i]],
            "exporter_id": dicts["exporter_id"][cols["exporter_id"][i]],
            "consignee_id": dicts["consignee_id"][cols["consignee_id"][i]],
            "representative_id": dicts["representative_id"][cols["representative_id"][i]],
            "representative_status": dicts["representative_status"][cols["representative_status"][i]],
            "forwarder_id": dicts["forwarder_id"][cols["forwarder_id"][i]],
            "destination": dicts["destination"][cols["destination"][i]],
            "routing": list(dicts["routing"][cols["routing"][i]]), "commodity_code": code,
            "description": data["descriptions"][code], "net_mass_kg": cols["net_mass_kg"][i] / 10,
            "supplementary_units": cols["supplementary_units"][i],
            "statistical_value_gbp": cols["statistical_value_gbp"][i],
            "mode_border": cols["mode_border"][i], "mode_inland": cols["mode_inland"][i],
            "documents": [] if doc == 0 else [{"code": data["documents"]["codes"][doc[0]],
                                               "ref": f"{data['documents']['prefix']}{doc[1]:06d}",
                                               "status": data["documents"]["statuses"][doc[2]]}],
        })
        out.append(rec)
    return out


# -- entities ---------------------------------------------------------------------------------

def entities(world, records: list[dict]) -> dict:
    stats = {}

    def bump(key, r, **extra):
        s = stats.setdefault(key, {"first_seen": r["acceptance_date"], "last_seen": r["acceptance_date"], "items": 0,
                                   "value_gbp": 0, "corridor_radar_items": 0, "links": set()})
        s["first_seen"] = min(s["first_seen"], r["acceptance_date"])
        s["last_seen"] = max(s["last_seen"], r["acceptance_date"])
        s["items"] += 1
        s["value_gbp"] += r["statistical_value_gbp"]
        if r["destination"] in CORRIDORS and is_radar(r["commodity_code"]):
            s["corridor_radar_items"] += 1
        s["links"].add(extra["link"])

    for r in records:
        bump(("E", r["exporter_id"]), r, link=r["consignee_id"])
        bump(("C", r["consignee_id"]), r, link=r["exporter_id"])
        if r["forwarder_id"]:
            bump(("F", r["forwarder_id"]), r, link=r["exporter_id"])
        if r["representative_id"]:
            bump(("R", r["representative_id"]), r, link=r["exporter_id"])

    def row(kind, i, links_name):
        s = stats[(kind, i)]
        return {"first_seen": s["first_seen"], "last_seen": s["last_seen"], "items": s["items"],
                "value_gbp": s["value_gbp"], "corridor_radar_items": s["corridor_radar_items"],
                links_name: len(s["links"])}

    groups = {}
    for e in world.exporters:
        groups.setdefault(e["group"], []).append(e["id"])
    return {
        "notice": NOTICE, "house_line": HOUSE_LINE,
        "about": ("Every party in the synthetic declarations, by pseudonymous id, with counts from the records. "
                  "Sector and ownership group are synthetic attributes; a deployment would take them from the "
                  "exporter's registered activity and ownership records [Likely]. corridor_radar_items counts goods "
                  "items of the radar's codes to the radar's corridors."),
        "exporters": [{"id": e["id"], "sector": e["sector"], "group": e["group"],
                       **row("E", e["id"], "consignees")} for e in world.exporters if ("E", e["id"]) in stats],
        "consignees": [{"id": c["id"], "country": c["country"], **row("C", c["id"], "exporters")}
                       for c in world.consignees if ("C", c["id"]) in stats],
        "forwarders": [{"id": f["id"], **row("F", f["id"], "exporters")} for f in world.forwarders
                       if ("F", f["id"]) in stats],
        "representatives": [{"id": r["id"], **row("R", r["id"], "exporters")} for r in world.representatives
                            if ("R", r["id"]) in stats],
        "groups": [{"id": g, "exporters": sorted(v)} for g, v in sorted(groups.items()) if len(v) > 1],
    }


# -- spec, truth and the rest -------------------------------------------------------------------

def signals_spec(redflags: dict) -> dict:
    out = []
    for d in DETECTORS:
        wording = {k: v for k, v in d.items() if k.startswith(("question", "basis"))}
        out.append({"id": d["id"], "name": d["name"], "title": d["title"], "pattern": d["pattern"], "unit": d["unit"],
                    "implements": [{"id": rf, "question": redflags[rf]} for rf in d["implements"]],
                    "then_check": [{"id": rf, "question": redflags[rf]} for rf in d["then_check"]],
                    "mapping": d["mapping"], "thresholds": d["thresholds"], "wording": wording})
    return {
        "notice": NOTICE, "house_line": HOUSE_LINE,
        "about": ("The restricted layer's detectors: one per pattern, each citing the red flags it implements "
                  "(radar/brief/spec/redflags.json, where each red flag's official source is cited). A detector "
                  "puts out questions for a person to check, never findings. Thresholds are ours, set on synthetic "
                  "data [Guessing]."),
        "red_flags_source": "radar/brief/spec/redflags.json",
        "scope": {"corridors": scope.CORRIDORS, "radar_codes": scope.RADAR_CODES,
                  "flagged_routes": [{"destination": cc, "code": c6, "status": st}
                                     for (cc, c6), st in sorted(scope.FLAGGED_ROUTES.items())],
                  "flagged_routes_source": scope.FLAGGED_ROUTES_SOURCE,
                  "enhanced_due_diligence_countries": scope.EDD_COUNTRIES, "edd_as_of": scope.EDD_AS_OF,
                  "neighbouring_codes": scope.NEIGHBOURS,
                  "neighbouring_codes_note": ("A neighbouring code is in the same heading and outside the radar's "
                                              "nine; whether it is controlled is not modelled [Certain]."),
                  "windows": {"review": list(scope.WINDOW), "prior": list(scope.PRIOR),
                              "shared_party": list(scope.SHARED_PERIOD), "before_invasion": list(scope.BEFORE_INVASION),
                              "after_invasion": list(scope.AFTER_INVASION)}},
        "detectors": out,
        "cases": {"grouping": ("Signals that share an exporter and destination, or a consignee, go into one case. "
                               "A case raised by two or more detectors is listed as check first; any other as check. "
                               "No case carries a score."),
                  "graph": f"Each case's parties plus one hop, at most {NEIGHBOUR_CAP} neighbours per party."},
    }


def ground_truth(world) -> dict:
    return {
        "notice": NOTICE, "house_line": HOUSE_LINE, "seed": world.seed,
        "about": ("What the generator put into the synthetic world. Injected patterns are built to match a red-flag "
                  "indicator; look-alikes are ordinary trade built to resemble one. A near miss is an injection "
                  "built to sit just outside a detector's thresholds. Units are what a detector fires on: C: a "
                  "consignee, F: a forwarder, E: an exporter, R: an exporter on a route, P: an exporter, consignee "
                  "and code, S: an exporter and consignee moving between two codes."),
        "patterns": {k: {"detector": d, "about": a} for k, (d, a) in PATTERNS.items()},
        "lookalikes": {k: {"detector": d, "about": a} for k, (d, a) in LOOKALIKES.items()},
        "records": world.truth,
        "world": {"forwarder_tiers": {f["id"]: f["tier"] for f in world.forwarders}},
    }


def schema_file() -> dict:
    return {"notice": NOTICE, "house_line": HOUSE_LINE, "schema": SCHEMA_ID, "record": json_schema(),
            "fields": field_docs(),
            "sources": [{"id": k, "publisher": p, "title": t, "date": d} for k, (p, t, d) in SOURCES.items()],
            "sources_note": ("Each field mirrors a data element in HMRC's CDS Declaration Completion Instructions "
                             "for Exports; the links are in the repo's private sources file."),
            "columnar_format": {"id": FORMAT, "about": ABOUT_FORMAT}}


def cases_file(cases: list[dict], signals: list[dict]) -> dict:
    sig = {s["id"]: s for s in signals}
    return {"notice": NOTICE, "house_line": HOUSE_LINE,
            "about": ("Signals grouped into cases around an exporter-route or a consignee cluster. Every line is a "
                      "question for a person to check, with the facts from the declarations that raised it; none is "
                      "a finding, and most will have an ordinary explanation. Cases carry no score."),
            "data_cannot_show": DATA_CANNOT_SHOW,
            "cases": [{**c, "signals": [sig[i] for i in c["signals"]]} for c in cases]}


def evaluation_file(ev: dict) -> dict:
    return {"notice": NOTICE, "house_line": HOUSE_LINE, **ev}


# -- text ---------------------------------------------------------------------------------------

def _flat(x) -> bool:
    if isinstance(x, list):
        return all(not isinstance(i, dict) and (not isinstance(i, list) or all(not isinstance(j, (dict, list)) for j in i))
                   for i in x)
    if isinstance(x, dict):
        return all(not isinstance(v, dict) and (not isinstance(v, list) or _flat(v)) for v in x.values())
    return True


def dumps(obj, level: int = 0) -> str:
    """JSON with objects indented and flat lists or flat objects kept on one line each."""
    pad = " " * level
    if isinstance(obj, dict) and obj and not (_flat(obj) and level > 1):
        items = [f'{pad} {json.dumps(k, ensure_ascii=False)}: {dumps(v, level + 1)}' for k, v in obj.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(obj, list) and obj and not _flat(obj):
        items = [pad + " " + dumps(x, level + 1) for x in obj]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def build(seed: int = SEED) -> dict[str, str]:
    world = generate(seed)
    redflags = redflag_questions()
    ctx = Context(groups={e["id"]: e["group"] for e in world.exporters})
    sigs = run_all(world.records, ctx)
    countries = {c["id"]: c["country"] for c in world.consignees}
    cases = build_cases(sigs, redflags, countries)
    graph = build_graph(world.records, cases, scope.FLAGGED_ROUTES, scope.WINDOW)
    ev = evaluate(sigs, cases, world.truth, DETECTORS)
    objs = {
        "declarations.json": encode(world.records),
        "declarations.schema.json": schema_file(),
        "entities.json": entities(world, world.records),
        "graph.json": {"notice": NOTICE, "house_line": HOUSE_LINE,
                       "about": ("Link graph of exporters, consignees, forwarders and routes (a corridor and one of "
                                 "the radar's codes), cut to each case's parties plus one hop. Edges are totals over "
                                 "2021 to June 2026; value_window_gbp is the last 12 months."), **graph},
        "cases.json": cases_file(cases, sigs),
        "signals_spec.json": signals_spec(redflags),
        "evaluation.json": evaluation_file(ev),
        "ground_truth.json": ground_truth(world),
    }
    return {name: dumps(objs[name]) + "\n" for name in FILE_NAMES}


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
