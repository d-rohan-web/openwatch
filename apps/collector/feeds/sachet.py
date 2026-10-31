"""NDMA SACHET: all-agency CAP disaster alerts for India (IMD, CWC, INCOIS, SDMAs …)."""
from __future__ import annotations

from lxml import etree

from apps.collector.feed import Feed
from packages.common.geo import district
from packages.contracts.record import record

RSS = "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml"
CAP = "{urn:oasis:names:tc:emergency:cap:1.2}"
SEVERITY = {"Extreme": "critical", "Severe": "warning", "Moderate": "advisory", "Minor": "info", "Unknown": "info"}

_cap_cache: dict[str, dict] = {}  # CAP messages never change once issued; fetch each identifier once


def parse_cap(xml: bytes) -> dict:
    root = etree.fromstring(xml)
    infos = root.findall(f"{CAP}info")
    info = next((i for i in infos if (i.findtext(f"{CAP}language") or "").lower().startswith("en")), infos[0])
    t = lambda el, tag: (el.findtext(f"{CAP}{tag}") or "").strip() or None
    areas = [a.findtext(f"{CAP}areaDesc") or "" for a in info.findall(f"{CAP}area")]
    return {"identifier": t(root, "identifier"), "sender": t(root, "sender"), "sent": t(root, "sent"),
            "msg_type": t(root, "msgType"), "event": t(info, "event"), "category": t(info, "category"),
            "urgency": t(info, "urgency"), "cap_severity": t(info, "severity"), "certainty": t(info, "certainty"),
            "effective": t(info, "effective"), "expires": t(info, "expires"), "headline": t(info, "headline"),
            "description": t(info, "description"), "instruction": t(info, "instruction"),
            "areas": [a.strip() for a in ",".join(areas).split(",") if a.strip()]}


def to_record(guid: str, cap: dict, link: str, raw_sha: str | None) -> dict:
    places = [d for d in (district(a) for a in cap["areas"]) if d]
    pt = places[0] if places else None
    geom = {"type": "MultiPoint", "coordinates": [[d["lon"], d["lat"]] for d in places]} if len(places) > 1 else None
    r = record(guid, title=cap["headline"] or cap["event"] or "Alert", kind=(cap["category"] or "alert").lower(),
               lon=pt and pt["lon"], lat=pt and pt["lat"], geometry=geom, observed_at=cap["sent"],
               severity=SEVERITY.get(cap["cap_severity"] or "", "info"), link=link, **cap)
    if raw_sha:
        r["raw_sha256"] = raw_sha
    return r


async def fetch(ctx) -> list[dict]:
    rss = etree.fromstring((await ctx.get(RSS, raw_ext="xml")).content)
    out = []
    for item in rss.iter("item"):
        guid, link = item.findtext("guid"), item.findtext("link")
        if guid not in _cap_cache:
            r = await ctx.get(link, raw_ext="xml")
            _cap_cache[guid] = {"cap": parse_cap(r.content), "sha": ctx.raw_sha}
        c = _cap_cache[guid]
        out.append(to_record(guid, c["cap"], link, c["sha"]))
    return out


FEED = Feed(id="sachet", label="Disaster alerts (NDMA SACHET)", section="hazards",
            homepage="https://sachet.ndma.gov.in/", terms="Public domain (feed <copyright>); NDMA / issuing agencies",
            every=120, fetch=fetch)
