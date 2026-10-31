"""Upcoming and recent orbital launches from Launch Library 2: Indian sites/agencies and any pad in the region."""
from __future__ import annotations

from datetime import datetime, timezone

from apps.collector.feed import Feed
from packages.common.geo import in_bbox
from packages.contracts.record import record

BASE = "https://ll.thespacedevs.com/2.3.0/launches"
# Free tier is ~15 requests/hour: two per hourly poll. `list` mode has no pad, so `normal` it is.
URLS = (f"{BASE}/upcoming/?limit=100&mode=normal", f"{BASE}/previous/?limit=50&mode=normal")


def indian(L: dict) -> bool:
    pad, lsp = L.get("pad") or {}, L.get("launch_service_provider") or {}
    agencies = ((L.get("mission") or {}).get("agencies") or []) + (pad.get("agencies") or [])
    return ((pad.get("country") or {}).get("alpha_3_code") == "IND" or lsp.get("abbrev") == "ISRO"
            or any(c.get("alpha_3_code") == "IND" for a in agencies for c in a.get("country") or []))


def parse(results: list[dict], now: datetime) -> list[dict]:
    out = []
    for L in results:
        pad = L.get("pad") or {}
        lat, lon = pad.get("latitude"), pad.get("longitude")
        if lat is None or lon is None:
            continue
        lat, lon = float(lat), float(lon)
        if not (indian(L) or in_bbox(lon, lat)):
            continue
        net = datetime.fromisoformat(L["net"].replace("Z", "+00:00"))
        mission, status = L.get("mission") or {}, L.get("status") or {}
        out.append(record(L["id"], title=L["name"], kind="launch", lon=lon, lat=lat, observed_at=L.get("last_updated"),
                          severity="advisory" if abs((net - now).total_seconds()) <= 86400 else "info",
                          net=L["net"], net_precision=(L.get("net_precision") or {}).get("name"),
                          window_start=L.get("window_start"), window_end=L.get("window_end"),
                          status=status.get("name"), status_abbrev=status.get("abbrev"),
                          provider=(L.get("launch_service_provider") or {}).get("name"),
                          rocket=((L.get("rocket") or {}).get("configuration") or {}).get("full_name"),
                          mission=mission.get("name"), mission_type=mission.get("type"),
                          orbit=(mission.get("orbit") or {}).get("name"), description=mission.get("description"),
                          pad=pad.get("name"), location=(pad.get("location") or {}).get("name"),
                          indian=indian(L), webcast_live=L.get("webcast_live"),
                          link=f"https://ll.thespacedevs.com/2.3.0/launches/{L['id']}/"))
    return out


async def fetch(ctx) -> list[dict]:
    seen, results = set(), []
    for url in URLS:
        for L in (await ctx.get(url)).json()["results"]:
            if L["id"] not in seen:  # a just-flown launch can sit in both lists
                seen.add(L["id"])
                results.append(L)
    return parse(results, datetime.now(timezone.utc))


FEED = Feed(id="launches", label="Launches (Launch Library 2)", section="space",
            homepage="https://thespacedevs.com/llapi",
            terms="Launch Library 2 by The Space Devs: free API (rate-limited), data under their terms; "
                  "images carry their own licences",
            every=3600, fetch=fetch)
