from pathlib import Path

from apps.collector.feeds.ncs_quakes import parse

HTML = (Path(__file__).parent.parent / "fixtures" / "ncs_quakes.html").read_text()


def test_parse():
    recs = parse(HTML)
    assert len(recs) == 4
    r = recs[0]
    assert r["id"] == "GIS_52458" and r["title"] == "M 3.2 - Palghar, Maharashtra"
    assert (r["lon"], r["lat"]) == (72.918, 20.013) and r["attrs"]["depth_km"] == 7
    assert r["observed_at"] == "2026-10-30T19:24:45+00:00" and r["severity"] == "info"
    assert recs[2]["severity"] == "advisory"   # M4.0
