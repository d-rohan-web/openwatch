from pathlib import Path

from apps.collector.feeds.airport_infra import parse

FIX = Path(__file__).parent.parent / "fixtures"


def test_parse():
    rs = {r["id"]: r for r in parse(*[(FIX / f"airport_infra_{f}.csv").read_bytes()
                                      for f in ("airports", "runways", "navaids")])}
    assert "rwy-244968" not in rs and "nav-85050" not in rs  # JFK runway, Canadian NDB
    r = rs["rwy-236778"]
    assert r["kind"] == "runway" and r["geometry"]["type"] == "LineString" and r["attrs"]["airport_ident"] == "VIDP"
    assert r["attrs"]["length_ft"] == 9239 and r["attrs"]["lighted"] and r["attrs"]["he_ident"] == "27"
    assert rs["rwy-320229"]["geometry"] is None and rs["rwy-320229"]["lat"] is not None  # no ends: airport point
    v = rs["nav-85181"]
    assert v["kind"] == "vor-dme" and v["attrs"]["frequency_khz"] == 113100
    assert v["attrs"]["associated_airport"] == "VAAH"
    assert rs["nav-85296"]["kind"] == "ndb" and "elevation_ft" not in rs["nav-85296"]["attrs"]
