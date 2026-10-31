from datetime import datetime, timezone
from pathlib import Path

from apps.collector.feeds.imd_cyclone import parse

TEXT = (Path(__file__).parent.parent / "fixtures" / "imd_cyclone.txt").read_text()


def test_parse():
    [r] = parse(TEXT, "u", datetime(2026, 10, 28, 3, 0, tzinfo=timezone.utc))
    assert r["id"] == "BOB/08/2026" and r["severity"] == "critical"
    assert (r["lon"], r["lat"]) == (82.0, 16.4) and r["observed_at"] == "2026-10-28T00:00:00+00:00"
    assert r["title"] == "Very Severe Cyclonic Storm “Arnab”"
    assert len(r["geometry"]["coordinates"]) == 6 and r["attrs"]["track"][-1]["category"] == "Well Marked Low Pressure Area"
    assert parse(TEXT, "u", datetime(2026, 10, 30, tzinfo=timezone.utc)) == []       # stale bulletin
    assert parse("SPECIAL MESSAGE NO. 1 Low Pressure Area", "u", datetime.now(timezone.utc)) == []
