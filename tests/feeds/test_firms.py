from pathlib import Path

from apps.collector.feeds.firms import parse


def test_parse():
    rs = parse((Path(__file__).parents[1] / "fixtures/firms.csv").read_text(), "N20")
    assert len(rs) == 4
    r = rs[0]
    assert r["id"] == "N20_29.27838_74.33997_2026-10-29_0828" and r["kind"] == "fire"
    assert r["observed_at"] == "2026-10-29T08:28:00+00:00"
    assert r["attrs"] == {"frp": 8.06, "confidence": "nominal", "brightness": 353.36, "daynight": "D", "satellite": "N20"}
    assert rs[2]["attrs"]["confidence"] == "low"
