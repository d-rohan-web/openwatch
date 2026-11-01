"""OpenSky Network state vectors over India: the densest open aircraft source here.

Anonymous access allows ~400 credits/day and this box costs 4, so it's polled every 15 min. A free OpenSky account
(API client: OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET) gives 4000/day → every 90 s.
"""
from __future__ import annotations

import os
import time

from apps.collector.feed import Feed
from packages.common.geo import GLOBAL, REGION_BBOX
from packages.contracts.record import record

URL = "https://opensky-network.org/api/states/all?extended=1" + ("" if GLOBAL else "&lamin={1}&lomin={0}&lamax={3}&lomax={2}".format(*REGION_BBOX))
TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"  # noqa: S105 (a URL)
CLIENT_ID, CLIENT_SECRET = os.getenv("OPENSKY_CLIENT_ID", ""), os.getenv("OPENSKY_CLIENT_SECRET", "")
_token: tuple[str, float] = ("", 0.0)


def parse(d: dict) -> list[dict]:
    # https://openskynetwork.github.io/opensky-api/rest.html#all-state-vectors
    out = []
    for s in d.get("states") or []:
        if s[5] is None or s[6] is None:
            continue
        callsign = (s[1] or "").strip()
        out.append(record(s[0], title=callsign or s[0], kind="aircraft", lon=s[5], lat=s[6], observed_at=s[3] or s[4],
                          callsign=callsign or None, country=s[2], on_ground=s[8],
                          alt_ft=None if s[7] is None else round(s[7] * 3.28084),
                          gs_kt=None if s[9] is None else round(s[9] * 1.94384, 1), track=s[10],
                          vrate_fpm=None if s[11] is None else round(s[11] * 196.85), squawk=s[14],
                          emergency=s[14] if s[14] in ("7500", "7600", "7700") else None,
                          category=s[17] if len(s) > 17 else None, source="opensky"))
    return out


async def bearer(ctx) -> dict:
    global _token
    if not CLIENT_ID:
        return {}
    if time.time() > _token[1] - 60:
        r = await ctx.client.post(TOKEN_URL, data={"grant_type": "client_credentials", "client_id": CLIENT_ID,
                                                   "client_secret": CLIENT_SECRET})
        r.raise_for_status()
        d = r.json()
        _token = (d["access_token"], time.time() + d.get("expires_in", 1800))
    return {"Authorization": f"Bearer {_token[0]}"}


async def fetch(ctx) -> list[dict]:
    return parse((await ctx.get(URL, headers=await bearer(ctx))).json())


FEED = Feed(id="opensky", label="Aircraft (OpenSky Network)", section="air", homepage="https://opensky-network.org/",
            terms="OpenSky Network: free for non-commercial research use; cite OpenSky (opensky-network.org/about/terms-of-use)",
            every=90 if CLIENT_ID else 900, fetch=fetch, store_all=True, keep_raw=False)
