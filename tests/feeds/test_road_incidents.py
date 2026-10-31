import json
from pathlib import Path

from apps.collector.feeds.road_incidents import parse


def test_parse():  # fixture follows the documented v5 response shape (no key to fetch a live sample)
    jam, closed = parse(json.loads(Path("tests/fixtures/road_incidents.json").read_text()), "Delhi NCR")
    assert jam["kind"] == "jam" and jam["severity"] == "warning" and jam["geometry"]["type"] == "LineString"
    assert (jam["lon"], jam["lat"]) == (77.145, 28.565) and jam["attrs"]["delay_s"] == 933
    assert jam["title"] == "Stationary traffic: Dhaula Kuan → Rajokri Flyover" and jam["attrs"]["from"] == "Dhaula Kuan"
    assert closed["kind"] == "closure" and closed["geometry"] is None and closed["severity"] == "advisory"
    assert "roads" not in closed["attrs"]
