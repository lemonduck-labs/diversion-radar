"""The triage view's synthetic reports, list and rules (radar/triage, demo/radar/triage)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from radar.triage import export as E  # noqa: E402
from radar.triage import generate as G  # noqa: E402
from radar.triage import match as M  # noqa: E402

OUT = ROOT / "demo" / "radar" / "triage"
APP = ROOT / "app" / "data" / "triage"


def load(name):
    return json.loads((OUT / f"{name}.json").read_text(encoding="utf-8"))


def test_files_are_up_to_date_and_copied_to_the_app():
    import build_triage
    for path, text in build_triage.outputs().items():
        assert path.read_text(encoding="utf-8") == text, f"{path.name} is out of date: run scripts/build_triage.py"
        assert (APP / path.name).read_text(encoding="utf-8") == text, f"app/data/triage/{path.name} differs: run scripts/build_app_data.py"


def test_same_seed_same_reports():
    assert G.build_reports(7) == G.build_reports(7)
    assert G.build_reports(7) != G.build_reports(8)


def test_files_pass_the_repository_screen():
    from fdcore.guardrails import scan_text
    for name in ("reports", "list"):
        raw = (OUT / f"{name}.json").read_text(encoding="utf-8")
        assert scan_text(raw, f"{name}.json") == [], name
    # spec.json cites the title of OTSI's guidance on how reports are assessed, which the screen
    # reads as accusing; config/guardrails_policy.txt switches that off for this file only.
    found = scan_text((OUT / "spec.json").read_text(encoding="utf-8"), "spec.json")
    assert found and all(f.kind == "accusing language" and M.FACTOR_SOURCE["title"][:40] in f.text for f in found)


def test_every_report_is_synthetic_with_coded_parties_only():
    d = load("reports")
    assert d["notice"].startswith("SYNTHETIC RECORDS") and d["house_line"] == "A rise in exports is a lead, not evidence of a breach."
    ids = [r["id"] for r in d["reports"]]
    assert ids == [f"RPT-SYN-{i:03d}" for i in range(1, len(ids) + 1)]
    assert [r["received"] for r in d["reports"]] == sorted(r["received"] for r in d["reports"])
    for r in d["reports"]:
        assert r["synthetic"] is True
        assert r["anonymous"] == (r["channel"] == "whistleblower")
        if r["anonymous"]:
            assert r["documents"] == [], "whistleblowers are told not to send supporting information"
        for p in r["parties"]:
            assert re.fullmatch(r"(EXP|CON|FWD)-\d{4}|PTY-\d{4}", p["id"]), p
            assert set(p) <= {"role", "id", "registration"}
            if "registration" in p:
                assert re.fullmatch(r"SYN-REG-[A-Z2-9]{6}", p["registration"])
        assert set(r["says"]) <= set(M.STATEMENTS)
        assert r["nexus"] in G.NEXUS and r["channel"] in G.CHANNELS and r["relationship"] in G.RELATIONSHIPS


def test_parties_from_the_declarations_exist_there():
    ent = json.loads((ROOT / "demo" / "radar" / "declarations" / "entities.json").read_text(encoding="utf-8"))
    known = {e["id"] for k in ("exporters", "consignees", "forwarders") for e in ent[k]}
    for r in load("reports")["reports"]:
        for p in r["parties"]:
            if not p["id"].startswith("PTY-"):
                assert p["id"] in known, p["id"]


def test_the_list_has_the_58_headings_and_synthetic_entities_only():
    d = load("list")
    assert d["headings"] == G.LIST_HEADINGS and len(d["headings"]) == 58
    regs = []
    for e in d["entries"]:
        assert list(e) == G.LIST_HEADINGS
        assert e["Individual, Entity, Ship"] == "Entity"
        assert e["Name 6"].startswith("Synthetic listed entity ")
        assert e["Other Information"].startswith("SYNTHETIC.")
        assert e["Unique ID"].startswith("SYN-RUS-")
        assert e["IMO number"] == "" and e["D.O.B"] == "" and e["Passport number"] == ""
        regs.append(e["Business registration number (s)"])
    for i, a in enumerate(regs):
        for b in regs[i + 1:]:
            assert sum(x != y for x, y in zip(a, b)) >= 3, (a, b)


def test_matches_follow_the_rules():
    d, lst = load("reports"), load("list")
    by_reg = {e["Business registration number (s)"]: e["Unique ID"] for e in lst["entries"]}
    rf = json.loads((ROOT / "radar" / "brief" / "spec" / "redflags.json").read_text(encoding="utf-8"))
    flag_ids = {x["id"] for x in rf["items"]}
    bands = {1: 0, 2: 0, 3: 0, 4: 0}
    for r in d["reports"]:
        m = r["matched"]
        assert m["body"]["name"] == M.BODIES[r["nexus"]][0]
        assert set(m["red_flags"]) <= flag_ids, set(m["red_flags"]) - flag_ids
        for f in m["factors"]:
            assert f["id"] in M.FACTORS[f["group"]]
        for hit in m["list"]:
            if hit["strength"] == "same number":
                assert by_reg[hit["registration"]] == hit["unique_id"]
            else:
                assert M.one_apart(hit["registration"], hit["listed_number"]) and hit["registration"] not in by_reg
        if r["goods"] and r["goods"]["hs_given"]:
            assert [c["code"] for c in m["codes"]] == [r["goods"]["hs_given"]] and m["codes"][0]["confidence"] == "Certain"
        assert m["routes"] == [f"{r['destination']}-{c['code']}" for c in m["codes"]]
        if any(h["strength"] == "same number" for h in m["list"]):
            assert m["order"] == 1
        if not m["codes"] and not m["list"]:
            assert m["order"] == 4
        bands[m["order"]] += 1
    assert all(bands.values()), bands     # the seed puts reports in every band


def test_every_body_and_outcome_is_reachable():
    d = load("reports")
    assert {r["matched"]["body"]["name"] for r in d["reports"]} == {v[0] for v in M.BODIES.values()}
    assert {k for k, _ in E.OUTCOMES} == {"assess", "pass_hmrc", "pass_other", "ask", "close"}


def test_goods_words_and_codes():
    codes = M._codes()
    assert M.goods_codes({"words": "network switches", "hs_given": None}, codes)[0]["code"] == "851762"
    assert M.goods_codes({"words": "office furniture", "hs_given": None}, codes) == []
    assert [c["code"] for c in M.goods_codes({"words": "capacitors", "hs_given": None}, codes)] == ["853221", "853224"]
    assert M.goods_codes({"words": "anything", "hs_given": "940360"}, codes) == []   # a code the radar does not hold
    for code, words in G.GOODS_WORDS.items():
        for w in words:
            assert [c["code"] for c in M.goods_codes({"words": w, "hs_given": None}, codes)] == [code], w


def test_spec_names_every_country_used():
    d, lst, sp = load("reports"), load("list"), load("spec")
    used = {r["destination"] for r in d["reports"]} | {t for r in d["reports"] for t in r["transit"]}
    assert used <= set(sp["countries"])
    assert {e["Address Country"] for e in lst["entries"]} <= set(sp["countries"].values())
