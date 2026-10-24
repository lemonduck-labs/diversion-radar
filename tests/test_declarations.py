"""The restricted layer (radar/declarations): the record schema, the seeded synthetic world,
each detector on hand-built records, cases, the evaluation and the data files in
demo/radar/declarations/ (rebuild with scripts/build_declarations.py). Synthetic data only."""
import csv
import itertools
import json
import re
from pathlib import Path

import jsonschema
import pytest

from radar.declarations import export, schema, scope
from radar.declarations import signals as S
from radar.declarations.cases import build_cases
from radar.declarations.evaluate import LABEL
from radar.declarations.generate import LOOKALIKES, PATTERNS, SEED, generate

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "demo" / "radar" / "declarations"
PKG = ROOT / "radar" / "declarations"
EM_DASH = chr(0x2014)
EORI_LIKE = re.compile(r"\b(?:GB|XI)\d{12}(?:\d{3})?\b")
REDFLAGS = {i["id"]: i for i in json.loads((ROOT / "radar" / "brief" / "spec" / "redflags.json").read_text())["items"]}


@pytest.fixture(scope="module")
def world():
    return generate(SEED)


@pytest.fixture(scope="module")
def built():
    return export.build(SEED)


@pytest.fixture(scope="module")
def data(built):
    return {name: json.loads(text) for name, text in built.items()}


# -- schema and sources -----------------------------------------------------------------------

def test_every_field_mirrors_a_cited_data_element():
    sources = {r["source_id"]: r for r in csv.DictReader((ROOT / "data" / "declaration_sources.csv").open())}
    for f in schema.FIELDS:
        if f["name"] in ("record_type", "synthetic", "acceptance_date"):
            assert f["mirrors"] is None
            continue
        assert f["mirrors"].startswith("DE "), f["name"]
        assert f["source"] in schema.SOURCES and f["source"] in sources, f["name"]
    for sid, (publisher, title, date) in schema.SOURCES.items():
        assert sources[sid]["publisher"] == publisher and sources[sid]["title"] == title, sid
        assert date in sources[sid]["date"], sid


def test_sources_file_holds_official_links_only():
    for r in csv.DictReader((ROOT / "data" / "declaration_sources.csv").open()):
        assert re.match(r"https://(www\.)?gov\.uk/", r["url"]), r["source_id"]
        assert r["publisher"] == "HM Revenue & Customs"


def test_schema_is_valid_and_the_records_match_it(world):
    jsonschema.Draft202012Validator.check_schema(schema.json_schema())
    v = jsonschema.Draft202012Validator(schema.json_schema())
    for r in world.records[::7]:
        errors = list(v.iter_errors(r))
        assert not errors, (r["declaration_ref"], errors[0].message)
    assert list(world.records[0]) == schema.FIELD_NAMES


# -- the synthetic world ----------------------------------------------------------------------

def test_the_same_seed_gives_the_same_world(world):
    again = generate(SEED)
    assert again.records == world.records and again.truth == world.truth
    assert generate(SEED + 1).records != world.records


def test_every_record_says_synthetic_and_holds_no_identifiers(world, built):
    ids = {"exporter_id": r"EXP-\d{4}", "consignee_id": r"CON-\d{4}", "forwarder_id": r"FWD-\d{4}",
           "representative_id": r"REP-\d{4}", "declaration_ref": r"SYN-DEC-\d{6}"}
    for r in world.records:
        assert r["synthetic"] is True and r["record_type"] == schema.RECORD_TYPE
        for k, pat in ids.items():
            assert r[k] is None or re.fullmatch(pat, r[k]), (k, r[k])
        assert r["description"] == scope.GOODS[r["commodity_code"]]
    for name, text in built.items():
        assert not EORI_LIKE.search(text), name
        assert "@" not in text, name


