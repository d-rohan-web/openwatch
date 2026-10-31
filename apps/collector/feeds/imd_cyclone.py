"""RSMC New Delhi tropical cyclone: position + forecast track from the latest IMD National Bulletin (PDF).

No depression or stronger over the north Indian Ocean → the latest bulletin has no track table → [].
"""
from __future__ import annotations

import io
import re
from datetime import datetime, timedelta, timezone, UTC

import pdfplumber

from apps.collector.feed import Feed
from packages.contracts.record import record

PAGE = "https://mausam.imd.gov.in/responsive/cycloneinformation.php"
IST = timezone(timedelta(hours=5, minutes=30))
ROW = re.compile(r"^(\d\d\.\d\d\.\d\d)/(\d{4})\s+(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\s+(.+?gusting to \d+)\s+(.+)$", re.M)

_cache: dict[str, str] = {}  # bulletin url → text; a PDF never changes once posted


def severity(category: str) -> str:
    c = category.lower()
    return ("critical" if "very severe" in c or "super" in c else "warning" if "cyclonic storm" in c
            else "advisory" if "depression" in c else "info")


def parse(text: str, url: str, now: datetime) -> list[dict]:
    track = [{"time": datetime.strptime(f"{d}{t}", "%d.%m.%y%H%M").replace(tzinfo=IST), "lat": float(la),
              "lon": float(lo), "wind_kmph": w, "category": c.strip()} for d, t, la, lo, w, c in ROW.findall(text)]
    if not track or now - track[0]["time"] > timedelta(hours=24):  # no table, or IMD stopped issuing
        return []
    now_pt = track[0]
    sys_id = re.search(r"\(((?:BOB|ARB|LAND)/\d+/\d{4})\)", text)
    name = re.search(r"[“\"]([A-Za-z]+)[”\"]", text)
    bno = re.search(r"BULLETIN NO\.\s*(\d+)", text)
    title = f"{now_pt['category']}" + (f" “{name[1]}”" if name else "")
    for p in track:
        p["time"] = p["time"].astimezone(UTC).isoformat()
    geom = {"type": "LineString", "coordinates": [[p["lon"], p["lat"]] for p in track]} if len(track) > 1 else None
    return [record(sys_id[1] if sys_id else url, title=title, kind="cyclone", lon=now_pt["lon"], lat=now_pt["lat"],
                   geometry=geom, observed_at=now_pt["time"], severity=severity(now_pt["category"]),
                   name=name and name[1], system=sys_id and sys_id[1], bulletin_no=bno and int(bno[1]),
                   wind_kmph=now_pt["wind_kmph"], category=now_pt["category"], track=track, link=url)]


async def fetch(ctx) -> list[dict]:
    m = re.search(r'openPDF\(\s*"National Bulletin",\s*"([^"]+)"', (await ctx.get(PAGE)).text)
    if not m:
        return []
    url = m[1]
    if url not in _cache:
        with pdfplumber.open(io.BytesIO((await ctx.get(url, raw_ext="pdf")).content)) as pdf:
            _cache.clear()
            _cache[url] = "\n".join(p.extract_text() or "" for p in pdf.pages[:3])  # track table is on p1–2
    return parse(_cache[url], url, datetime.now(UTC))


FEED = Feed(id="imd_cyclone", label="Tropical cyclones (IMD RSMC New Delhi)", section="hazards",
            homepage="https://rsmcnewdelhi.imd.gov.in/",
            terms="Government of India public page; attribution: India Meteorological Department (IMD), RSMC New Delhi",
            every=1800, fetch=fetch)
