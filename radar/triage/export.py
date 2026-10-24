"""The triage view's files: the reports with what they were read against, the synthetic list and
the view's rules, as written to demo/radar/triage/ by scripts/build_triage.py.

SYNTHETIC. A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

import json

from . import generate as G
from . import match as M

HOUSE_LINE = "A rise in exports is a lead, not evidence of a breach."
NOTICE = ("SYNTHETIC RECORDS. Made up by radar/triage/generate.py from a seed, to show what the radar would add "
          "where reports of a suspected breach of trade sanctions arrive. No report is or describes a real report, "
          "person or business; the parties are pseudonymous ids, and there are no names, addresses or contact details. "
          "A report is an allegation until a person has assessed it.")
LIST_NOTICE = ("SYNTHETIC. Entries in the UK Sanctions List's format (its 58 headings, in order), made up for the triage "
               "view: entities only, coded labels instead of names, and registration numbers that start SYN-. None is a "
               "designation. Last Updated and Date Designated are written dd/mm/yyyy here; the format guide's date format "
               "for them was not read [Guessing].")

#: What a person can decide for a report. A second person approves it, as for every outcome.
OUTCOMES = [
    ["assess", "Assess further: it is OTSI's to assess"],
    ["pass_hmrc", "Pass to HMRC: it involves UK customs"],
    ["pass_other", "Pass to another body: OFSI, HM Treasury or Ofcom"],
    ["ask", "Ask the reporter for more information"],
    ["close", "Close: the report gives nothing to assess"],
]


#: Names for the countries the reports and the list use that are not radar corridors.
OTHER_COUNTRIES = {"FR": "France", "DE": "Germany", "NL": "Netherlands", "IE": "Ireland", "US": "United States",
                   "NO": "Norway", "RU": "Russia", "BY": "Belarus", "GB": "United Kingdom"}


def countries() -> dict:
    import csv
    out = dict(OTHER_COUNTRIES)
    for name in ("countries.csv", "countries_run3.csv"):
        with open(M.ROOT / "config" / name, newline="") as f:
            for r in csv.DictReader(f):
                out.setdefault(r["iso2"], r["name"])
    return dict(sorted(out.items()))


def spec() -> dict:
    return {
        "schema": "radar-triage-spec/1",
        "house_line": HOUSE_LINE,
        "countries": countries(),
        "channels": G.CHANNELS, "relationships": G.RELATIONSHIPS, "nexus": G.NEXUS,
        "statements": {k: v[0] for k, v in M.STATEMENTS.items()},
        "bodies": {k: {"name": v[0], "why": v[1]} for k, v in M.BODIES.items()}, "body_source": M.BODY_SOURCE,
        "factors": M.FACTORS, "factor_source": M.FACTOR_SOURCE,
        "order_rule": [{"band": b, "rule": t} for b, t in M.RULE_ORDER],
        "order_note": "This tool's rule, set out here; OTSI publishes no triage scoring [Certain]. Within a band, oldest first. A person decides.",
        "outcomes": OUTCOMES,
        "limits": [
            "The goods table reads a few dozen phrases. Words it does not hold point to no code, and a person reads the description [Certain].",
            "A registration number is matched exactly or at one character apart. A real list check also needs names, aliases, addresses and owners, which these synthetic reports do not hold [Certain].",
            "Which body handles a report follows what the report says it is about. A report can touch several bodies, and OTSI passes on what is outside its powers [Certain].",
            "The factors are our reading of what each report states, in the terms of OTSI's guidance [Likely]. OTSI weighs them only once it has assessed a report.",
        ],
    }


def build(seed: int = G.SEED) -> dict[str, str]:
    reports, listed = G.build_reports(seed)
    matched = M.match_all(reports, listed)
    dump = lambda obj: json.dumps(obj, indent=1, ensure_ascii=False) + "\n"  # noqa: E731
    return {
        "reports.json": dump({"notice": NOTICE, "house_line": HOUSE_LINE, "seed": seed, "reports": matched}),
        "list.json": dump({"notice": LIST_NOTICE, "headings": G.LIST_HEADINGS, "entries": listed}),
        "spec.json": dump(spec()),
    }