def test_dates_and_russia_trade_stop_on_24_february_2022(world):
    days = [r["acceptance_date"] for r in world.records]
    assert min(days) >= scope.START.isoformat() and max(days) <= scope.END.isoformat()
    ru = [r["acceptance_date"] for r in world.records if r["destination"] == "RU"]
    assert ru and max(ru) < scope.INVASION.isoformat()


def test_the_world_is_mostly_ordinary_trade(world):
    assert 250 <= len(world.exporters) <= 400
    assert 2000 <= len(world.consignees) <= 6000
    assert len(world.forwarders) == 40
    corridor = sum(1 for r in world.records if r["destination"] in scope.CORRIDORS)
    assert corridor / len(world.records) < 0.2
    radar = sum(1 for r in world.records if scope.is_radar(r["commodity_code"]))
    assert radar / len(world.records) < 0.5


def test_injections_are_recorded_with_their_counts(world):
    injected = [t for t in world.truth if t["kind"] == "injected"]
    counts = {p: sum(1 for t in injected if t["pattern"] == p) for p in PATTERNS}
    assert counts == {"G1": 6, "G2": 3, "G3": 3, "G4": 4, "G5": 3, "G6": 4, "G7": 3}
    for p in LOOKALIKES:
        assert any(t["pattern"] == p for t in world.truth), p
    parties = ({r["exporter_id"] for r in world.records} | {r["consignee_id"] for r in world.records}
               | {r["forwarder_id"] for r in world.records if r["forwarder_id"]})
    for t in world.truth:
        assert t["detector"] == (PATTERNS if t["kind"] == "injected" else LOOKALIKES)[t["pattern"]][0]
        for units in t["units"].values():
            for u in units:
                for p in re.split(r"[:|]", u)[1:]:
                    if re.fullmatch(r"(EXP|CON|FWD)-\d{4}", p):
                        assert p in parties, (t["id"], u)


def test_ids_are_issued_by_first_appearance(world):
    first = {}
    for r in world.records:
        first.setdefault(r["consignee_id"], r["acceptance_date"])
    ordered = sorted(first, key=lambda c: (first[c], c))
    assert ordered == sorted(first)


# -- snapshots against their sources ----------------------------------------------------------

def test_scope_snapshots_match_their_sources():
    countries = list(csv.DictReader((ROOT / "config" / "countries.csv").open()))
    corridors = {r["iso2"]: r["name"] for r in countries if r["role"] == "corridor"}
    for iso2, name in scope.CORRIDORS.items():
        assert corridors.get(iso2) == name, iso2
    codes = {r["code"]: r["description"] for r in csv.DictReader((ROOT / "config" / "codes.csv").open())}
    assert {k: v for k, v in codes.items() if k in scope.RADAR_CODES} == scope.RADAR_CODES
    assert set(scope.RADAR_CODES) <= set(codes)
    # The layer covers the original nine corridors only. Run 3 added nine to the public radar and
    # left the original nine's shown routes as they were, so the radar's shown routes are compared
    # on the layer's own corridors.
    names = {name: iso2 for iso2, name in scope.CORRIDORS.items()}
    leads = json.loads((ROOT / "demo" / "radar" / "leads.json").read_text())
    shown = {(names[r["country"]], r["code"]): r["status"]
             for r in leads if r["country"] in names and r["status"] in ("lead", "watch")}
    assert shown == scope.FLAGGED_ROUTES, "the radar's shown routes on the layer's corridors moved: update scope.FLAGGED_ROUTES"
    assert any(r["country"] not in names for r in leads)  # run 3's corridors are shown, and left out here


def test_enhanced_due_diligence_list_matches_the_red_flags():
    listed = json.loads((ROOT / "radar" / "brief" / "spec" / "redflags.json").read_text())["uk_enhanced_due_diligence_countries"]
    assert listed["as_of"] == scope.EDD_AS_OF
    expect = set(scope.EDD_COUNTRIES.values()) - {"China", "Hong Kong", "Macau"} | {"China (including Hong Kong and Macau)"}
    assert set(listed["names"]) == expect


