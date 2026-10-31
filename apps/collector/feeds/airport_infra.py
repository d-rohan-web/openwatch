"""Runways and radio navaids in India from OurAirports (public domain)."""
from __future__ import annotations

import csv
import io

from apps.collector.feed import Feed
from packages.contracts.record import record

BASE = "https://davidmegginson.github.io/ourairports-data"


def _rows(body: bytes) -> csv.DictReader:
    return csv.DictReader(io.StringIO(body.decode("utf-8")))


def _num(v: str, t=float):
    return t(float(v)) if v else None


def parse(airports: bytes, runways: bytes, navaids: bytes) -> list[dict]:
    ports = {a["id"]: a for a in _rows(airports) if a["iso_country"] == "IN"}
    out = []
    for r in _rows(runways):
        a = ports.get(r["airport_ref"])
        if not a:
            continue
        ends = (r["le_longitude_deg"], r["le_latitude_deg"], r["he_longitude_deg"], r["he_latitude_deg"])
        if all(ends):
            le, he = (float(ends[0]), float(ends[1])), (float(ends[2]), float(ends[3]))
            geom = {"type": "LineString", "coordinates": [list(le), list(he)]}
            lon, lat = (le[0] + he[0]) / 2, (le[1] + he[1]) / 2
        else:  # no threshold coordinates: pin it on the airport
            geom, lon, lat = None, a["longitude_deg"], a["latitude_deg"]
        name = "/".join(x for x in (r["le_ident"], r["he_ident"]) if x)
        out.append(record(f"rwy-{r['id']}", title=f"{a['name']} runway {name}".strip(), kind="runway", lon=lon, lat=lat,
                          geometry=geom, airport_ident=a["ident"], airport_name=a["name"],
                          length_ft=_num(r["length_ft"], int), width_ft=_num(r["width_ft"], int),
                          surface=r["surface"] or None, lighted=r["lighted"] == "1", closed=r["closed"] == "1",
                          le_ident=r["le_ident"] or None, he_ident=r["he_ident"] or None,
                          le_heading_degT=_num(r["le_heading_degT"]), he_heading_degT=_num(r["he_heading_degT"])))
    for n in _rows(navaids):
        if n["iso_country"] != "IN" or not n["latitude_deg"]:
            continue
        out.append(record(f"nav-{n['id']}", title=f"{n['name']} {n['type']} {n['ident']}", kind=n["type"].lower(),
                          lon=n["longitude_deg"], lat=n["latitude_deg"], ident=n["ident"], name=n["name"],
                          frequency_khz=_num(n["frequency_khz"], int), elevation_ft=_num(n["elevation_ft"], int),
                          associated_airport=n["associated_airport"] or None))
    return out


async def fetch(ctx) -> list[dict]:
    return parse(*[(await ctx.get(f"{BASE}/{f}.csv")).content for f in ("airports", "runways", "navaids")])


# keep_raw off: worldwide CSVs, several MB each; OurAirports keeps its own history on GitHub.
FEED = Feed(id="airport_infra", label="Runways & navaids (OurAirports)", section="air",
            homepage="https://ourairports.com/", terms="Public domain (OurAirports)", every=7 * 86400, fetch=fetch,
            keep_raw=False)
