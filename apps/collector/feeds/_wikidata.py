"""Shared Wikidata Query Service plumbing for the static-infrastructure feeds (not a feed: `_` modules are skipped)."""
from __future__ import annotations

import json
import re

URL = "https://query.wikidata.org/sparql"
TERMS = "Wikidata (CC0)"
# label service: English first, then multilingual and Indian-language labels before it falls back to the QID
LABEL = 'SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mul,hi,ta,te,kn,ml,mr,bn,gu,pa,or,as,ur". }'
_POINT = re.compile(r"Point\(([-\d.eE+]+) ([-\d.eE+]+)\)")


async def query(ctx, sparql: str) -> bytes:
    # WDQS can take 20-40 s on a cold cache; its own limit is 60 s.
    r = await ctx.get(URL, params={"query": sparql}, headers={"Accept": "application/sparql-results+json"}, timeout=90)
    return r.content


def items(body: bytes) -> dict[str, dict[str, list[str]]]:
    """SPARQL JSON → qid → variable → distinct values in first-seen order (each OPTIONAL multiplies rows).

    Needs an ?item variable; entity URIs are shortened to QIDs."""
    out: dict[str, dict[str, list[str]]] = {}
    for b in json.loads(body)["results"]["bindings"]:
        d = out.setdefault(b["item"]["value"].rsplit("/", 1)[1], {})
        for k, v in b.items():
            val = v["value"].removeprefix("http://www.wikidata.org/entity/")
            vals = d.setdefault(k, [])
            if val not in vals:
                vals.append(val)
    return out


def point(wkt: str) -> tuple[float, float]:
    m = _POINT.search(wkt)
    return float(m[1]), float(m[2])


def common(qid: str, d: dict[str, list[str]]) -> dict:
    """record() kwargs every Wikidata feed shares: location, title, qid, link, operator, inception."""
    lon, lat = point(d["coord"][0])
    label = first(d, "itemLabel")
    label = None if label == qid else label  # the label service falls back to the QID
    return dict(lon=lon, lat=lat, title=label or qid, qid=qid, link=f"https://www.wikidata.org/wiki/{qid}",
                label=label, operator=", ".join(d.get("operatorLabel", [])) or None,
                inception=(first(d, "inception") or "")[:10] or None)


def first(d: dict[str, list[str]], k: str) -> str | None:
    return d[k][0] if d.get(k) else None
