"""Satellites relevant to India (stations, NavIC, Indian-owned, military over the region), propagated live with SGP4."""
from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime, UTC

from sgp4 import omm
from sgp4.api import Satrec, jday

from apps.collector.feed import Feed
from packages.common import config
from packages.common.geo import in_bbox
from packages.contracts.record import record

GP = "https://celestrak.org/NORAD/elements/gp.php?GROUP={}&FORMAT=json"
# GP has no owner and no OWNER query; SATCAT does, so take owners from the active-payload SATCAT.
SATCAT = "https://celestrak.org/satcat/records.php?GROUP=active&FORMAT=json"
GROUPS = ("stations", "military", "active")  # active = all payloads; only Indian-owned ones are kept from it
REFRESH = 6 * 3600  # CelesTrak asks for no more than once per 2 h; we keep elements 6 h
RETRY = 900         # with nothing cached yet, retry a failed load after 15 min
TRACK_MIN, TRACK_STEP = 100, 2

_sats: list[tuple[str, dict, Satrec]] = []  # (group, omm, satrec)
_owners: dict[int, str] = {}
_tried = 0.0
# Elements survive restarts on disk, so a restarted collector never re-downloads inside the 6 h window.
CACHE = os.path.join(config.DATA_DIR, "cache", "celestrak.json")


def _read_cache() -> tuple[dict, list] | None:
    try:
        if time.time() - os.path.getmtime(CACHE) < REFRESH:
            with open(CACHE) as f:
                d = json.load(f)
            return d["groups"], d["satcat"]
    except (OSError, ValueError, KeyError):
        pass
    return None

# WGS84
A, F = 6378.137, 1 / 298.257223563
E2 = F * (2 - F)


def gmst(jd: float, fr: float) -> float:
    """Greenwich mean sidereal time (rad), IAU 1982, UT1 ≈ UTC."""
    t = (jd - 2451545.0 + fr) / 36525.0
    sec = 67310.54841 + (876600 * 3600 + 8640184.812866) * t + 0.093104 * t * t - 6.2e-6 * t ** 3
    return math.radians(sec / 240.0) % (2 * math.pi)  # 240 s of time = 1°


def subpoint(sat: Satrec, when: datetime) -> tuple[float, float, float] | None:
    """lon, lat (deg) and alt (km) under the satellite, or None if SGP4 fails (decayed / bad elements)."""
    jd, fr = jday(when.year, when.month, when.day, when.hour, when.minute, when.second + when.microsecond / 1e6)
    err, r, _ = sat.sgp4(jd, fr)
    if err:
        return None
    g = gmst(jd, fr)
    x, y = r[0] * math.cos(g) + r[1] * math.sin(g), -r[0] * math.sin(g) + r[1] * math.cos(g)  # TEME → ECEF
    z, p = r[2], math.hypot(x, y)
    lat = math.atan2(z, p * (1 - E2))
    for _ in range(5):
        n = A / math.sqrt(1 - E2 * math.sin(lat) ** 2)
        lat = math.atan2(z + E2 * n * math.sin(lat), p)
    n = A / math.sqrt(1 - E2 * math.sin(lat) ** 2)
    alt = p / math.cos(lat) - n if abs(lat) < 1.5 else abs(z) / math.sin(abs(lat)) - n * (1 - E2)
    return (math.degrees(math.atan2(y, x)), math.degrees(lat), alt)


def track(sat: Satrec, now: datetime, minutes: int = TRACK_MIN, step: int = TRACK_STEP) -> dict:
    pts = []
    for m in range(0, minutes + 1, step):
        s = subpoint(sat, datetime.fromtimestamp(now.timestamp() + m * 60, UTC))
        if s:
            lon = s[0]
            if pts:  # unwrap so the line doesn't streak across the map at ±180
                lon += 360 * round((pts[-1][0] - lon) / 360)
            pts.append([round(lon, 3), round(s[1], 3)])
    return {"type": "LineString", "coordinates": pts}


def load(groups: dict[str, list[dict]], satcat: list[dict]) -> tuple[list, dict]:
    """GP JSON per group + SATCAT → [(group, omm, satrec)] and owners. From `active` only Indian payloads are kept."""
    owners = {s["NORAD_CAT_ID"]: s["OWNER"] for s in satcat}
    seen, sats = set(), []
    for g in GROUPS:
        for o in groups.get(g, []):
            n = o["NORAD_CAT_ID"]
            if n in seen or (g == "active" and owners.get(n) != "IND"):
                continue
            seen.add(n)
            s = Satrec()
            omm.initialize(s, o)
            sats.append((g, o, s))
    return sats, owners


def kind_of(group: str, name: str, owner: str | None) -> str:
    if group == "stations":
        return "station"
    if owner == "IND":
        return "navic" if name.startswith(("IRNSS", "NVS")) else "indian"
    return "military" if group == "military" else "satellite"


