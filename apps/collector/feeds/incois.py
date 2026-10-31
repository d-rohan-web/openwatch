"""INCOIS ocean alerts: high-wave / swell-surge / ocean-current alerts by coastal segment, plus active tsunami events.

Same JSON the incois.gov.in alerts map and the TEWS home page load. No active tsunami → just the ocean alerts (or []).
"""
from __future__ import annotations

import json
import logging

import httpx
from lxml import etree

from apps.collector.feed import Feed
from packages.common.geo import district
from packages.contracts.record import record

API = "https://samudra.incois.gov.in/incoismobileappdata/rest/incois/"
HWASSA = "https://sarat.incois.gov.in/incoismobileappdata/rest/incois/hwassalatestdata"
TSUNAMI = "https://tsunami.incois.gov.in/itews/homexmls/LatestEvents.xml"
COLOR = {"red": "critical", "orange": "warning", "yellow": "advisory", "green": "info"}
# ponytail: bulletin type codes guessed from INCOIS's levels (only "I" = information seen live); default advisory
TSU_SEV = {"I": "info", "W": "critical", "A": "warning"}

log = logging.getLogger("collector")
_centres: dict[int, list[float]] = {}  # OBJECTID → [lon, lat]; coastal segment polygons don't change


def centres(polygons: dict) -> dict[int, list[float]]:
    """Bounding-box centre per coastal segment (the polygons are ~7 MB, so we keep a point, not the shape)."""
    out = {}
    for f in polygons["features"]:
        pts = [c for poly in f["geometry"]["coordinates"] for ring in poly for c in ring]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        out[f["properties"]["OBJECTID"]] = [(min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2]
    return out


def alert_rows(hwassa: dict, currents: dict) -> list[dict]:
    rows = []
    for d, k in ((hwassa, "HWA"), (hwassa, "SSA"), (currents, "Currents")):
        if d.get(f"Latest{k}Date", "None") != "None":
            rows += json.loads(d[f"{k}Json"] or "[]")
    return rows


def parse_alerts(rows: list[dict], centre: dict[int, list[float]]) -> list[dict]:
    out = []
    for r in rows:
        sev = COLOR.get((r.get("Color") or "").lower())
        if sev in (None, "info"):
            continue
        pt = centre.get(r["OBJECTID"])
        if not pt and (d := district(r["District"], r.get("STATE"))):
            pt = [d["lon"], d["lat"]]
        out.append(record(f"{r['Alert']}:{r['OBJECTID']}".lower().replace(" ", "_"),
                          title=f"{r['Alert'].title()}: {r['District'].title()}", kind="ocean_alert",
                          lon=pt and pt[0], lat=pt and pt[1], severity=sev, alert=r["Alert"], segment=r["District"],
                          state=r.get("STATE"), message=r.get("Message"), issued=r.get("Issue Date"),
                          link="https://incois.gov.in/site/services/hwa.jsp"))
    return out


def parse_tsunami(xml: bytes) -> list[dict]:
    out = []
    for ev in etree.fromstring(xml).iter("event"):
        # field order as read by tsunami.incois.gov.in/TEWS/js/indexHome.js (children are positional there too)
        f = [(c.text or "").strip() for c in ev]
        evid, origin, place, lat, lon, depth, mag, issued, _, bno, btype, aos = f[:12]
        out.append(record(evid, title=f"Tsunami bulletin {bno}: M {mag} {place}", kind="tsunami",
                          lon=float(lon), lat=float(lat), severity=TSU_SEV.get(btype[:1].upper(), "advisory"),
                          mag=mag, depth=depth, place=place, origin_time=origin, issued=issued, bulletin_no=bno,
                          bulletin_type=btype,
                          link=f"https://tsunami.incois.gov.in/TEWS/displaybulletinslatest.jsp?type=NTWC"
                               f"&eventId={evid}&aos={aos}&latestBullNo={bno}"))
    return out


async def fetch(ctx) -> list[dict]:
    try:
        out = parse_tsunami((await ctx.get(TSUNAMI)).content)
    except httpx.ConnectError as e:  # TEWS host has had TLS chain trouble (see extra_ca.pem); keep the ocean alerts
        log.warning("incois tsunami fetch failed", extra={"error": str(e)})
        out = []
    rows = alert_rows((await ctx.get(HWASSA)).json(), (await ctx.get(API + "currentslatestdata")).json())
    if rows and not _centres:  # once per process
        _centres.update(centres((await ctx.get(API + "districtpolygons")).json()))
    return out + parse_alerts(rows, _centres)


FEED = Feed(id="incois", label="Ocean & tsunami alerts (INCOIS)", section="hazards",
            homepage="https://incois.gov.in/site/services/hwa.jsp",
            terms="Government of India public page; attribution: Indian National Centre for Ocean Information Services (INCOIS)",
            every=900, fetch=fetch)
