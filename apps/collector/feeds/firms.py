"""NASA FIRMS active fires over India: VIIRS S-NPP + NOAA-20 near-real-time detections, last 24 h."""
from __future__ import annotations

import csv
import io

from apps.collector.feed import Feed
from packages.common.geo import INDIA_BBOX
from packages.contracts.record import record

# https://firms.modaps.eosdis.nasa.gov/api/area/  /api/area/csv/[MAP_KEY]/[SOURCE]/[west,south,east,north]/[DAY_RANGE]
URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/" + ",".join(map(str, INDIA_BBOX)) + "/1"
SOURCES = {"VIIRS_SNPP_NRT": "N", "VIIRS_NOAA20_NRT": "N20"}
CONFIDENCE = {"l": "low", "n": "nominal", "h": "high"}  # area API abbreviates; the public CSVs spell it out


def parse(text: str, sat: str) -> list[dict]:
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        s, t = r.get("satellite") or sat, r["acq_time"].zfill(4)
        out.append(record(f"{s}_{r['latitude']}_{r['longitude']}_{r['acq_date']}_{t}",
                          title=f"Fire ({r['frp']} MW)", kind="fire", lon=r["longitude"], lat=r["latitude"],
                          observed_at=f"{r['acq_date']}T{t[:2]}:{t[2:]}:00Z", severity="info",
                          frp=float(r["frp"]), confidence=CONFIDENCE.get(r["confidence"], r["confidence"]),
                          brightness=float(r["bright_ti4"]), daynight=r["daynight"], satellite=s))
    return out


async def fetch(ctx) -> list[dict]:
    out = []
    for source, sat in SOURCES.items():
        out += parse((await ctx.get(URL.format(key=ctx.key, source=source), raw_ext="csv")).text, sat)
    return out


FEED = Feed(id="firms", label="Active fires (NASA FIRMS)", section="hazards",
            homepage="https://firms.modaps.eosdis.nasa.gov/",
            terms="NASA FIRMS / LANCE, free and open (cite NASA FIRMS); MAP_KEY required",
            every=900, fetch=fetch, key="FIRMS_MAP_KEY", snapshot=True)
