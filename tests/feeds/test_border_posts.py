from pathlib import Path

from apps.collector.feeds.border_posts import parse

FIX = Path(__file__).parent.parent / "fixtures" / "border_posts.json"


def test_parse():
    rs = {r["id"]: r for r in parse(FIX.read_bytes())}
    assert {r["kind"] for r in rs.values()} == {"crossing"}
    s = rs["Q547332"]
    assert s["title"] == "Shipki La" and s["attrs"]["neighbour"] == "People's Republic of China" and 31 < s["lat"] < 32
    assert rs["Q68035790"]["attrs"]["neighbour"] == "Nepal"
    assert rs["Q109927988"]["attrs"]["classes"] == ["border train station"]
