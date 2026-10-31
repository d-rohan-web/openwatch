"""Nuclear power plants, reactors, uranium mines and nuclear research sites in India, from Wikidata."""
from __future__ import annotations

from apps.collector.feed import Feed
from apps.collector.feeds import _wikidata as wd
from packages.contracts.record import record

# Nuclear classes that Indian items actually use (probed over the subclass trees of nuclear facility/plant/reactor).
KINDS = {
    "Q134447": "power_plant",                                          # nuclear power plant
    "Q80877": "reactor", "Q16624467": "reactor", "Q1438105": "reactor",  # reactor, fast breeder, research reactor
    "Q28599311": "mine",                                               # uranium mine
    "Q64785417": "fuel_cycle", "Q244990": "fuel_cycle",                # reprocessing site, interim waste repository
    "Q188589": "research", "Q109909183": "research",                   # tokamak, nuclear research institute
    "Q1739545": "other_nuclear",                                       # nuclear facility
}
# Generic classes most Indian sites actually carry (BARC is a "research center", Jaduguda a "mine"): kept only when
# the item's own label says nuclear/atomic/uranium/cyclotron.
GENERIC = {"Q820477": "mine", "Q31855": "research", "Q7315155": "research", "Q327333": "research"}
ORDER = ("power_plant", "reactor", "mine", "fuel_cycle", "research", "other_nuclear")

QUERY = """SELECT ?item ?itemLabel ?class ?classLabel ?coord ?operatorLabel ?mw ?inception ?stateLabel WHERE {
  { VALUES ?class { %s } ?item wdt:P31 ?class. }
  UNION
  { VALUES ?class { %s } ?item wdt:P31 ?class; wdt:P17 wd:Q668; rdfs:label ?l.
    FILTER(LANG(?l) = "en" && (CONTAINS(LCASE(?l), "nuclear") || CONTAINS(LCASE(?l), "atomic")
           || CONTAINS(LCASE(?l), "uranium") || CONTAINS(LCASE(?l), "cyclotron"))) }
  ?item wdt:P17 wd:Q668; wdt:P625 ?coord.
  OPTIONAL { ?item wdt:P137 ?operator }
  OPTIONAL { ?item p:P2109/psn:P2109/wikibase:quantityAmount ?w BIND(?w / 1000000 AS ?mw) }
  OPTIONAL { ?item wdt:P571 ?inception }
  OPTIONAL { ?item wdt:P5817 ?state }
  %s
}""" % (" ".join(f"wd:{q}" for q in KINDS), " ".join(f"wd:{q}" for q in GENERIC), wd.LABEL)


def parse(body: bytes) -> list[dict]:
    out = []
    for qid, d in wd.items(body).items():
        kinds = [k for c in d["class"] if (k := KINDS.get(c) or GENERIC.get(c))]
        mw = wd.first(d, "mw")
        out.append(record(qid, kind=min(kinds, key=ORDER.index) if kinds else "other_nuclear",
                          classes=d.get("classLabel"), capacity_mw=round(float(mw), 1) if mw else None,
                          status=wd.first(d, "stateLabel"), **wd.common(qid, d)))
    return out


async def fetch(ctx) -> list[dict]:
    return parse(await wd.query(ctx, QUERY))


FEED = Feed(id="nuclear", label="Nuclear sites (Wikidata)", section="infrastructure",
            homepage="https://www.wikidata.org/wiki/Q134447", terms=wd.TERMS, every=7 * 86400, fetch=fetch)