def test_neighbouring_codes_sit_in_the_same_heading_outside_the_nine():
    for a, b in scope.NEIGHBOURS.items():
        assert scope.is_radar(a) and not scope.is_radar(b) and a[:4] == b[:4], (a, b)


# -- detectors on hand-built records ----------------------------------------------------------

class Recs(list):
    """Hand-built records with one item per declaration."""
    _n = itertools.count(1)

    def add(self, day, exp, con, dest, code, value, mass, fwd=None, times=1):
        for _ in range(times):
            n = next(self._n)
            self.append({"record_type": schema.RECORD_TYPE, "synthetic": True, "declaration_ref": f"SYN-DEC-{n:06d}",
                         "goods_item": 1, "acceptance_date": day, "declaration_type": "EX",
                         "additional_declaration_type": "A", "procedure_code": "1040", "exporter_id": exp,
                         "consignee_id": con, "representative_id": None, "representative_status": None,
                         "forwarder_id": fwd, "destination": dest, "routing": ["GB", dest], "commodity_code": code,
                         "description": scope.GOODS[code], "net_mass_kg": mass, "supplementary_units": None,
                         "statistical_value_gbp": value, "mode_border": 4, "mode_inland": 3, "documents": []})
        return self


def _units(out):
    return {s["unit"] for s in out}


def test_d1_new_corridor_consignee_and_its_floor():
    r = Recs()
    r.add("2025-08-01", "EXP-0001", "CON-0001", "KZ", "85423100", 30000, 10, times=2)  # new, 60,000
    r.add("2025-08-01", "EXP-0001", "CON-0002", "KZ", "85423100", 49000, 10)  # under the floor
    r.add("2024-01-05", "EXP-0001", "CON-0003", "KZ", "22083000", 900, 60)  # seen before the window
    r.add("2025-08-01", "EXP-0001", "CON-0003", "KZ", "85423100", 90000, 30)
    r.add("2025-08-01", "EXP-0001", "CON-0004", "DE", "85423100", 90000, 30)  # not a corridor
    r.add("2025-08-01", "EXP-0001", "CON-0005", "GE", "85423100", 90000, 30)  # corridor the UK list does not name
    r.add("2025-08-01", "EXP-0001", "CON-0006", "AE", "22083000", 90000, 6000)  # not the radar's goods
    out = {s["unit"]: s for s in S.d1_new_corridor_consignee(r, S.Context())}
    assert set(out) == {"C:CON-0001", "C:CON-0005"}
    assert out["C:CON-0001"]["implements"] == ["new-chpl-trader", "transit-edd-country"]
    assert out["C:CON-0005"]["implements"] == ["new-chpl-trader"]


def test_d2_only_on_shown_routes_and_over_both_floors():
    r = Recs()
    for dest, code, prior, window in [("KZ", "85176200", 40000, 200000),  # shown, 5 times: fires
                                      ("GE", "85176200", 40000, 200000),  # not shown
                                      ("UZ", "85176200", 40000, 100000),  # shown, 2.5 times
                                      ("AE", "85423200", 30000, 95000)]:  # shown, 3.2 times but 65,000 more
        r.add("2024-09-01", "EXP-0001", f"CON-{dest}1", dest, code, prior, 100)
        r.add("2025-09-01", "EXP-0001", f"CON-{dest}1", dest, code, window, 500)
    assert _units(S.d2_route_volume_jump(r, S.Context())) == {"R:EXP-0001|KZ|851762"}


