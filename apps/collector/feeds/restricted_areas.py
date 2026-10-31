"""Prohibited / restricted / danger areas (VA/VE/VI/VO P/R/D) from the AAI eAIP, ENR 5.1."""
from __future__ import annotations

import math
import re
from datetime import date, datetime

import httpx
from lxml import html

from apps.collector.feed import Feed
from packages.contracts.record import record

EAIP = "https://aim-india.aai.aero.in/eaip"
TYPES = {"P": "prohibited", "R": "restricted", "D": "danger"}
IDENT = re.compile(r"^(V[AEIO])\s*([PRD])\s*(\d+)\s*(?:[-(]?\s*([A-Z])\b\)?)?\s*(.*)$")
COORD = re.compile(r"(\d{4,6}(?:\.\d+)?)\s*([NS])[\s,]*(\d{4,7}(?:\.\d+)?)\s*([EW])")
BOX = re.compile(r"(\d{4,6})N\s*to\s*(\d{4,6})N[\s,;and]*(\d{4,7})E\s*to\s*(\d{4,7})E", re.I)
RADIUS = re.compile(r"([\d.]+)\s*(NM|KM)", re.I)
SECTOR = re.compile(r"radius (?:of )?([\d.]+)\s*(NM|KM)\s+cent\w+\D*?(" + COORD.pattern + r")\D*?(\d+)\s*deg\w*\s+to\s+(\d+)", re.I)


def _dms(s: str, deg_digits: int) -> float:
    s, frac = (s.split(".") + [""])[:2]
    d, m, sec = s[:deg_digits], s[deg_digits:deg_digits + 2], s[deg_digits + 2:] or "0"
    return int(d) + int(m) / 60 + float(sec + ("." + frac if frac else "")) / 3600


def _lat(s, h): return _dms(s, 2) * (-1 if h == "S" else 1)
def _lon(s, h): return _dms(s, 3 if len(s.split(".")[0]) in (5, 7) else 2) * (-1 if h == "W" else 1)


def _nm(r: str, unit: str) -> float:
    return float(r) / (1.852 if unit.upper() == "KM" else 1)


# ponytail: flat-earth offsets, fine for areas up to ~100 NM; use geodesics if we ever draw ocean-sized ones
def _pt(c: tuple, r_nm: float, brg: float) -> list[float]:
    b = math.radians(brg)
    return [round(c[0] + r_nm / 60 * math.sin(b) / math.cos(math.radians(c[1])), 6),
            round(c[1] + r_nm / 60 * math.cos(b), 6)]


def _polar(c: tuple, p: tuple) -> tuple[float, float]:
    dx, dy = (p[0] - c[0]) * math.cos(math.radians(c[1])) * 60, (p[1] - c[1]) * 60
    return math.hypot(dx, dy), math.degrees(math.atan2(dx, dy)) % 360


def circle(lon: float, lat: float, r_nm: float) -> dict:
    """GeoJSON Polygon approximating a circle (36 sides)."""
    return {"type": "Polygon", "coordinates": [[_pt((lon, lat), r_nm, b) for b in range(0, 361, 10)]]}


def _sector(c, r_nm, b0, b1) -> list:
    b1 += 360 if b1 <= b0 else 0
    return [list(c)] + [_pt(c, r_nm, b) for b in [*range(int(b0), int(b1), 10), b1]] + [list(c)]


def _arc(start, c, end, cw: bool) -> list:
    (r0, b0), (r1, b1) = _polar(c, start), _polar(c, end)
    while cw and b1 <= b0: b1 += 360
    while not cw and b1 >= b0: b1 -= 360
    n = max(2, int(abs(b1 - b0) / 10))
    return [_pt(c, r0 + (r1 - r0) * i / n, b0 + (b1 - b0) * i / n) for i in range(1, n + 1)]


