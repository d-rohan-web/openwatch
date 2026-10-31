"""IMD district-wise weather warnings for today (the WFS layer behind mausam.imd.gov.in's district warnings map).

The documented api/warnings_district_api.php is IP-whitelisted; this is the public GeoServer the website itself uses.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from apps.collector.feed import Feed
from packages.common.geo import district
from packages.contracts.record import record

PROPS = ["District", "Date", "updated_at"] + [f"Day_{i}" for i in range(1, 6)] + [f"Day{i}_Color" for i in range(1, 6)]
URL = ("https://reactjs.imd.gov.in/geoserver/ows?service=WFS&version=1.1.0&request=GetFeature"
       "&typename=imd:district_warnings_india&outputFormat=application/json&propertyName=" + ",".join(PROPS))
# The warnings layer's `state` is blank; the nowcast layer uses the same IMD district names and fills it in.
STATES_URL = ("https://reactjs.imd.gov.in/geoserver/imd/ows?service=WFS&version=1.1.0&request=GetFeature"
              "&typename=imd:NowcastWarningDistrict&outputFormat=application/json&propertyName=District,State")
IST = timezone(timedelta(hours=5, minutes=30))
COLOR = {1: "critical", 2: "warning", 3: "advisory"}  # IMD: 1 red, 2 orange, 3 yellow, 4 green
NAMES = {1: "red", 2: "orange", 3: "yellow", 4: "green"}
TYPES = {"2": "Heavy Rain", "3": "Heavy Snow", "4": "Thunderstorm & Lightning", "5": "Hailstorm", "6": "Dust Storm",
         "7": "Dust Raising Winds", "8": "Strong Surface Winds", "9": "Heat Wave", "10": "Hot Day", "11": "Warm Night",
         "12": "Cold Wave", "13": "Cold Day", "14": "Ground Frost", "15": "Fog", "16": "Very Heavy Rain",
         "17": "Extremely Heavy Rain"}  # code 1 = no warning (from the map page's own legend)


_states: dict[str, str] = {}  # IMD district name → state; fetched once per process


def states(d: dict) -> dict[str, str]:
    return {p["District"].strip(): p["State"] for f in d["features"] if (p := f["properties"]).get("District")}


def parse(d: dict, today: date, state: dict[str, str] | None = None) -> list[dict]:
    out = []
    for f in d["features"]:
        p = f["properties"]
        if not p.get("Date") or not p.get("District"):
            continue
        issued = date.fromisoformat(p["Date"])
        first = (today - issued).days + 1          # Day_1 is the issue date
        if not 1 <= first <= 5 or p[f"Day{first}_Color"] not in COLOR:
            continue
        days = [{"date": (issued + timedelta(days=i - 1)).isoformat(), "color": NAMES.get(p[f"Day{i}_Color"]),
                 "warnings": [TYPES[c] for c in p[f"Day_{i}"].split(",") if c in TYPES]} for i in range(first, 6)]
        name = p["District"].strip()
        st = (state or {}).get(name)
        pt = district(name, st)
        out.append(record(name.lower(), title=f"{', '.join(days[0]['warnings']) or 'Weather warning'}: {name.title()}",
                          kind="weather_warning", lon=pt and pt["lon"], lat=pt and pt["lat"],
                          observed_at=p.get("updated_at"), severity=COLOR[p[f"Day{first}_Color"]], district=name,
                          state=st or (pt and pt["state"]), color=days[0]["color"], warnings=days[0]["warnings"], days=days,
                          issued=p["Date"], link="https://mausam.imd.gov.in/responsive/districtWiseWarningGIS.php"))
    return out


async def fetch(ctx) -> list[dict]:
    if not _states:
        _states.update(states((await ctx.get(STATES_URL)).json()))
    return parse((await ctx.get(URL)).json(), datetime.now(IST).date(), _states)


FEED = Feed(id="imd_warnings", label="Weather warnings by district (IMD)", section="hazards",
            homepage="https://mausam.imd.gov.in/responsive/districtWiseWarningGIS.php",
            terms="Government of India public page; attribution: India Meteorological Department (IMD)",
            every=1800, fetch=fetch)
