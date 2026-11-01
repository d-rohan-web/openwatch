"""Live aircraft over India from the adsb.fi community network (OpenSky is its own feed: opensky.py)."""
from __future__ import annotations

import asyncio
import time

from apps.collector.feed import Feed
from packages.common.geo import GLOBAL
from packages.contracts.record import record

# 250 nm circles on a ~6° grid cover India, the Arabian Sea, the Bay of Bengal and the Indian Ocean down to the equator.
TILES = [(lat, lon) for lat in (-3, 3, 9, 15, 21, 27, 33) for lon in (59, 65, 71, 77, 83, 89, 95)]
# adsb.fi allows ~1 request/s, so one sweep takes ~50 s (inside the 120 s ttl). (adsb.lol rate-limits tile sweeps and adds little here.)
SOURCES = {"adsb.fi": "https://opendata.adsb.fi/api/v2/lat/{lat}/lon/{lon}/dist/250"}
MILITARY_WORLD = "https://opendata.adsb.fi/api/v2/mil"  # global scope: every military-flagged aircraft adsb.fi sees


def from_readsb(a: dict, source: str) -> dict | None:
    if a.get("lat") is None or a.get("lon") is None:
        return None
    alt = a.get("alt_baro")
    military = bool((a.get("dbFlags") or 0) & 1)
    callsign = (a.get("flight") or "").strip()
    return record(a["hex"], title=callsign or a.get("r") or a["hex"], kind="military" if military else "aircraft",
                  lon=a["lon"], lat=a["lat"], observed_at=time.time() - (a.get("seen_pos") or 0),
                  callsign=callsign or None, reg=a.get("r"), type=a.get("t"), desc=a.get("desc"),
                  alt_ft=0 if alt == "ground" else alt, on_ground=alt == "ground", gs_kt=a.get("gs"),
                  track=a.get("track", a.get("true_heading")), squawk=a.get("squawk"),
                  emergency=None if a.get("emergency") in (None, "none") else a.get("emergency"),
                  military=military, category=a.get("category"), source=source)



async def fetch(ctx) -> list[dict]:
    best: dict[str, dict] = {}

    def keep(r):
        if r and (r["id"] not in best or r["observed_at"] > best[r["id"]]["observed_at"]):
            best[r["id"]] = r

    async def readsb(name, url):
        for lat, lon in TILES:
            try:
                d = (await ctx.get(url.format(lat=lat, lon=lon))).json()
            except Exception:
                continue  # one tile failing shouldn't drop the rest
            for a in d.get("aircraft") or d.get("ac") or []:
                keep(from_readsb(a, name))

    jobs = [readsb(n, u) for n, u in SOURCES.items()]
    if GLOBAL:
        async def military():
            try:
                d = (await ctx.get(MILITARY_WORLD)).json()
                for a in d.get("ac") or d.get("aircraft") or []:
                    keep(from_readsb({**a, "dbFlags": (a.get("dbFlags") or 0) | 1}, "adsb.fi"))
            except Exception:
                pass
        jobs.append(military())
    await asyncio.gather(*jobs)
    if not best:
        raise RuntimeError("no aircraft from any source")
    return list(best.values())


FEED = Feed(id="aircraft", label="Aircraft (ADS-B)", section="air", homepage="https://adsb.fi/",
            terms="adsb.fi open data: free, non-commercial use (adsb.fi)",
            every=30, fetch=fetch, snapshot=False, ttl=120, store_all=True, keep_raw=False)