def test_d3_counts_ownership_groups_not_exporters():
    groups = {f"EXP-000{i}": f"GRP-000{i}" for i in range(1, 5)} | {"EXP-0005": "GRP-0009", "EXP-0006": "GRP-0009"}
    r = Recs()
    for e in ("EXP-0001", "EXP-0002", "EXP-0003", "EXP-0004"):
        r.add("2025-01-10", e, "CON-0001", "AE", "85423100", 9000, 3, fwd="FWD-0001", times=2)
        r.add("2025-02-10", e, "CON-0007", "KZ", "85423100", 9000, 3, fwd="FWD-0002", times=3)
    for e in ("EXP-0001", "EXP-0002", "EXP-0005", "EXP-0006"):  # four exporters, three groups
        r.add("2025-03-10", e, "CON-0002", "AE", "85423100", 9000, 3, times=2)
    r.add("2025-04-10", "EXP-0001", "CON-0099", "DE", "22083000", 900, 60, fwd="FWD-0002", times=30)
    ctx = S.Context(groups=groups)
    # FWD-0001: 8 items, under the minimum of 10; FWD-0002: 12 of 42 items, under 40%
    assert _units(S.d3_shared_party(r, ctx)) == {"C:CON-0001", "C:CON-0007"}
    r.add("2025-05-10", "EXP-0004", "CON-0001", "AE", "85423100", 9000, 3, fwd="FWD-0001", times=2)
    assert "F:FWD-0001" in _units(S.d3_shared_party(r, ctx))


def test_d4_needs_three_items_far_from_the_code_norm():
    r = Recs()
    for k, f in enumerate([0.8, 0.9, 1.0, 1.1, 1.25] * 8):
        r.add(f"2023-{k % 12 + 1:02d}-10", f"EXP-{k % 5 + 10:04d}", f"CON-{k % 7 + 10:04d}", "DE", "85423100",
              round(2000 * f * 5), 5)
    r.add("2025-01-10", "EXP-0001", "CON-0001", "AE", "85423100", 20000, 1, times=3)  # 20,000 a kg
    r.add("2025-01-10", "EXP-0002", "CON-0002", "AE", "85423100", 20000, 1, times=2)  # only two
    r.add("2025-01-10", "EXP-0003", "CON-0003", "DE", "85423100", 20000, 1, times=3)  # not a corridor
    out = S.d4_unit_value(r, S.Context())
    assert _units(out) == {"P:EXP-0001|CON-0001|85423100"}
    assert out[0]["facts"]["direction"] == "above"


def test_d5_switch_at_a_similar_value_per_kg_only():
    r = Recs()
    for pair, b_value in (("1", 4000), ("2", 800)):  # 2 moves at a fifth of the value per kg
        for m in ("01", "03", "05"):
            r.add(f"2023-{m}-10", f"EXP-000{pair}", f"CON-000{pair}", "AE", "85423100", 4000, 2)
        for m in ("07", "09", "11"):
            r.add(f"2023-{m}-10", f"EXP-000{pair}", f"CON-000{pair}", "AE", "85429000", b_value, 2)
    for day, code in (("2023-01-10", "85423100"), ("2023-03-10", "85429000"), ("2023-06-10", "85423100"),
                      ("2023-09-10", "85429000"), ("2024-06-10", "85423100"), ("2024-07-10", "85429000")):
        r.add(day, "EXP-0003", "CON-0003", "AE", code, 4000, 2)  # interleaved, not a switch
    assert _units(S.d5_code_switch(r, S.Context())) == {"S:EXP-0001|CON-0001|85423100|85429000"}


def test_d6_counts_only_consignees_first_seen_after_the_invasion():
    r = Recs()
    for e in ("EXP-0001", "EXP-0002"):
        r.add("2021-06-10", e, f"CON-R{e[-1]}", "RU", "85423100", 75000, 30, times=2)  # 150,000 before
    r.add("2022-05-10", "EXP-0001", "CON-0002", "KZ", "85423100", 50000, 20, times=4)  # new after: 100,000 a year
    r.add("2021-03-10", "EXP-0002", "CON-0004", "TR", "85423100", 3000, 1)  # seen with these goods before 2022
    r.add("2022-05-10", "EXP-0002", "CON-0004", "TR", "85423100", 50000, 20, times=4)
    r.add("2021-06-10", "EXP-0003", "CON-R3", "RU", "85423100", 80000, 30)  # under the floor
    r.add("2022-05-10", "EXP-0003", "CON-0005", "KZ", "85423100", 50000, 20, times=4)
    out = S.d6_russia_switch(r, S.Context())
    assert _units(out) == {"E:EXP-0001"}
    assert out[0]["facts"]["new_consignees"] == ["CON-0002"]


