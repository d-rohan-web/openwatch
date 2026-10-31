from pathlib import Path

from apps.collector.feeds.nuclear import parse

FIX = Path(__file__).parent.parent / "fixtures" / "nuclear.json"


def test_parse():
    rs = {r["id"]: r for r in parse(FIX.read_bytes())}
    k = rs["Q1739415"]
    assert k["kind"] == "power_plant" and k["title"] == "Kakrapar Atomic Power Station"
    assert k["attrs"]["capacity_mw"] == 1140 and k["attrs"]["status"] == "in use"
    assert k["attrs"]["link"] == "https://www.wikidata.org/wiki/Q1739415" and 21 < k["lat"] < 22 and 73 < k["lon"] < 74
    assert "Bhavini" in rs["Q972715"]["attrs"]["operator"]  # two operators, one record
    assert rs["Q854682"]["kind"] == "research" and rs["Q854682"]["attrs"]["inception"] == "1954-01-01"
    assert rs["Q15229130"]["kind"] == "mine" and rs["Q3085713"]["kind"] == "reactor"
    assert rs["Q3664611"]["title"] == "Q3664611" and "label" not in rs["Q3664611"]["attrs"]  # no label anywhere
