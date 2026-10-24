"""A seeded, reproducible world of synthetic export declarations for the radar's restricted layer.

The world: 300 exporters, a few thousand consignees, 40 forwarders and 12 customs agents,
January 2021 to June 2026. Most of it is ordinary trade: steady customers, ordinary
destinations, ordinary codes, customers coming and going, and Russia trade that stops on
24 February 2022. Into it go the patterns in PATTERNS, each recorded as ground truth, and
look-alikes in LOOKALIKES: ordinary trade built to resemble a pattern, so that the detectors
have false positives to show. A few injections are built to sit just outside a detector's
thresholds, so that the evaluation has misses to show too.

Only random.Random(seed).random() is drawn on (every other draw is built from it here), so the
same seed gives the same world on any Python 3. Ids are issued at the end in order of first
appearance, so an id says nothing about whether a party was injected.

SYNTHETIC. No record, id or party is real; ids look nothing like EORI numbers; there are no
names, addresses or postcodes. A rise in exports is a lead, not evidence of a breach.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import scope
from .scope import CORRIDORS, END, INVASION, ORDINARY, START, code6, is_radar

SEED = 20261021

#: The patterns put into the world, with the detector each is built for.
PATTERNS = {
    "G1": ("D1", "A new consignee in a corridor buying goods on the Common High Priority Items List"),
    "G2": ("D2", "One exporter's exports to a corridor jumping on a route the public radar shows"),
    "G3": ("D3", "One consignee or forwarder shared by unrelated exporters"),
    "G4": ("D4", "Declared values per kilogram far out of line for the code"),
    "G5": ("D5", "A code switching to a neighbouring code outside the radar's nine"),
    "G6": ("D6", "Shipments to Russia stopping after 24 February 2022 and moving to a corridor"),
    "G7": ("D7", "Small, frequent shipments to one consignee"),
}
LOOKALIKES = {
    "L1": ("D1", "An ordinary new distributor in a corridor taking on a product line"),
    "L2": ("D2", "Ordinary growth on a route the public radar shows, from a new contract"),
    "L3": ("D3", "An established distributor or a forwarder specialising in corridor routes"),
    "L4": ("D4", "A premium product line with a value per kilogram well above the code's norm"),
    "L5": ("D5", "A product moving to another code after a reclassification"),
    "L6": ("D6", "An exporter that lost its Russia customers and found new customers in a corridor"),
    "L7": ("D7", "A spare-parts subscription with small monthly shipments"),
}

#: Median value per kilogram (GBP) for each code, and items per kilogram where the synthetic
#: world fills DE 6/2. Made up [Guessing]; they only need to differ between codes.
VALUE_PER_KG = {"85423100": 2400, "85423200": 1800, "85423300": 1500, "85423900": 1200, "85176200": 160,
                "85269100": 300, "85322100": 450, "85322400": 180, "85480000": 90, "85429000": 1000,
                "85177900": 110, "85322200": 90, "22083000": 14, "33049900": 28, "61091000": 22,
                "49019900": 9, "94036000": 7, "30049000": 65}
ITEMS_PER_KG = {"85423100": 500, "85423200": 400, "85423300": 600, "85423900": 500, "85176200": 1.5,
                "85269100": 4, "85322100": 2000, "85322400": 20000, "85480000": 50}

SECTORS = (("electronics", 100), ("telecoms", 40), ("general", 160))
SECTOR_CODES = {
    "electronics": (("85423100", 3), ("85423200", 3), ("85423300", 2), ("85423900", 3), ("85322100", 2),
                    ("85322400", 2), ("85480000", 2), ("85429000", 1)),
    "telecoms": (("85176200", 6), ("85269100", 2), ("85177900", 2), ("85480000", 1)),
    "general": (("22083000", 2), ("33049900", 2), ("61091000", 2), ("49019900", 2), ("94036000", 1),
                ("30049000", 2)),
}
SECTOR_VALUE = {"electronics": 7000, "telecoms": 9000, "general": 4500}
ORDINARY_WEIGHTS = {"US": 15, "DE": 14, "FR": 10, "NL": 9, "IE": 7, "JP": 5, "KR": 4, "SG": 5, "CH": 5, "NO": 3,
                    "IT": 5, "ES": 4, "SE": 4, "PL": 4, "CA": 4, "AU": 4}
CORRIDOR_WEIGHTS = {"TR": 28, "AE": 30, "KZ": 10, "GE": 8, "AM": 6, "AZ": 7, "UZ": 5, "KG": 4, "TJ": 2}
EUROPE = {"DE", "FR", "NL", "IE", "IT", "ES", "SE", "PL", "CH", "NO"}
ROAD_ROUTES = {"FR": ("GB", "FR"), "NL": ("GB", "NL"), "IE": ("GB", "IE"),
               "TR": ("GB", "FR", "DE", "HU", "BG", "TR"), "GE": ("GB", "DE", "BG", "TR", "GE"),
               "AZ": ("GB", "DE", "BG", "TR", "GE", "AZ"), "AM": ("GB", "DE", "BG", "TR", "GE", "AM")}
DOC_CODES = ("SYN1", "SYN2", "SYN3")
DOC_STATUS = ("EP", "AP", "UP")


class Rng:
    """Draws built only on random.Random.random(), which is the same stream on every Python 3."""

    def __init__(self, seed: int):
        self._r = random.Random(seed)

    def u(self) -> float:
        return self._r.random()

    def uniform(self, a: float, b: float) -> float:
        return a + (b - a) * self.u()

    def randint(self, a: int, b: int) -> int:
        return a + min(int(self.u() * (b - a + 1)), b - a)

    def chance(self, p: float) -> bool:
        return self.u() < p

    def choice(self, seq):
        return seq[min(int(self.u() * len(seq)), len(seq) - 1)]

    def weighted(self, items, weights):
        x, acc = self.u() * sum(weights), 0.0
        for item, w in zip(items, weights):
            acc += w
            if x < acc:
                return item
        return items[-1]

    def normal(self) -> float:
        u1 = max(self.u(), 1e-12)
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * self.u())

    def lognormal(self, median: float, sigma: float) -> float:
        return median * math.exp(sigma * self.normal())

    def poisson(self, lam: float) -> int:
        if lam <= 0:
            return 0
        limit, k, p = math.exp(-lam), 0, 1.0
        while True:
            p *= self.u()
            if p <= limit:
                return k
            k += 1

    def sample(self, seq, k: int) -> list:
        pool, out = list(seq), []
        for _ in range(min(k, len(pool))):
            out.append(pool.pop(min(int(self.u() * len(pool)), len(pool) - 1)))
        return out


@dataclass
class Exporter:
    idx: int
    sector: str
    group: int
    start: date
    end: date
    rate: float
    growth: float
    codes: list
    code_weights: list
    corridor_share: float
    russia_share: float
    typical: dict = field(default_factory=dict)
    offset: dict = field(default_factory=dict)
    rep: int | None = None
    rep_status: str | None = None
    fwd_primary: int = 0
    fwd_secondary: int | None = None
    fwd_specialist: int | None = None
    customers: list = field(default_factory=list)


@dataclass
class Customer:
    consignee: int
    start: date
    end: date
    weight: float
    size: float
    codes: list


@dataclass
class Shipment:
    day: date
    exporter: int
    consignee: int
    items: list  # dicts: code, value, mass, units, doc
    forwarder: int | None
    mode_border: int
    mode_inland: int
    routing: tuple
    procedure: str
    seq: int = 0


def _month_starts(a: date, b: date):
    d = date(a.year, a.month, 1)
    while d <= b:
        yield d
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def _days_in_month(d: date) -> int:
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return (nxt - d).days


def _d(s: str) -> date:
    return date.fromisoformat(s)


class World:
    """Builds the synthetic world. Use generate() rather than this class directly."""

    def __init__(self, seed: int = SEED):
        self.rng = Rng(seed)
        self.exporters: list[Exporter] = []
        self.consignees: list[dict] = []  # country, kind
        self.forwarders: list[dict] = []  # tier, role
        self.reps: list[float] = []
        self.shipments: list[Shipment] = []
        self.truth: list[dict] = []
        self.used: set[int] = set()
        self._seq = 0
        self._doc = 0

    # -- parties -------------------------------------------------------------------------------

    def new_consignee(self, country: str, kind: str = "customer") -> int:
        self.consignees.append({"country": country, "kind": kind})
        return len(self.consignees) - 1

    def _build_parties(self):
        r = self.rng
        tiers = (["hub"] * 3 + ["mid"] * 18 + ["specialist"] * 2 + ["small"] * 16 + ["reserved"])
        self.forwarders = [{"tier": t} for t in tiers]
        self.hubs = [i for i, f in enumerate(self.forwarders) if f["tier"] == "hub"]
        self.mids = [i for i, f in enumerate(self.forwarders) if f["tier"] == "mid"]
        self.specialists = [i for i, f in enumerate(self.forwarders) if f["tier"] == "specialist"]
        self.smalls = [i for i, f in enumerate(self.forwarders) if f["tier"] == "small"]
        self.reserved_forwarder = len(self.forwarders) - 1
        self.reps = [r.lognormal(1.0, 0.8) for _ in range(12)]

        sectors = [s for s, n in SECTORS for _ in range(n)]
        groups = list(range(len(sectors)))
        shared, k = r.sample(range(len(sectors)), 50), 0
        for size in [3] * 10 + [2] * 10:
            for m in shared[k:k + size]:
                groups[m] = shared[k]
            k += size
        for i, sector in enumerate(sectors):
            start = START if r.chance(0.85) else _d(f"{r.randint(2021, 2025)}-{r.randint(1, 12):02d}-01")
            start = min(start, date(2025, 3, 1))
            end = END if r.chance(0.94) else _d(f"{r.randint(2023, 2025)}-{r.randint(1, 12):02d}-28")
            pool = SECTOR_CODES[sector]
            k = {"electronics": r.randint(1, 4), "telecoms": r.randint(1, 3), "general": r.randint(1, 2)}[sector]
            codes, weights, items, ws = [], [], [c for c, _ in pool], [w for _, w in pool]
            for _ in range(k):
                c = r.weighted(items, ws)
                j = items.index(c)
                codes.append(c)
                weights.append(ws[j])
                del items[j], ws[j]
            if sector == "general":
                cshare = 0.0 if r.chance(0.7) else r.uniform(0.03, 0.12)
                rshare = r.uniform(0.03, 0.15) if r.chance(0.10) else 0.0
            else:
                cshare = 0.0 if r.chance(0.45) else r.uniform(0.04, 0.22)
                rshare = r.uniform(0.05, 0.30) if r.chance(0.30) else 0.0
            e = Exporter(idx=i, sector=sector, group=groups[i], start=start, end=end,
                         rate=min(9.0, max(0.12, r.lognormal(0.95, 0.75))), growth=r.lognormal(1.02, 0.12),
                         codes=codes, code_weights=weights, corridor_share=cshare, russia_share=rshare)
            for c in codes:
                self._ensure_code(e, c)
            if r.chance(0.75):
                e.rep = r.weighted(list(range(len(self.reps))), self.reps)
                e.rep_status = "2" if r.chance(0.6) else "3"
            e.fwd_primary = r.choice(self.hubs) if r.chance(0.6) else r.choice(self.mids)
            e.fwd_secondary = r.choice(self.smalls) if r.chance(0.3) else None
            if cshare > 0 and r.chance(0.5):
                e.fwd_specialist = r.choice(self.specialists)
            self.exporters.append(e)

    def _ensure_code(self, e: Exporter, c: str):
        if c not in e.typical:
            e.typical[c] = self.rng.lognormal(SECTOR_VALUE[e.sector] if e.sector in SECTOR_VALUE else 6000, 0.8)
            e.offset[c] = self.rng.lognormal(1.0, 0.25)

    def _pick_country(self, e: Exporter, day: date) -> str:
        r = self.rng
        if day < INVASION and e.russia_share and r.chance(e.russia_share):
            return "RU"
        if e.corridor_share and r.chance(e.corridor_share):
            return r.weighted(list(CORRIDOR_WEIGHTS), list(CORRIDOR_WEIGHTS.values()))
        return r.weighted(list(ORDINARY_WEIGHTS), list(ORDINARY_WEIGHTS.values()))

    def _add_customer(self, e: Exporter, start: date, con: int | None = None, weight=None, size=None, codes=None):
        r = self.rng
        if con is None:
            con = self.new_consignee(self._pick_country(e, start))
        country = self.consignees[con]["country"]
        end = END
        if country == "RU":
            end = INVASION - timedelta(days=1)
        if codes is None:
            n = 1 if len(e.codes) == 1 or r.chance(0.6) else 2
            codes = r.sample(e.codes, n)
        e.customers.append(Customer(con, start, min(end, e.end), weight if weight is not None else r.lognormal(1.0, 0.9),
                                    size if size is not None else r.lognormal(1.0, 0.5), codes))

    def _link_distributors(self):
        r = self.rng
        ordinary = [self.new_consignee(r.weighted(list(ORDINARY_WEIGHTS), list(ORDINARY_WEIGHTS.values())),
                                       "distributor") for _ in range(120)]
        corridor = [self.new_consignee(c, "distributor") for c in
                    ["AE"] * 6 + ["TR"] * 6 + ["KZ"] * 3 + ["GE"] * 2 + ["AZ", "AM", "UZ"]]
        self.corridor_distributors = corridor
        starts = {d: (START if r.chance(0.8) else _d(f"{r.randint(2021, 2023)}-{r.randint(1, 12):02d}-01"))
                  for d in ordinary + corridor}
        for e in self.exporters:
            if not r.chance(0.5 if e.sector != "general" else 0.35):
                continue
            for _ in range(r.randint(1, 2)):
                pool = corridor if (e.corridor_share and r.chance(0.3)) else ordinary
                d = r.choice(pool)
                if any(c.consignee == d for c in e.customers):
                    continue
                self._add_customer(e, max(e.start, starts[d]), con=d, weight=r.lognormal(2.5, 0.5),
                                   size=r.lognormal(1.8, 0.4), codes=list(e.codes))

    # -- shipments -----------------------------------------------------------------------------

    def _mode(self, dest: str, value: float, mass: float, sector: str) -> tuple[int, int, tuple]:
        r = self.rng
        inland = 3 if r.chance(0.95) else 2
        if dest in EUROPE:
            m = 3 if r.chance(0.7) else (4 if r.chance(0.67) else 1)
        elif dest in ("TR", "GE", "AZ", "AM"):
            m = 4 if r.chance(0.6) else 3
        elif dest == "AE":
            m = 4 if r.chance(0.7) else 1
        elif dest in ORDINARY:
            m = 4 if r.chance(0.85 if sector != "general" else 0.6) else 1
        else:
            m = 4
        if value < 2000 and mass < 2 and r.chance(0.4):
            m = 5
        if m == 3 and dest in ROAD_ROUTES:
            routing = ROAD_ROUTES[dest]
        elif m == 3:
            routing = ("GB", "FR", dest)
        else:
            routing = ("GB", dest)
        return m, inland, routing

    def _forwarder(self, e: Exporter, dest: str) -> int | None:
        r = self.rng
        if not r.chance(0.7):
            return None
        if dest in CORRIDORS and e.fwd_specialist is not None and r.chance(0.8):
            return e.fwd_specialist
        if e.fwd_secondary is not None and r.chance(0.25):
            return e.fwd_secondary
        return e.fwd_primary

    def _item(self, e: Exporter, code: str, value: float | None = None, size: float = 1.0,
              uv_factor: float = 1.0) -> dict:
        r = self.rng
        self._ensure_code(e, code)
        v = value if value is not None else max(150.0, e.typical[code] * size * r.lognormal(1.0, 0.55))
        uv = VALUE_PER_KG[code] * e.offset[code] * r.lognormal(1.0, 0.3) * uv_factor
        mass = max(0.1, round(v / uv, 1))
        upk = ITEMS_PER_KG.get(code)
        units = max(1, round(mass * upk * r.lognormal(1.0, 0.25))) if upk else None
        doc = None
        if r.chance(0.12):
            self._doc += 1
            doc = (r.choice(DOC_CODES), self._doc, r.choice(DOC_STATUS))
        return {"code": code, "value": int(round(v)), "mass": mass, "units": units, "doc": doc}

    def ship(self, e: Exporter, con: int, day: date, code: str, value: float | None = None, size: float = 1.0,
             uv_factor: float = 1.0, extra_codes=(), forwarder="auto", mode: int | None = None) -> Shipment:
        r = self.rng
        items = [self._item(e, code, value, size, uv_factor)] + [self._item(e, c, None, size) for c in extra_codes]
        dest = self.consignees[con]["country"]
        value_all = sum(i["value"] for i in items)
        mass_all = sum(i["mass"] for i in items)
        m, inland, routing = self._mode(dest, value_all, mass_all, e.sector)
        if mode is not None:
            m = mode
            routing = ROAD_ROUTES.get(dest, ("GB", "FR", dest)) if m == 3 else ("GB", dest)
        fwd = self._forwarder(e, dest) if forwarder == "auto" else forwarder
        self._seq += 1
        s = Shipment(day, e.idx, con, items, fwd, m, inland, routing, "3171" if r.chance(0.04) else "1040", self._seq)
        self.shipments.append(s)
        return s

    def _background(self):
        r = self.rng
        for e in self.exporters:
            n0 = min(30, max(2, round(r.lognormal(6.0, 0.55))))
            for _ in range(n0):
                self._add_customer(e, e.start)
            for m in _month_starts(e.start, e.end):
                dim = _days_in_month(m)
                for c in e.customers:
                    if c.start <= m <= c.end and c.end == END and r.chance(0.009):
                        c.end = m + timedelta(days=r.randint(0, dim - 1))
                for _ in range(r.poisson(n0 * 0.012)):
                    self._add_customer(e, m + timedelta(days=r.randint(0, dim - 1)))
                years = (m - START).days / 365.25
                season = {12: 0.85, 8: 0.9}.get(m.month, 1.0)
                for _ in range(r.poisson(e.rate * e.growth ** years * season)):
                    day = m + timedelta(days=r.randint(0, dim - 1))
                    if day < e.start or day > e.end:
                        continue
                    active = [c for c in e.customers if c.start <= day <= c.end]
                    if not active:
                        continue
                    c = r.weighted(active, [a.weight for a in active])
                    code = r.choice(c.codes)
                    extra = ()
                    if len(e.codes) > 1 and r.chance(0.15):
                        others = [x for x in e.codes if x != code]
                        extra = tuple(r.sample(others, 1 if r.chance(0.8) else 2))
                    self.ship(e, c.consignee, day, code, size=c.size, extra_codes=extra)

    # -- injections ----------------------------------------------------------------------------

    def pick_exporters(self, n: int, sectors=("electronics", "telecoms"), code: str | None = None,
                       distinct_groups: bool = False, russia: bool | None = None) -> list[Exporter]:
        pool = [e for e in self.exporters if e.sector in sectors and e.idx not in self.used and e.start <= date(2021, 1, 1)
                and e.end == END and (code is None or code in e.codes) and any(is_radar(c) for c in e.codes)
                and (russia is None or (e.russia_share > 0) == russia)]
        out, groups = [], set()
        for e in self.rng.sample(pool, len(pool)):
            if distinct_groups and e.group in groups:
                continue
            out.append(e)
            groups.add(e.group)
            if len(out) == n:
                break
        if len(out) < n:
            raise RuntimeError("not enough exporters to inject into")
        for e in out:
            self.used.add(e.idx)
        return out

    def days(self, a: str, b: str, n: int) -> list[date]:
        """n days spread through [a, b], in order, each one jittered by up to a week."""
        a, b = _d(a), _d(b)
        span = (b - a).days
        out = []
        for i in range(n):
            base = a + timedelta(days=int(span * (i + 0.5) / n))
            out.append(min(b, max(a, base + timedelta(days=self.rng.randint(-6, 6)))))
        return sorted(out)

    def record(self, rid: str, kind: str, about: str, units: dict, entities: dict, near_miss: str | None = None):
        pattern = rid.split("-")[0]
        detector = (PATTERNS if kind == "injected" else LOOKALIKES)[pattern][0]
        self.truth.append({"id": rid, "pattern": pattern, "kind": kind, "detector": detector, "about": about,
                           "units": units, "entities": entities, "near_miss": near_miss})

    def radar_codes(self, e: Exporter) -> list[str]:
        return [c for c in e.codes if is_radar(c)]

    def _inject(self):
        r = self.rng
        # G1: new consignees in a corridor buying the radar's goods, first seen in the review window.
        for i, cc in enumerate(["KZ", "KG", "AM", "AE", "UZ", "GE"]):
            exps = self.pick_exporters(2 if i in (1, 3) else 1)
            con = self.new_consignee(cc)
            near = i == 5
            n = 6 if near else r.randint(8, 12)
            for k, day in enumerate(self.days("2025-08-01", "2026-06-20", n)):
                e = exps[k % len(exps)]
                value = r.lognormal(6000 if near else 14000, 0.3)
                self.ship(e, con, day, r.choice(self.radar_codes(e)), value=value, mode=4)
            self.record(f"G1-{i + 1}", "injected",
                        f"A consignee in {scope.country_in(cc)}, first seen in the review window, buying the radar's goods",
                        {"D1": [("C", con)]}, {"exporters": [e.idx for e in exps], "consignees": [con]},
                        "built to stay under D1's floor of 50,000 pounds in the window" if near else None)
        # L1: ordinary new distributors in a corridor, first seen in the review window.
        for i, cc in enumerate(["TR", "AE", "KZ", "AZ"]):
            e = self.pick_exporters(1)[0]
            con = self.new_consignee(cc)
            for day in self.days("2025-08-15", "2026-06-25", r.randint(6, 9)):
                self.ship(e, con, day, r.choice(self.radar_codes(e)), value=r.lognormal(11000, 0.3))
            self.record(f"L1-{i + 1}", "look-alike", f"An ordinary new distributor in {scope.country_in(cc)}",
                        {"D1": [("C", con)]}, {"exporters": [e.idx], "consignees": [con]})

        # G2: one exporter's exports jumping on a route the public radar shows.
        for i, (cc, c6) in enumerate([("KZ", "851762"), ("AE", "854232"), ("TR", "853221")]):
            code = scope.cn8(c6)
            e = self.pick_exporters(1, sectors=("telecoms",) if c6 == "851762" else ("electronics",))[0]
            self._ensure_code(e, code)
            cons = [self.new_consignee(cc) for _ in range(2)]
            for con in cons:
                first = f"2023-{r.randint(3, 9):02d}-{r.randint(1, 28):02d}"
                for day in self.days(first, "2025-06-25", r.randint(18, 24)):
                    self.ship(e, con, day, code, value=r.lognormal(4500, 0.3))
                for day in self.days("2025-07-05", "2026-06-25", r.randint(24, 30)):
                    self.ship(e, con, day, code, value=r.lognormal(9000, 0.3))
            units = {"D2": [("R", e.idx, cc, c6)]}
            ents = {"exporters": [e.idx], "consignees": list(cons)}
            if i == 0:
                new = self.new_consignee(cc)
                for day in self.days("2025-09-10", "2026-06-20", 6):
                    self.ship(e, new, day, code, value=r.lognormal(15000, 0.25))
                units["D1"] = [("C", new)]
                ents["consignees"].append(new)
            self.record(f"G2-{i + 1}", "injected",
                        f"One exporter's exports of {c6} to {scope.country_in(cc)} jumping in the review window", units, ents)
        # L2: ordinary growth on shown routes from a new contract with existing customers.
        for i, (cc, c6) in enumerate([("AE", "854239"), ("TR", "854232"), ("UZ", "851762")]):
            code = scope.cn8(c6)
            e = self.pick_exporters(1, sectors=("telecoms",) if c6 == "851762" else ("electronics",))[0]
            self._ensure_code(e, code)
            con = self.new_consignee(cc)
            for day in self.days("2022-05-01", "2025-06-25", 30):
                self.ship(e, con, day, code, value=r.lognormal(5500, 0.3))
            for day in self.days("2025-07-05", "2026-06-25", 28):
                self.ship(e, con, day, code, value=r.lognormal(9000, 0.3))
            self.record(f"L2-{i + 1}", "look-alike", f"Ordinary growth of {c6} to {scope.country_in(cc)} from a new contract",
                        {"D2": [("R", e.idx, cc, c6)]}, {"exporters": [e.idx], "consignees": [con]})

        # G3: two consignees and one forwarder shared by unrelated exporters.
        for i, (cc, n, first) in enumerate([("AE", 6, "2024-07-15"), ("TR", 5, "2024-09-02")]):
            exps = self.pick_exporters(n, distinct_groups=True)
            hub = self.new_consignee(cc)
            for e in exps:
                for day in self.days(first, "2026-06-20", r.randint(2, 5)):
                    self.ship(e, hub, day, r.choice(self.radar_codes(e)), value=r.lognormal(12000, 0.4))
            self.record(f"G3-{i + 1}", "injected",
                        f"A consignee in {scope.country_in(cc)} receiving the radar's goods from {n} unrelated exporters",
                        {"D3": [("C", hub)]}, {"exporters": [e.idx for e in exps], "consignees": [hub]})
        fwd = self.reserved_forwarder
        exps = self.pick_exporters(7, distinct_groups=True)
        cons = []
        for e, cc in zip(exps, ["KZ", "KG", "AM", "UZ", "GE", "AZ", "AE"]):
            con = self.new_consignee(cc)
            cons.append(con)
            for day in self.days(f"2024-{r.randint(7, 12):02d}-01", "2026-06-20", r.randint(3, 5)):
                self.ship(e, con, day, r.choice(self.radar_codes(e)), value=r.lognormal(9000, 0.4), forwarder=fwd, mode=4)
        self.record("G3-3", "injected", "A small forwarder that seven unrelated exporters use for the radar's goods "
                    "to corridor countries", {"D3": [("F", fwd)]},
                    {"exporters": [e.idx for e in exps], "consignees": cons, "forwarders": [fwd]})
        # L3: established corridor distributors with several unrelated suppliers, and the two
        # forwarders that specialise in corridor routes.
        firsts = [next(c for c in self.corridor_distributors if self.consignees[c]["country"] == cc) for cc in ("AE", "TR", "KZ")]
        for i, d in enumerate(firsts):
            exps = self.pick_exporters(r.randint(4, 5), distinct_groups=True)
            for e in exps:
                for day in self.days("2021-02-01", "2026-06-25", r.randint(20, 30)):
                    self.ship(e, d, day, r.choice(self.radar_codes(e)), value=r.lognormal(8000, 0.4))
            self.record(f"L3-{i + 1}", "look-alike", f"An established distributor in {scope.country_in(self.consignees[d]['country'])} "
                        "with several unrelated suppliers since 2021", {"D3": [("C", d)]},
                        {"exporters": [e.idx for e in exps], "consignees": [d]})
        for i, f in enumerate(self.specialists):
            self.record(f"L3-{4 + i}", "look-alike", "A forwarder specialising in corridor routes",
                        {"D3": [("F", f)]}, {"forwarders": [f]})

        # G4: values per kilogram far out of line for the code.
        g4 = [("AE", "85423200", 10.0, 4), ("KZ", "85176200", 0.1, 5), ("TR", "85322100", 9.0, 4), ("AM", "85423900", 0.12, 2)]
        for i, (cc, code, factor, n_out) in enumerate(g4):
            e = self.pick_exporters(1, sectors=("telecoms",) if code.startswith("8517") else ("electronics",))[0]
            con = self.new_consignee(cc)
            for day in self.days(f"{r.randint(2022, 2023)}-{r.randint(1, 12):02d}-01", "2026-06-20", r.randint(6, 10)):
                self.ship(e, con, day, code)
            for day in self.days("2024-09-01", "2026-05-31", n_out):
                self.ship(e, con, day, code, value=r.lognormal(18000, 0.3), uv_factor=factor)
            self.record(f"G4-{i + 1}", "injected",
                        f"Shipments of {code} to {scope.country_in(cc)} at about "
                        + (f"{factor:g} times" if factor >= 1 else f"{factor:.0%} of") + " the code's value per kilogram",
                        {"D4": [("P", e.idx, con, code)]}, {"exporters": [e.idx], "consignees": [con]},
                        "built with only two shipments out of line, under D4's minimum of three" if n_out < 3 else None)
        # L4: premium product lines to corridor customers.
        for i, (cc, code) in enumerate([("TR", "85423100"), ("AE", "85423300"), ("GE", "85269100")]):
            e = self.pick_exporters(1, sectors=("telecoms",) if code.startswith("8526") else ("electronics",))[0]
            con = self.new_consignee(cc)
            for day in self.days("2021-03-01", "2026-06-20", r.randint(8, 14)):
                self.ship(e, con, day, code, value=r.lognormal(16000, 0.3), uv_factor=r.uniform(6.5, 8.0))
            self.record(f"L4-{i + 1}", "look-alike", f"A premium product line of {code} to {scope.country_in(cc)}",
                        {"D4": [("P", e.idx, con, code)]}, {"exporters": [e.idx], "consignees": [con]})

        # G5: a radar code switching to a neighbouring code at the same value per kilogram.
        g5 = [("AE", "85423100", "2022-06-01", "2024-02-01"), ("KZ", "85176200", "2022-10-01", "2023-09-01"),
              ("TR", "85322400", "2022-03-01", "2024-05-01")]
        for i, (cc, a, first, switch) in enumerate(g5):
            b = scope.NEIGHBOURS[a]
            e = self.pick_exporters(1, sectors=("telecoms",) if a.startswith("8517") else ("electronics",))[0]
            con = self.new_consignee(cc)
            same = VALUE_PER_KG[a] / VALUE_PER_KG[b]
            before = _d(switch) - timedelta(days=20)
            for day in self.days(first, before.isoformat(), r.randint(10, 16)):
                self.ship(e, con, day, a, value=r.lognormal(11000, 0.3))
            self._ensure_code(e, b)
            e.offset[b] = e.offset[a]
            for day in self.days(switch, "2026-06-20", r.randint(12, 18)):
                self.ship(e, con, day, b, value=r.lognormal(11000, 0.3), uv_factor=same)
            self.record(f"G5-{i + 1}", "injected", f"Shipments to {scope.country_in(cc)} moving from {a} to {b} "
                        "at the same value per kilogram", {"D5": [("S", e.idx, con, a, b)]},
                        {"exporters": [e.idx], "consignees": [con]})
        # L5: a reclassification at a similar value per kilogram, and a move to parts at a lower one.
        for i, (cc, a, switch, uvf) in enumerate([("GE", "85423900", "2024-09-01", 1.0), ("TR", "85423100", "2023-11-01", 0.2)]):
            b = scope.NEIGHBOURS[a]
            e = self.pick_exporters(1)[0]
            con = self.new_consignee(cc)
            before = _d(switch) - timedelta(days=25)
            for day in self.days("2021-06-01", before.isoformat(), r.randint(10, 14)):
                self.ship(e, con, day, a, value=r.lognormal(9000, 0.3))
            self._ensure_code(e, b)
            e.offset[b] = e.offset[a]
            for day in self.days(switch, "2026-06-20", r.randint(10, 14)):
                self.ship(e, con, day, b, value=r.lognormal(9000, 0.3),
                          uv_factor=uvf * VALUE_PER_KG[a] / VALUE_PER_KG[b])
            self.record(f"L5-{i + 1}", "look-alike",
                        f"A product to {scope.country_in(cc)} moving from {a} to {b} after a reclassification"
                        + ("" if uvf == 1.0 else ", at a much lower value per kilogram"),
                        {"D5": [("S", e.idx, con, a, b)]}, {"exporters": [e.idx], "consignees": [con]})

        # G6: Russia trade stopping on 24 February 2022 and moving to a corridor.
        for i, cc in enumerate(["KZ", "KG", "AM", "TR"]):
            e = self.pick_exporters(1)[0]
            codes = self.radar_codes(e)[:2]
            ru = [self.new_consignee("RU") for _ in range(2)]
            for con in ru:
                for day in self.days("2021-01-10", "2022-02-18", r.randint(24, 30)):
                    self.ship(e, con, day, r.choice(codes), value=r.lognormal(9000, 0.3))
            near = cc == "TR"
            ents = {"exporters": [e.idx], "consignees": list(ru)}
            units = {"D6": [("E", e.idx)]}
            if near:
                new = self.new_consignee(cc)
                for day in self.days("2021-03-01", "2021-12-15", 3):
                    self.ship(e, new, day, codes[0], value=r.lognormal(3000, 0.3))
            else:
                new = self.new_consignee(cc)
            for day in self.days(f"2022-{r.randint(4, 6):02d}-{r.randint(1, 28):02d}", "2024-02-25", r.randint(60, 70)):
                self.ship(e, new, day, r.choice(codes), value=r.lognormal(9000, 0.3))
            for day in self.days("2024-03-10", "2026-06-20", r.randint(14, 20)):
                self.ship(e, new, day, r.choice(codes), value=r.lognormal(8000, 0.3))
            ents["consignees"].append(new)
            if cc == "KG":
                small = [c for c in codes if VALUE_PER_KG[c] >= 1000] or ["85423100"]
                for day in self.days("2025-07-05", "2026-06-25", 26):
                    self.ship(e, new, day, r.choice(small), value=r.uniform(300, 1500), mode=r.choice([4, 5]))
                units["D7"] = [("C", new)]
            self.record(f"G6-{i + 1}", "injected", "Shipments to Russia stopping by 24 February 2022 and moving to "
                        f"a consignee in {scope.country_in(cc)}", units, ents,
                        "built so the Russia volume moves to a consignee first seen before 2022, which D6 does not "
                        "count" if near else None)
        # L6: lost Russia customers, new ordinary customers in a corridor.
        for i, cc in enumerate(["TR", "AE", "GE"]):
            e = self.pick_exporters(1)[0]
            codes = self.radar_codes(e)[:2]
            ru = self.new_consignee("RU")
            for day in self.days("2021-01-10", "2022-02-18", r.randint(28, 34)):
                self.ship(e, ru, day, r.choice(codes), value=r.lognormal(8000, 0.3))
            new = self.new_consignee(cc)
            for day in self.days("2022-05-01", "2026-06-20", r.randint(80, 90)):
                self.ship(e, new, day, r.choice(codes), value=r.lognormal(8000, 0.3))
            self.record(f"L6-{i + 1}", "look-alike", f"An exporter that lost its Russia customer and found an ordinary "
                        f"new customer in {scope.country_in(cc)}", {"D6": [("E", e.idx)]},
                        {"exporters": [e.idx], "consignees": [ru, new]})

        # G7: small, frequent shipments to one consignee.
        for i, (cc, first, n_exp, spread) in enumerate([("KG", "2024-02-10", 1, False), ("AM", "2023-11-20", 2, False),
                                                         ("KZ", "2024-09-15", 1, True)]):
            exps = self.pick_exporters(n_exp, sectors=("electronics",))
            con = self.new_consignee(cc)
            for k, day in enumerate(self.days(first, "2025-05-30", 3)):
                self.ship(exps[0], con, day, self.radar_codes(exps[0])[0])
            a, n = ("2024-10-01", 30) if spread else ("2025-07-05", r.randint(26, 30))
            for k, day in enumerate(self.days(a, "2026-06-25", n)):
                e = exps[k % n_exp]
                small = [c for c in self.radar_codes(e) if VALUE_PER_KG[c] >= 1000] or ["85423100"]
                self.ship(e, con, day, r.choice(small), value=r.uniform(250, 1500), mode=r.choice([4, 5]))
            self.record(f"G7-{i + 1}", "injected", f"Small, frequent shipments of the radar's goods to a consignee in "
                        f"{scope.country_in(cc)}", {"D7": [("C", con)]}, {"exporters": [e.idx for e in exps], "consignees": [con]},
                        "built with the shipments spread over 21 months, so fewer than 20 fall in the window" if spread else None)
        # L7: spare-parts subscriptions.
        for i, (cc, code) in enumerate([("TR", "85423300"), ("AE", "85322100"), ("GE", "85423900")]):
            e = self.pick_exporters(1, sectors=("electronics",))[0]
            con = self.new_consignee(cc)
            for day in self.days("2022-01-10", "2026-06-25", r.randint(120, 135)):
                self.ship(e, con, day, code, value=r.uniform(300, 1700 if VALUE_PER_KG[code] >= 1000 else 750), mode=4)
            self.record(f"L7-{i + 1}", "look-alike", f"A spare-parts subscription to a consignee in {scope.country_in(cc)}",
                        {"D7": [("C", con)]}, {"exporters": [e.idx], "consignees": [con]})

    def build(self):
        self._build_parties()
        self._link_distributors()
        self._background()
        self._inject()
        return self


@dataclass
class Synthetic:
    """The generated world: records in object form, entity tables and ground truth, all with public ids."""
    seed: int
    records: list
    exporters: list
    consignees: list
    forwarders: list
    representatives: list
    truth: list


def generate(seed: int = SEED) -> Synthetic:
    """Build the world for a seed and return it with public ids. Same seed, same world."""
    w = World(seed).build()
    ships = sorted(w.shipments, key=lambda s: (s.day, s.seq))
    first_e, first_c, first_f, first_r = {}, {}, {}, {}
    for s in ships:
        first_e.setdefault(s.exporter, s.day)
        first_c.setdefault(s.consignee, s.day)
        if s.forwarder is not None:
            first_f.setdefault(s.forwarder, s.day)
    e_ids = {i: f"EXP-{n + 1:04d}" for n, i in enumerate(sorted(first_e, key=lambda i: (first_e[i], i)))}
    c_ids = {i: f"CON-{n + 1:04d}" for n, i in enumerate(sorted(first_c, key=lambda i: (first_c[i], i)))}
    perm = w.rng.sample(range(len(w.forwarders)), len(w.forwarders))
    f_ids = {i: f"FWD-{perm[i] + 1:04d}" for i in range(len(w.forwarders))}
    rperm = w.rng.sample(range(len(w.reps)), len(w.reps))
    r_ids = {i: f"REP-{rperm[i] + 1:04d}" for i in range(len(w.reps))}
    g_order = []
    for i in sorted(e_ids, key=lambda i: e_ids[i]):
        g = w.exporters[i].group
        if g not in g_order:
            g_order.append(g)
    g_ids = {g: f"GRP-{n + 1:04d}" for n, g in enumerate(g_order)}

    records, n_decl = [], 0
    for s in ships:
        n_decl += 1
        e = w.exporters[s.exporter]
        dest = w.consignees[s.consignee]["country"]
        for k, it in enumerate(s.items, start=1):
            records.append({
                "record_type": "synthetic export declaration item", "synthetic": True,
                "declaration_ref": f"SYN-DEC-{n_decl:06d}", "goods_item": k,
                "acceptance_date": s.day.isoformat(), "declaration_type": "EX", "additional_declaration_type": "A",
                "procedure_code": s.procedure, "exporter_id": e_ids[s.exporter], "consignee_id": c_ids[s.consignee],
                "representative_id": r_ids[e.rep] if e.rep is not None else None,
                "representative_status": e.rep_status if e.rep is not None else None,
                "forwarder_id": f_ids[s.forwarder] if s.forwarder is not None else None,
                "destination": dest, "routing": list(s.routing), "commodity_code": it["code"],
                "description": scope.GOODS[it["code"]], "net_mass_kg": it["mass"],
                "supplementary_units": it["units"], "statistical_value_gbp": it["value"],
                "mode_border": s.mode_border, "mode_inland": s.mode_inland,
                "documents": [] if it["doc"] is None else [{"code": it["doc"][0], "ref": f"SYN-DOC-{it['doc'][1]:06d}",
                                                            "status": it["doc"][2]}],
            })

    def unit(u):
        kind = u[0]
        if kind == "C":
            return f"C:{c_ids[u[1]]}"
        if kind == "F":
            return f"F:{f_ids[u[1]]}"
        if kind == "E":
            return f"E:{e_ids[u[1]]}"
        if kind == "R":
            return f"R:{e_ids[u[1]]}|{u[2]}|{u[3]}"
        if kind == "P":
            return f"P:{e_ids[u[1]]}|{c_ids[u[2]]}|{u[3]}"
        if kind == "S":
            return f"S:{e_ids[u[1]]}|{c_ids[u[2]]}|{u[3]}|{u[4]}"
        raise ValueError(u)

    truth = []
    for t in w.truth:
        truth.append({**t, "units": {d: [unit(u) for u in us] for d, us in t["units"].items()},
                      "entities": {"exporters": sorted(e_ids[i] for i in t["entities"].get("exporters", [])),
                                   "consignees": sorted(c_ids[i] for i in t["entities"].get("consignees", [])),
                                   "forwarders": sorted(f_ids[i] for i in t["entities"].get("forwarders", []))}})
    exporters = [{"id": e_ids[e.idx], "sector": e.sector, "group": g_ids[e.group]}
                 for e in sorted(w.exporters, key=lambda e: e_ids.get(e.idx, "~")) if e.idx in e_ids]
    consignees = [{"id": c_ids[i], "country": c["country"]} for i, c in enumerate(w.consignees) if i in c_ids]
    consignees.sort(key=lambda c: c["id"])
    forwarders = sorted(({"id": f_ids[i], "tier": f["tier"].replace("reserved", "small")}
                         for i, f in enumerate(w.forwarders)), key=lambda f: f["id"])
    reps = [{"id": r_ids[i]} for i in sorted(r_ids, key=lambda i: r_ids[i])]
    return Synthetic(seed, records, exporters, consignees, forwarders, reps, sorted(truth, key=_truth_order))


def _truth_order(t: dict):
    p = t["pattern"]
    return (p[0] != "G", int(p[1:]), int(t["id"].split("-")[1]))
