import json
from datetime import datetime, timezone
from pathlib import Path

from apps.collector.feeds.imd_nowcast import parse

FIX = json.loads((Path(__file__).parent.parent / "fixtures" / "imd_nowcast.json").read_text())


def test_parse():
    recs = {r["id"]: r for r in parse(FIX, datetime(2026, 10, 30, 21, 0, tzinfo=timezone.utc))}  # 02:30 IST
    assert set(recs) == {"kushinagar", "sangareddy", "bijapur"}  # Lawngtlai expired at 01:00 IST, Saitual green
    k = recs["kushinagar"]
    assert k["severity"] == "warning" and k["lat"] is not None
    assert k["attrs"]["warnings"] == ["Light thunderstorm", "Moderate lightning probability"]
    assert k["attrs"]["valid_until"] == "2026-10-31T03:00:00+05:30"
