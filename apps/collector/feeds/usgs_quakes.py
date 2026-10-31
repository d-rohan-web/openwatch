"""USGS earthquakes (past week, M2.5+) around India — cross-check for NCS."""
from __future__ import annotations

from apps.collector.feed import Feed
from packages.common.geo import in_bbox
from packages.contracts.record import record

URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_week.geojson"


def severity(mag: float | None) -> str:
    m = mag or 0
    return "critical" if m >= 6.5 else "warning" if m >= 5 else "advisory" if m >= 4 else "info"


def parse(d: dict) -> list[dict]:
    out = []
    for f in d["features"]:
        lon, lat, depth = f["geometry"]["coordinates"]
        if not in_bbox(lon, lat):
            continue
        p = f["properties"]
        out.append(record(f["id"], title=p["title"], kind="earthquake", lon=lon, lat=lat,
                          observed_at=p["time"] / 1000, severity=severity(p["mag"]), mag=p["mag"],
                          depth_km=depth, place=p["place"], tsunami=p["tsunami"], alert=p.get("alert"),
                          link=p["url"]))
    return out


async def fetch(ctx) -> list[dict]:
    return parse((await ctx.get(URL)).json())


FEED = Feed(id="usgs_quakes", label="Earthquakes (USGS)", section="hazards",
            homepage="https://earthquake.usgs.gov/earthquakes/feed/", terms="Public domain (USGS)",
            every=120, fetch=fetch)
