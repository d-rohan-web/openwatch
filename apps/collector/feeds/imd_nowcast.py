"""IMD district nowcast (next ~3 h), from the WFS layer behind mausam.imd.gov.in's district nowcast map.

The documented api/nowcast_district_api.php is IP-whitelisted; this is the public GeoServer the website itself uses.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apps.collector.feed import Feed
from packages.common.geo import district
from packages.contracts.record import record

CATS = {1: "No warning", 2: "Light rain", 3: "Light snow", 4: "Light thunderstorm", 5: "Slight dust storm",
        6: "Low lightning probability", 7: "Moderate rain", 8: "Moderate snow", 9: "Moderate thunderstorm",
        10: "Moderate dust storm", 11: "Moderate lightning probability", 12: "Heavy rain", 13: "Heavy snow",
        14: "Severe thunderstorm", 15: "Very severe thunderstorm", 17: "Thunderstorm with hail",
        18: "Severe dust storm", 19: "High lightning probability"}  # cat16 is free text
PROPS = ["District", "State", "Date", "toi", "vupto", "Color", "message", "impact", "action", "update_time", "cat16"] + \
        [f"cat{i}" for i in CATS]
URL = ("https://reactjs.imd.gov.in/geoserver/imd/ows?service=WFS&version=1.1.0&request=GetFeature"
       "&typename=imd:NowcastWarningDistrict&outputFormat=application/json&propertyName=" + ",".join(PROPS))
IST = timezone(timedelta(hours=5, minutes=30))
COLOR = {2: "advisory", 3: "warning", 4: "critical"}  # nowcast scale runs the other way: 1 green … 4 red


def _at(day: str, hhmm: str) -> datetime:
    return datetime.fromisoformat(day).replace(tzinfo=IST) + timedelta(hours=int(hhmm[:2]), minutes=int(hhmm[2:]))


def parse(d: dict, now: datetime) -> list[dict]:
    out = []
    for f in d["features"]:
        p = f["properties"]
        if p.get("Color") not in COLOR or not p.get("Date") or not p.get("District"):
            continue
        issued, until = _at(p["Date"], p["toi"]), _at(p["Date"], p["vupto"])
        if until < issued:
            until += timedelta(days=1)
        if until < now:                            # stale rows linger in the layer after they expire
            continue
        cats = [CATS[i] for i in CATS if i > 1 and p.get(f"cat{i}")] + ([p["cat16"]] if p.get("cat16") else [])
        name = p["District"].strip()
        pt = district(name, p.get("State"))
        out.append(record(name.lower(), title=f"{p.get('message') or ', '.join(cats) or 'Nowcast'}: {name.title()}",
                          kind="nowcast", lon=pt and pt["lon"], lat=pt and pt["lat"], observed_at=issued,
                          severity=COLOR[p["Color"]], district=name, state=p.get("State"), warnings=cats,
                          valid_until=until.isoformat(), impact=p.get("impact") or None,
                          action=p.get("action") or None,
                          link="https://mausam.imd.gov.in/responsive/districtWiseNowcastGIS.php"))
    return out


async def fetch(ctx) -> list[dict]:
    return parse((await ctx.get(URL)).json(), datetime.now(timezone.utc))


FEED = Feed(id="imd_nowcast", label="Nowcast by district (IMD)", section="hazards",
            homepage="https://mausam.imd.gov.in/responsive/districtWiseNowcastGIS.php",
            terms="Government of India public page; attribution: India Meteorological Department (IMD)",
            every=600, fetch=fetch)
