"""National Center for Seismology earthquakes (the "Earthquakes in India" list on riseq.seismo.gov.in, last ~10 days)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from selectolax.lexbor import LexborHTMLParser

from apps.collector.feed import Feed
from apps.collector.feeds.usgs_quakes import severity
from packages.contracts.record import record

URL = "https://riseq.seismo.gov.in/"
IST = timezone(timedelta(hours=5, minutes=30))


def parse(html: str) -> list[dict]:
    out = []
    for li in LexborHTMLParser(html).css("li.event_list[data-json]"):
        j = json.loads(li.attributes["data-json"])
        lat, lon = (float(x) for x in j["lat_long"].split(","))
        mag, depth = (float(x) for x in re.findall(r"[\d.]+", j["magnitude_depth"])[:2])
        place = j["event_name"].split(" - ", 1)[-1]
        t = datetime.strptime(j["origin_time"].removesuffix(" IST"), "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
        out.append(record(li.attributes.get("id") or j["event_id"], title=f"M {mag:g} - {place}", kind="earthquake",
                          lon=lon, lat=lat, observed_at=t, severity=severity(mag), mag=mag, depth_km=depth,
                          place=place, status=j.get("event_type"),
                          link=f"https://riseq.seismo.gov.in/riseq/earthquake/event/{j['event_id']}/{j.get('event_type')}"))
    return out


async def fetch(ctx) -> list[dict]:
    return parse((await ctx.get(URL)).text)


FEED = Feed(id="ncs_quakes", label="Earthquakes (NCS)", section="hazards", homepage="https://riseq.seismo.gov.in/",
            terms="Government of India public page; attribution: National Center for Seismology (NCS), MoES",
            every=300, fetch=fetch)
