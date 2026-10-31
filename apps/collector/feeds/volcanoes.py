"""Smithsonian GVP / USGS Weekly Volcanic Activity Report, kept to the coverage region (Barren Island, Sumatra, …)."""
from __future__ import annotations

import re
from email.utils import parsedate_to_datetime

from lxml import etree

from apps.collector.feed import Feed
from packages.common.geo import in_bbox
from packages.contracts.record import record

URL = "https://volcano.si.edu/news/WeeklyVolcanoRSS.xml"
NS = {"georss": "http://www.georss.org/georss"}


def parse(xml: bytes) -> list[dict]:
    out = []
    for it in etree.fromstring(xml).iter("item"):
        pt = it.findtext("georss:point", namespaces=NS)
        if not pt:
            continue
        lat, lon = map(float, pt.split())
        if not in_bbox(lon, lat):
            continue
        title = it.findtext("title").strip()
        status = title.rsplit(" - ", 1)[-1]
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", it.findtext("description") or "")).strip()
        out.append(record(it.findtext("guid").rsplit("#", 1)[-1], title=title, kind="volcano", lon=lon, lat=lat,
                          observed_at=parsedate_to_datetime(it.findtext("pubDate")),
                          severity="advisory" if status.startswith("New") else "info",
                          volcano=title.split(" (", 1)[0], status=status, report=text, link=it.findtext("guid")))
    return out


async def fetch(ctx) -> list[dict]:
    return parse((await ctx.get(URL)).content)


FEED = Feed(id="volcanoes", label="Volcanoes (Smithsonian GVP weekly)", section="hazards",
            homepage="https://volcano.si.edu/reports_weekly.cfm",
            terms="Smithsonian GVP / USGS Weekly Volcanic Activity Report; free use with citation of the Smithsonian "
                  "Institution Global Volcanism Program", every=21600, fetch=fetch)
