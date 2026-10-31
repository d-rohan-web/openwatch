"""CWC flood forecasting: river stations at or above warning level, with their warning/danger/HFL marks."""
from __future__ import annotations

from apps.collector.feed import Feed
from packages.contracts.record import record

# The FFS map's own backend. The live list only carries stations above warning; levels for the ~1,600 normal
# stations would take one request each, so we don't poll them.
FFM = "https://ffs.india-water.gov.in/ffm/api/station-water-level-above-warning/"
IAM = "https://ffs.india-water.gov.in/iam/api"
META = {"stations": ("layer-station", "LayerStationDto"), "geo": ("layer-station-geo", "LayerStationGeoDto"),
        "static": ("flood-forecast-static", "FloodForecastStaticDto")}


def severity(level, warning, danger, hfl, status) -> str:
    if level is not None:
        for mark, sev in ((hfl, "critical"), (danger, "warning"), (warning, "advisory")):
            if mark is not None and level > mark:
                return sev
        return "info"
    return {"EXTREME": "critical", "DANGER": "warning", "WARNING": "advisory"}.get(status, "info")


def parse(d: dict) -> list[dict]:
    """d: {"above": [...], "stations": [...], "geo": [...], "static": [...]} as the API returns them."""
    by = {k: {x["stationCode"]: x for x in d[k]} for k in ("stations", "geo", "static")}
    out = []
    for a in d["above"]:
        code = a["stationCode"]
        st, geo, ff = (by[k].get(code, {}) for k in ("stations", "geo", "static"))
        level, warning, danger, hfl = a.get("value"), ff.get("warningLevel"), ff.get("dangerLevel"), ff.get("highestFlowLevel")
        name = st.get("name") or code
        trend = (a.get("trend") or "").lower() or None
        out.append(record(code, title=f"{name}: {level} m ({a['status'].lower()}{', ' + trend if trend else ''})",
                          kind="river_level", lon=geo.get("lon"), lat=geo.get("lat"),
                          severity=severity(level, warning, danger, hfl, a["status"]), station=name, level_m=level,
                          warning_m=warning, danger_m=danger, hfl_m=hfl, hfl_date=ff.get("highestFlowLevelDate"),
                          trend=trend, status=a["status"], nearest_town=ff.get("nearestTown") or None,
                          link="https://ffs.india-water.gov.in/"))
    return out


async def fetch(ctx) -> list[dict]:
    above = (await ctx.get(FFM, headers={"class-name": "StationWaterLevelAboveWarningDto"})).json()
    d = {"above": above}
    codes = ",".join(a["stationCode"] for a in above)
    for k, (path, cls) in META.items():
        d[k] = (await ctx.get(f"{IAM}/{path}//all/{codes}", headers={"class-name": cls})).json() if codes else []
    return parse(d)


FEED = Feed(id="cwc_rivers", label="River levels above warning (CWC)", section="hazards",
            homepage="https://ffs.india-water.gov.in/",
            terms="Central Water Commission, Govt. of India (public flood forecast site; no explicit licence)",
            every=1800, fetch=fetch)
