"""What the restricted layer looks at, held as snapshots so that the synthetic world and the
detectors give the same answer when the public radar moves on. tests/test_declarations.py
checks each snapshot against the file it was taken from.

- CORRIDORS and RADAR_CODES: config/countries.csv (role corridor) and config/codes.csv.
- FLAGGED_ROUTES: the routes the public radar showed as a lead or a watch item in
  demo/radar/leads.json when this layer was built (run of October 2026, run 2's nine
  corridors). Series held back under the display rule are not here and never will be: the
  restricted layer is pointed only at routes the public layer shows. The layer covers the
  original nine corridors only; run 3 added nine to the public radar and left these routes
  as they were.
- EDD_COUNTRIES: the countries the UK guidance for businesses names for enhanced due
  diligence, as radar/brief/spec/redflags.json records them (as of 12 Mar 2026).
- NEIGHBOURS: for some of the radar's codes, a code in the same heading that is outside the
  radar's nine. Whether a neighbouring code is controlled or on the Common High Priority
  Items List is not modelled; it is only outside the nine [Certain].

A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

from datetime import date

CORRIDORS = {"KG": "Kyrgyz Republic", "AM": "Armenia", "KZ": "Kazakhstan", "GE": "Georgia",
             "AE": "United Arab Emirates", "TR": "Turkey", "UZ": "Uzbekistan", "AZ": "Azerbaijan",
             "TJ": "Tajikistan"}
TARGET = {"RU": "Russia"}
ORDINARY = {"US": "United States", "DE": "Germany", "FR": "France", "NL": "Netherlands", "IE": "Ireland",
            "JP": "Japan", "KR": "South Korea", "SG": "Singapore", "CH": "Switzerland", "NO": "Norway",
            "IT": "Italy", "ES": "Spain", "SE": "Sweden", "PL": "Poland", "CA": "Canada", "AU": "Australia"}
TRANSIT = {"GB": "United Kingdom", "HU": "Hungary", "BG": "Bulgaria"}
COUNTRY_NAMES = {**CORRIDORS, **TARGET, **ORDINARY, **TRANSIT}

#: The radar's nine codes (six-digit HS, 8548 as a heading) and their descriptions.
RADAR_CODES = {
    "854231": "Electronic integrated circuits: processors and controllers",
    "854232": "Electronic integrated circuits: memories",
    "854233": "Electronic integrated circuits: amplifiers",
    "854239": "Electronic integrated circuits: other",
    "851762": "Machines for the reception, conversion and transmission of voice, images or other data",
    "852691": "Radio navigational aid apparatus",
    "853221": "Fixed capacitors: tantalum",
    "853224": "Fixed capacitors: ceramic dielectric, multilayer",
    "8548": "Electrical parts of machinery or apparatus not elsewhere specified",
}

#: Routes the public radar showed as a lead or a watch item (demo/radar/leads.json, run of
#: October 2026): (destination, code) -> status.
FLAGGED_ROUTES = {("KZ", "851762"): "lead", ("AE", "854232"): "lead", ("AE", "854239"): "lead",
                  ("TR", "854232"): "watch", ("UZ", "851762"): "watch", ("TR", "853221"): "watch"}
FLAGGED_ROUTES_SOURCE = ("routes shown as a lead or a watch item in demo/radar/leads.json when this layer "
                         "was built (run of October 2026)")

#: The UK guidance for businesses names these for enhanced due diligence, "including but
#: not limited to" (radar/brief/spec/redflags.json, as of 12 Mar 2026). China includes Hong
#: Kong and Macau.
EDD_COUNTRIES = {"AM": "Armenia", "CN": "China", "HK": "Hong Kong", "MO": "Macau", "IN": "India", "IL": "Israel",
                 "KZ": "Kazakhstan", "KG": "Kyrgyzstan", "MY": "Malaysia", "RS": "Serbia", "TH": "Thailand",
                 "TR": "Türkiye", "AE": "UAE", "UZ": "Uzbekistan", "VN": "Vietnam"}
EDD_AS_OF = "12 Mar 2026"

#: Eight-digit codes used in the synthetic world: the radar's codes padded with 00 (8548 as
#: 85480000), three neighbouring codes outside the nine, and six ordinary codes.
GOODS = {
    "85423100": RADAR_CODES["854231"], "85423200": RADAR_CODES["854232"],
    "85423300": RADAR_CODES["854233"], "85423900": RADAR_CODES["854239"],
    "85176200": RADAR_CODES["851762"], "85269100": RADAR_CODES["852691"],
    "85322100": RADAR_CODES["853221"], "85322400": RADAR_CODES["853224"],
    "85480000": RADAR_CODES["8548"],
    "85429000": "Electronic integrated circuits: parts",
    "85177900": "Parts of apparatus for the transmission or reception of voice, images or other data",
    "85322200": "Fixed capacitors: aluminium electrolytic",
    "22083000": "Whiskies",
    "33049900": "Beauty or make-up preparations",
    "61091000": "T-shirts, singlets and other vests, of cotton, knitted or crocheted",
    "49019900": "Printed books, brochures, leaflets and similar printed matter",
    "94036000": "Wooden furniture",
    "30049000": "Medicaments, put up in measured doses or for retail sale",
}

#: A radar code and the neighbouring code outside the nine that a switch would move it to.
NEIGHBOURS = {"85423100": "85429000", "85423200": "85429000", "85423300": "85429000", "85423900": "85429000",
              "85176200": "85177900", "85322100": "85322200", "85322400": "85322200"}

START, END = date(2021, 1, 1), date(2026, 6, 30)
INVASION = date(2022, 2, 24)
#: The review window (the last 12 months of the data) and the 12 months before it.
WINDOW = ("2025-07-01", "2026-06-30")
PRIOR = ("2024-07-01", "2025-06-30")
#: The period the shared-party detector looks at: the last 24 months.
SHARED_PERIOD = ("2024-07-01", "2026-06-30")
#: Before and after 24 February 2022, for the Russia switch.
BEFORE_INVASION = ("2021-01-01", "2022-02-23")
AFTER_INVASION = ("2022-03-01", "2024-02-29")


def code6(cn8: str) -> str:
    """The radar's code for an eight-digit code: its first six digits, or 8548 for heading 8548."""
    return "8548" if cn8.startswith("8548") else cn8[:6]


def is_radar(cn8: str) -> bool:
    """True when an eight-digit code falls under one of the radar's nine codes."""
    return code6(cn8) in RADAR_CODES


def cn8(code: str) -> str:
    """The eight-digit code the synthetic world uses for one of the radar's codes."""
    return code.ljust(8, "0")


def country(iso2: str) -> str:
    return COUNTRY_NAMES.get(iso2, iso2)


#: Country names that take "the" in running text.
_THE = {"KG", "AE", "US", "NL", "GB"}


def country_in(iso2: str) -> str:
    """The country's name as it reads in a sentence: "the Kyrgyz Republic", "Kazakhstan"."""
    return f"the {country(iso2)}" if iso2 in _THE else country(iso2)


def listed(names: list[str]) -> str:
    """Names joined for a sentence: "A", "A and B", "A, B and C"."""
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
