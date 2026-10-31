import json
from pathlib import Path

from apps.collector.feeds.city_weather import parse, severity


def test_parse():
    delhi, mumbai, kolkata = parse(json.loads(Path("tests/fixtures/city_weather.json").read_text()))
    assert delhi["id"] == "delhi" and delhi["lon"] == 77.21 and delhi["kind"] == "weather"
    a = mumbai["attrs"]
    assert a["temp_c"] == 30.7 and a["apparent_c"] == 36.2 and a["weather"] == "Mainly clear" and a["precip_mm_h"] == 0
    assert [severity(46, 35, 0), severity(41, 33, 0), severity(5, 1.5, 0), severity(30, 25, 25), severity(30, 25, 2)] == \
        ["warning", "advisory", "advisory", "warning", "info"]
