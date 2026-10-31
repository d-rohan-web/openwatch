"""Indian airports and heliports from OurAirports (public domain)."""
from __future__ import annotations

import csv
import io

from apps.collector.feed import Feed
from packages.contracts.record import record

URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
TYPES = {"large_airport", "medium_airport", "small_airport", "heliport"}


def parse(body: bytes) -> list[dict]:
    out = []
    for a in csv.DictReader(io.StringIO(body.decode("utf-8"))):
        if a["iso_country"] != "IN" or a["type"] not in TYPES:
            continue
        out.append(record(a["ident"], title=a["name"], kind=a["type"], lon=a["longitude_deg"], lat=a["latitude_deg"],
                          ident=a["ident"], icao=a["icao_code"] or a["gps_code"] or None, iata=a["iata_code"] or None,
                          elevation_ft=int(a["elevation_ft"]) if a["elevation_ft"] else None, region=a["iso_region"],
                          municipality=a["municipality"] or None, scheduled=a["scheduled_service"] == "yes",
                          wikipedia=a["wikipedia_link"] or None, link=f"https://ourairports.com/airports/{a['ident']}/"))
    return out


async def fetch(ctx) -> list[dict]:
    return parse((await ctx.get(URL)).content)


# keep_raw off: the 12 MB worldwide CSV changes daily, and OurAirports keeps its own history on GitHub.
FEED = Feed(id="airports", label="Airports & heliports (OurAirports)", section="air", homepage="https://ourairports.com/",
            terms="Public domain (OurAirports)", every=7 * 86400, fetch=fetch, keep_raw=False)
