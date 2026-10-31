from pathlib import Path

from apps.collector.feeds.restricted_areas import parse

FIX = Path(__file__).parent.parent / "fixtures" / "restricted_areas.html"


def test_parse():
    rs = {r["id"]: r for r in parse(FIX.read_bytes())}
    assert "VOD198" not in rs  # intentionally left blank
    a = rs["VOD188"]  # lat/lon box
    assert a["attrs"]["type"] == "danger" and a["attrs"]["region"] == "Chennai"
    assert a["geometry"]["type"] == "Polygon" and len(a["geometry"]["coordinates"][0]) == 5
    assert a["attrs"]["upper_ft"] == 19000 and a["attrs"]["lower_ft"] == 0
    assert rs["VOD177"]["geometry"]["type"] == "Polygon" and abs(rs["VOD177"]["lat"] - 12.5775) < 0.01  # circle
    assert len(rs["VOP190"]["geometry"]["coordinates"]) == 2  # two sectors
    assert rs["VER146A"]["attrs"]["upper_ft"] == 32500 and rs["VER146A"]["attrs"]["lower_ft"] == 5000
    arc = rs["VOD171"]["geometry"]["coordinates"][0]  # two points + 100 km clockwise arc
    assert len(arc) > 6 and arc[0] == arc[-1]
    assert rs["VED54"]["lon"] is not None  # "280 002N" split digits
