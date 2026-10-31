from pathlib import Path

from apps.collector.feeds.airports import parse

FIX = Path(__file__).parent.parent / "fixtures" / "airports.csv"


def test_parse():
    rs = {r["id"]: r for r in parse(FIX.read_bytes())}
    assert "KJFK" not in rs and not any(r["kind"] == "closed" for r in rs.values())
    d = rs["VIDP"]
    assert d["kind"] == "large_airport" and d["attrs"]["iata"] == "DEL" and d["attrs"]["scheduled"]
    assert 28 < d["lat"] < 29 and 76 < d["lon"] < 78
    assert rs["IN-0002"]["kind"] == "heliport"
