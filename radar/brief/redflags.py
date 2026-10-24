"""Questions to check on a radar lead for Common High Priority List goods, written from
official public guidance only.

Each item is a question for an analyst, never an accusation. Each cites the guidance it
comes from by publisher, document title and date. The official URLs are kept privately in
data/brief_sources.csv and appear in nothing shown.

Confidence: an item is [Certain] when the cited guidance lists the indicator or step it
asks about; the wording of the question is ours, checked against the guidance on
21 October 2026. The tags that group items for the page are our own grouping [Likely].

spec/redflags.json is generated from this module (scripts/build_brief_spec.py) and a test
keeps the two equal. Ids are stable: the page stores checklist ticks against them, so an
item may be reworded but an id is never reused for a different question.

Contains public sector information licensed under the Open Government Licence v3.0.
A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

SCHEMA = "radar-redflags/1"

#: The fixed tag set the page's exporter screen picks questions by.
TAGS = {
    "chpl": "any goods on the Common High Priority Items List",
    "corridor": "the destination is a known transshipment corridor",
    "new_customer": "a new customer",
    "volume_rise": "orders or exports have risen",
    "end_use": "what the goods are for",
    "end_user": "who ends up with the goods",
    "payment": "how the goods are paid for",
    "routing": "how and where the goods travel",
    "customer_profile": "who the customer is",
    "paperwork": "contracts and trade documents",
}

#: Official guidance, as read on 21 October 2026.
SOURCES = {
    "uk-dbt-otsi": {
        "publisher": "Department for Business and Trade and Office of Trade Sanctions Implementation",
        "title": "Countering Russian sanctions evasion - guidance for businesses",
        "date": "7 Jan 2025, updated 12 Mar 2026",
    },
    "uk-fcdo-chpl": {
        "publisher": "Foreign, Commonwealth & Development Office",
        "title": "Russia Sanctions – Common High Priority Items List",
        "date": "30 May 2023, updated 8 Aug 2024",
    },
    "uk-nca-red-alert": {
        "publisher": ("National Crime Agency (National Economic Crime Centre), with HM Treasury's Office "
                      "of Financial Sanctions Implementation and the Foreign, Commonwealth & Development Office"),
        "title": "Red Alert: Exporting High Risk Goods",
        "date": "Dec 2023",
    },
    "us-fincen-bis-2023": {
        "publisher": ("US Treasury Financial Crimes Enforcement Network (FinCEN) and US Department of "
                      "Commerce Bureau of Industry and Security (BIS)"),
        "title": ("Supplemental Alert: FinCEN and the U.S. Department of Commerce's Bureau of Industry and "
                  "Security Urge Continued Vigilance for Potential Russian Export Control Evasion Attempts "
                  "(FIN-2023-Alert004)"),
        "date": "19 May 2023",
    },
    "us-fincen-bis-2022": {
        "publisher": ("US Treasury Financial Crimes Enforcement Network (FinCEN) and US Department of "
                      "Commerce Bureau of Industry and Security (BIS)"),
        "title": ("FinCEN and the U.S. Department of Commerce's Bureau of Industry and Security Urge Increased "
                  "Vigilance for Potential Russian and Belarusian Export Control Evasion Attempts "
                  "(FIN-2022-Alert003)"),
        "date": "28 Jun 2022",
    },
    "eu-ec-guidance": {
        "publisher": "European Commission",
        "title": ("Guidance for EU operators: Implementing enhanced due diligence to shield against Russia "
                  "sanctions circumvention"),
        "date": "7 Sep 2023",
    },
    "eu-ec-chp-faq": {
        "publisher": "European Commission",
        "title": ("Enhanced due diligence for operators manufacturing and/or trading with CHP items: frequently "
                  "asked questions (Article 12gb of Council Regulation 833/2014)"),
        "date": "as of 23 Jul 2025",
    },
    "g7-industry": {
        "publisher": "G7 Sub-Working Group on Export Control Enforcement",
        "title": "Preventing Russian Export Control and Sanctions Evasion: Updated Guidance for Industry",
        "date": "24 Sep 2024",
    },
}

#: Countries the UK guidance names for enhanced due diligence (section 2.3, "including but not
#: limited to"), as updated 12 Mar 2026 [Certain]. ISO codes of the radar's corridors among them:
#: six of run 2's nine, and the nine run 3 added (config/countries_run3.csv), which are the
#: countries on the list the radar did not yet watch, with Hong Kong and Macao under China.
UK_EDD_COUNTRIES = ("Armenia", "China (including Hong Kong and Macau)", "India", "Israel", "Kazakhstan",
                    "Kyrgyzstan", "Malaysia", "Serbia", "Thailand", "Türkiye", "UAE", "Uzbekistan", "Vietnam")
UK_EDD_SOURCE = "uk-dbt-otsi"
UK_EDD_AS_OF = "12 Mar 2026"
UK_EDD_RADAR_ISO2 = frozenset({"AM", "KZ", "KG", "TR", "AE", "UZ",
                               "CN", "HK", "MO", "IN", "IL", "MY", "RS", "TH", "VN"})


@dataclass(frozen=True)
class RedFlag:
    id: str
    question: str
    why: str
    applies_to: str
    tags: tuple[str, ...]
    source: str
    confidence: str = "Certain"
    #: Other official sources that list the same indicator, after the main one (UK first).
    also: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {"id": self.id, "question": self.question, "why": self.why, "applies_to": self.applies_to,
                "tags": list(self.tags), "citation": dict(SOURCES[self.source]),
                "also_cited": [dict(SOURCES[s]) for s in self.also], "confidence": self.confidence}


UK, CHPL, NCA = "uk-dbt-otsi", "uk-fcdo-chpl", "uk-nca-red-alert"
US23, US22, EU, EUFAQ, G7 = "us-fincen-bis-2023", "us-fincen-bis-2022", "eu-ec-guidance", "eu-ec-chp-faq", "g7-industry"
UK_GUIDE = "The UK guidance for businesses"
US23_ALERT = "The 2023 US supplemental alert"

RED_FLAGS: tuple[RedFlag, ...] = (
    RedFlag("chpl-end-destination",
            "Do the goods fall within the Common High Priority Items List, and what checks show that their end "
            "destination is not Russia?",
            "The FCDO's list page says businesses should undertake due diligence to ensure that the end "
            "destination of these products is not Russia.",
            "Exports of goods on the Common High Priority Items List", ("chpl",), CHPL),
    RedFlag("transit-edd-country",
            "Is the destination, or any country the goods pass through, one that the UK guidance names for "
            "enhanced due diligence?",
            f"{UK_GUIDE} lists transit via a country for which additional due diligence is suggested, and names "
            "countries for enhanced due diligence including Armenia, Kazakhstan, Kyrgyzstan, Türkiye, the UAE "
            "and Uzbekistan; it says the list is not exhaustive.",
            "Shipments to or through corridor countries", ("corridor", "routing"), UK),
    RedFlag("new-customer-dual-use",
            "Is the customer new, and was it incorporated outside the UK after 24 February 2022 with a line of "
            "business in military or dual-use goods?",
            f"{UK_GUIDE} lists a new customer whose line of business includes trade in military or dual-use "
            "goods and that was incorporated overseas after 24 February 2022.",
            "New customers", ("new_customer", "customer_profile"), UK),
    RedFlag("new-chpl-trader",
            "Is the customer new to importing or exporting goods on the Common High Priority Items List?",
            "The G7 industry guidance lists new importers or exporters of Common High Priority List items as a "
            "red flag.",
            "New customers ordering CHPL goods", ("new_customer", "chpl"), G7),
    RedFlag("order-volume-rise",
            "Have an existing customer's orders risen in volume or value beyond its usual pattern, and is there "
            "a business reason for the rise?",
            f"{UK_GUIDE} lists anomalous increases in the volume or value of orders placed by existing customers.",
            "Existing customers", ("volume_rise", "customer_profile"), UK),
    RedFlag("chpl-orders-since-2022",
            "Did the customer start receiving these goods only after 24 February 2022, or receive far more of "
            "them since then?",
            f"{US23_ALERT} lists an existing customer that did not receive exports under the nine high priority "
            "HS codes before 24 February 2022 but receives them now, and one whose exports under those codes "
            "rose significantly after that date.",
            "Customers for CHPL goods", ("volume_rise", "chpl", "customer_profile"), US23),
    RedFlag("small-frequent-shipments",
            "Are the goods going out in small, frequent shipments to one central location, such as a warehouse "
            "in a third country, where they are combined into one shipment?",
            "The G7 industry guidance lists, among concerning business practices, items that may arrive in small, "
            "frequent shipments to a central location, such as a warehouse in a third country, where they are "
            "combined into one shipment. It describes the practice as often used for luxury goods; applying it "
            "to these goods is our reading.",
            "Shipping and delivery", ("routing", "volume_rise"), G7, confidence="Likely"),
    RedFlag("line-of-business",
            "Do the goods and their capabilities fit the buyer's and the end user's line of business?",
            f"{UK_GUIDE} lists product capabilities that do not fit the buyer's or end user's line of business.",
            "Any order", ("end_use", "customer_profile"), UK),
    RedFlag("end-use-details",
            "Has the customer given clear details of the end user, the intended end use and its own ownership "
            "when asked?",
            f"{US23_ALERT} lists a customer that lacks or refuses to provide details to banks, shippers or third "
            "parties, including about end users, intended end use or company ownership.",
            "Any order", ("end_use", "end_user", "customer_profile"), US23),
    RedFlag("end-user-certificate",
            "Who is the end user, and can an end-user certificate be provided and checked?",
            "The European Commission's guidance for EU operators asks who the end user is and whether the "
            "end-user certificate can be provided.",
            "Any order", ("end_user", "paperwork"), EU),
    RedFlag("civilian-claim-military-links",
            "Where a civilian end use or end user is stated, does anything link the customer or other parties "
            "to military users?",
            f"{UK_GUIDE} lists a civilian end use or end user being claimed while the customer or other parties "
            "have military connections.",
            "Any order", ("end_use", "end_user"), UK),
    RedFlag("destination-clear",
            "Is the customer open about where the goods will end up and what they are for?",
            f"{UK_GUIDE} lists a customer that tries by any means to obscure the product's ultimate destination "
            "and purpose.",
            "Any order", ("end_use", "end_user", "routing"), UK),
    RedFlag("consignee-uses-goods",
            "Is the consignee a business that would use the goods, rather than a bank, a mail centre or a "
            "logistics firm?",
            f"{US23_ALERT} lists ultimate consignees that do not typically engage in business consistent with "
            "using the goods, such as financial institutions, mail centres or logistics companies.",
            "Any order", ("end_user", "routing"), US23),
    RedFlag("forwarder-as-destination",
            "Is a freight forwarder named as the final destination of the goods?",
            f"{UK_GUIDE} lists a freight-forwarding firm being listed as the product's final destination.",
            "Shipping and delivery", ("end_user", "routing", "paperwork"), UK),
    RedFlag("third-country-payer",
            "Does payment come from the customer itself, or from a party in a third country that is not "
            "otherwise part of the deal?",
            f"{UK_GUIDE} lists payments from entities located in third countries that are not otherwise involved "
            "in the transaction. The 2022 US alert lists the same where the third country is known to be a "
            "potential transshipment point for exports to Russia and Belarus.",
            "Payments", ("payment", "corridor"), UK, also=(US22,)),
    RedFlag("payment-route",
            "Has the customer asked for a non-standard payment route, such as outside SWIFT, through smaller "
            "overseas banks or in cryptocurrency, or offered cash for an expensive item?",
            f"{UK_GUIDE} lists requests for non-standard payment routes, and a customer willing to pay cash for "
            "an expensive item when the terms of sale would normally require financing.",
            "Payments", ("payment",), UK),
    RedFlag("price-and-invoices",
            "Is the customer paying well above the market price, or are invoices split so that each stays under "
            "a control limit?",
            f"{UK_GUIDE} lists paying significantly above market rate, and splitting invoices to stay under "
            "export control limits.",
            "Payments", ("payment", "paperwork"), UK),
    RedFlag("split-payments-suppliers",
            "Is the same end user's foreign bank account making smaller payments to several similar suppliers "
            "of dual-use goods?",
            f"{US23_ALERT} lists smaller-volume payments from the same end user's foreign bank account to "
            "multiple, similar suppliers of dual-use products.",
            "Payments", ("payment",), US23),
    RedFlag("lc-consignee",
            "Under a letter of credit, are the goods consigned to the actual end user rather than to the "
            "issuing bank?",
            "The NCA red alert lists purchases under a letter of credit that are consigned to the issuing bank, "
            "not to the actual end user.",
            "Payments", ("payment", "end_user", "paperwork"), NCA),
    RedFlag("payment-routing-change",
            "Has a payment that was scheduled to come from a country of concern been rerouted at the last "
            "minute?",
            "The NCA red alert lists transactions involving a last-minute change in payment routing that was "
            "previously scheduled from a country of concern.",
            "Payments", ("payment",), NCA),
    RedFlag("route-complex",
            "Is the shipping route clear and usual for these goods and this destination, or complex and through "
            "several third countries?",
            f"{UK_GUIDE} lists an unclear transportation route, or a complex route involving multiple third "
            "countries.",
            "Shipping and delivery", ("routing", "corridor"), UK),
    RedFlag("transport-changed",
            "Has the way these goods are shipped to this customer changed since sanctions were imposed?",
            "The European Commission's guidance for EU operators asks whether the method of transport or "
            "shipping has changed since the imposition of sanctions.",
            "Shipping and delivery", ("routing",), EU),
    RedFlag("delivery-vague",
            "Are delivery dates or destinations vague, or are several third-country freight forwarders used on "
            "one transaction?",
            f"{UK_GUIDE} lists vague delivery dates or deliveries planned for remote destinations, and the use "
            "of multiple third-country freight forwarders or shippers on a single transaction.",
            "Shipping and delivery", ("routing",), UK),
    RedFlag("documents-end-user",
            "Do the supporting documents name the actual end user, and are they complete and consistent?",
            f"{UK_GUIDE} lists supporting documents that do not list the actual end user or are otherwise vague, "
            "and false, inaccurate or missing documentation.",
            "Trade documents", ("paperwork", "end_user"), UK),
    RedFlag("hs-code-check",
            "Are the goods recorded under the correct HS code on every document?",
            f"{UK_GUIDE} lists goods recorded under a false Harmonised System code that is not subject to "
            "sanctions or export controls.",
            "Trade documents", ("paperwork", "chpl"), UK),
    RedFlag("country-mismatch",
            "Is the end user in the same country as the party that placed the order, and do the customer's "
            "phone numbers carry the destination's country code?",
            f"{UK_GUIDE} lists a stated end user's country that differs from the country that placed the order, "
            "and telephone country codes that do not match the destination country.",
            "Customer checks", ("customer_profile", "paperwork"), UK),
    RedFlag("web-presence",
            "Does the customer have a business history and a web presence that fit the order?",
            f"{UK_GUIDE} lists a customer with little to no business background, and transactions involving "
            "entities with little to no web presence; the NCA red alert lists the second too.",
            "Customer checks", ("customer_profile", "new_customer"), UK, also=(NCA,)),
    RedFlag("shared-address",
            "Does the customer share its address with many other businesses dealing in similar goods, or trade "
            "from a residential address?",
            f"{UK_GUIDE} lists an address shared with multiple businesses or holding companies dealing in "
            "comparable goods, or a residential address.",
            "Customer checks", ("customer_profile",), UK),
    RedFlag("ownership-change",
            "Did the customer's ultimate beneficial ownership change shortly before or after sanctions were "
            "imposed?",
            f"{UK_GUIDE} lists a change of ultimate beneficial ownership shortly before or after sanctions were "
            "imposed.",
            "Customer checks", ("customer_profile",), UK),
    RedFlag("russia-ties",
            "Does the customer have business ties to a sanctioned person or entity, or a branch office in Russia?",
            f"{UK_GUIDE} lists a customer that has business ties to a sanctioned entity or person, or a branch "
            "office in Russia.",
            "Customer checks", ("customer_profile", "end_user"), UK),
    RedFlag("sanctions-list-check",
            "Have the customer and its known directors been checked against the UK Sanctions List?",
            f"{UK_GUIDE} says an initial step with a new customer should be to check whether the entity or any "
            "known directors appear on the UK Sanctions List.",
            "Customer checks", ("customer_profile", "new_customer"), UK),
    RedFlag("listed-party-resemblance",
            "Does the customer's name or address resemble that of a party on a sanctions list?",
            f"{UK_GUIDE} lists a customer or address similar to one of the persons or entities on the UK "
            f"Sanctions List. {US23_ALERT} lists the same for the parties on a proscribed parties list.",
            "Customer checks", ("customer_profile", "end_user"), UK, also=(US23,)),
    RedFlag("representative-only",
            "Can you deal with the customer's managers directly, or does everything go through one "
            "representative?",
            f"{UK_GUIDE} lists all communications being routed via a representative who seems to possess "
            "general power of attorney.",
            "Customer checks", ("customer_profile",), UK),
    RedFlag("indirect-deal",
            "Does the deal run through intermediaries in a way that makes little economic sense?",
            f"{UK_GUIDE} lists indirect transactions, for example using intermediaries, with no clear economic "
            "rationale. The European Commission's questions and answers on due diligence for CHP items list "
            "indirect transactions, such as those using intermediaries, that make no or little economic sense.",
            "Any order", ("routing", "payment", "customer_profile"), UK, also=(EUFAQ,)),
    RedFlag("no-russia-clause",
            "Does the contract bar re-export of the goods to Russia?",
            f"{UK_GUIDE} says businesses may consider adding a no export to Russia clause to their contracts.",
            "Contracts", ("paperwork", "end_use"), UK),
    RedFlag("checks-repeated",
            "When were the checks on this customer last repeated, and are they recorded in writing?",
            f"{UK_GUIDE} says due diligence should be repeated at intervals even with established trading "
            "partners, and that written records of due diligence should be kept.",
            "Customer checks", ("customer_profile", "paperwork"), UK),
    RedFlag("sales-rise-destination",
            "Do the business's own sales figures show a significant rise in exports of this product to this "
            "destination, especially where that trade was limited or absent before?",
            f"{UK_GUIDE} lists company sales data showing a significant increase in exports of a specific "
            "product, for example semiconductors or machine parts, especially if trade in that product to that "
            "destination was previously limited or non-existent.",
            "Exports to a destination", ("volume_rise", "corridor"), UK),
)


def by_id() -> dict[str, RedFlag]:
    return {f.id: f for f in RED_FLAGS}


def items() -> list[dict]:
    """Every item as the page and the brief context carry it (no URLs)."""
    return [f.as_dict() for f in RED_FLAGS]


def uk_edd_named(iso2: str) -> bool:
    """Whether a radar corridor is among the countries the UK guidance names for enhanced due
    diligence (as updated 12 Mar 2026)."""
    return str(iso2).upper() in UK_EDD_RADAR_ISO2


def export() -> dict:
    """The content of spec/redflags.json."""
    return {
        "schema": SCHEMA,
        "title": "Questions to check on a radar lead",
        "note": ("Each item is a question for an analyst to check, never an accusation. Confidence: [Certain] "
                 "means the cited guidance lists the indicator or step the question asks about; the wording of "
                 "the question is ours. The tags are our own grouping [Likely]. Ids are stable: store checklist "
                 "ticks against them. Generated from radar/brief/redflags.py; do not edit by hand."),
        "licence": "Contains public sector information licensed under the Open Government Licence v3.0.",
        "house_line": "A rise in exports is a lead, not evidence of a breach.",
        "tags": dict(TAGS),
        "tags_confidence": "Likely",
        "uk_enhanced_due_diligence_countries": {
            "names": list(UK_EDD_COUNTRIES),
            "as_of": UK_EDD_AS_OF,
            "note": "Named in the UK guidance for businesses as 'including but not limited to'; not exhaustive.",
            "citation": dict(SOURCES[UK_EDD_SOURCE]),
            "confidence": "Certain",
        },
        "items": items(),
    }


def export_text() -> str:
    return json.dumps(export(), indent=1, ensure_ascii=False) + "\n"
