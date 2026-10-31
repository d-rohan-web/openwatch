import json
from datetime import date
from pathlib import Path

from apps.collector.feeds.imd_warnings import parse

FIX = json.loads((Path(__file__).parent.parent / "fixtures" / "imd_warnings.json").read_text())


def test_parse():
    recs = {r["id"]: r for r in parse(FIX, date(2026, 10, 30))}
    assert set(recs) == {"bijapur", "hyderabad", "thoubal"}       # yellow+ only; green and blank rows dropped
    h = recs["hyderabad"]
    assert h["severity"] == "advisory" and h["lon"] is not None
    assert h["attrs"]["warnings"] == ["Thunderstorm & Lightning", "Strong Surface Winds"]
    assert len(h["attrs"]["days"]) == 5
    # next day: Day_2 becomes today; Thoubal is green on day 2
    assert {r["id"] for r in parse(FIX, date(2026, 10, 31))} == {"bijapur", "hyderabad"}
