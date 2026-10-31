"""NOTAMs for the Indian FIRs (and Colombo) via the FAA NOTAM API (api.faa.gov, v1).

FAA_NOTAM_KEY is "client_id:client_secret" from api.faa.gov, sent as the documented client_id / client_secret headers.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from apps.collector.feed import Feed
from apps.collector.feeds.restricted_areas import circle
from packages.contracts.record import record

URL = "https://external-api.faa.gov/notamapi/v1/notams"
FIRS = ("VIDF", "VABF", "VECF", "VOMF", "VCCF")
Q = re.compile(r"Q\)\s*(\w{4})/(\w{5})/(\w*)/(\w*)/(\w*)/(\d{3})/(\d{3})/(\d{2})(\d{2})([NS])(\d{3})(\d{2})([EW])(\d{3})?")
MILITARY = re.compile(r"\b(FIRING|MISSILE|ROCKET|MIL|MILITARY|DANGER AREA)\b")


def _t(s: str | None) -> str | None:
    return datetime.strptime(s, "%y%m%d%H%M").replace(tzinfo=timezone.utc).isoformat() if s else None


def parse_icao(text: str) -> dict:
    """ICAO NOTAM text (Q/A/B/C/D/E/F/G items) → fields, point and circle."""
    out: dict = {}
    if q := Q.search(text):
        lat = (int(q[8]) + int(q[9]) / 60) * (-1 if q[10] == "S" else 1)
        lon = (int(q[11]) + int(q[12]) / 60) * (-1 if q[13] == "W" else 1)
        r = int(q[14]) if q[14] else None
        out.update(fir=q[1], qcode=q[2], traffic=q[3] or None, purpose=q[4] or None, scope=q[5] or None,
                   lower_fl=int(q[6]), upper_fl=int(q[7]), lon=lon, lat=lat, radius_nm=r,
                   geometry=circle(lon, lat, r) if r and r < 999 else None)  # 999 = whole FIR
    item = lambda k: (m := re.search(rf"(?:^|\s){k}\)\s*(.*?)(?=\s+[A-G]\)\s|$)", text, re.S)) and m[1].strip()
    c = item("C") or ""
    out.update(location=item("A"), valid_from=_t((item("B") or "")[:10] or None),
               valid_to=_t(c[:10]) if c[:10].isdigit() else None, perm=c.startswith("PERM") or None,
               estimated="EST" in c or None, schedule=item("D"), text=item("E") or text, lower=item("F"), upper=item("G"))
    return out


def to_record(f: dict) -> dict:
    core = f["properties"]["coreNOTAMData"]
    n = core["notam"]
    icao = next((t.get("formattedText") for t in core.get("notamTranslation") or [] if t.get("type") == "ICAO"), None)
    p = parse_icao(icao or n.get("text") or "")
    text = p.pop("text")
    lon, lat, geom = p.pop("lon", None), p.pop("lat", None), p.pop("geometry", None)
    military = bool(MILITARY.search(text.upper()))
    fir = p.pop("fir", None) or n.get("affectedFIR")
    loc = p.pop("location", None) or n.get("icaoLocation") or n.get("location")
    return record(n.get("id") or f"{n['number']}-{loc}", title=f"{n['number']} {loc}: {text[:80]}", kind="notam",
                  lon=lon, lat=lat, geometry=geom, observed_at=n.get("issued"),
                  severity="advisory" if military else None, number=n["number"], fir=fir, location=loc,
                  **{**p, "valid_from": p["valid_from"] or n.get("effectiveStart"),
                     "valid_to": p["valid_to"] or (None if n.get("effectiveEnd") == "PERM" else n.get("effectiveEnd"))},
                  text=text, military=military or None, icao=icao, source="faa")


def parse(d: dict) -> list[dict]:
    return [to_record(f) for f in d.get("items") or []]


async def fetch(ctx) -> list[dict]:
    cid, _, secret = ctx.key.partition(":")
    out = []
    for fir in FIRS:
        page, pages = 1, 1
        while page <= pages:
            d = (await ctx.get(URL, params={"icaoLocation": fir, "responseFormat": "geoJson", "pageSize": 1000,
                                            "pageNum": page}, headers={"client_id": cid, "client_secret": secret})).json()
            out += parse(d)
            pages, page = d.get("totalPages") or 1, page + 1
    return list({r["id"]: r for r in out}.values())


FEED = Feed(id="faa_notam", label="NOTAMs, Indian FIRs (FAA NOTAM API)", section="air",
            homepage="https://api.faa.gov/s/", terms="FAA NOTAM API; US Government data, API terms at api.faa.gov",
            every=900, fetch=fetch, key="FAA_NOTAM_KEY", snapshot=True)
