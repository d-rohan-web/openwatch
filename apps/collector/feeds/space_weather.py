"""NOAA SWPC space weather: planetary Kp, latest X-ray flare, and active alerts/warnings/watches. No location."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, UTC

from apps.collector.feed import Feed
from packages.contracts.record import record

SWPC = "https://services.swpc.noaa.gov/"
KP, FLARE, ALERTS = "products/noaa-planetary-k-index.json", "json/goes/primary/xray-flares-latest.json", "products/alerts.json"


def severity(level: int) -> str:
    """NOAA G/S/R scale level (0-5) → record severity."""
    return "critical" if level >= 4 else "warning" if level == 3 else "advisory" if level >= 1 else "info"


def g_scale(kp: float) -> int:
    # G1 = Kp 5- (4.67) … G4 = Kp 8- to 9-, G5 = Kp 9o
    return 5 if kp >= 9 else max(0, min(4, int(kp + 0.34) - 4))


def r_scale(flux: float) -> int:
    # 0.1-0.8 nm peak flux, W/m²: M1, M5, X1, X10, X20
    return sum(flux >= t for t in (1e-5, 5e-5, 1e-4, 1e-3, 2e-3))


def kp_record(rows: list[dict]) -> dict:
    last = rows[-1]
    kp = float(last["Kp"])
    g = g_scale(kp)
    return record("kp", title=f"Planetary Kp {kp:.2f}" + (f" (G{g})" if g else ""), kind="kp",
                  observed_at=last["time_tag"], severity=severity(g), kp=kp, g_scale=g,
                  a_running=last.get("a_running"), station_count=last.get("station_count"))


def _when(*vals) -> str | None:
    """First value that is a real timestamp: SWPC writes "Unk" for times it doesn't know yet (flare still rising)."""
    for v in vals:
        try:
            if v:
                datetime.fromisoformat(str(v).replace("Z", "+00:00"))
                return v
        except ValueError:
            continue
    return None


def flare_record(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    f = rows[-1]
    r = r_scale(f.get("max_xrlong") or 0)
    return record("flare", title=f"X-ray flare {f['max_class']}" + (f" (R{r})" if r else ""), kind="flare",
                  observed_at=_when(f.get("max_time"), f.get("begin_time"), f.get("time_tag")), severity=severity(r),
                  max_class=f["max_class"],
                  r_scale=r, begin_time=f.get("begin_time"), max_time=f.get("max_time"), end_time=f.get("end_time"),
                  current_class=f.get("current_class"), max_xrlong=f.get("max_xrlong"), satellite=f.get("satellite"))


def _t(s: str) -> datetime:
    return datetime.strptime(s.strip(), "%Y %b %d %H%M UTC").replace(tzinfo=UTC)


def alert_records(msgs: list[dict], now: datetime) -> list[dict]:
    """Messages still in force: until 'Valid To'/'Now Valid Until' if given, else 3 days for watches, 1 for the rest."""
    out = []
    for m in msgs:
        text = m["message"].replace("\r", "")
        if not _when(m.get("issue_datetime")):
            continue  # no usable issue time: can't tell if it's still in force
        issued = datetime.fromisoformat(m["issue_datetime"]).replace(tzinfo=UTC)
        until = re.search(r"^(?:Valid To|Now Valid Until): (.+)$", text, re.M)
        headline = next((ln.strip() for ln in text.split("\n\n", 1)[-1].split("\n") if ln.strip()), "")
        try:
            end = _t(until.group(1)) if until else issued + timedelta(days=3 if "WATCH" in headline else 1)
        except ValueError:  # "Valid To: Unk" and the like: fall back to the default lifetime
            end = issued + timedelta(days=3 if "WATCH" in headline else 1)
        if end < now:
            continue
        scale = re.search(r"NOAA Scale: ([GSR])(\d)", text, re.I)
        code = re.search(r"Message Code: (\w+)", text)
        serial = re.search(r"Serial Number: (\d+)", text)
        level = int(scale.group(2)) if scale else 0
        out.append(record(f"{m['product_id']}-{serial.group(1) if serial else m['issue_datetime']}", title=headline,
                          kind="alert", observed_at=issued, severity=severity(level),
                          code=code and code.group(1), scale=scale and scale.group(1).upper() + scale.group(2),
                          valid_until=end.isoformat(), message=text))
    return out


async def fetch(ctx) -> list[dict]:
    out = []
    for path, parse in ((KP, kp_record), (FLARE, flare_record)):
        r = parse((await ctx.get(SWPC + path)).json())
        if r:
            r["raw_sha256"] = ctx.raw_sha  # each from its own response
            out.append(r)
    return out + alert_records((await ctx.get(SWPC + ALERTS)).json(), datetime.now(UTC))


FEED = Feed(id="space_weather", label="Space weather (NOAA SWPC)", section="space",
            homepage="https://www.swpc.noaa.gov/", terms="Public domain (NOAA / US Government work)",
            every=900, fetch=fetch)