def lateral(text: str) -> dict | None:
    """ENR 5.1 'Lateral Limits' prose → GeoJSON Polygon/MultiPolygon. Rivers/borders/coastlines become straight lines."""
    t = re.sub(r"(?<=\d) (?=[\dNE])", "", " ".join(text.split()))  # "280 002N" / "0865400 E" / "25 NM"
    if "sector" in t.lower():
        rings = [_sector((_lon(*m.group(6, 7)), _lat(*m.group(4, 5))), _nm(*m.group(1, 2)), float(m[8]), float(m[9]))
                 for m in SECTOR.finditer(t)]
        return {"type": "MultiPolygon", "coordinates": [[r] for r in rings]} if rings else None
    if m := BOX.search(t):
        la0, la1, lo0, lo1 = _lat(m[1], "N"), _lat(m[2], "N"), _lon(m[3], "E"), _lon(m[4], "E")
        return {"type": "Polygon", "coordinates": [[[lo0, la0], [lo1, la0], [lo1, la1], [lo0, la1], [lo0, la0]]]}
    coords = list(COORD.finditer(t))
    if len(coords) == 1 and (r := RADIUS.search(t)):
        m = coords[0]
        return circle(_lon(m[3], m[4]), _lat(m[1], m[2]), _nm(*r.groups()))
    pts, prev, i = [], 0, 0
    while i < len(coords):
        m = coords[i]
        p, pre = (_lon(m[3], m[4]), _lat(m[1], m[2])), t[prev:m.start()].lower()
        prev = m.end()
        if "cent" in pre and pts and i + 1 < len(coords):  # arc: this is the centre, next coord is where it ends
            e = coords[i + 1]
            pts += _arc(tuple(pts[-1]), p, (_lon(e[3], e[4]), _lat(e[1], e[2])), "anti" not in pre and "counter" not in pre)
            prev, i = e.end(), i + 2
            continue
        pts.append([round(p[0], 6), round(p[1], 6)])
        i += 1
    if len(pts) < 3:
        return None
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return {"type": "Polygon", "coordinates": [pts]}


def _ft(s: str) -> int | None:
    s = s.upper()
    if m := re.search(r"FL\s*(\d+)", s): return int(m[1]) * 100
    if m := re.search(r"(\d+)\s*FT", s): return int(m[1])
    return 0 if re.search(r"GND|MSL|SFC", s) else None


def parse(body: bytes, link: str | None = None) -> list[dict]:
    out, region = [], None
    # UTF-8 with a BOM, though the page's meta claims ISO-8859-1
    for tr in html.fromstring(body, parser=html.HTMLParser(encoding="utf-8")).iter("tr"):
        cells = [" ".join(c.text_content().split()) for c in tr.xpath("./td|./th")]
        if len(cells) == 1 and "Region" in cells[0]:
            region = cells[0].rsplit("-", 1)[-1].replace("Region", "").strip()
        if len(cells) != 4 or not (m := IDENT.match(cells[0])) or not cells[1] or "left blank" in cells[1].lower():
            continue  # header rows and "Intentionally left blank"
        fir, typ, num, suffix, name = m.groups()
        geom = lateral(cells[1])
        ring = geom and (geom["coordinates"][0] if geom["type"] == "Polygon" else geom["coordinates"][0][0])
        lon, lat = (sum(p[0] for p in ring[:-1]) / (len(ring) - 1), sum(p[1] for p in ring[:-1]) / (len(ring) - 1)) \
            if ring else (None, None)
        upper, _, lower = cells[2].partition("/")
        ident = f"{fir}{typ}{num}{suffix or ''}"
        out.append(record(ident, title=f"{fir}{typ} {num}{suffix or ''} {name.strip(' []')}".strip(), kind="airspace",
                          lon=lon, lat=lat, geometry=geom, ident=ident, type=TYPES[typ], name=name.strip(" []") or None,
                          region=region, lateral=cells[1], upper=upper.strip(), lower=lower.strip(),
                          upper_ft=_ft(upper), lower_ft=_ft(lower), remarks=cells[3] or None, link=link))
    return out


async def fetch(ctx) -> list[dict]:
    # The current AIRAC folder (eaip-v2-NN-YYYY) is only linked from the site's JS app, so probe newest first and take
    # the first whose GEN 0.2 is already effective (the next amendment is published weeks early).
    today = date.today()
    for y in (today.year, today.year - 1):
        for n in range(13, 0, -1):
            base = f"{EAIP}/eaip-v2-{n:02d}-{y}/eAIP/"
            try:
                gen = (await ctx.get(base + "IN-GEN%200.2-en-GB.html", raw_ext="html")).content
            except httpx.HTTPStatusError:
                continue
            eff = re.search(rb"effectiveDateStart' content='([^']+)'", gen)
            if eff and datetime.strptime(eff[1].decode(), "%d %b %Y").date() <= today:
                url = base + "IN-ENR%205.1-en-GB.html"
                return parse((await ctx.get(url, raw_ext="html")).content, url)
    raise RuntimeError("no effective eAIP amendment found")


FEED = Feed(id="restricted_areas", label="Prohibited / restricted / danger areas (AAI eAIP ENR 5.1)", section="air",
            homepage="https://aim-india.aai.aero.in/eaip-india",
            terms="Government of India public page (AAI eAIP); terms not stated", every=86400, fetch=fetch)