# Indian payload mission by name (public mission names, first match wins)
MISSIONS = [
    (("IRNSS", "NVS"), "Navigation (NavIC)"),
    (("GSAT-7", "CMS-03"), "Strategic communication"),
    (("EMISAT",), "Electronic intelligence"),
    (("INSAT-3D", "KALPANA", "MEGHA", "OCEANSAT", "SCATSAT", "SARAL", "EOS-06", "INSAT-3DS"), "Weather & ocean"),
    (("CARTOSAT", "RESOURCESAT", "RISAT", "EOS", "HYSIS", "IMS-", "MICROSAT", "NISAR", "IRS"), "Earth observation"),
    (("GSAT", "INSAT", "CMS", "HAMSAT"), "Communication"),
    (("ASTROSAT", "ADITYA", "XPOSAT", "CHANDRAYAAN"), "Space science"),
    (("POEM", "SPADEX", "PSLV", "INS-", "TDS"), "Technology demo"),
]
MU, RE = 398600.4418, 6378.137


def mission(name: str) -> str:
    n = name.upper()
    return next((m for keys, m in MISSIONS if n.startswith(keys) or any(f" {k}" in n for k in keys)), "Other")


def orbit(o: dict) -> dict:
    """Orbit class and shape from the mean elements."""
    n = o["MEAN_MOTION"] * 2 * math.pi / 86400               # rad/s
    a = (MU / n ** 2) ** (1 / 3)
    e, inc = o["ECCENTRICITY"], o["INCLINATION"]
    apo, peri = a * (1 + e) - RE, a * (1 - e) - RE
    period = 1440 / o["MEAN_MOTION"]
    cls = ("GEO" if inc < 5 else "IGSO") if abs(period - 1436) < 30 else "LEO" if apo < 2000 else "HEO" if e > 0.25 else "MEO"
    return {"orbit": cls, "inclination": round(inc, 2), "period_min": round(period, 1), "apogee_km": round(apo), "perigee_km": round(peri)}


def positions(sats: list, owners: dict, now: datetime) -> list[dict]:
    out = []
    for group, o, sat in sats:
        name, nid = o["OBJECT_NAME"], o["NORAD_CAT_ID"]
        owner = owners.get(nid)
        sp = subpoint(sat, now)
        if not sp:
            continue
        lon, lat, alt = sp
        if owner != "IND" and not in_bbox(lon, lat):
            continue
        kind = kind_of(group, name, owner)
        # ground track only for Indian ones and stations: one revolution ahead for LEO/MEO; the full 24 h figure-of-eight
        # for inclined geosynchronous (NavIC IGSO); none for true GEO, which stays put
        step_min = None
        if kind in ("station", "navic", "indian"):
            if o["MEAN_MOTION"] > 2.4:
                step_min = TRACK_STEP
                geom = track(sat, now, min(int(1440 / o["MEAN_MOTION"]) + 10, 200), TRACK_STEP)
            elif o["INCLINATION"] > 2:
                step_min = 20
                geom = track(sat, now, 1440, 20)
            else:
                geom = None
        else:
            geom = None
        out.append(record(nid, title=name, kind=kind, lon=lon, lat=lat, geometry=geom, observed_at=now,
                          norad_id=nid, name=name, alt_km=round(alt, 1), owner=owner, group=group,
                          mission=mission(name) if owner == "IND" else None, **orbit(o),
                          track_step_s=step_min * 60 if geom and step_min else None,
                          intl_id=o["OBJECT_ID"], epoch=o["EPOCH"]))
    return out


async def fetch(ctx) -> list[dict]:
    global _sats, _owners, _tried
    if time.monotonic() - _tried >= (REFRESH if _sats else RETRY):
        _tried = time.monotonic()
        try:
            cached = _read_cache()
            if cached:
                groups, satcat = cached
            else:
                groups = {g: (await ctx.get(GP.format(g))).json() for g in GROUPS}
                satcat = (await ctx.get(SATCAT)).json()
                os.makedirs(os.path.dirname(CACHE), exist_ok=True)
                with open(CACHE + ".tmp", "w") as f:
                    json.dump({"groups": groups, "satcat": satcat}, f)
                os.replace(CACHE + ".tmp", CACHE)
            _sats, _owners = load(groups, satcat)
            if cached:
                _tried -= REFRESH - (time.time() - os.path.getmtime(CACHE))  # refresh when the file turns 6 h old
        except Exception:
            if not _sats:
                raise  # otherwise keep flying the old elements until the next refresh
    if not _sats:
        raise RuntimeError("no orbital elements yet (CelesTrak unavailable); retrying every 15 min")
    return positions(_sats, _owners, datetime.now(UTC))


FEED = Feed(id="satellites", label="Satellites (CelesTrak + SGP4)", section="space",
            homepage="https://celestrak.org/NORAD/elements/",
            terms="CelesTrak GP/SATCAT: free public data from US Space Force (space-track.org) via CelesTrak; "
                  "elements fetched at most every 6 h per CelesTrak usage policy",
            every=60, fetch=fetch, store_all=False)