def test_d7_twenty_small_shipments_in_the_window():
    r = Recs()
    r.add("2025-09-10", "EXP-0001", "CON-0001", "KG", "85423100", 1000, 0.5, times=20)
    r.add("2025-09-10", "EXP-0001", "CON-0002", "KG", "85423100", 1000, 0.5, times=19)
    r.add("2025-09-10", "EXP-0001", "CON-0003", "KG", "85423100", 2500, 0.5, times=20)
    r.add("2025-09-10", "EXP-0001", "CON-0004", "DE", "85423100", 1000, 0.5, times=20)
    r.add("2024-09-10", "EXP-0001", "CON-0005", "KG", "85423100", 1000, 0.5, times=20)  # before the window
    assert _units(S.d7_small_frequent(r, S.Context())) == {"C:CON-0001"}


# -- detectors, signals and cases on the synthetic world -----------------------------------------

def test_detectors_cite_red_flags_that_exist():
    assert [d["id"] for d in S.DETECTORS] == sorted(S.RUNNERS)
    for d in S.DETECTORS:
        assert d["pattern"] in PATTERNS and PATTERNS[d["pattern"]][0] == d["id"]
        for rf in d["implements"] + d["then_check"]:
            assert rf in REDFLAGS, (d["id"], rf)
        assert not set(d["implements"]) & set(d["then_check"])


def test_signals_are_questions_not_findings(data):
    from fdcore.guardrails import scan_text
    sigs = [s for c in data["cases.json"]["cases"] for s in c["signals"]]
    assert sigs
    for s in sigs:
        assert s["question"].endswith("?"), s["id"]
        assert not s["basis"].endswith("?")
        assert set(s["implements"]) <= set(S.BY_ID[s["detector"]]["implements"])
        text = s["question"] + "\n" + s["basis"]
        assert not scan_text(text), (s["id"], scan_text(text))
        assert not re.search(r"suspicious|risk score|evidence|proves?|confirmed", text, re.I), s["id"]


def test_cases_join_signals_that_share_a_party():
    def sig(i, det, unit, keys):
        return {"id": f"SIG-000{i}", "detector": det, "unit": unit, "keys": keys,
                "entities": {"exporters": [], "consignees": [], "forwarders": [], "routes": []},
                "question": "A question?", "basis": "The facts.", "implements": S.BY_ID[det]["implements"][:1],
                "then_check": S.BY_ID[det]["then_check"]}
    redflags = {k: v["question"] for k, v in REDFLAGS.items()}
    cases = build_cases([sig(1, "D1", "C:CON-0001", ["C:CON-0001"]),
                         sig(2, "D2", "R:EXP-0001|KZ|851762", ["ED:EXP-0001|KZ", "C:CON-0001"]),
                         sig(3, "D7", "C:CON-0009", ["C:CON-0009"])], redflags, {"CON-0001": "KZ", "CON-0009": "KG"})
    assert [(c["kind"], c["check_order"], c["signals"]) for c in cases] == [
        ("exporter-route", "check first", ["SIG-0001", "SIG-0002"]), ("consignee cluster", "check", ["SIG-0003"])]
    assert cases[0]["title"] == "EXP-0001 to Kazakhstan"


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


def test_every_signal_sits_in_one_case_and_no_case_carries_a_score(data):
    cases = data["cases.json"]["cases"]
    ids = [s["id"] for c in cases for s in c["signals"]]
    assert len(ids) == len(set(ids)) == data["evaluation.json"]["overall"]["signals"]
    for n, c in enumerate(cases, start=1):
        assert c["id"] == f"SYN-CASE-{n:03d}"
        assert c["check_order"] == ("check first" if len(c["detectors"]) >= 2 else "check")
        assert all(q["question"].endswith("?") for q in c["questions"])
    assert not {k for k in _keys(cases) if re.search(r"score|risk|rank", k, re.I)}


