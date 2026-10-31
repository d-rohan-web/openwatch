"""TomTom Traffic Incident Details v5: accidents, jams, closures and roadworks in India's major metros."""
from __future__ import annotations

from apps.collector.feed import Feed
from packages.contracts.record import record

API = "https://api.tomtom.com/traffic/services/5/incidentDetails"
FIELDS = ("{incidents{type,geometry{type,coordinates},properties{id,iconCategory,magnitudeOfDelay,"
          "events{description,code,iconCategory},startTime,endTime,from,to,length,delay,roadNumbers}}}")
# lon_min, lat_min, lon_max, lat_max: each under TomTom's 10,000 km² bbox limit
CITIES = {
    "Delhi NCR": (76.80, 28.30, 77.65, 28.90),
    "Mumbai": (72.75, 18.85, 73.20, 19.50),
    "Bengaluru": (77.35, 12.75, 77.85, 13.25),
    "Chennai": (80.05, 12.80, 80.35, 13.25),
    "Kolkata": (88.20, 22.40, 88.55, 22.75),
    "Hyderabad": (78.25, 17.25, 78.70, 17.65),
    "Pune": (73.70, 18.40, 74.05, 18.70),
    "Ahmedabad": (72.45, 22.90, 72.75, 23.15),
}
# https://developer.tomtom.com/traffic-api/documentation/traffic-incidents/incident-details
KIND = {0: "unknown", 1: "accident", 2: "fog", 3: "dangerous_conditions", 4: "rain", 5: "ice", 6: "jam",
        7: "lane_closed", 8: "closure", 9: "roadworks", 10: "wind", 11: "flooding", 14: "broken_down_vehicle"}
SEVERITY = {0: "info", 1: "info", 2: "advisory", 3: "warning", 4: "advisory"}  # 4 = undefined (closures etc.)


def parse(d: dict, city: str) -> list[dict]:
    out = []
    for f in d.get("incidents") or []:
        p, g = f["properties"], f["geometry"]
        line = g["type"] == "LineString"
        lon, lat = g["coordinates"][len(g["coordinates"]) // 2] if line else g["coordinates"]
        kind = KIND.get(p.get("iconCategory"), "unknown")
        desc = "; ".join(e["description"] for e in p.get("events") or [] if e.get("description"))
        where = " → ".join(x for x in (p.get("from"), p.get("to")) if x)
        out.append(record(p["id"], title=f"{desc or kind.replace('_', ' ').title()}" + (f": {where}" if where else ""),
                          kind=kind, lon=lon, lat=lat, geometry=g if line else None, observed_at=p.get("startTime"),
                          severity=SEVERITY.get(p.get("magnitudeOfDelay"), "info"), city=city,
                          magnitude=p.get("magnitudeOfDelay"), description=desc or None, **{"from": p.get("from")},
                          to=p.get("to"), delay_s=p.get("delay"), length_m=p.get("length"),
                          roads=p.get("roadNumbers") or None, end=p.get("endTime")))
    return out


async def fetch(ctx) -> list[dict]:
    out = []
    for city, bbox in CITIES.items():
        params = {"key": ctx.key, "bbox": ",".join(map(str, bbox)), "fields": FIELDS, "language": "en-GB",
                  "timeValidityFilter": "present"}
        out += parse((await ctx.get(API, params=params, raw_ext="json")).json(), city)
    return out


FEED = Feed(id="road_incidents", label="Road incidents (TomTom)", section="infrastructure",
            homepage="https://developer.tomtom.com/traffic-api", key="TOMTOM_KEY",
            terms="© TomTom; TomTom API terms (display only, no redistribution/storage beyond caching)",
            every=600, fetch=fetch, keep_raw=False)  # TomTom terms restrict storing their data
