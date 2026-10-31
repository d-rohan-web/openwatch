import json
from datetime import datetime, timezone
from pathlib import Path

from apps.collector.feeds.launches import parse

FX = json.loads((Path(__file__).parent.parent / "fixtures" / "launches.json").read_text())


def test_launches():
    recs = {r["title"]: r for r in parse(FX["results"], datetime(2026, 10, 30, 12, tzinfo=timezone.utc))}
    assert "Falcon 9 Block 5 | Starlink Group 15-18" not in recs  # US pad, not Indian
    nvs = recs["GSLV Mk II | IRNSS-1L (NVS-03)"]
    assert nvs["kind"] == "launch" and nvs["severity"] == "advisory" and nvs["attrs"]["indian"]
    assert (nvs["lon"], nvs["lat"]) == (80.2304, 13.7199) and nvs["attrs"]["provider"].startswith("Indian Space")
    assert recs["GSLV Mk II | GISAT-1A (EOS-05)"]["severity"] == "info"
    china = recs["Kinetica 2 | SpaceSail Polar Group TBD?"]  # Jiuquan is inside the region box
    assert not china["attrs"]["indian"] and china["severity"] == "info"
