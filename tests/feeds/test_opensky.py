import json
from pathlib import Path

from apps.collector.feeds.opensky import parse


def test_parse():
    recs = parse(json.loads((Path(__file__).parents[1] / "fixtures" / "opensky.json").read_text()))
    assert [r["id"] for r in recs] == ["80162d", "800def"]  # no position → skipped
    a, g = recs
    assert a["title"] == "AXB4HV" and a["attrs"]["alt_ft"] == 30550 and a["attrs"]["gs_kt"] == 431.5
    assert g["attrs"]["on_ground"] is True and g["attrs"]["emergency"] == "7700"
