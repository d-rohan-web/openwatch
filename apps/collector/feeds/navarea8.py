"""Indian Navy NAVAREA VIII navigational warnings in force (NHO, hydrobharat.gov.in), from the published PDF."""
from __future__ import annotations

import io
import re
from datetime import datetime, UTC

import pdfplumber

from apps.collector.feed import Feed
from packages.contracts.record import record

# The page's "In-Force Navarea VIII Warnings" button. NHO updates it irregularly: check `list_as_on`.
PDF = "https://hydrobharat.gov.in/documents/d/guest/in-force-navarea-viii-warnings-2"
MON = {m: i for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}
WARN = re.compile(r"(\d{2})(\d{2})(\d{2})Z/([A-Z]{3}) (\d{2})\s*\n\s*NAVAREA VIII\s*-\s*(\d+)/(\d{2})\s*\n-+\n(.*?)(?=\n-{10,}|\Z)",
                  re.S)
LAT, LON = r"(\d{1,2})-(\d{1,2}(?:\.\d+)?)([NS])", r"(\d{1,3})-(\d{1,2}(?:\.\d+)?)([EW])"
PAIR = re.compile(LAT + r"\s+" + LON)
CANCEL = re.compile(r"CANCEL THIS MSG (\d{2})(\d{2})(\d{2}) UTC ([A-Z]{3}) (\d{2})")
FIRING = re.compile(r"FIRING|MISSILE|GUNNERY|ROCKET")


def _deg(d, m, h) -> float:
    v = int(d) + float(m) / 60
    return round(-v if h in "SW" else v, 5)


def _dt(day, hh, mm, mon, yy) -> datetime:
    return datetime(2000 + int(yy), MON[mon], int(day), int(hh), int(mm), tzinfo=UTC)


def _points(s: str) -> list[list[float]]:
    return [[_deg(*m[3:]), _deg(*m[:3])] for m in PAIR.findall(s)]


def _geometry(text: str) -> dict | None:
    if "BOUND" in text:
        # "AREAS BOUNDED BY (A) ... (B) ..." → one ring per lettered area
        rings = [p + p[:1] for p in map(_points, re.split(r"\([A-H]\)", text)) if len(p) >= 3]
        if len(rings) == 1:
            return {"type": "Polygon", "coordinates": rings}
        if rings:
            return {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}
        # "BOUNDED WITHIN 21-37.50N TO 21-55.50N AND 091-23.50E TO 091-42.50E"
        lats, lons = [_deg(*m) for m in re.findall(LAT, text)], [_deg(*m) for m in re.findall(LON, text)]
        if len(lats) == 2 and len(lons) == 2:
            (s, n), (w, e) = sorted(lats), sorted(lons)
            return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}
    pts = _points(text)
    if len(pts) >= 3 and "AREA" in text:
        return {"type": "Polygon", "coordinates": [pts + pts[:1]]}
    if len(pts) >= 2:
        return {"type": "MultiPoint", "coordinates": pts}
    return {"type": "Point", "coordinates": pts[0]} if pts else None


def _center(g: dict | None) -> tuple[float | None, float | None]:
    if not g:
        return None, None
    c, t = g["coordinates"], g["type"]
    pts = [c] if t == "Point" else c if t == "MultiPoint" else c[0][:-1] if t == "Polygon" else [p for r in c for p in r[0][:-1]]
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def parse(text: str) -> list[dict]:
    as_on = re.search(r"IN FORCE AS ON (\d{1,2} [A-Z]{3} \d{4})", text)
    as_on = as_on and datetime.strptime(as_on[1].title(), "%d %b %Y").date().isoformat()
    out = []
    for m in WARN.finditer(text):
        day, hh, mm, mon, yy, num, nyy, body = m.groups()
        body = re.sub(r"\s+", " ", body.replace("-\n", "-")).strip()
        if body.startswith("NAVAREA VIII - WARNINGS IN FORCE"):
            continue  # the weekly in-force list message itself
        area = body.split(" (.)")[0]
        geom = _geometry(body)
        lon, lat = _center(geom)
        cancel = CANCEL.search(body)
        firing = bool(FIRING.search(body))
        out.append(record(f"{int(num)}/{nyy}", title=f"NAVAREA VIII {int(num)}/{nyy}: {area}",
                          kind="firing" if firing else "navwarn", lon=lon, lat=lat,
                          geometry=None if geom and geom["type"] == "Point" else geom,
                          observed_at=_dt(day, hh, mm, mon, yy), severity="advisory" if firing else None,
                          number=f"NAVAREA VIII {int(num)}/{nyy}", area=area, text=body,
                          cancel_at=cancel and _dt(*cancel.groups()).isoformat(), list_as_on=as_on))
    return out


async def fetch(ctx) -> list[dict]:
    pdf = (await ctx.get(PDF, raw_ext="pdf")).content
    with pdfplumber.open(io.BytesIO(pdf)) as p:
        text = "\n".join(pg.extract_text() or "" for pg in p.pages)
    now = datetime.now(UTC).isoformat()
    # the PDF can lag weeks behind: drop warnings whose own "CANCEL THIS MSG" time has passed
    return [r for r in parse(text) if r["attrs"].get("cancel_at", "9") > now]


FEED = Feed(id="navarea8", label="NAVAREA VIII warnings (Indian Navy)", section="sea",
            homepage="https://hydrobharat.gov.in/navarea-warnings",
            terms="Government of India public navigational warnings (National Hydrographic Office); not for navigation",
            every=3600, fetch=fetch)
