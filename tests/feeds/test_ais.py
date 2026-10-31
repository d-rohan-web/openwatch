import json
from pathlib import Path

from apps.collector.feeds.ais import handle

# Messages in aisstream.io's documented format (https://aisstream.io/documentation); no key to record a live sample.
MSGS = json.loads((Path(__file__).parent.parent / "fixtures" / "ais.json").read_text())


def test_merge_static_and_position():
    out = [handle(m) for m in MSGS]
    assert out[0] is None and out[2] is None  # static data alone; position "not available" (91/181)
    r = out[1]
    assert r["id"] == "419001234" and r["kind"] == "ship" and (r["lat"], r["lon"]) == (18.91, 72.81)
    assert r["title"] == "INS EXAMPLE" and r["observed_at"] == "2026-10-30T06:12:32+00:00"
    a = r["attrs"]
    assert a["military"] is True and a["ship_type"] == "military" and a["destination"] == "MUMBAI"
    assert a["sog_kt"] == 12.4 and "heading" not in a and a["length_m"] == 163 and a["callsign"] == "AVXX"
