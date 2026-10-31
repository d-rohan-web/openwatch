import json
from pathlib import Path

from apps.collector.feeds.faa_notam import parse

# Shape from the FAA NOTAM API v1 docs (geoJson response); no key available to capture a live sample.
FIX = Path(__file__).parent.parent / "fixtures" / "faa_notam.json"


def test_parse():
    rs = {r["id"]: r for r in parse(json.loads(FIX.read_text()))}
    m = rs["NOTAM_1_00000001"]
    assert m["kind"] == "notam" and m["severity"] == "advisory" and m["attrs"]["military"]
    assert abs(m["lat"] - 19.0833) < 0.001 and abs(m["lon"] - 72.1667) < 0.001
    assert m["geometry"]["type"] == "Polygon" and m["attrs"]["radius_nm"] == 15
    assert m["attrs"]["valid_from"].startswith("2026-11-02T03:30") and m["attrs"]["valid_to"].startswith("2026-11-02T10:30")
    assert m["attrs"]["text"].startswith("MISSILE") and m["attrs"]["schedule"] == "0330-1030" and m["attrs"]["upper"] == "UNL"
    r = rs["NOTAM_1_00000002"]
    assert r["severity"] is None and "military" not in r["attrs"]
    assert r["attrs"]["perm"] and "valid_to" not in r["attrs"] and r["attrs"]["location"] == "VIDP"
    assert r["attrs"]["text"] == "RWY 10/28 CLSD"
