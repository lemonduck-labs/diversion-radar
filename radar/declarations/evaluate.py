"""How the detectors do against the ground truth the generator recorded.

For each detector: the units it fired on, the units the injected patterns were built to create
for it (truth), and from those the true positives, false positives and misses, precision and
recall. False positives are split by where they come from: a look-alike built for that
detector, a party that is part of another injected pattern or look-alike, or ordinary
background trade.

These are figures on synthetic data, where the patterns were put in by the same people who
wrote the detectors. They say nothing about how the detectors would do on real declarations
[Certain].
"""
from __future__ import annotations

LABEL = ("Performance on synthetic data. The patterns were put in by the same people who wrote the detectors, so "
         "these figures show how the machinery behaves, not how well it would find anything in real declarations. "
         "They say nothing about real-world performance [Certain].")


def _parties(unit: str) -> set[str]:
    kind, _, rest = unit.partition(":")
    parts = rest.split("|")
    if kind in ("C", "F", "E"):
        return {parts[0]}
    if kind == "R":
        return {parts[0]}
    return {parts[0], parts[1]}


def _ratio(a: int, b: int):
    return round(a / b, 3) if b else None


def evaluate(signals: list[dict], cases: list[dict], truth: list[dict], detectors: list[dict]) -> dict:
    case_of = {sid: c["id"] for c in cases for sid in c["signals"]}
    fired: dict[str, dict[str, str]] = {}
    for s in signals:
        fired.setdefault(s["detector"], {})[s["unit"]] = s["id"]
    injected = [t for t in truth if t["kind"] == "injected"]
    lookalikes = [t for t in truth if t["kind"] == "look-alike"]
    involved = set().union(*[set(t["entities"]["exporters"]) | set(t["entities"]["consignees"])
                             | set(t["entities"]["forwarders"]) for t in truth])
    rows = []
    for d in detectors:
        det = d["id"]
        got = fired.get(det, {})
        want = {u for t in injected for u in t["units"].get(det, [])}
        look = {u for t in lookalikes for u in t["units"].get(det, [])}
        near = {u for t in injected if t["near_miss"] for u in t["units"].get(det, [])}
        tp, fp, fn = sorted(set(got) & want), sorted(set(got) - want), sorted(want - set(got))
        split = {"look-alike": [u for u in fp if u in look],
                 "touches another pattern or look-alike": [u for u in fp if u not in look and _parties(u) & involved],
                 "ordinary background": [u for u in fp if u not in look and not _parties(u) & involved]}
        rows.append({
            "detector": det, "name": d["name"], "fired": len(got), "truth": len(want),
            "true_positives": len(tp), "false_positives": len(fp), "misses": len(fn),
            "precision": _ratio(len(tp), len(got)), "recall": _ratio(len(tp), len(want)),
            "false_positives_by_source": {k: len(v) for k, v in split.items()},
            "units": {"true_positive": tp, "false_positive": split, "missed": fn,
                      "missed_by_design": sorted(set(fn) & near)},
            "cases": sorted({case_of[got[u]] for u in got}),
        })
    per_injection = []
    for t in truth:
        hits, cs = {}, set()
        for det, us in t["units"].items():
            hits[det] = [u for u in us if u in fired.get(det, {})]
            cs.update(case_of[fired[det][u]] for u in hits[det])
        per_injection.append({"id": t["id"], "kind": t["kind"], "pattern": t["pattern"], "detector": t["detector"],
                              "about": t["about"], "fired": {d: bool(v) for d, v in hits.items()},
                              "cases": sorted(cs), "near_miss": t["near_miss"]})
    truth_units = {(det, u) for t in injected for det, us in t["units"].items() for u in us}
    look_units = {(det, u) for t in lookalikes for det, us in t["units"].items() for u in us}
    by_case = {"with an injected pattern": 0, "look-alikes only": 0, "ordinary background only": 0}
    sig = {s["id"]: s for s in signals}
    for c in cases:
        keys = {(sig[i]["detector"], sig[i]["unit"]) for i in c["signals"]}
        if keys & truth_units:
            by_case["with an injected pattern"] += 1
        elif keys & look_units:
            by_case["look-alikes only"] += 1
        else:
            by_case["ordinary background only"] += 1
    all_tp = sum(r["true_positives"] for r in rows)
    return {
        "label": LABEL,
        "detectors": rows,
        "overall": {"signals": len(signals), "true_positives": all_tp,
                    "false_positives": sum(r["false_positives"] for r in rows),
                    "misses": sum(r["misses"] for r in rows),
                    "precision": _ratio(all_tp, len(signals)),
                    "recall": _ratio(all_tp, sum(r["truth"] for r in rows))},
        "injections": per_injection,
        "cases": {"total": len(cases), **by_case,
                  "check first": sum(1 for c in cases if c["check_order"] == "check first")},
    }
