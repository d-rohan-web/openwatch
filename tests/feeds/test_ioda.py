import json
from pathlib import Path

from apps.collector.feeds.ioda import centroids, parse


def test_parse():
    recs = parse(json.loads(Path("tests/fixtures/ioda.json").read_text()))
    assert len(recs) == 5
    wb = recs[0]
    assert wb["title"] == "Internet outage: West Bengal" and wb["attrs"]["datasource"] == "bgp"
    assert 86 < wb["lon"] < 89 and 21 < wb["lat"] < 27
    india = recs[-1]
    assert india["lon"] is None and india["severity"] == "warning"
    assert {"Telangana", "Ladakh", "NCT of Delhi"} <= centroids().keys()
