"""Ships around India from aisstream.io (terrestrial AIS, websocket). Positions merged with static data by MMSI."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone

import websockets

from apps.collector.feed import Feed
from packages.common import config
from packages.common.geo import GLOBAL
from packages.contracts.record import record

URL = "wss://stream.aisstream.io/v0/stream"
BOX = [[-90, -180], [90, 180]] if GLOBAL else [[-5, 55], [25, 100]]  # [lat, lon] corners: Arabian Sea, Indian EEZ, Bay of Bengal, Andaman Sea
POSITIONS = ("PositionReport", "StandardClassBPositionReport", "ExtendedClassBPositionReport")
EMIT_EVERY = 5  # seconds: batch emits, the stream is many messages a second
MILITARY, LAW = 35, 55
TYPES = {30: "fishing", 31: "towing", 32: "towing", 33: "dredging", 34: "diving", 35: "military", 36: "sailing",
         37: "pleasure", 50: "pilot", 51: "search and rescue", 52: "tug", 53: "port tender", 54: "anti-pollution",
         55: "law enforcement", 58: "medical"}
BANDS = {4: "high speed craft", 6: "passenger", 7: "cargo", 8: "tanker"}

_static: dict[int, dict] = {}  # MMSI -> latest ShipStaticData fields, kept across reconnects


def ship_type(code: int | None) -> str | None:
    return TYPES.get(code) or BANDS.get((code or 0) // 10) or ("other" if code else None)


def _txt(s: str | None) -> str | None:
    return (s or "").strip(" @") or None  # AIS pads text with '@'


def _time(meta: dict) -> datetime | None:
    # "2022-12-29 18:22:32.318353 +0000 UTC"
    m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", meta.get("time_utc") or "")
    return datetime.fromisoformat(m[1]).replace(tzinfo=timezone.utc) if m else None


def handle(msg: dict) -> dict | None:
    """Fold one aisstream message into module memory; return a ship record for position messages."""
    kind, meta = msg.get("MessageType"), msg.get("MetaData") or {}
    body = (msg.get("Message") or {}).get(kind) or {}
    mmsi = meta.get("MMSI") or body.get("UserID")
    if not mmsi:
        return None
    if kind == "ShipStaticData":
        dim = body.get("Dimension") or {}
        _static[mmsi] = {"name": _txt(body.get("Name")), "callsign": _txt(body.get("CallSign")),
                         "imo": body.get("ImoNumber") or None, "type_code": body.get("Type"),
                         "destination": _txt(body.get("Destination")),
                         "draught_m": body.get("MaximumStaticDraught") or None,
                         "length_m": (dim.get("A") or 0) + (dim.get("B") or 0) or None}
        return None
    if kind not in POSITIONS or not body.get("Valid", True):
        return None
    lat, lon = body.get("Latitude"), body.get("Longitude")
    if lat is None or lon is None or abs(lat) > 90 or abs(lon) > 180:  # 91/181 = "not available"
        return None
    s = _static.get(mmsi, {})
    name = s.get("name") or _txt(meta.get("ShipName"))
    code = s.get("type_code")
    sog, hdg = body.get("Sog"), body.get("TrueHeading")
    return record(mmsi, title=name or str(mmsi), kind="ship", lon=lon, lat=lat, observed_at=_time(meta) or time.time(),
                  mmsi=mmsi, name=name, ship_type=ship_type(code), military=code == MILITARY or None,
                  law_enforcement=code == LAW or None, sog_kt=None if sog is None or sog >= 102.3 else sog,
                  cog=None if (body.get("Cog") or 0) >= 360 else body.get("Cog"), heading=None if hdg == 511 else hdg, nav_status=body.get("NavigationalStatus"),
                  ais_class="B" if "ClassB" in kind else "A", **{k: v for k, v in s.items() if k != "name"})


async def stream(ctx, emit) -> None:
    if "stream.aisstream.io" not in ctx.feed.hosts:
        ctx.feed.hosts.append("stream.aisstream.io")
    async with websockets.connect(URL, user_agent_header=config.USER_AGENT, open_timeout=15) as ws:
        await ws.send(json.dumps({"APIKey": ctx.key, "BoundingBoxes": [BOX],
                                  "FilterMessageTypes": [*POSITIONS, "ShipStaticData"]}))
        batch: dict[str, dict] = {}
        last = time.monotonic()
        async for raw in ws:
            msg = json.loads(raw)
            if "error" in msg:  # bad key / bad subscription: aisstream sends {"error": ...} and closes
                raise RuntimeError(f"aisstream: {msg['error']}")
            r = handle(msg)
            if r:
                batch[r["id"]] = r
            if batch and time.monotonic() - last >= EMIT_EVERY:
                emit(list(batch.values()))
                batch, last = {}, time.monotonic()


FEED = Feed(id="ais", label="Ships (AIS, aisstream.io)", section="sea", homepage="https://aisstream.io/",
            terms="aisstream.io free API; data use under aisstream.io terms of service (attribution: aisstream.io)",
            stream=stream, key="AISSTREAM_KEY", snapshot=False, ttl=1800, store_all=True, keep_raw=False)
