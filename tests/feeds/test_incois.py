import json
from pathlib import Path

from apps.collector.feeds.incois import alert_rows, centres, parse_alerts, parse_tsunami

FIX = json.loads((Path(__file__).parent.parent / "fixtures" / "incois.json").read_text())


def test_parse():
    assert parse_tsunami(FIX["tsunami"].encode()) == []        # no active tsunami event
    recs = {r["id"]: r for r in parse_alerts(alert_rows(FIX["hwassa"], FIX["currents"]), centres(FIX["polygons"]))}
    assert set(recs) == {"swell_surge_watch:242", "ocean_current_watch:284", "ocean_current_alert:294"}
    m = recs["swell_surge_watch:242"]
    assert m["severity"] == "advisory" and 72 < m["lon"] < 74 and 8 < m["lat"] < 9   # Minicoy
    assert recs["ocean_current_alert:294"]["severity"] == "warning"
    assert recs["ocean_current_watch:284"]["attrs"]["state"] == "ANDHRA PRADESH" and recs["ocean_current_watch:284"]["lon"] is not None  # no polygon in sample → alias to 2011 district
