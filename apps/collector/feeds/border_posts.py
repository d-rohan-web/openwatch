"""India's land border crossings, check posts and border railway stations, from Wikidata."""
from __future__ import annotations

from apps.collector.feed import Feed
from apps.collector.feeds import _wikidata as wd
from packages.contracts.record import record

# border crossing, border checkpoint (where nearly all Indian ones sit, incl. passes like Shipki La), border train
# station, railway border crossing
CLASSES = ("Q55599109", "Q757292", "Q1402443", "Q115110263")

QUERY = """SELECT ?item ?itemLabel ?classLabel ?coord ?operatorLabel ?neighbourLabel ?inception WHERE {
  VALUES ?class { %s }
  ?item wdt:P31 ?class; wdt:P17 wd:Q668; wdt:P625 ?coord.
  FILTER NOT EXISTS { ?item wdt:P576 [] }
  OPTIONAL { { ?item wdt:P17 ?neighbour FILTER(?neighbour != wd:Q668) }
             UNION { ?item wdt:P47 ?neighbour. ?neighbour wdt:P31 wd:Q6256 FILTER(?neighbour != wd:Q668) } }
  OPTIONAL { ?item wdt:P137 ?operator }
  OPTIONAL { ?item wdt:P571 ?inception }
  %s
}""" % (" ".join(f"wd:{q}" for q in CLASSES), wd.LABEL)


def parse(body: bytes) -> list[dict]:
    return [record(qid, kind="crossing", classes=d.get("classLabel"),
                   neighbour=", ".join(d.get("neighbourLabel", [])) or None, **wd.common(qid, d))
            for qid, d in wd.items(body).items()]


async def fetch(ctx) -> list[dict]:
    return parse(await wd.query(ctx, QUERY))


FEED = Feed(id="border_posts", label="Border crossings (Wikidata)", section="defence",
            homepage="https://www.wikidata.org/wiki/Q757292", terms=wd.TERMS, every=7 * 86400, fetch=fetch)
