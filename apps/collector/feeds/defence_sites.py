"""Publicly documented defence installations in India (air/naval bases, academies, cantonments), from Wikidata."""
from __future__ import annotations

import re

from apps.collector.feed import Feed
from apps.collector.feeds import _wikidata as wd
from packages.contracts.record import record

KINDS = {
    "Q695850": "airbase", "Q6981985": "airbase",                            # airbase, naval airbase
    "Q1324633": "naval_base", "Q331367": "naval_base",                      # naval base, submarine base
    "Q917182": "academy", "Q1522839": "academy", "Q4698330": "academy",     # military/air force academy, staff college
    "Q245016": "military_base", "Q2604714": "military_base",                # military base, forward operating base
    "Q57178953": "cantonment", "Q111212994": "cantonment",                  # cantonment town, cantonment in India
}
ORDER = ("airbase", "naval_base", "academy", "military_base", "cantonment")
# Old forts are often tagged "military base" with nothing else; a fort/qila/durg name marks them historical.
FORT = re.compile(r"\b(fort|qila|kila|quila|durg)\b", re.I)
BRANCHES = ((r"\bcoast guard\b", "coast_guard"), (r"\bair\b", "air_force"),
            (r"\bnav(y|al)\b|^(INS|INHS|NAS)\b", "navy"), (r"\barmy\b", "army"))

QUERY = """SELECT ?item ?itemLabel ?class ?coord ?operatorLabel ?icao ?inception WHERE {
  VALUES ?class { %s }
  ?item wdt:P31 ?class; wdt:P17 wd:Q668; wdt:P625 ?coord.
  FILTER NOT EXISTS { ?item wdt:P576 [] }
  FILTER NOT EXISTS { VALUES ?old { wd:Q57821 wd:Q109607 wd:Q16560 wd:Q23413 wd:Q839954 }
                      ?item wdt:P31/wdt:P279* ?old }  # fortification, ruins, palace, castle, archaeological site
  OPTIONAL { ?item wdt:P137 ?operator }
  OPTIONAL { ?item wdt:P239 ?icao }
  OPTIONAL { ?item wdt:P571 ?inception }
  %s
}""" % (" ".join(f"wd:{q}" for q in KINDS), wd.LABEL)


def branch(names: list[str]) -> str | None:
    """From the operators, else the site's own name ("... Air Force Station", "INS ...")."""
    for op in names:
        for pat, b in BRANCHES:
            if re.search(pat, op, re.I):
                return b
    return None


def parse(body: bytes) -> list[dict]:
    out = []
    for qid, d in wd.items(body).items():
        if FORT.search(wd.first(d, "itemLabel") or ""):
            continue
        out.append(record(qid, kind=min((KINDS[c] for c in d["class"]), key=ORDER.index), icao=wd.first(d, "icao"),
                          branch=branch(d.get("operatorLabel", []) + d["itemLabel"]), **wd.common(qid, d)))
    return out


async def fetch(ctx) -> list[dict]:
    return parse(await wd.query(ctx, QUERY))


FEED = Feed(id="defence_sites", label="Defence installations (Wikidata)", section="defence",
            homepage="https://www.wikidata.org/wiki/Q695850", terms="Wikidata (CC0); publicly documented sites only",
            every=7 * 86400, fetch=fetch)