def test_the_graph_covers_every_case(data):
    g = data["graph.json"]
    nodes = {n["id"]: n for n in g["nodes"]}
    assert {n["type"] for n in nodes.values()} == {"exporter", "consignee", "forwarder", "route"}
    for e in g["edges"]:
        assert e["source"] in nodes and e["target"] in nodes
    for c in data["cases.json"]["cases"]:
        assert set(g["cases"][c["id"]]["focus"]) <= set(nodes)
    for n in nodes.values():
        if n["type"] == "route":
            assert n["public_status"] == scope.FLAGGED_ROUTES.get((n["country"], n["code"]), "not shown")


def test_evaluation_counts_add_up_and_carry_the_label(data):
    ev = data["evaluation.json"]
    assert ev["label"] == LABEL and "say nothing about real-world performance [Certain]" in LABEL
    for r in ev["detectors"]:
        assert r["true_positives"] + r["false_positives"] == r["fired"]
        assert r["true_positives"] + r["misses"] == r["truth"]
        assert sum(r["false_positives_by_source"].values()) == r["false_positives"]
        assert r["units"]["missed"] == r["units"]["missed_by_design"], r["detector"]
        assert r["precision"] == round(r["true_positives"] / r["fired"], 3)
        assert r["recall"] == round(r["true_positives"] / r["truth"], 3)
    assert ev["cases"]["total"] == len(data["cases.json"]["cases"])


# -- the data files ---------------------------------------------------------------------------

def test_data_files_are_up_to_date(built):
    for name, text in built.items():
        path = OUT / name
        assert path.exists(), f"{name} missing: run scripts/build_declarations.py"
        assert path.read_text(encoding="utf-8") == text, f"{name} out of date: run scripts/build_declarations.py"
    assert sorted(p.name for p in OUT.iterdir()) == sorted(built)


def test_data_files_carry_the_notice_stay_small_and_pass_the_screen(built, data):
    from fdcore.guardrails import scan_text
    assert sum(len(t.encode("utf-8")) for t in built.values()) < 4_000_000
    for name, obj in data.items():
        assert obj["notice"] == schema.NOTICE and obj["notice"].startswith("SYNTHETIC"), name
        assert obj["house_line"] == schema.HOUSE_LINE, name
        assert EM_DASH not in built[name], name
        assert not scan_text(built[name], name), name


def test_the_columns_decode_to_the_records(world, data):
    assert export.decode(data["declarations.json"]) == world.records


def test_code_and_readme_carry_no_em_dash_and_pass_the_screen():
    from fdcore.guardrails import scan_text
    for path in list(PKG.glob("*.py")) + [PKG / "README.md", ROOT / "scripts" / "build_declarations.py"]:
        text = path.read_text(encoding="utf-8")
        assert EM_DASH not in text, path.name
        assert not scan_text(text, path.name), path.name


def test_readme_figures_match_the_data(data):
    text = (PKG / "README.md").read_text(encoding="utf-8")
    decl = data["declarations.json"]
    n_decl = sum(1 for g in decl["columns"]["goods_item"] if g == 1)
    ents = data["entities.json"]
    world = (f"{decl['records']:,} goods items on {n_decl:,} declarations, {len(ents['exporters'])} exporters, "
             f"{len(ents['consignees']):,} consignees")
    assert world in " ".join(text.split())
    for r in data["evaluation.json"]["detectors"]:
        row = (f"| {r['detector']} | {r['fired']} | {r['truth']} | {r['true_positives']} | {r['false_positives']} | "
               f"{r['misses']} | {r['precision']} | {r['recall']} |")
        assert row in text, row
    assert "lawyers" in text and schema.HOUSE_LINE in text
