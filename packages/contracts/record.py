"""The one flat record shape every feed emits, stored, streamed and exported (docs/architecture.md §2).

No ontology: a record is what one source said about one thing at one time. `attrs` keeps the source's own fields.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SEVERITIES = ("info", "advisory", "warning", "critical")

# Archive column order. geometry/attrs are JSON text so the Parquet schema never changes when a source does.
COLUMNS = ("feed", "id", "observed_at", "fetched_at", "lon", "lat", "geometry", "kind", "severity", "title",
           "attrs", "raw_sha256")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def iso(t: datetime | str | int | float | None) -> str | None:
    """Datetime / ISO string / unix seconds → UTC ISO string (naive datetimes are taken as UTC)."""
    if t is None or t == "":
        return None
    if isinstance(t, (int, float)):
        t = datetime.fromtimestamp(t, timezone.utc)
    elif isinstance(t, str):
        t = datetime.fromisoformat(t.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc).isoformat(timespec="seconds")


def record(id: Any, *, title: str, kind: str, lon: float | None = None, lat: float | None = None,
           geometry: dict | None = None, observed_at: Any = None, severity: str | None = None,
           **attrs: Any) -> dict:
    """What a feed returns. The runner adds feed, fetched_at and raw_sha256."""
    if severity is not None and severity not in SEVERITIES:
        raise ValueError(f"severity {severity!r} not in {SEVERITIES}")
    if (lon is None) != (lat is None):
        raise ValueError("lon and lat go together")
    return {"id": str(id), "title": title, "kind": kind,
            "lon": None if lon is None else round(float(lon), 6), "lat": None if lat is None else round(float(lat), 6),
            "geometry": geometry, "observed_at": iso(observed_at), "severity": severity,
            "attrs": {k: v for k, v in attrs.items() if v is not None}}
