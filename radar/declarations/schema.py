"""The record a synthetic export declaration item carries, and the data element each field
mirrors in HMRC's CDS Declaration Completion Instructions for Exports.

One record is one goods item of one declaration (DE 1/6 numbers the items). The fields are
the few a deployment needs to ask the questions in radar/brief/spec/redflags.json: who
exported, to whom, through whom, where, what (an 8-digit commodity code), how much (value,
net mass, units) and how it travelled. A real declaration carries many more elements.

SYNTHETIC. Every value here is made up. Ids look nothing like EORI numbers (EXP-0001,
CON-0001, FWD-0001, REP-0001); there are no names, addresses or postcodes. Where a real
declaration would hold a name and address (DE 3/1, DE 3/9), the synthetic record holds
nothing. The sources behind each field are cited by publisher, title and date; their
links are in the private file data/declaration_sources.csv.

A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

SCHEMA_ID = "radar-declaration/1"
RECORD_TYPE = "synthetic export declaration item"
NOTICE = ("SYNTHETIC RECORDS. Made up by radar/declarations/generate.py from a seed, to show what the "
          "radar's restricted layer would do with export declarations. No record is or describes a real "
          "declaration, exporter, consignee, forwarder or agent; the ids are made up and look nothing like "
          "EORI numbers; there are no names, addresses or postcodes.")
HOUSE_LINE = "A rise in exports is a lead, not evidence of a breach."

#: The guidance each field mirrors: id, publisher, title, date. Links: data/declaration_sources.csv.
SOURCES = {
    "cds-export-group-1": ("HM Revenue & Customs", "CDS Declaration Completion Instructions for Exports: "
                           "Group 1: Message Information (including Procedure Codes)", "last updated 1 Jul 2026"),
    "cds-export-group-2": ("HM Revenue & Customs", "CDS Declaration Completion Instructions for Exports: "
                           "Group 2: References of Messages, Document, Certificates and Authorisations",
                           "last updated 1 Jul 2026"),
    "cds-export-group-3": ("HM Revenue & Customs", "CDS Declaration Completion Instructions for Exports: "
                           "Group 3: Parties", "last updated 6 Oct 2026"),
    "cds-export-group-5": ("HM Revenue & Customs", "CDS Declaration Completion Instructions for Exports: "
                           "Group 5: Dates, Times, Periods, Places, Countries and Regions", "last updated 1 Jul 2026"),
    "cds-export-group-6": ("HM Revenue & Customs", "CDS Declaration Completion Instructions for Exports: "
                           "Group 6: Goods Identification", "last updated 6 Oct 2026"),
    "cds-export-group-7": ("HM Revenue & Customs", "CDS Declaration Completion Instructions for Exports: "
                           "Group 7: Transport Information (Modes, Means and Equipment)", "last updated 1 Jul 2026"),
    "cds-export-group-8": ("HM Revenue & Customs", "CDS Declaration Completion Instructions for Exports: "
                           "Group 8: Other Data Elements (Statistical Data, Guarantees and Tariff Related Data)",
                           "last updated 7 Sep 2026"),
    "cds-appendix-1": ("HM Revenue & Customs", "Appendix 1: DE 1/10: Requested and Previous Procedure Codes",
                       "last updated 13 Jul 2026"),
    "cds-de23-licences": ("HM Revenue & Customs", "Data Element 2/3: Document and Other Reference Codes: Licence "
                          "Types (imports and exports) of the Customs Declaration Service (CDS)",
                          "last updated 4 Sep 2026"),
}

#: Transport mode codes for DE 7/4 and DE 7/5, as the Group 7 guidance lists them.
TRANSPORT_MODES = {1: "maritime (sea)", 2: "rail", 3: "road", 4: "air", 5: "postal (mail)",
                   6: "roll on roll-off", 7: "fixed transport installations", 8: "inland waterway",
                   9: "mode unknown"}

#: One entry per field: the name, its JSON Schema, the data element it mirrors (None where it
#: is not a data element), the source id, what it holds, and how the synthetic value is made.
FIELDS = [
    {"name": "record_type", "schema": {"const": RECORD_TYPE}, "mirrors": None, "source": None,
     "about": "Says what the record is.", "synthetic": "Always the same text."},
    {"name": "synthetic", "schema": {"const": True}, "mirrors": None, "source": None,
     "about": "Every record says it is synthetic.", "synthetic": "Always true."},
    {"name": "declaration_ref", "schema": {"type": "string", "pattern": "^SYN-DEC-[0-9]{6}$"},
     "mirrors": "DE 2/5 LRN", "source": "cds-export-group-2",
     "about": "The declaration's reference. A real declaration has the declarant's own Local Reference Number "
              "(DE 2/5) and a reference the system gives it [Likely].",
     "synthetic": "SYN-DEC- and a running number; items of one declaration share it."},
    {"name": "goods_item", "schema": {"type": "integer", "minimum": 1, "maximum": 999},
     "mirrors": "DE 1/6 Goods Item Number", "source": "cds-export-group-1",
     "about": "The item's number within the declaration.", "synthetic": "1, or 2 and 3 on declarations with more items."},
    {"name": "acceptance_date", "schema": {"type": "string", "pattern": "^20[0-9]{2}-[01][0-9]-[0-3][0-9]$"},
     "mirrors": None, "source": None,
     "about": "The date the declaration was accepted. It is the system's date, not a data element the declarant "
              "fills in [Likely].", "synthetic": "A day in the month the shipment is drawn for, 2021 to mid 2026."},
    {"name": "declaration_type", "schema": {"const": "EX"}, "mirrors": "DE 1/1 Declaration Type",
     "source": "cds-export-group-1",
     "about": "EX: trade with countries and territories outside the customs territory.",
     "synthetic": "Always EX."},
    {"name": "additional_declaration_type", "schema": {"const": "A"},
     "mirrors": "DE 1/2 Additional Declaration Type", "source": "cds-export-group-1",
     "about": "A: a standard customs declaration for goods that have arrived.", "synthetic": "Always A."},
    {"name": "procedure_code", "schema": {"enum": ["1040", "3171"]}, "mirrors": "DE 1/10 Procedure",
     "source": "cds-appendix-1",
     "about": "1040: permanent export or dispatch of Union goods or goods in free circulation and home use. "
              "3171: re-export of non-Union goods previously entered to customs warehousing.",
     "synthetic": "1040 for most items, 3171 for a few."},
    {"name": "exporter_id", "schema": {"type": "string", "pattern": "^EXP-[0-9]{4}$"},
     "mirrors": "DE 3/2 Exporter Identification Number", "source": "cds-export-group-3",
     "about": "Who exported. A real declaration holds the exporter's EORI number.",
     "synthetic": "EXP- and a number. No name or address (DE 3/1) is held."},
    {"name": "consignee_id", "schema": {"type": "string", "pattern": "^CON-[0-9]{4}$"},
     "mirrors": "DE 3/10 Consignee Identification Number", "source": "cds-export-group-3",
     "about": "The party the goods are consigned to. The guidance makes DE 3/10 mandatory where the consignee has a "
              "valid GB, EU or XI EORI number or another recognisable reference number; otherwise the consignee's "
              "name and address go in DE 3/9. Most consignees in the corridors will have only DE 3/9 [Likely], so a "
              "deployment would match consignees on name and address to give each a stable pseudonymous id.",
     "synthetic": "CON- and a number, stable for each consignee. No name or address (DE 3/9) is held."},
    {"name": "representative_id", "schema": {"type": ["string", "null"], "pattern": "^REP-[0-9]{4}$"},
     "mirrors": "DE 3/20 Representative Identification Number", "source": "cds-export-group-3",
     "about": "A customs agent declaring for the exporter, where there is one.",
     "synthetic": "REP- and a number, or null for self-representation."},
    {"name": "representative_status", "schema": {"enum": ["2", "3", None]},
     "mirrors": "DE 3/21 Representative Status Code", "source": "cds-export-group-3",
     "about": "2: direct representation. 3: indirect representation. Left blank for self-representation.",
     "synthetic": "2 or 3 where there is a representative, null otherwise."},
    {"name": "forwarder_id", "schema": {"type": ["string", "null"], "pattern": "^FWD-[0-9]{4}$"},
     "mirrors": "DE 3/37 Additional Supply Chain Actor(s) Identification Number, role code FW",
     "source": "cds-export-group-3",
     "about": "The freight forwarder, declared as an additional supply chain actor with role code FW (an EORI or a "
              "recognised third-country identifier). The guidance says the element is optional and may be left "
              "blank, so a real declaration may not carry it.",
     "synthetic": "FWD- and a number, or null where none is declared."},
    {"name": "destination", "schema": {"type": "string", "pattern": "^[A-Z]{2}$"},
     "mirrors": "DE 5/8 Country of Destination Code", "source": "cds-export-group-5",
     "about": "The country of destination, as a two-letter country code.", "synthetic": "Drawn per customer."},
    {"name": "routing", "schema": {"type": "array", "items": {"type": "string", "pattern": "^[A-Z]{2}$"},
                                   "minItems": 2, "maxItems": 6},
     "mirrors": "DE 5/18 Country of Routing Codes", "source": "cds-export-group-5",
     "about": "The countries the goods are routed through, in order.",
     "synthetic": "GB and the destination, with one transit country on some road shipments."},
    {"name": "commodity_code", "schema": {"type": "string", "pattern": "^[0-9]{8}$"},
     "mirrors": "DE 6/14 Commodity Code: Combined Nomenclature Code", "source": "cds-export-group-6",
     "about": "The first 8 digits of the commodity code from the UK Trade Tariff.",
     "synthetic": "The radar's six-digit codes padded with 00 (8548 as 85480000), a few neighbouring codes and some "
                  "ordinary codes. A real declaration carries the leaf code from the tariff [Certain]."},
    {"name": "description", "schema": {"type": "string", "minLength": 1, "maxLength": 280},
     "mirrors": "DE 6/8 Description of Goods", "source": "cds-export-group-6",
     "about": "A plain description of the goods, at most 280 characters.",
     "synthetic": "The code's description, the same on every record with that code."},
    {"name": "net_mass_kg", "schema": {"type": "number", "exclusiveMinimum": 0},
     "mirrors": "DE 6/1 Net Mass", "source": "cds-export-group-6",
     "about": "Net mass in kilograms, without packaging; the format allows up to 3 decimal places.",
     "synthetic": "From the value and a unit value per kilogram for the code; to 0.1 kg."},
    {"name": "supplementary_units", "schema": {"type": ["integer", "null"], "minimum": 1},
     "mirrors": "DE 6/2 Supplementary Units", "source": "cds-export-group-6",
     "about": "The quantity in the unit the commodity code specifies, where the code calls for one.",
     "synthetic": "A count of items for the radar's codes, null for the others. Which codes call for units is not "
                  "modelled [Guessing]."},
    {"name": "statistical_value_gbp", "schema": {"type": "number", "minimum": 0},
     "mirrors": "DE 8/6 Statistical Value", "source": "cds-export-group-8",
     "about": "The statistical value of the item in pounds sterling.", "synthetic": "Whole pounds."},
    {"name": "mode_border", "schema": {"type": "integer", "minimum": 1, "maximum": 9},
     "mirrors": "DE 7/4 Mode of Transport at the Border", "source": "cds-export-group-7",
     "about": "The mode of transport at the border: 1 sea, 2 rail, 3 road, 4 air, 5 post and so on.",
     "synthetic": "Air for most of the radar's goods, road or sea for the rest."},
    {"name": "mode_inland", "schema": {"type": "integer", "minimum": 1, "maximum": 9, "not": {"const": 6}},
     "mirrors": "DE 7/5 Inland Mode of Transport", "source": "cds-export-group-7",
     "about": "The inland mode of transport, from the same codes; roll on roll-off (6) is not used inland.",
     "synthetic": "Road, mostly."},
    {"name": "documents", "schema": {"type": "array", "maxItems": 5, "items": {
        "type": "object", "additionalProperties": False, "required": ["code", "ref", "status"],
        "properties": {"code": {"type": "string", "pattern": "^SYN[0-9]$"},
                       "ref": {"type": "string", "pattern": "^SYN-DOC-[0-9]{6}$"},
                       "status": {"enum": ["EP", "AP", "UP"]}}}},
     "mirrors": "DE 2/3 Documents produced, certificates and authorisations, additional references",
     "source": "cds-export-group-2",
     "about": "Licences, certificates and other documents: a four-character document code, the document's "
              "reference and a status code. Export licence codes are listed in Appendix 5C.",
     "synthetic": "Made-up codes SYN1 to SYN3, never the real ones, on a few items. The synthetic world does not "
                  "model which goods need a licence [Certain]."},
]
FIELD_NAMES = [f["name"] for f in FIELDS]


def json_schema() -> dict:
    """JSON Schema (draft 2020-12) for one record in its object form."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": SCHEMA_ID,
        "description": NOTICE,
        "type": "object",
        "additionalProperties": False,
        "required": FIELD_NAMES,
        "properties": {f["name"]: f["schema"] for f in FIELDS},
    }


def field_docs() -> list[dict]:
    """The fields as a table for the README and the page: name, data element, source, about."""
    out = []
    for f in FIELDS:
        src = SOURCES.get(f["source"]) if f["source"] else None
        out.append({"field": f["name"], "mirrors": f["mirrors"], "about": f["about"], "synthetic": f["synthetic"],
                    "source": None if src is None else {"id": f["source"], "publisher": src[0], "title": src[1],
                                                        "date": src[2]}})
    return out


def validate(record: dict) -> list[str]:
    """Problems with one record against the schema (empty when it matches)."""
    import jsonschema
    v = jsonschema.Draft202012Validator(json_schema())
    return [f"{'/'.join(map(str, e.absolute_path)) or '(record)'}: {e.message}" for e in v.iter_errors(record)]
