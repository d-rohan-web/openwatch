"""IODA (Georgia Tech): Internet outage events for India and its states, last 24 h."""
from __future__ import annotations

import time
from collections import defaultdict
from functools import cache

from apps.collector.feed import Feed
from packages.common.geo import _districts
from packages.contracts.record import iso, record

API = "https://api.ioda.inetintel.cc.gatech.edu/v2/outages/events"
# IODA (NetAcuity) region name → state name in districts.json (2011 census spellings)
ALIAS = {"Delhi": "NCT of Delhi", "Orissa": "Odisha", "Uttaranchal": "Uttarakhand", "Arunachal Pradesh": "Arunanchal Pradesh",
         "Jammu and Kashmir": "Jammu & Kashmir", "Andaman and Nicobar": "Andaman & Nicobar Island",
         "Dadra and Nagar Haveli": "Dadara & Nagar Havelli", "Daman and Diu": "Daman & Diu"}
# States carved out after 2011: their districts still sit under the parent in districts.json
CARVED = {"Telangana": ("Andhra Pradesh", {"Adilabad", "Hyderabad", "Karimnagar", "Khammam", "Mahbubnagar", "Medak",
                                           "Nalgonda", "Nizamabad", "Rangareddy", "Warangal"}),
          "Ladakh": ("Jammu & Kashmir", {"Leh (ladakh)", "Kargil"})}


@cache
def centroids() -> dict[str, tuple[float, float]]:
    """State name → (lon, lat): mean of its district points."""
    pts = defaultdict(list)
    for r in _districts().values():
        state = next((new for new, (old, names) in CARVED.items() if r["state"] == old and r["name"] in names), r["state"])
        pts[state].append((r["lon"], r["lat"]))
    return {s: (sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v)) for s, v in pts.items()}


def severity(e: dict) -> str:
    # ponytail: IODA scores are unitless; thresholds are a rough eyeball, tune once we've watched a few weeks
    if e["location"].startswith("country/"):
        return "warning"
    return "advisory" if (e.get("score") or 0) >= 100 else "info"


def parse(d: dict) -> list[dict]:
    out = []
    for e in d["data"]:
        name = e.get("location_name") or e["location"]
        pt = centroids().get(ALIAS.get(name, name))
        out.append(record(f'{e["location"]}:{e["datasource"]}:{e["start"]}', title=f"Internet outage: {name}",
                          kind="internet_outage", lon=pt and pt[0], lat=pt and pt[1], observed_at=e["start"],
                          severity=severity(e), entity=e["location"], name=name, datasource=e["datasource"],
                          method=e.get("method"), score=e.get("score"), duration_s=e.get("duration"),
                          end=iso(e["start"] + (e.get("duration") or 0)), overlaps_window=e.get("overlaps_window"),
                          link=f'https://ioda.inetintel.cc.gatech.edu/{e["location"]}'))
    return out


async def fetch(ctx) -> list[dict]:
    until = int(time.time())
    win = f"from={until - 86400}&until={until}"
    out = parse((await ctx.get(f"{API}?entityType=country&entityCode=IN&{win}")).json())
    return out + parse((await ctx.get(f"{API}?entityType=region&relatedTo=country/IN&{win}")).json())


FEED = Feed(id="ioda", label="Internet outages (IODA)", section="infrastructure",
            homepage="https://ioda.inetintel.cc.gatech.edu/country/IN",
            terms="© Georgia Tech Research Corporation, all rights reserved (API notice); attribute IODA",
            every=600, fetch=fetch)
