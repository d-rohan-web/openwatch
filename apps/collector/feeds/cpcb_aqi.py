"""CPCB real-time air quality per monitoring station (data.gov.in), rows grouped into one record per station."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apps.collector.feed import Feed
from packages.contracts.record import record

URL = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
PAGE = 1000
IST = timezone(timedelta(hours=5, minutes=30))
# Indian AQI bands (upper bound inclusive): good, satisfactory, moderate, poor, very poor, severe.
BANDS = ((50, "good", "info"), (100, "satisfactory", "info"), (200, "moderate", "info"),
         (300, "poor", "advisory"), (400, "very poor", "warning"), (float("inf"), "severe", "critical"))


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None  # "NA"


def parse(rows: list[dict]) -> list[dict]:
    # The values are CPCB pollutant sub-indices, so the station AQI is the highest average sub-index.
    # ponytail: ignores CPCB's "3 pollutants incl. PM" validity rule; add it if partial stations mislead.
    stations: dict[str, dict] = {}
    for r in rows:
        s = stations.setdefault(r["station"], {"row": r, "pollutants": {}})
        avg = num(r.get("avg_value", r.get("pollutant_avg")))
        if avg is not None:
            s["pollutants"][r["pollutant_id"]] = {"avg": avg, "min": num(r.get("min_value", r.get("pollutant_min"))),
                                                  "max": num(r.get("max_value", r.get("pollutant_max")))}
    out = []
    for name, s in stations.items():
        r, p = s["row"], s["pollutants"]
        aqi = max((v["avg"] for v in p.values()), default=None)
        prominent = max(p, key=lambda k: p[k]["avg"]) if p else None
        band, sev = next((b, sv) for top, b, sv in BANDS if aqi <= top) if aqi is not None else (None, "info")
        when = datetime.strptime(r["last_update"], "%d-%m-%Y %H:%M:%S").replace(tzinfo=IST) if r.get("last_update") else None
        out.append(record(name, title=f"{name}: AQI {aqi:.0f} ({band})" if aqi is not None else f"{name}: no data",
                          kind="air_quality", lon=num(r.get("longitude")), lat=num(r.get("latitude")),
                          observed_at=when, severity=sev, aqi=aqi, band=band, prominent=prominent, pollutants=p,
                          station=name, city=r.get("city"), state=r.get("state")))
    return out


async def fetch(ctx) -> list[dict]:
    rows, offset = [], 0
    while True:
        d = (await ctx.get(URL, params={"api-key": ctx.key, "format": "json", "limit": PAGE, "offset": offset})).json()
        rows += d.get("records") or []
        offset += PAGE
        if not d.get("records") or offset >= int(d.get("total") or 0):
            return parse(rows)


FEED = Feed(id="cpcb_aqi", label="Air quality (CPCB)", section="hazards",
            homepage="https://data.gov.in/resource/real-time-air-quality-index-various-locations",
            terms="Government Open Data License - India (GODL); source CPCB", every=3600, fetch=fetch,
            key="DATA_GOV_IN_KEY")
